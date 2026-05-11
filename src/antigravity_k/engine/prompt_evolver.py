"""
Antigravity-K: Prompt Evolver (OPRO 기반 프롬프트 자동 최적화)
=============================================================
LLM이 자기 시스템 프롬프트를 분석하고 최적화하는 자동 진화 엔진.

연구 근거: OPRO (Google DeepMind), MetaSPO (Bilevel Optimization),
          Grammar-Guided Genetic Programming (G3P)

핵심 개념:
  OPRO 루프:
    1. 현재 프롬프트 + 최근 성능 데이터를 Optimizer LLM에 전달
    2. Optimizer가 새 프롬프트 후보 N개 생성
    3. 각 후보를 동일 테스트 세트에서 실행
    4. 최고 성능 프롬프트를 선택하여 교체

  "내가 하는 것과 같은 행위":
    - 나(Antigravity)가 프롬프트를 수정하는 것과 정확히 같은 방식으로
    - Antigravity-K의 LLM이 자기 프롬프트를 수정합니다.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import urllib.request
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("antigravity_k.prompt_evolver")


@dataclass
class PromptCandidate:
    """프롬프트 후보 1건."""
    candidate_id: str
    content: str
    generation: int
    parent_id: str = ""
    score: float = 0.0
    keyword_coverage: float = 0.0
    latency_ms: float = 0.0
    mutation_op: str = ""  # rephrase, expand, compress, restructure
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode()).hexdigest()[:16]


@dataclass
class EvolutionRecord:
    """프롬프트 진화 기록 1건."""
    generation: int
    candidates_tested: int
    best_score: float
    selected_id: str
    timestamp: float
    improvement: float = 0.0


class PromptEvolver:
    """OPRO 기반 프롬프트 자동 최적화 엔진.

    LLM이 자기 시스템 프롬프트를 분석하고,
    더 나은 프롬프트 후보를 생성하여 벤치마크로 검증합니다.
    """

    # 프롬프트 변이 연산자
    MUTATION_OPS = [
        "rephrase",       # 동일 의미, 다른 표현
        "expand",         # 세부 지시사항 추가
        "compress",       # 핵심만 남기고 압축
        "restructure",    # 섹션 순서/구조 변경
        "add_constraint", # 제약 조건 추가 (환각 방지 등)
        "add_example",    # 예시 추가
    ]

    def __init__(
        self,
        ollama_url: str = config.model.api_base.replace('/v1', '').rstrip('/'),
        optimizer_model: str = "",
        candidates_per_gen: int = 3,
        persist_dir: str = "data/prompt_evolution",
    ):
        self._ollama_url = ollama_url
        self._optimizer_model = optimizer_model
        self._candidates_per_gen = candidates_per_gen
        self._persist_dir = Path(persist_dir)
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._history: List[EvolutionRecord] = []
        self._generation = 0
        self._load_history()

    # ─── 핵심 API ────────────────────────────────────────────────

    def evolve_system_prompt(
        self,
        current_prompt: str,
        performance_data: Dict[str, Any],
        eval_fn: Optional[Callable[[str], float]] = None,
    ) -> Tuple[str, float]:
        """시스템 프롬프트를 한 세대 진화시킵니다.

        Args:
            current_prompt: 현재 시스템 프롬프트
            performance_data: 최근 성능 데이터 (점수, 실패 패턴 등)
            eval_fn: 프롬프트 평가 함수 (prompt -> score 0.0~1.0)

        Returns:
            (best_prompt, best_score) 튜플
        """
        self._generation += 1
        logger.info(
            f"[PromptEvolver] 세대 {self._generation} 시작 "
            f"(후보 {self._candidates_per_gen}개 생성)"
        )

        # 1. 현재 프롬프트 기준 점수
        current_score = eval_fn(current_prompt) if eval_fn else 0.5
        current_candidate = PromptCandidate(
            candidate_id=f"current_{self._generation}",
            content=current_prompt,
            generation=self._generation,
            score=current_score,
            mutation_op="baseline",
        )

        # 2. 후보 생성 (OPRO: LLM이 자기 프롬프트를 분석하고 개선안 제안)
        candidates = [current_candidate]
        new_candidates = self._generate_candidates(
            current_prompt, performance_data
        )
        candidates.extend(new_candidates)

        # 3. 각 후보 평가
        if eval_fn:
            for c in new_candidates:
                try:
                    c.score = eval_fn(c.content)
                except Exception as e:
                    logger.warning(f"[PromptEvolver] 평가 실패: {c.candidate_id}: {e}")
                    c.score = 0.0

        # 4. 최고 성능 프롬프트 선택
        best = max(candidates, key=lambda c: c.score)
        improvement = best.score - current_score

        # 진화 기록
        record = EvolutionRecord(
            generation=self._generation,
            candidates_tested=len(candidates),
            best_score=best.score,
            selected_id=best.candidate_id,
            timestamp=time.time(),
            improvement=improvement,
        )
        self._history.append(record)
        self._save_history()

        # 프롬프트 버전 저장
        self._save_prompt_version(best)

        logger.info(
            f"[PromptEvolver] 세대 {self._generation} 완료: "
            f"최고 {best.score:.2%} (Δ{improvement:+.2%}), "
            f"선택: {best.mutation_op}"
        )

        return best.content, best.score

    def evolve_few_shots(
        self,
        current_examples: List[Dict[str, str]],
        task_type: str,
        eval_fn: Optional[Callable] = None,
    ) -> List[Dict[str, str]]:
        """Few-shot 예시를 자동 발견/교체합니다.

        기존 예시를 분석하고 더 효과적인 예시를 LLM에게 생성하게 합니다.
        """
        prompt = (
            "[ROLE] 당신은 AI 프롬프트 엔지니어링 전문가입니다.\n\n"
            "[TASK] 아래 few-shot 예시를 분석하고, "
            f"'{task_type}' 작업에 더 효과적인 예시 3개를 생성하세요.\n\n"
            "현재 예시:\n"
            + json.dumps(current_examples, ensure_ascii=False, indent=2)
            + "\n\n"
            "더 나은 예시를 JSON 배열로 반환하세요. "
            '각 예시는 {"input": "...", "output": "..."} 형태입니다.\n'
            "JSON만 반환하세요."
        )

        try:
            response = self._call_optimizer(prompt)
            # JSON 추출
            examples = self._extract_json_array(response)
            if examples and isinstance(examples, list):
                return examples[:3]
        except Exception as e:
            logger.warning(f"[PromptEvolver] Few-shot 진화 실패: {e}")

        return current_examples  # 실패 시 원본 유지

    # ─── 후보 생성 (OPRO 핵심) ───────────────────────────────────

    def _generate_candidates(
        self,
        current_prompt: str,
        performance_data: Dict[str, Any],
    ) -> List[PromptCandidate]:
        """OPRO 패턴: LLM이 프롬프트 개선안을 생성합니다."""
        candidates = []

        # 성능 데이터를 분석용 텍스트로 변환
        perf_text = self._format_performance_data(performance_data)

        for i in range(self._candidates_per_gen):
            # 변이 연산자 순환
            mutation_op = self.MUTATION_OPS[i % len(self.MUTATION_OPS)]

            meta_prompt = self._build_meta_prompt(
                current_prompt, perf_text, mutation_op
            )

            try:
                result = self._call_optimizer(meta_prompt)
                if result and len(result) > 50:
                    # <think> 태그 제거
                    result = re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL)
                    result = result.strip()

                    candidate = PromptCandidate(
                        candidate_id=f"gen{self._generation}_c{i}_{mutation_op}",
                        content=result,
                        generation=self._generation,
                        parent_id=f"current_{self._generation}",
                        mutation_op=mutation_op,
                    )
                    candidates.append(candidate)
            except Exception as e:
                logger.warning(f"[PromptEvolver] 후보 생성 실패 ({mutation_op}): {e}")

        return candidates

    def _build_meta_prompt(
        self,
        current_prompt: str,
        performance_data: str,
        mutation_op: str,
    ) -> str:
        """OPRO 메타 프롬프트를 구성합니다."""
        op_instructions = {
            "rephrase": (
                "동일한 의미를 유지하면서 더 명확하고 간결하게 다시 작성하세요."
            ),
            "expand": (
                "환각을 방지하는 제약 조건과 구체적인 출력 형식 지시를 추가하세요."
            ),
            "compress": (
                "핵심 지시사항만 남기고 불필요한 부분을 제거하세요. "
                "토큰 효율을 최대화하세요."
            ),
            "restructure": (
                "섹션 순서를 [ROLE]→[CONSTRAINTS]→[CONTEXT]→[TASK] 구조로 "
                "재배치하세요."
            ),
            "add_constraint": (
                "'절대 하지 말 것' 목록을 추가하세요: 환각 금지, 코드만 출력 금지, "
                "외국어 혼용 금지 등."
            ),
            "add_example": (
                "좋은 응답과 나쁜 응답의 대비 예시를 1개 추가하세요."
            ),
        }

        return (
            "[ROLE] 당신은 AI 시스템 프롬프트 최적화 전문가입니다.\n\n"
            "[CONTEXT] 아래는 현재 AI 에이전트의 시스템 프롬프트와 최근 성능 데이터입니다.\n\n"
            f"--- 현재 프롬프트 (첫 1000자) ---\n{current_prompt[:1000]}\n\n"
            f"--- 성능 데이터 ---\n{performance_data}\n\n"
            f"[TASK] 변이 연산: **{mutation_op}**\n"
            f"{op_instructions.get(mutation_op, '프롬프트를 개선하세요.')}\n\n"
            "개선된 전체 시스템 프롬프트를 출력하세요. 프롬프트만 출력하세요.\n"
            "마크다운 코드 블록이나 설명 없이, 프롬프트 텍스트만 반환하세요."
        )

    # ─── 통계 및 유틸 ────────────────────────────────────────────

    def get_evolution_trend(self) -> Dict[str, Any]:
        """진화 트렌드를 반환합니다."""
        if not self._history:
            return {"generations": 0, "message": "진화 기록 없음"}

        scores = [r.best_score for r in self._history]
        improvements = [r.improvement for r in self._history]

        return {
            "generations": len(self._history),
            "current_generation": self._generation,
            "best_score": max(scores),
            "latest_score": scores[-1],
            "avg_improvement": sum(improvements) / len(improvements),
            "total_improvement": sum(improvements),
            "score_trend": scores[-10:],
            "improving": (
                sum(1 for i in improvements if i > 0)
                > len(improvements) / 2
            ),
        }

    def _format_performance_data(self, data: Dict[str, Any]) -> str:
        """성능 데이터를 분석용 텍스트로 변환합니다."""
        lines = []
        if "quality_avg" in data:
            lines.append(f"평균 품질 점수: {data['quality_avg']:.2%}")
        if "weaknesses" in data:
            lines.append(f"약점: {', '.join(data['weaknesses'])}")
        if "failure_patterns" in data:
            lines.append(f"반복 실패 패턴: {', '.join(data['failure_patterns'])}")
        if "keyword_coverage" in data:
            lines.append(f"키워드 커버리지: {data['keyword_coverage']:.2%}")
        if "hallucination_rate" in data:
            lines.append(f"환각 비율: {data['hallucination_rate']:.2%}")
        return "\n".join(lines) if lines else "성능 데이터 없음"

    def _call_optimizer(self, prompt: str) -> str:
        """Optimizer LLM을 호출합니다."""
        model = self._optimizer_model
        if not model:
            # 사용 가능한 모델 자동 탐지
            try:
                resp = urllib.request.urlopen(
                    f"{self._ollama_url}/api/tags", timeout=5
                )
                tags = json.loads(resp.read())
                models = [m["name"] for m in tags.get("models", [])]
                model = models[0] if models else "llama3.2:latest"
            except Exception:
                model = "llama3.2:latest"

        data = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": 2048, "temperature": 0.4},
        }).encode()

        req = urllib.request.Request(
            f"{self._ollama_url}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            return result.get("response", "")

    def _extract_json_array(self, text: str) -> Any:
        """텍스트에서 JSON 배열을 추출합니다."""
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        decoder = json.JSONDecoder()
        for i, ch in enumerate(text):
            if ch == "[":
                try:
                    obj, _ = decoder.raw_decode(text, i)
                    if isinstance(obj, list):
                        return obj
                except json.JSONDecodeError:
                    continue
        return None

    def _save_prompt_version(self, candidate: PromptCandidate) -> None:
        """프롬프트 버전을 파일로 저장합니다."""
        version_file = self._persist_dir / f"gen{candidate.generation}_{candidate.mutation_op}.txt"
        try:
            with open(version_file, "w", encoding="utf-8") as f:
                f.write(f"# Generation {candidate.generation}\n")
                f.write(f"# Mutation: {candidate.mutation_op}\n")
                f.write(f"# Score: {candidate.score:.4f}\n")
                f.write(f"# Timestamp: {time.time()}\n\n")
                f.write(candidate.content)
        except Exception as e:
            logger.warning(f"[PromptEvolver] 버전 저장 실패: {e}")

    def _load_history(self) -> None:
        history_file = self._persist_dir / "evolution_history.json"
        if not history_file.exists():
            return
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._history = [
                EvolutionRecord(**r) for r in data.get("records", [])
            ]
            self._generation = data.get("generation", 0)
        except Exception as e:
            logger.warning(f"[PromptEvolver] 이력 로드 실패: {e}")

    def _save_history(self) -> None:
        history_file = self._persist_dir / "evolution_history.json"
        try:
            data = {
                "generation": self._generation,
                "updated_at": time.time(),
                "records": [asdict(r) for r in self._history],
            }
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[PromptEvolver] 이력 저장 실패: {e}")


"""Antigravity-K Prompt Evolver — OPRO-based automated prompt optimization."""
