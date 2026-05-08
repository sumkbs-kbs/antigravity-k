"""
Antigravity-K: Agent Archive (에이전트 변이체 아카이브)
=====================================================
성공한 에이전트 변이체를 저장하고 진화 계보를 추적합니다.

연구 근거: ADAS Meta Agent Search (ICLR 2025), Darwin Gödel Machine (Sakana AI)

핵심 개념:
  - AgentVariant: 프롬프트 + 샘플링 설정 + 도구 설정의 불변 스냅샷
  - Archive: 검증된 변이체만 저장하는 진화 기록소
  - Lineage: 어떤 변이가 어떤 개선을 가져왔는지 추적
  - Crossover: 두 성공 변이체의 장점을 교차 결합
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("antigravity_k.agent_archive")


@dataclass
class AgentVariant:
    """에이전트 변이체 — 특정 시점의 에이전트 설정 스냅샷."""

    variant_id: str
    generation: int  # 세대 번호
    parent_id: str = ""  # 부모 변이체 ID (계보 추적)

    # 프롬프트 설정
    system_prompt_hash: str = ""
    system_prompt_snippet: str = ""  # 첫 200자
    tool_prompt_hash: str = ""
    few_shot_examples: List[str] = field(default_factory=list)

    # 샘플링 설정
    sampling_profiles: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # 성능 지표
    benchmark_score: float = 0.0
    quality_avg: float = 0.0
    keyword_coverage: float = 0.0
    latency_avg_ms: float = 0.0

    # 변이 정보
    mutation_type: str = ""  # "prompt" | "sampling" | "code" | "tool" | "crossover"
    mutation_description: str = ""
    improvement_delta: float = 0.0  # 부모 대비 개선율

    # 메타데이터
    timestamp: float = 0.0
    archived: bool = False
    retired: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AgentVariant":
        return cls(**{
            k: v for k, v in data.items()
            if k in cls.__dataclass_fields__
        })


class AgentArchive:
    """에이전트 변이체 아카이브.

    진화 알고리즘의 '군집(population)'을 관리합니다.
    성공한 변이체만 저장하고, 실패한 변이체는 기록만 남깁니다.
    """

    MAX_ARCHIVE_SIZE = 50  # 최대 보존 변이체 수
    MIN_IMPROVEMENT_THRESHOLD = 0.01  # 최소 개선율 (1%)

    def __init__(self, archive_dir: str = "data/agent_archive"):
        self._dir = Path(archive_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._variants: List[AgentVariant] = []
        self._generation_counter = 0
        self._load()

    # ─── 핵심 API ────────────────────────────────────────────────

    def archive(self, variant: AgentVariant) -> bool:
        """검증된 변이체를 아카이브에 저장합니다.

        저장 조건:
        1. 부모보다 성능이 향상되었거나 (improvement_delta > 0)
        2. 첫 번째 변이체 (부모 없음)

        Returns:
            True if archived, False if rejected
        """
        if variant.parent_id:
            parent = self.get(variant.parent_id)
            if parent and variant.benchmark_score <= parent.benchmark_score:
                if variant.improvement_delta < self.MIN_IMPROVEMENT_THRESHOLD:
                    logger.info(
                        f"[Archive] 변이체 거부: {variant.variant_id} "
                        f"(개선 미달: {variant.improvement_delta:+.2%})"
                    )
                    return False

        variant.archived = True
        variant.timestamp = time.time()
        variant.generation = self._generation_counter
        self._variants.append(variant)

        # 아카이브 크기 제한 — 최저 성능 변이체부터 은퇴
        if len(self._variants) > self.MAX_ARCHIVE_SIZE:
            self._retire_weakest()

        self._save()
        logger.info(
            f"[Archive] 저장: {variant.variant_id} "
            f"(Gen {variant.generation}, score: {variant.benchmark_score:.2%}, "
            f"Δ{variant.improvement_delta:+.2%})"
        )
        return True

    def get(self, variant_id: str) -> Optional[AgentVariant]:
        """변이체를 ID로 조회합니다."""
        for v in self._variants:
            if v.variant_id == variant_id:
                return v
        return None

    def get_best(self) -> Optional[AgentVariant]:
        """가장 높은 성능의 변이체를 반환합니다."""
        active = [v for v in self._variants if not v.retired]
        if not active:
            return None
        return max(active, key=lambda v: v.benchmark_score)

    def get_latest(self) -> Optional[AgentVariant]:
        """가장 최근 변이체를 반환합니다."""
        active = [v for v in self._variants if not v.retired]
        return active[-1] if active else None

    def advance_generation(self) -> int:
        """세대를 진행합니다."""
        self._generation_counter += 1
        self._save()
        return self._generation_counter

    # ─── 진화 계보 ───────────────────────────────────────────────

    def lineage(self, variant_id: str) -> List[AgentVariant]:
        """변이체의 진화 계보를 추적합니다 (자손 → 조상)."""
        chain = []
        current_id = variant_id

        while current_id:
            variant = self.get(current_id)
            if not variant:
                break
            chain.append(variant)
            current_id = variant.parent_id

        return chain

    def lineage_markdown(self, variant_id: str = "") -> str:
        """진화 계보를 마크다운으로 시각화합니다."""
        if not variant_id:
            best = self.get_best()
            if not best:
                return "아카이브가 비어 있습니다."
            variant_id = best.variant_id

        chain = self.lineage(variant_id)
        if not chain:
            return f"변이체 `{variant_id}`를 찾을 수 없습니다."

        lines = ["## 🧬 진화 계보\n"]
        for i, v in enumerate(chain):
            prefix = "🏆" if i == 0 else "  " * i + "↑"
            lines.append(
                f"{prefix} **Gen {v.generation}** `{v.variant_id}` "
                f"— {v.mutation_type} ({v.benchmark_score:.1%}, "
                f"Δ{v.improvement_delta:+.1%})"
            )
            if v.mutation_description:
                lines.append(f"{'  ' * (i + 1)}*{v.mutation_description}*")

        return "\n".join(lines)

    # ─── 교차 결합 (Crossover) ───────────────────────────────────

    def crossover(
        self,
        parent_a_id: str,
        parent_b_id: str,
    ) -> Optional[AgentVariant]:
        """두 성공 변이체의 장점을 교차 결합합니다.

        결합 전략:
        - 프롬프트: 더 높은 점수의 변이체에서 가져옴
        - 샘플링: 각 프로파일별로 더 나은 쪽 선택
        - Few-shot: 양쪽의 합집합
        """
        parent_a = self.get(parent_a_id)
        parent_b = self.get(parent_b_id)

        if not parent_a or not parent_b:
            return None

        # 더 나은 프롬프트를 기본으로 사용
        base = parent_a if parent_a.benchmark_score >= parent_b.benchmark_score else parent_b
        other = parent_b if base is parent_a else parent_a

        # 샘플링 프로파일 교차
        merged_sampling = dict(base.sampling_profiles)
        for key, profile in other.sampling_profiles.items():
            if key not in merged_sampling:
                merged_sampling[key] = profile

        # Few-shot 합집합 (중복 제거)
        merged_fewshots = list(set(base.few_shot_examples + other.few_shot_examples))

        child_id = f"cross_{parent_a_id[:8]}x{parent_b_id[:8]}_{int(time.time())}"
        child = AgentVariant(
            variant_id=child_id,
            generation=self._generation_counter,
            parent_id=f"{parent_a_id}+{parent_b_id}",
            system_prompt_hash=base.system_prompt_hash,
            system_prompt_snippet=base.system_prompt_snippet,
            tool_prompt_hash=base.tool_prompt_hash,
            few_shot_examples=merged_fewshots,
            sampling_profiles=merged_sampling,
            mutation_type="crossover",
            mutation_description=(
                f"교차 결합: {parent_a_id[:12]} ({parent_a.benchmark_score:.1%}) "
                f"× {parent_b_id[:12]} ({parent_b.benchmark_score:.1%})"
            ),
        )

        logger.info(f"[Archive] 교차 결합 생성: {child_id}")
        return child

    # ─── 통계 및 유틸 ────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        """아카이브 통계를 반환합니다."""
        active = [v for v in self._variants if not v.retired]
        if not active:
            return {"total": 0, "active": 0, "generations": 0}

        scores = [v.benchmark_score for v in active]
        return {
            "total": len(self._variants),
            "active": len(active),
            "retired": len(self._variants) - len(active),
            "generations": self._generation_counter,
            "best_score": max(scores),
            "avg_score": sum(scores) / len(scores),
            "mutation_types": {
                mt: sum(1 for v in active if v.mutation_type == mt)
                for mt in {"prompt", "sampling", "code", "tool", "crossover"}
            },
        }

    def _retire_weakest(self) -> None:
        """가장 약한 변이체를 은퇴시킵니다."""
        active = [v for v in self._variants if not v.retired]
        if len(active) <= self.MAX_ARCHIVE_SIZE:
            return
        weakest = min(active, key=lambda v: v.benchmark_score)
        weakest.retired = True
        logger.info(f"[Archive] 은퇴: {weakest.variant_id} ({weakest.benchmark_score:.1%})")

    def _load(self) -> None:
        archive_file = self._dir / "archive.json"
        if not archive_file.exists():
            return
        try:
            with open(archive_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._variants = [
                AgentVariant.from_dict(v) for v in data.get("variants", [])
            ]
            self._generation_counter = data.get("generation_counter", 0)
            logger.info(f"[Archive] {len(self._variants)}개 변이체 로드")
        except Exception as e:
            logger.warning(f"[Archive] 로드 실패: {e}")

    def _save(self) -> None:
        archive_file = self._dir / "archive.json"
        try:
            data = {
                "version": 1,
                "generation_counter": self._generation_counter,
                "updated_at": time.time(),
                "variants": [v.to_dict() for v in self._variants],
            }
            with open(archive_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[Archive] 저장 실패: {e}")


"""Antigravity-K Agent Archive — Evolutionary variant storage with lineage tracking."""
