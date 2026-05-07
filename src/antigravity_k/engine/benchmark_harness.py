"""
Antigravity-K: 벤치마크 하네스 (BenchmarkHarness)
===================================================
collective-council vs 단일 모델 품질/속도/토큰 효율 A/B 비교 엔진.

동일 코딩 과제를 복수 타겟(collective-council, 개별 모델)에 순차 투입하고
QualityGate 자동 채점 → JSON DB 누적 저장 → 마크다운 비교표 생성.

사용법:
    harness = BenchmarkHarness(model_manager)
    report = harness.run_suite("all", targets=["collective-council", "deepseek-r1:32b"])
    print(harness.comparison_table())
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from antigravity_k.engine.benchmark_cases import BenchmarkCase, get_suite
from antigravity_k.engine.quality_gate import QualityGate

logger = logging.getLogger("antigravity_k.benchmark_harness")


# ─── 데이터 클래스 ───────────────────────────────────────────────────


@dataclass
class BenchmarkResult:
    """벤치마크 과제 1건의 실행 결과."""

    case_id: str
    target: str  # "collective-council" or "deepseek-r1:32b" etc.
    quality_score: float  # 0.0 ~ 1.0
    quality_grade: str  # A / B / C / F
    latency_ms: float
    tokens_in: int
    tokens_out: int
    output_preview: str  # 첫 500자
    timestamp: float
    issues: list[str] = field(default_factory=list)
    benchmark_score: float = 0.0  # QualityGate + expected keyword coverage composite
    keyword_coverage: float = 0.0  # 0.0 ~ 1.0
    passed_keywords: list[str] = field(default_factory=list)
    missing_keywords: list[str] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BenchmarkReport:
    """스위트 실행 전체 리포트."""

    suite_name: str
    targets: list[str]
    results: list[BenchmarkResult] = field(default_factory=list)
    started_at: float = 0.0
    finished_at: float = 0.0

    @property
    def duration_s(self) -> float:
        return self.finished_at - self.started_at

    def to_dict(self) -> dict:
        return {
            "suite_name": self.suite_name,
            "targets": self.targets,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_s": round(self.duration_s, 1),
            "results": [r.to_dict() for r in self.results],
        }


# ─── 메인 하네스 ─────────────────────────────────────────────────────


class BenchmarkHarness:
    """Collective-council vs 단일 모델 벤치마크 실행기."""

    DEFAULT_DB_PATH = Path("data/benchmark_results.json")

    def __init__(
        self,
        model_manager,
        db_path: Optional[Path] = None,
        quality_gate: Optional[QualityGate] = None,
    ):
        self._manager = model_manager
        self._db_path = db_path or self.DEFAULT_DB_PATH
        self._quality_gate = quality_gate or QualityGate(max_retries=0)
        self._history: list[BenchmarkResult] = []
        self._load_history()

    # ─── 공개 API ────────────────────────────────────────────────────

    def run_case(
        self,
        case: BenchmarkCase,
        targets: list[str],
    ) -> list[BenchmarkResult]:
        """단일 과제를 복수 타겟에 순차 실행합니다."""
        results: list[BenchmarkResult] = []
        for target in targets:
            result = self._execute_single(case, target)
            results.append(result)
            self._history.append(result)
            logger.info(
                "[Benchmark] %s × %s → %s (%.0f%%, %.1fs)",
                case.id,
                target,
                result.quality_grade,
                result.quality_score * 100,
                result.latency_ms / 1000,
            )
        self._save_history()
        return results

    def run_suite(
        self,
        suite_name: str = "all",
        targets: Optional[list[str]] = None,
    ) -> BenchmarkReport:
        """과제 스위트를 실행합니다.

        Args:
            suite_name: "all", "simple", "algorithm", 또는 개별 ID
            targets: 비교 대상 목록. None이면 config에서 자동 결정.
        """
        if targets is None:
            targets = self._default_targets()

        cases = get_suite(suite_name)
        report = BenchmarkReport(
            suite_name=suite_name,
            targets=targets,
            started_at=time.time(),
        )

        total = len(cases) * len(targets)
        logger.info(
            "[Benchmark] 스위트 '%s' 시작: %d 과제 × %d 타겟 = %d 실행",
            suite_name,
            len(cases),
            len(targets),
            total,
        )

        for idx, case in enumerate(cases, start=1):
            logger.info(
                "[Benchmark] [%d/%d] %s (%s, 난이도 %d)",
                idx,
                len(cases),
                case.id,
                case.description,
                case.difficulty,
            )
            case_results = self.run_case(case, targets)
            report.results.extend(case_results)

        report.finished_at = time.time()
        logger.info(
            "[Benchmark] 스위트 '%s' 완료: %.1fs, %d 결과",
            suite_name,
            report.duration_s,
            len(report.results),
        )
        return report

    def comparison_table(self, suite_name: str = "all") -> str:
        """누적 결과를 기반으로 마크다운 비교표를 생성합니다."""
        cases = get_suite(suite_name)
        case_ids = {c.id for c in cases}

        # 해당 스위트의 결과만 필터
        relevant = [r for r in self._history if r.case_id in case_ids]
        if not relevant:
            return "벤치마크 결과가 없습니다. `/benchmark run`으로 실행하세요."

        # 타겟별 집계
        targets: dict[str, list[BenchmarkResult]] = {}
        for r in relevant:
            targets.setdefault(r.target, []).append(r)

        # ── 요약 테이블 ──
        lines = [
            "## 📊 Benchmark 비교표\n",
            "| 타겟 | 실행 수 | 평균 종합점수 | 평균 품질 | 키워드 커버리지 | A/B 비율 | 평균 레이턴시 | 평균 토큰(out) |",
            "|------|---------|---------------|----------|----------------|---------|-------------|---------------|",
        ]

        target_summaries = []
        for target, results in sorted(targets.items()):
            n = len(results)
            avg_b = sum(r.benchmark_score for r in results) / n
            avg_q = sum(r.quality_score for r in results) / n
            avg_k = sum(r.keyword_coverage for r in results) / n
            ab_count = sum(
                1 for r in results if r.quality_grade in ("excellent", "good")
            )
            ab_ratio = ab_count / n * 100
            avg_lat = sum(r.latency_ms for r in results) / n / 1000
            avg_tok = sum(r.tokens_out for r in results) / n
            target_summaries.append((target, avg_b, avg_q, avg_k, avg_lat))
            lines.append(
                f"| `{target}` | {n} | {avg_b:.0%} | {avg_q:.0%} | {avg_k:.0%} | {ab_ratio:.0f}% | {avg_lat:.1f}s | {avg_tok:.0f} |"
            )

        if target_summaries:
            leader = max(target_summaries, key=lambda item: item[1])
            lines.insert(
                1,
                f"> 현재 우세 타겟: `{leader[0]}` "
                f"(종합 {leader[1]:.0%}, 품질 {leader[2]:.0%}, 키워드 {leader[3]:.0%}, 평균 {leader[4]:.1f}s)\n",
            )

        # ── 과제별 상세 ──
        lines.append("\n### 과제별 상세\n")
        target_names = sorted(targets.keys())
        header = (
            "| 과제 | 난이도 | " + " | ".join(f"`{t}`" for t in target_names) + " |"
        )
        sep = "|------|--------|" + "|".join("--------" for _ in target_names) + "|"
        lines.append(header)
        lines.append(sep)

        for case in cases:
            row = f"| {case.id} | {'⭐' * case.difficulty} |"
            for target in target_names:
                # 가장 최근 결과 사용
                matching = [
                    r for r in relevant if r.case_id == case.id and r.target == target
                ]
                if matching:
                    latest = max(matching, key=lambda r: r.timestamp)
                    grade_emoji = {
                        "excellent": "🟢A",
                        "good": "🔵B",
                        "retry": "🟡C",
                        "fail": "🔴F",
                    }.get(latest.quality_grade, latest.quality_grade)
                    row += f" {grade_emoji} (종합 {latest.benchmark_score:.0%}, {latest.latency_ms / 1000:.1f}s) |"
                else:
                    row += " — |"
            lines.append(row)

        return "\n".join(lines)

    # ─── 내부 실행 ───────────────────────────────────────────────────

    def _execute_single(
        self,
        case: BenchmarkCase,
        target: str,
    ) -> BenchmarkResult:
        """단일 과제 × 단일 타겟 실행."""
        start = time.time()
        output = ""
        error = ""

        try:
            output = self._manager.generate(
                prompt=case.prompt,
                target=target,
                max_tokens=4096,
                temperature=0.4,
            )
        except Exception as exc:
            error = str(exc)
            logger.error("[Benchmark] %s × %s 실행 실패: %s", case.id, target, exc)

        elapsed_ms = (time.time() - start) * 1000

        # QualityGate 평가
        if output and not error:
            qscore = self._quality_gate.evaluate("coding", case.prompt, output)
            quality_score = qscore.score
            quality_grade = qscore.grade.value
            issues = qscore.issues
        else:
            quality_score = 0.0
            quality_grade = "fail"
            issues = [error] if error else ["empty_output"]

        # 토큰 추정
        tokens_in = len(case.prompt) // 4
        tokens_out = len(output) // 4
        keyword_coverage, passed_keywords, missing_keywords = self._score_keywords(
            case, output
        )
        benchmark_score = self._compose_benchmark_score(
            quality_score=quality_score,
            keyword_coverage=keyword_coverage,
            error=error,
        )
        if missing_keywords:
            issues = list(issues)
            issues.append("missing_keywords:" + ",".join(missing_keywords))

        return BenchmarkResult(
            case_id=case.id,
            target=target,
            benchmark_score=benchmark_score,
            quality_score=round(quality_score, 3),
            quality_grade=quality_grade,
            keyword_coverage=keyword_coverage,
            latency_ms=round(elapsed_ms, 1),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            output_preview=output[:500] if output else "",
            timestamp=time.time(),
            issues=issues,
            passed_keywords=passed_keywords,
            missing_keywords=missing_keywords,
            error=error,
        )

    @staticmethod
    def _score_keywords(
        case: BenchmarkCase,
        output: str,
    ) -> tuple[float, list[str], list[str]]:
        """과제별 기대 키워드 충족률을 계산합니다."""
        expected = list(case.expected_keywords or ())
        if not expected:
            return 1.0, [], []

        output_lower = (output or "").lower()
        passed = [kw for kw in expected if kw.lower() in output_lower]
        missing = [kw for kw in expected if kw.lower() not in output_lower]
        coverage = len(passed) / len(expected)
        return round(coverage, 3), passed, missing

    @staticmethod
    def _compose_benchmark_score(
        *,
        quality_score: float,
        keyword_coverage: float,
        error: str,
    ) -> float:
        """품질 점수와 과제 충족률을 결합한 종합 점수."""
        if error:
            return 0.0
        return round((quality_score * 0.7) + (keyword_coverage * 0.3), 3)

    def _default_targets(self) -> list[str]:
        """config.yaml에서 벤치마크 비교 대상을 결정합니다."""
        # collective-council + 개별 모델 중 가용한 것
        targets = ["collective-council"]
        raw = getattr(self._manager._registry, "_raw", {})
        combo = raw.get("combos", {}).get("collective-council", {})
        models = combo.get("models", [])
        targets.extend(models[:3])  # 최대 3개 개별 모델
        return targets

    # ─── 영속화 ──────────────────────────────────────────────────────

    def _load_history(self) -> None:
        """기존 결과를 JSON에서 로드합니다."""
        if not self._db_path.exists():
            return
        try:
            with open(self._db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._history = []
            for raw_result in data.get("results", []):
                result = BenchmarkResult(**raw_result)
                if "benchmark_score" not in raw_result:
                    result.benchmark_score = result.quality_score
                if "keyword_coverage" not in raw_result:
                    result.keyword_coverage = (
                        1.0 if result.output_preview and not result.error else 0.0
                    )
                self._history.append(result)
            logger.info("[Benchmark] %d개 기존 결과 로드", len(self._history))
        except Exception as exc:
            logger.warning("[Benchmark] 기존 결과 로드 실패: %s", exc)
            self._history = []

    def _save_history(self) -> None:
        """누적 결과를 JSON에 저장합니다."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "updated_at": datetime.now().isoformat(),
            "total_results": len(self._history),
            "results": [r.to_dict() for r in self._history],
        }
        try:
            with open(self._db_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug("[Benchmark] 결과 저장: %s", self._db_path)
        except Exception as exc:
            logger.error("[Benchmark] 결과 저장 실패: %s", exc)

    def clear_history(self) -> None:
        """누적 결과를 초기화합니다."""
        self._history.clear()
        self._save_history()
        logger.info("[Benchmark] 누적 결과 초기화")
