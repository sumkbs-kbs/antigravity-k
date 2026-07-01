"""Antigravity-K: 스마트 모델 라우터.

================================
9Router 패턴 이식 — 3-Tier 폴백, 라운드로빈, 로드밸런싱 전략 지원.

핵심 개념:
- ModelCombo: 여러 모델을 하나의 "콤보"로 묶어 관리
- ModelRouter: 콤보 내에서 최적의 모델을 자동 선택
- UnavailabilityTracker: 실패한 모델의 지수 백오프 쿨다운 관리
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum

from .model_registry import ModelProfile, ModelRegistry

logger = logging.getLogger("antigravity_k.model_router")


# ─── 전략 열거형 ─────────────────────────────────────────────────────


class RouteStrategy(Enum):
    """모델 선택 전략."""

    FALLBACK = "fallback"  # 순서대로 시도, 실패 시 다음 모델
    ROUND_ROBIN = "round-robin"  # 순환 분배
    LOAD_BALANCE = "load-balance"  # 메모리 부하 기반 분배
    COLLECTIVE = "collective"  # 여러 모델 제안/비판/합성 집단지성 실행
    CASCADING = "cascading"  # 경량→중형→대형 점진적 에스컬레이션 (신뢰도 기반)


# ─── 데이터 클래스 ───────────────────────────────────────────────────


@dataclass
class ModelCombo:
    """모델 콤보: 여러 모델을 하나의 그룹으로 관리.

    예시 (config.yaml):
      combos:
        coding-stack:
          models: [qwen3-72b, qwen-coder-32b, llama4-scout]
          strategy: fallback
    """

    name: str
    models: list[str]  # 모델 이름 목록 (우선순위순)
    strategy: RouteStrategy = RouteStrategy.FALLBACK
    description: str = ""

    @classmethod
    def from_dict(cls, name: str, data: dict) -> "ModelCombo":
        """From Dict.

        Args:
            name (str): str name.
            data (dict): dict data.

        Returns:
            'ModelCombo': The 'modelcombo' result.

        """
        strategy_str = data.get("strategy", "fallback")
        try:
            strategy = RouteStrategy(strategy_str)
        except ValueError:
            logger.warning(
                "콤보 '%s': 알 수 없는 전략 '%s', fallback으로 대체합니다.",
                name,
                strategy_str,
            )
            strategy = RouteStrategy.FALLBACK

        return cls(
            name=name,
            models=data.get("models", []),
            strategy=strategy,
            description=data.get("description", ""),
        )


@dataclass
class UnavailableEntry:
    """사용 불가 모델 추적 항목."""

    model_name: str
    marked_at: float  # 마킹 시각 (timestamp)
    cooldown_sec: float  # 현재 쿨다운 (지수 증가)
    retry_count: int = 0  # 재시도 횟수
    reason: str = ""  # 실패 사유

    @property
    def available_at(self) -> float:
        """다시 사용 가능해지는 시각."""
        return self.marked_at + self.cooldown_sec

    def is_expired(self) -> bool:
        """쿨다운이 만료되었는지 확인."""
        return time.time() >= self.available_at

    def remaining_sec(self) -> float:
        """남은 쿨다운 시간 (초)."""
        return max(0.0, self.available_at - time.time())


# ─── 비가용 추적기 ───────────────────────────────────────────────────


class UnavailabilityTracker:
    """실패한 모델의 지수 백오프 쿨다운 관리.

    9Router 패턴: markAccountUnavailable() → 지수 백오프
    - 첫 실패: base_cooldown (60초)
    - 두 번째: base_cooldown × 2
    - 세 번째: base_cooldown × 4
    - 최대: max_cooldown (3600초)
    """

    def __init__(
        self,
        base_cooldown_sec: float = 60.0,
        max_cooldown_sec: float = 3600.0,
        backoff_multiplier: float = 2.0,
    ):
        """Initialize the UnavailabilityTracker.

        Args:
            base_cooldown_sec (float): float base cooldown sec.
            max_cooldown_sec (float): float max cooldown sec.
            backoff_multiplier (float): float backoff multiplier.

        """
        self._base = base_cooldown_sec
        self._max = max_cooldown_sec
        self._multiplier = backoff_multiplier
        self._entries: dict[str, UnavailableEntry] = {}

    def mark_unavailable(self, model_name: str, reason: str = "") -> None:
        """모델을 사용 불가로 마킹 (지수 백오프 적용)."""
        existing = self._entries.get(model_name)

        if existing and not existing.is_expired():
            # 이미 마킹됨 → 재시도 횟수 증가, 쿨다운 확장
            retry = existing.retry_count + 1
            cooldown = min(
                self._base * (self._multiplier**retry),
                self._max,
            )
        else:
            retry = 0
            cooldown = self._base

        entry = UnavailableEntry(
            model_name=model_name,
            marked_at=time.time(),
            cooldown_sec=cooldown,
            retry_count=retry,
            reason=reason,
        )
        self._entries[model_name] = entry
        logger.warning(
            "[%s] 사용 불가 마킹 — 쿨다운: %s초, 재시도: %s회, 사유: %s",
            model_name,
            cooldown,
            retry,
            reason or "없음",
        )

    def is_available(self, model_name: str) -> bool:
        """모델이 사용 가능한지 확인."""
        entry = self._entries.get(model_name)
        if entry is None:
            return True
        if entry.is_expired():
            # 쿨다운 만료 → 자동 복구
            logger.info("[%s] 쿨다운 만료, 재활성화", model_name)
            del self._entries[model_name]
            return True
        return False

    def mark_available(self, model_name: str) -> None:
        """모델을 수동으로 사용 가능 상태로 복원."""
        if model_name in self._entries:
            del self._entries[model_name]
            logger.info("[%s] 수동 재활성화", model_name)

    def get_entry(self, model_name: str) -> UnavailableEntry | None:
        """비가용 항목 조회."""
        return self._entries.get(model_name)

    def status(self) -> list[dict]:
        """현재 비가용 모델 목록 반환."""
        result = []
        for name, entry in self._entries.items():
            result.append(
                {
                    "model": name,
                    "reason": entry.reason,
                    "retry_count": entry.retry_count,
                    "remaining_sec": round(entry.remaining_sec(), 1),
                    "expired": entry.is_expired(),
                },
            )
        return result

    def clear_expired(self) -> int:
        """만료된 항목 정리, 정리된 수 반환."""
        expired = [name for name, entry in self._entries.items() if entry.is_expired()]
        for name in expired:
            del self._entries[name]
        return len(expired)

    def clear_all(self) -> None:
        """모든 비가용 마킹 초기화."""
        self._entries.clear()
        logger.info("모든 비가용 마킹 초기화")


# ─── 커스텀 예외 ─────────────────────────────────────────────────────


class AllModelsUnavailableError(Exception):
    """콤보 내 모든 모델이 사용 불가."""

    def __init__(self, combo_name: str, tried: list[str]):
        """Initialize the AllModelsUnavailableError.

        Args:
            combo_name (str): str combo name.
            tried (list[str]): list[str] tried.

        """
        self.combo_name = combo_name
        self.tried = tried
        super().__init__(f"콤보 '{combo_name}' 내 모든 모델이 사용 불가: {tried}")


class ComboNotFoundError(Exception):
    """요청한 콤보가 등록되어 있지 않음."""

    def __init__(self, combo_name: str, available: list[str]):
        """Initialize the ComboNotFoundError.

        Args:
            combo_name (str): str combo name.
            available (list[str]): list[str] available.

        """
        self.combo_name = combo_name
        self.available = available
        super().__init__(f"콤보 '{combo_name}'을 찾을 수 없습니다. 등록된 콤보: {available}")


# ─── 메인 라우터 ─────────────────────────────────────────────────────


class ModelRouter:
    """스마트 모델 라우터 — 9Router 패턴 기반.

    핵심 기능:
    - route(combo_name): 콤보 내에서 최적의 모델 선택
    - mark_failure(model_name): 실패한 모델을 쿨다운 처리
    - status(): 라우터 상태 조회

    사용 예시:
        router = ModelRouter(registry)
        router.register_combo(ModelCombo(
            name="coding-stack",
            models=["qwen3-72b", "qwen-coder-32b", "llama4-scout"],
            strategy=RouteStrategy.FALLBACK,
        ))
        profile = router.route("coding-stack")
    """

    def __init__(
        self,
        registry: ModelRegistry,
        base_cooldown_sec: float = 60.0,
        max_cooldown_sec: float = 3600.0,
        max_retries: int = 3,
    ):
        """Initialize the ModelRouter.

        Args:
            registry (ModelRegistry): ModelRegistry registry.
            base_cooldown_sec (float): float base cooldown sec.
            max_cooldown_sec (float): float max cooldown sec.
            max_retries (int): int max retries.

        """
        self._registry = registry
        self._combos: dict[str, ModelCombo] = {}
        self._tracker = UnavailabilityTracker(
            base_cooldown_sec=base_cooldown_sec,
            max_cooldown_sec=max_cooldown_sec,
        )
        self._max_retries = max_retries
        # 라운드로빈 인덱스 추적
        self._rr_index: dict[str, int] = {}

        # config.yaml에서 콤보 자동 로드
        self._load_combos_from_registry()

    def _load_combos_from_registry(self) -> None:
        """ModelRegistry의 raw config에서 combos 섹션 로드."""
        raw = getattr(self._registry, "_raw", {})
        combos_data = raw.get("combos", {})

        for combo_name, combo_config in combos_data.items():
            if isinstance(combo_config, dict):
                combo = ModelCombo.from_dict(combo_name, combo_config)
                self._combos[combo_name] = combo
                logger.info(
                    "콤보 로드: %s (%s개 모델, %s)",
                    combo_name,
                    len(combo.models),
                    combo.strategy.value,
                )

    def reload(self) -> None:
        """레지스트리 변경 후 콤보를 핫 리로드합니다."""
        self._combos.clear()
        self._load_combos_from_registry()
        logger.info("ModelRouter 콤보 핫 리로드 완료")

    # ─── 콤보 관리 ───────────────────────────────────────────────────

    def register_combo(self, combo: ModelCombo) -> None:
        """콤보 등록."""
        self._combos[combo.name] = combo
        logger.info("콤보 등록: %s", combo.name)

    def unregister_combo(self, name: str) -> bool:
        """콤보 등록 해제."""
        if name in self._combos:
            del self._combos[name]
            if name in self._rr_index:
                del self._rr_index[name]
            return True
        return False

    def get_combo(self, name: str) -> ModelCombo | None:
        """콤보 조회."""
        return self._combos.get(name)

    def list_combos(self) -> list[ModelCombo]:
        """등록된 모든 콤보 반환."""
        return list(self._combos.values())

    # ─── 핵심 라우팅 ─────────────────────────────────────────────────

    def route(self, combo_name: str) -> ModelProfile:
        """콤보 내에서 최적의 모델을 선택하여 반환.

        전략에 따라 동작이 다릅니다:
        - FALLBACK: 순서대로 시도, 사용 불가 시 다음 모델
        - ROUND_ROBIN: 순환 분배 (부하 분산)
        - LOAD_BALANCE: 메모리 사용량 기반 최적 선택
        - COLLECTIVE: ModelManager의 집단지성 실행기가 전체 후보를 호출.
          단일 라우팅이 필요한 레거시 경로에서는 fallback과 동일하게 동작.
        """
        combo = self._combos.get(combo_name)
        if combo is None:
            raise ComboNotFoundError(
                combo_name,
                list(self._combos.keys()),
            )

        # 만료된 비가용 항목 정리
        self._tracker.clear_expired()

        if combo.strategy == RouteStrategy.FALLBACK:
            return self._route_fallback(combo)
        elif combo.strategy == RouteStrategy.ROUND_ROBIN:
            return self._route_round_robin(combo)
        elif combo.strategy == RouteStrategy.LOAD_BALANCE:
            return self._route_load_balance(combo)
        elif combo.strategy == RouteStrategy.CASCADING:
            return self._route_cascading(combo)
        elif combo.strategy == RouteStrategy.COLLECTIVE:
            return self._route_fallback(combo)
        else:
            return self._route_fallback(combo)

    def route_single(self, model_name: str) -> ModelProfile:
        """단일 모델 직접 라우팅 (콤보 없이)."""
        if not self._tracker.is_available(model_name):
            entry = self._tracker.get_entry(model_name)
            remaining = entry.remaining_sec() if entry else 0
            raise AllModelsUnavailableError(
                f"single:{model_name}",
                [f"{model_name} (쿨다운 {remaining:.0f}초 남음)"],
            )

        profile = self._registry.get_model(model_name)
        if profile is None:
            raise ValueError(f"모델 '{model_name}'이 레지스트리에 없습니다.")
        return profile

    def available_model_names(self, combo_name: str) -> list[str]:
        """콤보 안에서 현재 라우팅 가능한 모델 이름 목록을 반환합니다."""
        combo = self._combos.get(combo_name)
        if combo is None:
            raise ComboNotFoundError(combo_name, list(self._combos.keys()))

        self._tracker.clear_expired()
        return [
            model_name
            for model_name in combo.models
            if self._tracker.is_available(model_name) and self._registry.get_model(model_name) is not None
        ]

    # ─── 전략별 라우팅 구현 ──────────────────────────────────────────

    def _route_fallback(self, combo: ModelCombo) -> ModelProfile:
        """폴백 전략: 순서대로 시도, 사용 불가 모델은 건너뜀.

        9Router의 handleSingleModelChat → while(true) 폴백 루프 패턴.
        """
        tried = []
        for model_name in combo.models:
            tried.append(model_name)

            if not self._tracker.is_available(model_name):
                entry = self._tracker.get_entry(model_name)
                remaining = entry.remaining_sec() if entry else 0
                logger.debug("[%s] %s 스킵 (쿨다운 %s초 남음)", combo.name, model_name, remaining)
                continue

            profile = self._registry.get_model(model_name)
            if profile is None:
                logger.warning("[%s] %s이 레지스트리에 없음, 스킵", combo.name, model_name)
                continue

            logger.info("[%s] 라우팅 → %s (fallback)", combo.name, model_name)
            return profile

        raise AllModelsUnavailableError(combo.name, tried)

    def _route_round_robin(self, combo: ModelCombo) -> ModelProfile:
        """라운드로빈 전략: 사용 가능한 모델을 순환 선택."""
        available = [
            m for m in combo.models if self._tracker.is_available(m) and self._registry.get_model(m) is not None
        ]

        if not available:
            raise AllModelsUnavailableError(combo.name, combo.models)

        idx = self._rr_index.get(combo.name, 0) % len(available)
        selected = available[idx]
        self._rr_index[combo.name] = idx + 1

        profile = self._registry.get_model(selected)
        logger.info("[%s] 라우팅 → %s (round-robin, idx=%s)", combo.name, selected, idx)
        return profile  # type: ignore

    def _route_load_balance(self, combo: ModelCombo) -> ModelProfile:
        """로드밸런싱 전략: 메모리 사용량이 적은 모델 우선."""
        available = []
        for model_name in combo.models:
            if not self._tracker.is_available(model_name):
                continue
            profile = self._registry.get_model(model_name)
            if profile:
                available.append(profile)

        if not available:
            raise AllModelsUnavailableError(combo.name, combo.models)

        # 메모리 적게 쓰는 모델 우선 (경량 모델 선호)
        selected = min(available, key=lambda p: p.estimated_memory_gb)
        logger.info(
            "[%s] 라우팅 → %s (load-balance, %sGB)",
            combo.name,
            selected.name,
            selected.estimated_memory_gb,
        )
        return selected

    def _route_cascading(self, combo: ModelCombo) -> ModelProfile:
        """Cascading 전략: 경량 모델부터 시도하고, 신뢰도가 낮으면 자동 에스컬레이션.

        모델 목록의 순서가 곧 에스컬레이션 티어입니다:
          - models[0]: Tier 1 (경량, 4B 급) — 빠른 응답
          - models[1]: Tier 2 (중형, 24B 급) — 품질 응답
          - models[2]: Tier 3 (대형, 72B 급 또는 MoA) — 최고 품질

        route()는 가장 가벼운 가용 모델을 반환하고,
        실제 에스컬레이션은 ModelManager에서 응답 품질을 평가한 후
        escalate()를 호출하여 다음 티어 모델을 받아옵니다.
        """
        for model_name in combo.models:
            if not self._tracker.is_available(model_name):
                continue
            profile = self._registry.get_model(model_name)
            if profile is None:
                continue
            logger.info(
                "[%s] 라우팅 → %s (cascading, Tier %s/%s)",
                combo.name,
                model_name,
                combo.models.index(model_name) + 1,
                len(combo.models),
            )
            return profile

        raise AllModelsUnavailableError(combo.name, combo.models)

    def escalate(self, combo_name: str, current_model: str) -> ModelProfile | None:
        """현재 모델에서 다음 티어로 에스컬레이션합니다.

        Args:
            combo_name: 콤보 이름
            current_model: 현재 사용 중인 모델 이름

        Returns:
            다음 티어의 ModelProfile, 또는 없으면 None (최고 티어 도달)

        """
        combo = self._combos.get(combo_name)
        if combo is None:
            return None

        try:
            idx = combo.models.index(current_model)
        except ValueError:
            return None

        # 다음 티어부터 가용 모델 탐색
        for next_model in combo.models[idx + 1 :]:
            if not self._tracker.is_available(next_model):
                continue
            profile = self._registry.get_model(next_model)
            if profile:
                logger.info(
                    "[%s] 에스컬레이션: %s → %s (Tier %s)",
                    combo_name,
                    current_model,
                    next_model,
                    combo.models.index(next_model) + 1,
                )
                return profile

        logger.info("[%s] 에스컬레이션 불가: %s이 최고 티어", combo_name, current_model)
        return None

    @staticmethod
    def estimate_confidence(response: str) -> float:
        """응답 텍스트에서 신뢰도 점수를 휴리스틱으로 추정합니다.

        신뢰도가 낮은 응답의 특징:
        - 매우 짧은 응답 (정보 부족)
        - "확실하지 않습니다", "모르겠습니다" 등 불확실성 표현
        - 반복적인 패턴
        - 도구 호출 실패/에러 포함

        Returns:
            0.0 ~ 1.0 사이의 신뢰도 점수

        """
        import re

        if not response or len(response.strip()) < 20:
            return 0.1

        score = 1.0

        # 너무 짧은 응답 감점
        if len(response) < 100:
            score *= 0.6
        elif len(response) < 200:
            score *= 0.8

        # 불확실성 표현 감점
        uncertainty_patterns = [
            r"확실하지 않",
            r"모르겠",
            r"잘 모르",
            r"정확하지 않",
            r"불확실",
            r"추측",
            r"I'm not sure",
            r"I don't know",
            r"uncertain",
        ]
        for pat in uncertainty_patterns:
            if re.search(pat, response, re.IGNORECASE):
                score *= 0.7
                break

        # 에러/실패 표현 감점
        error_patterns = [
            r"\[API Error",
            r"\[Error",
            r"실패",
            r"failed",
            r"error",
            r"exception",
        ]
        for pat in error_patterns:
            if re.search(pat, response, re.IGNORECASE):
                score *= 0.5
                break

        # 반복 패턴 감점
        sentences = response.split(".")
        if len(sentences) > 3:
            unique_ratio = len(set(sentences)) / len(sentences)
            if unique_ratio < 0.5:
                score *= 0.5

        return max(0.0, min(1.0, score))

    # ─── 실패/복구 관리 ──────────────────────────────────────────────

    def mark_failure(self, model_name: str, reason: str = "") -> None:
        """모델 사용 실패 시 호출 — 쿨다운 등록."""
        self._tracker.mark_unavailable(model_name, reason)

    def mark_recovered(self, model_name: str) -> None:
        """모델 복구 시 호출 — 쿨다운 해제."""
        self._tracker.mark_available(model_name)

    # ─── 상태 조회 ───────────────────────────────────────────────────

    def status(self) -> dict:
        """라우터 전체 상태 반환."""
        combos_info = []
        for combo in self._combos.values():
            available_models = [m for m in combo.models if self._tracker.is_available(m)]
            combos_info.append(
                {
                    "name": combo.name,
                    "strategy": combo.strategy.value,
                    "total_models": len(combo.models),
                    "available_models": len(available_models),
                    "models": combo.models,
                    "description": combo.description,
                },
            )

        return {
            "combos": combos_info,
            "unavailable": self._tracker.status(),
            "max_retries": self._max_retries,
        }

    def summary(self) -> str:
        """사람이 읽기 쉬운 요약."""
        lines = ["=== Model Router ==="]
        for combo in self._combos.values():
            available = [m for m in combo.models if self._tracker.is_available(m)]
            lines.append(f"\n[{combo.name}] ({combo.strategy.value})")
            for m in combo.models:
                marker = "✓" if self._tracker.is_available(m) else "✗"
                lines.append(f"  {marker} {m}")
            lines.append(f"  → 사용 가능: {len(available)}/{len(combo.models)}")

        unavailable = self._tracker.status()
        if unavailable:
            lines.append("\n[비가용 모델]")
            for entry in unavailable:
                lines.append(
                    f"  ✗ {entry['model']} — 남은 시간: {entry['remaining_sec']}초, 재시도: {entry['retry_count']}회",
                )

        return "\n".join(lines)
