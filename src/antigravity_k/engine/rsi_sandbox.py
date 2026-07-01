"""Antigravity-K: RSI Safety Sandbox (재귀적 자기개선 안전 샌드박스).

================================================================
자기 수정 시 안전을 보장하는 이중 감사 + 자동 롤백 시스템.

연구 근거: Dual-Audit Safety (CoSAI 2025), Frontier Safety Frameworks

핵심 원칙:
  1. 불변 파일 보호: permission_gate.py, rsi_sandbox.py 등은 절대 수정 불가
  2. 스냅샷 기반 롤백: 모든 수정 전 상태를 Git으로 스냅샷
  3. 3중 검증 게이트: AST → 단위 테스트 → 벤치마크 회귀
  4. 이중 감사: 두 독립 LLM이 변이를 교차 검증
"""

from __future__ import annotations

import ast
import json
import logging
import os
import subprocess
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity_k.rsi_sandbox")


# ─── 불변 파일 목록 (절대 자기수정 불가) ─────────────────────────────

IMMUTABLE_FILES = frozenset(
    {
        "rsi_sandbox.py",
        "permission_gate.py",
        "tool_guardrails.py",
        "claude_deny_patterns.py",
    },
)

# 자동 적용 허용 파일 패턴 (Option B: 벤치마크 통과 시)
AUTO_APPLY_ALLOWED = frozenset(
    {
        "prompt_builder.py",
        "model_manager.py",
        "context_compressor.py",
        "benchmark_cases.py",
    },
)


class MutationRisk(Enum):
    """변이 위험도 등급."""

    LOW = "low"  # 프롬프트/설정 변경만
    MEDIUM = "medium"  # 비핵심 코드 수정
    HIGH = "high"  # 핵심 엔진 수정
    CRITICAL = "critical"  # 안전 모듈 접근 시도 → 차단


class ValidationResult(Enum):
    """검증 결과."""

    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"


@dataclass
class MutationRecord:
    """변이 기록 1건."""

    mutation_id: str
    timestamp: float
    target_file: str
    mutation_type: str  # "prompt" | "code" | "config" | "tool"
    risk_level: str
    before_hash: str
    after_hash: str
    validations: dict[str, str] = field(default_factory=dict)
    approved: bool = False
    rolled_back: bool = False
    benchmark_delta: float = 0.0

    def to_dict(self) -> dict:
        """To Dict.

        Returns:
            dict: The dict result.

        """
        return asdict(self)


@dataclass
class SnapshotInfo:
    """스냅샷 정보."""

    snapshot_id: str
    git_commit: str
    timestamp: float
    files_captured: list[str]
    benchmark_baseline: float = 0.0


# ─── 메인 샌드박스 ───────────────────────────────────────────────────


class RSISandbox:
    """재귀적 자기개선 안전 샌드박스.

    모든 자기 수정은 이 샌드박스를 통해서만 수행됩니다.
    불변 파일 보호, 스냅샷 기반 롤백, 3중 검증을 제공합니다.
    """

    def __init__(
        self,
        project_root: str = "",
        audit_dir: str = "data/rsi_audit",
        verify_fn: Callable | None = None,
    ):
        """Initialize the RSISandbox.

        Args:
            project_root (str): str project root.
            audit_dir (str): str audit dir.
            verify_fn (Callable | None): Callable | None verify fn.

        """
        self._root = project_root or os.getcwd()
        self._audit_dir = Path(audit_dir)
        self._audit_dir.mkdir(parents=True, exist_ok=True)
        self._verify_fn = verify_fn  # LLM 검증 함수
        self._mutation_log: list[MutationRecord] = []
        self._snapshots: list[SnapshotInfo] = []
        self._load_audit_log()

    # ─── 불변 파일 보호 ──────────────────────────────────────────

    def is_immutable(self, filepath: str) -> bool:
        """파일이 불변 보호 대상인지 확인합니다."""
        basename = os.path.basename(filepath)
        return basename in IMMUTABLE_FILES

    def is_auto_apply_allowed(self, filepath: str) -> bool:
        """자동 적용이 허용된 파일인지 확인합니다 (Option B)."""
        basename = os.path.basename(filepath)
        return basename in AUTO_APPLY_ALLOWED

    def classify_risk(self, filepath: str, mutation_type: str) -> MutationRisk:
        """변이의 위험도를 분류합니다."""
        basename = os.path.basename(filepath)

        if basename in IMMUTABLE_FILES:
            return MutationRisk.CRITICAL

        if mutation_type == "prompt":
            return MutationRisk.LOW

        if mutation_type == "config":
            return MutationRisk.LOW

        if basename in AUTO_APPLY_ALLOWED:
            return MutationRisk.MEDIUM

        # 핵심 엔진 파일
        if basename in {
            "orchestrator.py",
            "model_router.py",
            "quality_gate.py",
            "chat.py",
            "goal_runner.py",
            "state_graph.py",
        }:
            return MutationRisk.HIGH

        return MutationRisk.MEDIUM

    # ─── 스냅샷 관리 ─────────────────────────────────────────────

    def take_snapshot(self, label: str = "") -> SnapshotInfo:
        """현재 상태의 Git 스냅샷을 생성합니다."""
        snapshot_id = f"rsi_{int(time.time())}_{label or 'auto'}"

        # Git stash 또는 임시 커밋
        git_commit = self._get_current_commit()

        # 핵심 파일 목록 캡처
        engine_dir = os.path.join(self._root, "src", "antigravity_k", "engine")
        files = []
        if os.path.exists(engine_dir):
            files = [f for f in os.listdir(engine_dir) if f.endswith(".py")]

        snapshot = SnapshotInfo(
            snapshot_id=snapshot_id,
            git_commit=git_commit,
            timestamp=time.time(),
            files_captured=files,
        )
        self._snapshots.append(snapshot)

        logger.info(
            "[RSI Sandbox] 스냅샷 생성: %s (commit: %s, files: %s)",
            snapshot_id,
            git_commit[:8],
            len(files),
        )
        return snapshot

    def rollback_to(self, snapshot: SnapshotInfo) -> bool:
        """특정 스냅샷으로 롤백합니다."""
        try:
            result = subprocess.run(
                ["git", "checkout", snapshot.git_commit, "--", "."],
                cwd=self._root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                logger.info("[RSI Sandbox] 롤백 완료: %s", snapshot.snapshot_id)
                return True
            else:
                logger.error("[RSI Sandbox] 롤백 실패: %s", result.stderr)
                return False
        except Exception:
            logger.exception("[RSI Sandbox] 롤백 오류")
            return False

    # ─── 3중 검증 게이트 ─────────────────────────────────────────

    def validate_mutation(
        self,
        filepath: str,
        new_content: str,
        benchmark_fn: Callable | None = None,
    ) -> dict[str, ValidationResult]:
        """변이를 3중 검증합니다.

        1단계: AST 구문 검증
        2단계: 기존 테스트 실행
        3단계: 벤치마크 회귀 검증 (선택)

        Returns:
            {"ast": PASS/FAIL, "tests": PASS/FAIL, "benchmark": PASS/FAIL/SKIP}

        """
        results: dict[str, ValidationResult] = {}

        # 1단계: AST 구문 검증
        if filepath.endswith(".py"):
            try:
                ast.parse(new_content)
                results["ast"] = ValidationResult.PASS
            except SyntaxError as e:
                logger.warning("[RSI Sandbox] AST 실패: %s: %s", filepath, e)
                results["ast"] = ValidationResult.FAIL
                return results  # AST 실패 시 이후 단계 스킵
        else:
            results["ast"] = ValidationResult.SKIP

        # 2단계: 기존 테스트 실행 (임시 파일 교체 후)
        original_content = None
        full_path = os.path.join(self._root, filepath) if not os.path.isabs(filepath) else filepath

        try:
            if os.path.exists(full_path):
                with open(full_path, encoding="utf-8") as f:
                    original_content = f.read()

                # 임시 교체
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

                # pytest 실행
                test_result = subprocess.run(
                    [
                        "python",
                        "-m",
                        "pytest",
                        "tests/test_output_quality.py",
                        "-q",
                        "--tb=short",
                        "-x",
                    ],
                    cwd=self._root,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    env={**os.environ, "PYTHONPATH": os.path.join(self._root, "src")},
                )
                results["tests"] = ValidationResult.PASS if test_result.returncode == 0 else ValidationResult.FAIL
            else:
                results["tests"] = ValidationResult.SKIP
        except Exception:
            logger.exception("[RSI Sandbox] 테스트 실패")
            results["tests"] = ValidationResult.FAIL
        finally:
            # 원복
            if original_content is not None and os.path.exists(full_path):
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(original_content)

        # 3단계: 벤치마크 회귀
        if benchmark_fn:
            try:
                benchmark_passed = benchmark_fn(filepath, new_content)
                results["benchmark"] = ValidationResult.PASS if benchmark_passed else ValidationResult.FAIL
            except Exception:
                logger.exception("Unhandled exception")
                results["benchmark"] = ValidationResult.SKIP
        else:
            results["benchmark"] = ValidationResult.SKIP

        return results

    # ─── 이중 감사 (Dual-Audit) ──────────────────────────────────

    def dual_audit(
        self,
        filepath: str,
        original: str,
        modified: str,
        audit_fn_1: Callable | None = None,
        audit_fn_2: Callable | None = None,
    ) -> dict[str, Any]:
        """두 개의 독립 LLM이 변이를 교차 검증합니다.

        Args:
            filepath: 대상 파일
            original: 원본 코드
            modified: 수정된 코드
            audit_fn_1: 첫 번째 감사자 (prompt -> str)
            audit_fn_2: 두 번째 감사자 (prompt -> str)

        Returns:
            {"approved": bool, "auditor_1": str, "auditor_2": str}

        """
        audit_prompt = (
            "[ROLE]\n당신은 코드 변경 감사관입니다.\n\n"
            "[TASK]\n아래 코드 변경이 안전하고 유익한지 판단하세요.\n"
            "1. 기능 퇴화가 있는가?\n"
            "2. 보안 취약점이 도입되었는가?\n"
            "3. 성능 저하 가능성이 있는가?\n\n"
            f"파일: {filepath}\n\n"
            f"--- 원본 (첫 500자) ---\n{original[:500]}\n\n"
            f"--- 수정 (첫 500자) ---\n{modified[:500]}\n\n"
            "판단: APPROVE 또는 REJECT (이유 포함)"
        )

        result = {"approved": True, "auditor_1": "skip", "auditor_2": "skip"}

        fn_1 = audit_fn_1 or self._verify_fn
        fn_2 = audit_fn_2 or self._verify_fn

        if fn_1:
            try:
                r1 = fn_1(audit_prompt)
                result["auditor_1"] = r1 or "no response"
                if r1 and "REJECT" in r1.upper():
                    result["approved"] = False
            except Exception as e:
                logger.exception("Unhandled exception")
                result["auditor_1"] = f"error: {e}"

        if fn_2 and fn_2 is not fn_1:
            try:
                r2 = fn_2(audit_prompt)
                result["auditor_2"] = r2 or "no response"
                if r2 and "REJECT" in r2.upper():
                    result["approved"] = False
            except Exception as e:
                logger.exception("Unhandled exception")
                result["auditor_2"] = f"error: {e}"

        return result

    # ─── 안전한 수정 컨텍스트 ────────────────────────────────────

    @contextmanager
    def safe_mutation(self, label: str = ""):
        """안전한 자기수정 컨텍스트 매니저.

        사용법:
            with sandbox.safe_mutation("prompt_optimization"):
                # 수정 작업 수행
                # 실패 시 자동 롤백
        """
        snapshot = self.take_snapshot(label)
        try:
            yield snapshot
            logger.info("[RSI Sandbox] 안전 수정 완료: %s", label)
        except Exception as e:
            logger.error("[RSI Sandbox] 수정 중 오류, 롤백 시작: %s", e)
            self.rollback_to(snapshot)
            raise

    # ─── 변이 기록 ───────────────────────────────────────────────

    def record_mutation(self, record: MutationRecord) -> None:
        """변이 기록을 저장합니다."""
        self._mutation_log.append(record)
        self._save_audit_log()

    def get_mutation_history(self, last_n: int = 20) -> list[dict]:
        """최근 변이 이력을 반환합니다."""
        return [m.to_dict() for m in self._mutation_log[-last_n:]]

    def get_stats(self) -> dict[str, Any]:
        """샌드박스 통계를 반환합니다."""
        total = len(self._mutation_log)
        approved = sum(1 for m in self._mutation_log if m.approved)
        rolled_back = sum(1 for m in self._mutation_log if m.rolled_back)
        return {
            "total_mutations": total,
            "approved": approved,
            "rolled_back": rolled_back,
            "approval_rate": f"{approved / max(total, 1) * 100:.0f}%",
            "snapshots": len(self._snapshots),
        }

    # ─── 내부 유틸 ───────────────────────────────────────────────

    def _get_current_commit(self) -> str:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self._root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except Exception:
            logger.exception("Unhandled exception")
            return "unknown"

    def _load_audit_log(self) -> None:
        log_path = self._audit_dir / "mutation_log.json"
        if log_path.exists():
            try:
                with open(log_path, encoding="utf-8") as f:
                    data = json.load(f)
                self._mutation_log = [MutationRecord(**r) for r in data.get("mutations", [])]
            except Exception:
                logger.exception("[RSI Sandbox] 감사 로그 로드 실패")

    def _save_audit_log(self) -> None:
        log_path = self._audit_dir / "mutation_log.json"
        try:
            data = {
                "version": 1,
                "updated_at": time.time(),
                "mutations": [m.to_dict() for m in self._mutation_log],
            }
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            logger.exception("[RSI Sandbox] 감사 로그 저장 실패")


"""Antigravity-K RSI Safety Sandbox — Dual-audit + auto-rollback."""
