"""Antigravity-K: 모델 매니저.

런타임 모델 로드/언로드/핫스왑 + 메모리 자동 관리
"""

from __future__ import annotations

import gc
import json
import logging
import os
import time
from collections import OrderedDict
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any, final

if TYPE_CHECKING:
    from antigravity_k.engine.best_of_n_verifier import VerificationOutcome

from ..tools.egress_policy import safe_urlopen
from .collective_intelligence import CollectiveIntelligenceEngine
from .context_budget import context_budget_for_model
from .local_runtime import LocalRuntimeSupervisor
from .long_context_policy import LongContextExecutionPlan, build_long_context_plan
from .memory_policy import MemoryPolicy
from .model_registry import ModelProfile, ModelRegistry
from .model_router import AllModelsUnavailableError, ModelCombo, ModelRouter, RouteStrategy
from .provider_adapters.inference_providers import BaseInferenceProvider
from .provider_capabilities import LocalProviderCapabilityProbe, ProviderCapability
from .usage_tracker import UsageTracker

logger = logging.getLogger("antigravity_k.model_manager")

Message = dict[str, Any]
Payload = dict[str, Any]


# ─── 적응형 샘플링 프로파일 (Adaptive Sampling Profiles) ───
# Single Source of Truth: engine/sampling_config.py
from .sampling_config import SAMPLING_PROFILES


@dataclass
class LoadedModel:
    """현재 메모리에 로드된 모델 정보."""

    profile: ModelProfile
    model: Any = None  # mlx_lm 모델 객체
    tokenizer: Any = None  # 토크나이저
    loaded_at: float = 0.0  # 로드 시각 (timestamp)
    last_used_at: float = 0.0  # 마지막 사용 시각
    actual_memory_gb: float = 0.0

    def touch(self):
        """사용 시각 갱신 (LRU용)."""
        self.last_used_at = time.time()


@final
class ModelManager:
    """동적 모델 로드/언로드 매니저.

    핵심 기능:
    - load(name): 모델 로드 (메모리 부족 시 자동 언로드)
    - unload(name): 모델 언로드
    - swap(name): 같은 역할의 모델 교체 (기존 언로드 → 새 모델 로드)
    - get(name): 로드된 모델 반환, 없으면 자동 로드
    - status(): 현재 로드 상태 반환
    """

    def __init__(
        self,
        registry: ModelRegistry,
        router: ModelRouter | None = None,
        tracker: UsageTracker | None = None,
    ):
        """Initialize the ModelManager.

        Args:
            registry (ModelRegistry): ModelRegistry registry.
            router (ModelRouter | None): ModelRouter | None router.
            tracker (UsageTracker | None): UsageTracker | None tracker.

        """
        self._registry = registry
        self._loaded: OrderedDict[str, LoadedModel] = OrderedDict()
        self._mem_config = registry.memory_config

        # MemoryPolicy: 메모리 관리 정책 위임
        self._memory_policy = MemoryPolicy(
            max_gb=self._mem_config.max_loaded_gb,
            cooldown_sec=self._mem_config.unload_cooldown_sec,
            auto_unload=self._mem_config.auto_unload,
        )

        # 9Router 패턴 통합
        self.router = router or ModelRouter(registry)
        self.tracker = tracker or UsageTracker()
        self._capability_probe = LocalProviderCapabilityProbe(registry)
        self._local_discovery_at = 0.0
        self._runtime_supervisor = LocalRuntimeSupervisor()

    def discover_local_models(self, *, refresh: bool = False) -> tuple[ModelProfile, ...]:
        enabled = os.getenv("AGK_AUTO_DISCOVER_LOCAL_MODELS", "true").casefold() not in {"0", "false", "no", "off"}
        if not enabled:
            return ()
        now = time.monotonic()
        try:
            ttl = max(0.0, float(os.getenv("AGK_LOCAL_MODEL_DISCOVERY_TTL", "30")))
        except ValueError:
            ttl = 30.0
        if not refresh and now - self._local_discovery_at < ttl:
            return ()
        added = self._registry.refresh_local_models()
        self._local_discovery_at = now
        if added:
            self._capability_probe.clear()
        return added

    def reload(self) -> None:
        """설정 파일 변경 후 레지스트리 및 라우터를 핫 리로드합니다."""
        self._registry.reload()
        self.router.reload()
        self._mem_config = self._registry.memory_config
        self._capability_probe.clear()
        logger.info("ModelManager 핫 리로드 완료")

    # ─── 핵심 API ────────────────────────────────────────────────────

    def load(self, name: str) -> LoadedModel:
        """모델을 메모리에 로드."""
        # 이미 로드됨
        if name in self._loaded:
            loaded = self._loaded[name]
            loaded.touch()
            logger.info("[%s] 이미 로드됨, 재사용", name)
            return loaded

        # 레지스트리에서 프로필 확인
        profile = self._registry.get_model(name)
        if profile is None:
            raise ValueError(
                f"모델 '{name}'이 config.yaml에 등록되어 있지 않습니다.\n"
                f"등록된 모델: {[m.name for m in self._registry.list_models()]}",
            )

        # 메모리 확보
        self._ensure_memory(profile.estimated_memory_gb)
        _ = self._runtime_supervisor.ensure_available(profile)

        # 실제 모델 로드
        logger.info("[%s] 로드 시작 (예상 %sGB)...", name, profile.estimated_memory_gb)
        model_obj, tokenizer_obj = self._load_mlx_model(profile)

        now = time.time()
        loaded = LoadedModel(
            profile=profile,
            model=model_obj,
            tokenizer=tokenizer_obj,
            loaded_at=now,
            last_used_at=now,
            actual_memory_gb=profile.estimated_memory_gb,
        )

        self._loaded[name] = loaded
        logger.info("[%s] 로드 완료 ✓", name)
        return loaded

    def unload(self, name: str) -> bool:
        """모델을 메모리에서 해제."""
        if name not in self._loaded:
            logger.warning("[%s] 로드되지 않은 모델", name)
            return False

        loaded = self._loaded.pop(name)
        # 모델 객체 해제
        del loaded.model
        del loaded.tokenizer
        _ = gc.collect()

        logger.info("[%s] 언로드 완료 (%sGB 해제)", name, loaded.actual_memory_gb)
        return True

    def swap(self, new_name: str, role: str | None = None) -> LoadedModel:
        """같은 역할의 모델 교체 (기존 언로드 → 새 모델 로드)."""
        new_profile = self._registry.get_model(new_name)
        if new_profile is None:
            raise ValueError(f"모델 '{new_name}'이 등록되어 있지 않습니다.")

        target_role = role or new_profile.role

        # 같은 역할로 로드된 기존 모델 찾아서 언로드
        to_unload = [
            name
            for name, loaded in self._loaded.items()
            if target_role in loaded.profile.supported_roles and name != new_name
        ]
        for name in to_unload:
            logger.info("[%s] → [%s] 교체를 위해 언로드", name, new_name)
            _ = self.unload(name)

        return self.load(new_name)

    def get(self, name: str) -> LoadedModel:
        """로드된 모델 반환 (없으면 자동 로드)."""
        if name in self._loaded:
            loaded = self._loaded[name]
            loaded.touch()
            return loaded
        return self.load(name)

    def get_by_role(self, role: str) -> LoadedModel | None:
        """역할별로 현재 로드된 모델 반환."""
        for loaded in self._loaded.values():
            if role in loaded.profile.supported_roles:
                loaded.touch()
                return loaded
        # 로드된 게 없으면 기본 모델 로드 시도
        default = self._registry.get_default(role)
        if default:
            return self.load(default.name)
        return None

    def get_target_for_role(self, role_name: str, default_role: str = "reasoning") -> str:
        """역할별 실행 타겟을 반환합니다.

        config.yaml의 agent_models는 단일 모델뿐 아니라 콤보 이름도 허용합니다.
        콤보가 반환되면 generate()/stream_generate()가 해당 전략에 따라 처리합니다.
        """
        raw = getattr(self._registry, "_raw", {})
        agent_models = raw.get("agent_models", {})
        configured: list[str] = []

        def registered(target: str) -> bool:
            return bool(self.router.get_combo(target)) or self._registry.get_model(target) is not None

        if isinstance(agent_models, dict):
            for key in (role_name, role_name.upper(), role_name.lower(), "default"):
                value = agent_models.get(key)
                if isinstance(value, str) and value:
                    configured.append(value)
                    if registered(value):
                        return value

        added = self.discover_local_models() if configured else ()
        for value in configured:
            if registered(value):
                return value

        default = self._registry.get_default(default_role)
        if isinstance(default, ModelProfile):
            return default.name

        discovered = [item for item in added if isinstance(item, ModelProfile)]
        discovered.extend(
            item
            for item in self._registry.list_models()
            if isinstance(item, ModelProfile) and item.is_local and item not in discovered
        )
        for profile in discovered:
            roles = profile.supported_roles
            if role_name in roles or default_role in roles:
                return profile.name
        if discovered:
            return discovered[0].name
        if configured:
            return configured[0]
        return "default_model"

    def prefetch(self, name: str) -> bool:
        """런타임 지연을 방지하기 위해 사전에 모델을 로드합니다.

        필요한 메모리가 확보 가능할 때만 로드하며, 이미 로드되어 있다면 무시합니다.
        """
        if name in self._loaded:
            return True

        profile = self._registry.get_model(name)
        if profile is None:
            logger.warning("Prefetch 실패: '%s' 모델을 찾을 수 없습니다.", name)
            return False

        # 메모리 여유 체크
        current_used = sum(m.actual_memory_gb for m in self._loaded.values())
        if current_used + profile.estimated_memory_gb > self._mem_config.max_loaded_gb:
            logger.warning("Prefetch 보류: [%s] 로드를 위한 메모리 부족 예상", name)
            if self._mem_config.auto_unload:
                logger.info("[%s] 프리패치를 위해 기존 모델 자동 교체 시도", name)
                try:
                    _ = self.load(name)
                    return True
                except MemoryError:
                    return False
            return False

        try:
            _ = self.load(name)
            return True
        except Exception:
            logger.exception("Prefetch 실패 [%s]", name)
            return False

    # ─── 추론 API (9Router 연동) ─────────────────────────────────────

    def _record_successful_call(
        self,
        model: str,
        prompt: str,
        response: str,
        latency_ms: float,
        combo_name: str,
        fallback_depth: int,
        *,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
    ) -> None:
        """Record usage + tracing for a successful inference call."""
        resolved_tokens_in = len(prompt) // 4 if tokens_in is None else tokens_in
        resolved_tokens_out = len(response) // 4 if tokens_out is None else tokens_out
        _ = self.tracker.record(
            model_name=model,
            tokens_in=resolved_tokens_in,
            tokens_out=resolved_tokens_out,
            latency_ms=latency_ms,
            success=True,
            combo_name=combo_name,
            fallback_depth=fallback_depth,
        )
        self._trace_llm_call(
            model=model,
            tokens_in=resolved_tokens_in,
            tokens_out=resolved_tokens_out,
            latency_ms=latency_ms,
            success=True,
            combo=combo_name,
            fallback_depth=fallback_depth,
        )
        self.router.mark_recovered(model)

    def _record_failed_call(
        self,
        model: str,
        error: str,
        latency_ms: float,
        combo_name: str,
        fallback_depth: int,
    ) -> None:
        """Record usage + tracing for a failed inference call."""
        _ = self.tracker.record(
            model_name=model,
            latency_ms=latency_ms,
            success=False,
            error=error,
            combo_name=combo_name,
            fallback_depth=fallback_depth,
        )
        self._trace_llm_call(
            model=model,
            latency_ms=latency_ms,
            success=False,
            error=error,
            combo=combo_name,
            fallback_depth=fallback_depth,
        )
        self.router.mark_failure(model, reason=error)

    def _maybe_cascade_escalate(
        self,
        prompt: str,
        combo_name: str | None,
        combo: ModelCombo | None,
        used_model: str,
        response_text: str,
        kwargs: Payload,
    ) -> str | None:
        """Cascading 콤보에서 낮은 신뢰도 응답을 상위 티어로 재생성한다.

        self-contained 루프: combo 컨텍스트를 유지하며 최대 cascade_max_escalations
        만큼 상위 티어를 시도한다. 에스컬레이션이 일어나지 않으면 None을 반환해
        호출자가 원 응답을 사용한다.
        """
        if not getattr(self.router, "cascade_on_low_confidence", False):
            return None
        if not combo_name or combo is None or combo.strategy != RouteStrategy.CASCADING:
            return None

        threshold = self.router.cascade_confidence_threshold
        current_model = used_model
        current_text = response_text
        escalated = False
        confidence = self._estimate_confidence(prompt, current_text)

        for _ in range(self.router.cascade_max_escalations):
            if confidence >= threshold:
                logger.debug(
                    "[%s] 신뢰도 %.2f >= %.2f, 응답 유지 (%s)",
                    combo_name,
                    confidence,
                    threshold,
                    current_model,
                )
                return current_text if escalated else None

            next_profile = self.router.escalate(combo_name, current_model)
            if next_profile is None:
                logger.info(
                    "[%s] 신뢰도 %.2f 낮으나 상위 티어 없음, 응답 유지 (%s)",
                    combo_name,
                    confidence,
                    current_model,
                )
                return current_text if escalated else None

            logger.info(
                "[%s] 신뢰도 %.2f < %.2f, %s -> %s 에스컬레이션",
                combo_name,
                confidence,
                threshold,
                current_model,
                next_profile.name,
            )
            try:
                loaded = self.get(next_profile.name)
                current_text = self._do_generate(loaded, prompt, **kwargs)
                current_text = self._strip_hidden_reasoning(current_text)
                current_model = next_profile.name
                escalated = True
                self.router.mark_recovered(current_model)
                if _ + 1 < self.router.cascade_max_escalations:
                    confidence = self._estimate_confidence(prompt, current_text)
            except Exception as e:  # noqa: BLE001  # 상위 티어 호출 실패 시 최선 응답 복귀
                logger.warning(
                    "[%s] 에스컬레이션 대상 %s 실패: %s",
                    combo_name,
                    next_profile.name,
                    e,
                )
                self.router.mark_failure(next_profile.name, reason=str(e))
                return current_text if escalated else None

        logger.info(
            "[%s] max 에스컬레이션 도달 (최종 %s, 신뢰도 %.2f)",
            combo_name,
            current_model,
            confidence,
        )
        return current_text

    def _estimate_confidence(self, prompt: str, response_text: str) -> float:
        heuristic_score = ModelRouter.estimate_confidence(response_text)
        if not getattr(self.router, "confidence_evaluator_enabled", False):
            return heuristic_score

        evaluator = self.router.select_confidence_evaluator()
        if evaluator is None:
            logger.warning("20B 이상 신뢰도 평가기를 사용할 수 없어 휴리스틱으로 폴백합니다.")
            return heuristic_score

        evaluation_prompt = (
            "Evaluate the answer against the question. Return exactly one line as "
            "score=0.0, where the value is from 0.0 to 1.0. Do not explain.\n"
            f"Question:\n{prompt[:12000]}\nAnswer:\n{response_text[:12000]}"
        )
        try:
            loaded = self.get(evaluator.name)
            evaluation_kwargs = {
                "max_tokens": self.router.confidence_evaluator_max_tokens,
                "temperature": 0.0,
            }
            if evaluator.provider == "ollama":
                raw_evaluation = "".join(self._do_stream_generate(loaded, evaluation_prompt, **evaluation_kwargs))
            else:
                raw_evaluation = self._do_generate(loaded, evaluation_prompt, **evaluation_kwargs)
        except (ImportError, OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("신뢰도 평가기 %s 호출 실패: %s", evaluator.name, exc)
            return heuristic_score

        score = ModelRouter.parse_confidence_score(raw_evaluation)
        if score is None:
            logger.warning("신뢰도 평가기 %s가 유효한 점수를 반환하지 않았습니다.", evaluator.name)
            return heuristic_score
        return score

    def generate(self, prompt: str, target: str, **kwargs: Any) -> str:
        """텍스트 생성 수행.

        Args:
            prompt: 입력 프롬프트
            target: 단일 모델 이름 또는 라우팅 콤보 이름
            **kwargs: max_tokens, temperature 등 생성 파라미터

        Returns:
            생성된 텍스트

        """
        collective_internal = bool(kwargs.pop("_collective_internal", False))
        if not self.router.get_combo(target) and not self._registry.model_exists(target):
            _ = self.discover_local_models()
        combo = self.router.get_combo(target)
        if combo and combo.strategy == RouteStrategy.COLLECTIVE and not collective_internal:
            return self.generate_collective(prompt, target, **kwargs)

        start_time = time.time()
        fallback_depth = 0
        used_model = None
        combo_name = None

        # 타겟이 콤보인지 확인
        try:
            if self.router.get_combo(target):
                combo_name = target
                profile = self.router.route(target)
                used_model = profile.name
                combo = self.router.get_combo(target)
                if combo is not None and used_model in combo.models:
                    fallback_depth = combo.models.index(used_model)
            else:
                profile = self.router.route_single(target)
                used_model = profile.name
        except AllModelsUnavailableError as e:
            logger.error("추론 실패 (모든 모델 비가용): %s", e)
            raise

        try:
            loaded = self.get(used_model)
            response_text = self._do_generate(loaded, prompt, **kwargs)
            response_text = self._strip_hidden_reasoning(response_text)

            # API 오류가 문자열로 삼켜진 경우(예: 모델 404) 콤보 폴백을 발동시킨다.
            # 단일 모델 타깃은 기존 동작(문자열 반환)을 유지한다.
            if combo_name and response_text.strip().lower().startswith("[api error"):
                raise RuntimeError(response_text.strip())

            latency_ms = (time.time() - start_time) * 1000
            self._record_successful_call(
                used_model,
                prompt,
                response_text,
                latency_ms,
                combo_name or "",
                fallback_depth,
            )

            escalated = self._maybe_cascade_escalate(prompt, combo_name, combo, used_model, response_text, kwargs)
            if escalated is not None:
                return escalated
            return response_text

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            error_msg = str(e)
            self._record_failed_call(
                used_model,
                error_msg,
                latency_ms,
                combo_name or "",
                fallback_depth,
            )

            # 콤보 라우팅인 경우 재귀적으로 다음 모델 시도
            if combo_name:
                logger.warning(
                    "[%s] 실패 (%s), 콤보[%s]의 다음 모델로 폴백 시도합니다...",
                    used_model,
                    error_msg,
                    combo_name,
                )
                return self.generate(prompt, combo_name, **kwargs)
            else:
                logger.error("[%s] 단일 모델 추론 실패: %s", used_model, error_msg)
            raise

    def generate_collective(self, prompt: str, target: str, **kwargs: Any) -> str:
        """여러 모델의 제안, 비판, 최종 합성을 거쳐 답변을 생성합니다."""
        cfg = self._collective_config()
        combo = self.router.get_combo(target)
        if combo:
            participants = self.router.available_model_names(target)
        else:
            participants = [target]

        min_participants = int(cfg.get("min_participants", 2))
        max_proposers = int(cfg.get("max_proposers", 3))
        max_critics = int(cfg.get("max_critics", 2))

        if len(participants) < min_participants:
            logger.warning(
                "집단지성 최소 참여 모델 부족: target=%s participants=%s",
                target,
                participants,
            )
            routed = self.router.route(target) if combo else self.router.route_single(target)
            return self.generate(
                prompt,
                routed.name,
                _collective_internal=True,
                **kwargs,
            )

        critic_combo = cfg.get("critic_combo", "critic-swarm")
        critics = self._available_combo_or_models(critic_combo, participants)
        arbiter = str(cfg.get("arbiter_combo", "supreme-court"))
        if not self.router.get_combo(arbiter) and self._registry.get_model(arbiter) is None:
            arbiter = participants[0]

        def generate_fn(model_or_combo: str, phase_prompt: str, phase_kwargs: Payload) -> str:
            response = self.generate(
                phase_prompt,
                model_or_combo,
                _collective_internal=True,
                **phase_kwargs,
            )
            if response.strip().lower().startswith("[api error"):
                self.router.mark_failure(model_or_combo, reason=response[:300])
            return response

        engine = CollectiveIntelligenceEngine(generate_fn)
        return engine.run(
            prompt,
            proposers=participants,
            critics=critics,
            arbiter=arbiter,
            max_proposers=max_proposers,
            max_critics=max_critics,
            min_participants=min_participants,
            expose_trace=bool(cfg.get("expose_trace", True)),
            generation_kwargs=kwargs,
        )

    def stream_generate(self, prompt: str, target: str, **kwargs: Any) -> Iterator[str]:
        """텍스트 생성 수행 (스트리밍)."""
        collective_internal = bool(kwargs.pop("_collective_internal", False))
        if not self.router.get_combo(target) and not self._registry.model_exists(target):
            _ = self.discover_local_models()
        combo = self.router.get_combo(target)
        if combo and combo.strategy == RouteStrategy.COLLECTIVE and not collective_internal:
            try:
                text = self.generate_collective(prompt, target, **kwargs)
            except Exception as e:
                logger.exception("Unhandled exception")
                text = f"[API Error] 집단지성 실행 중 오류가 발생했습니다: {e}"
            chunk_size = int(kwargs.get("stream_chunk_size", 256))
            for idx in range(0, len(text), chunk_size):
                yield text[idx : idx + chunk_size]
            return

        start_time = time.time()
        fallback_depth = 0
        used_model = None
        combo_name = None

        try:
            if self.router.get_combo(target):
                combo_name = target
                profile = self.router.route(target)
                used_model = profile.name
                combo = self.router.get_combo(target)
                if combo is not None and used_model in combo.models:
                    fallback_depth = combo.models.index(used_model)
            else:
                profile = self.router.route_single(target)
                used_model = profile.name
        except AllModelsUnavailableError as e:
            logger.error("추론 실패 (모든 모델 비가용): %s", e)
            raise

        try:
            loaded = self.get(used_model)

            full_text = ""
            for chunk in self._do_stream_generate(loaded, prompt, **kwargs):
                if not full_text and combo_name and chunk.strip().lower().startswith("[api error"):
                    raise RuntimeError(chunk.strip())
                full_text += chunk
                yield chunk

            # Record usage after completion
            tokens_in = len(loaded.tokenizer.encode(prompt)) if loaded.tokenizer else len(prompt) // 4
            tokens_out = len(loaded.tokenizer.encode(full_text)) if loaded.tokenizer else len(full_text) // 4
            latency_ms = (time.time() - start_time) * 1000

            self._record_successful_call(
                used_model,
                prompt,
                full_text,
                latency_ms,
                combo_name or "",
                fallback_depth,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            error_msg = str(e)

            self._record_failed_call(
                used_model,
                error_msg,
                latency_ms,
                combo_name or "",
                fallback_depth,
            )

            if combo_name:
                logger.warning(
                    "[%s] 실패 (%s), 콤보[%s]의 다음 모델로 폴백 시도합니다...",
                    used_model,
                    error_msg,
                    combo_name,
                )
                yield from self.stream_generate(prompt, combo_name, **kwargs)
            else:
                logger.error("[%s] 단일 모델 추론 실패: %s", used_model, error_msg)
                raise

    def _collective_config(self) -> Payload:
        raw = getattr(self._registry, "_raw", {})
        cfg = raw.get("collective_intelligence", {})
        return cfg if isinstance(cfg, dict) else {}

    def _self_consistency_config(self) -> dict[str, Any]:
        """amplification.self_consistency 섹션을 반환한다."""
        raw = getattr(self._registry, "_raw", {})
        amp = raw.get("amplification", {})
        if not isinstance(amp, dict):
            return {}
        cfg = amp.get("self_consistency", {})
        return cfg if isinstance(cfg, dict) else {}

    def _task_decomposition_config(self) -> dict[str, Any]:
        """amplification.task_decomposition 섹션을 반환한다."""
        raw = getattr(self._registry, "_raw", {})
        amp = raw.get("amplification", {})
        if not isinstance(amp, dict):
            return {}
        cfg = amp.get("task_decomposition", {})
        return cfg if isinstance(cfg, dict) else {}

    def _best_of_n_config(self) -> dict[str, Any]:
        """amplification.best_of_n 섹션을 반환한다."""
        raw = getattr(self._registry, "_raw", {})
        amp = raw.get("amplification", {})
        if not isinstance(amp, dict):
            return {}
        cfg = amp.get("best_of_n", {})
        return cfg if isinstance(cfg, dict) else {}

    def _resolve_bon_verifier(
        self,
        cfg: dict[str, Any],
        make_syntax_verifier,
        language: str,
        make_answer_patch_verifier,
    ):
        """best_of_n.verifier 설정에 따라 검증자를 선택한다.

        "syntax"(기본): 구문 검사. "worktree_tests": 답변 파일 블록을 git
        worktree 스냅샷에 적용해 실제 테스트 명령으로 판정한다.
        """
        mode = str(cfg.get("verifier", "syntax"))
        if mode != "worktree_tests":
            return make_syntax_verifier(language)

        import shlex as _shlex

        try:
            from antigravity_k.config import config as app_config

            project_root = getattr(app_config.paths, "project_root", ".")
        except ImportError:
            project_root = "."
        test_command = _shlex.split(str(cfg.get("test_command", "pytest -q")))
        try:
            return make_answer_patch_verifier(
                project_root,
                test_command,
                timeout_sec=float(cfg.get("test_timeout_sec", 120)),
            )
        except (TypeError, ValueError) as exc:
            logger.warning("worktree_tests 검증자 생성 실패(%s) — 구문 검사로 폴백", exc)
            return make_syntax_verifier(language)

    def generate_best_of_n(
        self,
        prompt: str,
        target: str,
        verifier_fn: Callable[[str], "VerificationOutcome"] | None = None,
        **kwargs: Any,
    ) -> str:
        """실행 검증 기반 Best-of-N 증폭으로 답변을 생성한다.

        amplification.best_of_n.enabled가 false(기본)면 일반 generate로 폴백.
        켜져 있으면 N개 후보를 샘플링해 검증자(기본: Python 구문 검사)를 통과한
        첫 답변을 선택한다. 유사도 다수결(self_consistency)보다 코딩 과제에서
        강한 신호다 — 실행 가능성이 실제 정답의 상위 집합이므로.
        """
        cfg = self._best_of_n_config()
        if not cfg.get("enabled", False):
            return self.generate(prompt, target, **kwargs)

        from antigravity_k.engine.best_of_n_verifier import (
            BestOfNVerifier,
            config_to_engine_kwargs,
            make_answer_patch_verifier,
            make_syntax_verifier,
        )

        threshold = cfg.get("complexity_threshold")
        if threshold is not None:
            from antigravity_k.engine.chain_of_verification import estimate_complexity

            try:
                if estimate_complexity(prompt) < float(threshold):
                    return self.generate(prompt, target, **kwargs)
            except (TypeError, ValueError):
                logger.warning("best_of_n.complexity_threshold 무시(잘못된 값): %r", threshold)

        language = str(cfg.get("language_hint", "python"))
        sample_kwargs = {k: v for k, v in kwargs.items() if k != "temperature"}

        if verifier_fn is None:
            verifier_fn = self._resolve_bon_verifier(cfg, make_syntax_verifier, language, make_answer_patch_verifier)

        def _sample(sample_prompt: str, **sample_overrides) -> str:
            merged = {**sample_kwargs, **sample_overrides}
            return self.generate(sample_prompt, target, **merged)

        engine_kwargs = config_to_engine_kwargs(cfg)
        if cfg.get("use_compute_budget"):
            # o-series/DeepSeek-R1 테스트타임 스케일링: 과제 복잡도 티어가
            # 샘플 수(branching factor)를 결정한다. 어려운 작업일수록 N이 커진다.
            from antigravity_k.engine.best_of_n_verifier import budget_to_n_samples
            from antigravity_k.engine.test_time_compute_scaler import TestTimeComputeScaler

            budget = TestTimeComputeScaler.evaluate_budget(prompt)
            engine_kwargs["n_samples"] = budget_to_n_samples(budget.branching_factor)

        engine = BestOfNVerifier(
            generate_fn=_sample,
            verifier_fn=verifier_fn or make_syntax_verifier(language),
            **engine_kwargs,
        )
        trace = engine.run(
            prompt,
            feedback_loop=bool(cfg.get("feedback_loop", True)),
            max_feedback_rounds=int(cfg.get("max_feedback_rounds", 1)),
        )
        if trace.skipped or not trace.selected:
            return self.generate(prompt, target, **kwargs)
        logger.info(
            "best-of-n selected (idx=%s/%s, early_exit=%s)",
            trace.selected_index,
            trace.n_candidates,
            trace.early_exit,
        )
        return trace.selected

    def generate_self_consistent(self, prompt: str, target: str, **kwargs: Any) -> str:
        """단일 모델 N샘플링 self-consistency 증폭으로 답변을 생성한다.

        amplification.self_consistency.enabled가 false(기본)면 일반 generate로 폴백.
        켜져 있으면 같은 모델을 다양한 온도로 N회 샘플링해 가장 일관된 답변을 선택한다.
        로컬 단일 모델(qwen3.6)의 추론/코드 정확도를 구조적으로 보완한다.
        """
        cfg = self._self_consistency_config()
        if not cfg.get("enabled", False):
            return self.generate(prompt, target, **kwargs)
        from antigravity_k.engine.self_consistency import (
            SelfConsistencyEngine,
            config_to_engine_kwargs,
        )

        # 샘플링엔 컨텍스트 품질을 위해 max_tokens를 보존하되 temperature는 엔진이 주입
        sample_kwargs = {k: v for k, v in kwargs.items() if k != "temperature"}

        def _sample(sample_prompt: str, **sample_overrides) -> str:
            merged = {**sample_kwargs, **sample_overrides}
            return self.generate(sample_prompt, target, **merged)

        engine = SelfConsistencyEngine(generate_fn=_sample, **config_to_engine_kwargs(cfg))
        trace = engine.run(prompt)
        if trace.skipped or not trace.selected:
            return self.generate(prompt, target, **kwargs)
        logger.info(
            "self-consistency selected (confidence=%.2f, clusters=%s)",
            trace.confidence,
            trace.cluster_sizes,
        )
        return trace.selected

    def generate_decomposed(self, prompt: str, target: str, *, force: bool = False, **kwargs: Any) -> str:
        """복잡 작업을 단계 분해 후 단계별 실행해 통합 답변을 생성한다.

        amplification.task_decomposition.enabled가 false면
        generate_self_consistent로 폴백한다. force=True는 revision 실패 후
        승격 호출처럼 초기 비용 게이트를 이미 통과한 경로에서만 분해를
        강제한다. 분해는 is_complex_task 게이트를 통과한 멀티스텝 작업에만
        적용되며, 단순 작업은 즉시 폴백해 호출 비용을 낭비하지 않는다.
        """
        cfg = self._task_decomposition_config()
        if not cfg.get("enabled", False) and not force:
            return self.generate_self_consistent(prompt, target, **kwargs)
        from antigravity_k.engine.llm_task_decomposer import LlmTaskDecomposer

        def _gen(p: str) -> str:
            return self.generate(p, target, **kwargs)

        decomposer = LlmTaskDecomposer(
            generate_fn=_gen,
            min_steps=int(cfg.get("min_steps", 2) or 2),
            max_steps=int(cfg.get("max_steps", 6) or 6),
        )
        dec = decomposer.decompose(prompt)
        if dec.skipped or not dec.steps:
            return self.generate_self_consistent(prompt, target, **kwargs)

        parts: list[str] = []
        completed: list[str] = []
        for idx, step in enumerate(dec.steps, start=1):
            out = _gen(decomposer.step_prompt(step, prompt, completed))
            completed.append(out)
            parts.append(f"## {idx}단계: {step}\n\n{out}".rstrip())
        logger.info(
            "task decomposition applied (steps=%d, model=%s)",
            len(dec.steps),
            target,
        )
        return "\n\n---\n\n".join(parts)

    def _available_combo_or_models(
        self,
        combo_name: str,
        fallback_models: list[str],
    ) -> list[str]:
        if self.router.get_combo(combo_name):
            try:
                available = self.router.available_model_names(combo_name)
                if available:
                    return available
            except Exception:
                logger.exception("비판 콤보 조회 실패: %s", combo_name)
        return fallback_models

    @staticmethod
    def _uses_anthropic_direct(loaded: LoadedModel) -> bool:
        """Anthropic SDK 직접 호출 경로를 사용할지 결정합니다.

        Anthropic 직접 호출은 다음 조건을 *모두* 만족할 때만 활성화됩니다:
          1. 모델 이름/레포가 Claude/Anthropic 계열이고, **OpenRouter 경유가 아닌** 경우
          2. config.yaml의 api_keys.anthropic 에 유효한 키가 설정된 경우

        OpenRouter(api_base에 'openrouter' 포함)를 통한 Claude 호출은
        OpenAI 호환 엔드포인트로 처리되어야 합니다 (Anthropic SDK 우회 금지).
        """
        from ..config import config

        name = (loaded.profile.name or "").lower()
        repo = (loaded.profile.repo or "").lower()
        is_claude_family = name.startswith("claude") or "anthropic/claude" in repo

        if not is_claude_family:
            return False

        # OpenRouter를 경유하는 Claude는 Anthropic 직접 호출에서 제외
        if "openrouter" in config.model.api_base.lower():
            return False

        # 유효한 Anthropic API 키가 있을 때만 직접 호출
        raw = getattr(config, "_raw", {}) or {}
        api_key = raw.get("api_keys", {}).get("anthropic", "") if isinstance(raw, dict) else ""
        return bool(api_key) and api_key != "sk-ant-your-key-here"

    @staticmethod
    def _is_openrouter() -> bool:
        """현재 구성이 OpenRouter를 가리키는지 판단합니다.

        api_engine이 'openrouter'이거나 api_base 호스트에 'openrouter'가 포함된 경우 True.
        URL 문자열 단독 판단의 취약점(포트/경로 변형)을 보완하기 위해 engine 값도 함께 검사합니다.
        """
        from ..config import config

        engine = (config.model.api_engine or "").lower()
        base = (config.model.api_base or "").lower()
        return engine == "openrouter" or "openrouter" in base

    @staticmethod
    def _ollama_native_base(api_base: str) -> str:
        """Ollama Native API(/api/chat)용 베이스 URL을 정규화합니다.

        OpenAI 호환 접미사(/v1)가 붙은 경우 이를 제거하여 Ollama Native 엔드포인트로 변환합니다.
        예: http://localhost:11434/v1 → http://localhost:11434
        """
        base = (api_base or "").rstrip("/")
        # /v1 (또는 /v2 등) 버전 접미사 제거
        import re

        base = re.sub(r"/v\d+$", "", base)
        return base

    def _do_generate(self, loaded: LoadedModel, prompt: str, **kwargs: Any) -> str:
        """내부 텍스트 생성 로직 — per-model provider 위임 (작업 2).

        멀티 프로바이더 지원: loaded.profile.provider에 따라 적절한 프로바이더로 위임.
        Anthropic 직접 SDK 호출은 _uses_anthropic_direct가 True일 때만 유지.
        """
        # Anthropic 직접 SDK 호출 (OpenRouter 경유가 아닌 Claude 전용)
        if self._uses_anthropic_direct(loaded):
            result = ""
            for chunk in self._do_anthropic_stream(loaded, prompt, **kwargs):
                result += chunk
            return result

        # per-model provider 기반 위임 (ollama/openrouter/nim/mlx)
        provider = self._get_provider(loaded)
        if provider is not None:
            provider_kwargs = self._provider_kwargs(loaded, kwargs)
            return provider.generate(loaded, prompt, **provider_kwargs)

        # 폴백: 레거시 인라인 경로 (provider 결정 실패 시)
        return self._do_ollama_generate(loaded, prompt, **kwargs)

    def _do_stream_generate(self, loaded: LoadedModel, prompt: str, **kwargs: Any) -> Iterator[str]:
        """내부 텍스트 생성 로직 (스트리밍) — per-model provider 위임 (작업 2)."""
        if self._uses_anthropic_direct(loaded):
            yield from self._do_anthropic_stream(loaded, prompt, **kwargs)
            return

        provider = self._get_provider(loaded)
        if provider is not None:
            provider_kwargs = self._provider_kwargs(loaded, kwargs)
            yield from provider.stream_generate(loaded, prompt, **provider_kwargs)
            return

        # 폴백: 레거시 인라인 경로
        yield from self._do_ollama_stream(loaded, prompt, **kwargs)

    def _provider_kwargs(self, loaded: LoadedModel, kwargs: dict[str, Any]) -> dict[str, Any]:
        if "execution_plan" in kwargs:
            return kwargs
        plan = self.long_context_plan(loaded.profile.name)
        if plan is None:
            return kwargs
        return {**kwargs, "execution_plan": plan}

    def _trace_llm_call(
        self,
        model: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        latency_ms: float = 0.0,
        success: bool = True,
        error: str = "",
        combo: str | None = None,
        fallback_depth: int = 0,
    ) -> None:
        """LLM 호출을 tracing span으로 기록합니다 (작업 E).

        ModelManager의 generate/stream_generate에서 호출됩니다.
        tracing 모듈이 없거나 실패해도 메인 플로우에 영향을 주지 않습니다.
        """
        try:
            from .tracing import get_tracer

            tracer = get_tracer()
            # 컨텍스트 매니저 대신 직접 Span 생성 후 finalize (이미 측정 완료된 값)
            from .tracing import Span

            attributes: dict[str, Any] = {
                "model": model,
                "combo": combo or "",
                "fallback_depth": fallback_depth,
            }
            profile = self._registry.get_model(model)
            if profile is not None:
                attributes.update(
                    {
                        "provider": profile.provider,
                        "is_local": profile.is_local,
                        "parameter_count_b": profile.effective_parameter_count_b,
                    }
                )
                capability = self.provider_capability(model)
                if capability is not None:
                    attributes.update(
                        {
                            "native_tool_calling": capability["native_tool_calling"],
                            "provider_runtime_status": capability["runtime_status"],
                        }
                    )
            span = Span(
                name=f"llm:{model}",
                span_type="llm_inference",
                start_time=time.time() - (latency_ms / 1000),
                end_time=time.time(),
                duration_ms=latency_ms,
                token_count=tokens_in + tokens_out,
                status="ok" if success else "error",
                error_message=error[:200] if error else "",
                attributes=attributes,
                input_data={"tokens_in": tokens_in} if tokens_in else {},
                output_data={"tokens_out": tokens_out} if tokens_out else {},
            )
            # 활성 trace가 있으면 span 추가
            if tracer._active_trace:
                tracer._active_trace.add_span(span)
        except Exception:
            logger.debug("Tracing span add failed (non-critical)", exc_info=True)

    def _get_provider(self, loaded: LoadedModel) -> BaseInferenceProvider | None:
        """loaded.profile.provider 기반으로 추론 프로바이더를 반환합니다.

        provider가 명시적이지 않으면(빈 문자열) None을 반환하여 레거시 경로로 폴백.
        어댑터 위임은 inference_providers.py의 get_inference_provider를 사용.
        """
        profile = loaded.profile
        provider_name = (getattr(profile, "provider", "") or "").lower()

        # provider가 명시된 경우에만 위임 (빈 값이면 레거시 _do_ollama_stream 사용)
        if not provider_name:
            return None

        try:
            from .provider_adapters.inference_providers import get_inference_provider

            return get_inference_provider(loaded)
        except Exception:
            logger.debug("provider adapter 로드 실패 — 레거시 경로로 폴백", exc_info=True)
            return None

    def _do_ollama_generate(self, loaded: LoadedModel, prompt: str, **kwargs) -> str:
        """OpenAI 호환 HTTP API (LM Studio, Ollama 등)를 통한 생성 로직."""
        import json
        import urllib.request

        from ..config import config

        base_url = config.model.api_base.rstrip("/")
        url = f"{base_url}/chat/completions"
        api_key = config.model.api_key

        # ─── 적응형 샘플링 프로파일 적용 ───
        task_type = kwargs.get("task_type", "GENERAL")
        profile = SAMPLING_PROFILES.get(task_type, SAMPLING_PROFILES["GENERAL"])

        # kwargs에 명시적으로 지정된 값이 있으면 그것을 우선 사용 (하위 호환성)
        base_temp = kwargs.get("temperature", profile.temperature)

        # DINKIssTyle-AI-BBS: Randomizer & Temperature Boost
        boost = self.router.get_temperature_boost(loaded.profile.name)
        temperature = min(1.0, base_temp + boost)

        min_p = kwargs.get("min_p", profile.min_p)
        repeat_penalty = kwargs.get("repeat_penalty", profile.repeat_penalty)

        data = {
            "model": loaded.profile.name,
            "stream": False,
            "temperature": temperature,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "repeat_penalty": repeat_penalty,
            "options": {
                "min_p": min_p,
            },
        }

        # ─── Ollama Structured Output (JSON Schema 강제) ───
        json_schema = kwargs.get("response_format")
        if json_schema:
            data["format"] = json_schema

        if "raw_messages" in kwargs:
            sys_msg = kwargs.get("system_prompt", "")
            if sys_msg:
                api_msgs = [{"role": "system", "content": sys_msg}] + kwargs["raw_messages"]
            else:
                api_msgs = kwargs["raw_messages"]
            data["messages"] = api_msgs
        else:
            data["messages"] = [{"role": "user", "content": prompt}]
        data["messages"] = self._suppress_model_thinking(
            loaded.profile.name,
            data["messages"],
        )

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        # OpenRouter 전용 헤더 (식별용)
        if self._is_openrouter():
            headers["HTTP-Referer"] = "https://github.com/sumkbs-kbs/antigravity-k"
            headers["X-Title"] = "Antigravity-K"

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers=headers,
        )
        try:
            with safe_urlopen(req, timeout=300) as response:
                result = json.loads(response.read().decode("utf-8"))
                message = result["choices"][0]["message"]
                content = message.get("content", "")
                if not content and message.get("thinking"):
                    raise RuntimeError("model returned hidden thinking without final content")
                logger.debug("Ollama response content (%s chars): %s", len(content), content[:200])
                return content
        except Exception as e:
            logger.exception("Local API generation failed")
            return f"[API Error for {loaded.profile.name}] {e}"

    @staticmethod
    def _suppress_model_thinking(model_name: str, messages: list[Message]) -> list[Message]:
        """Inject direct-answer mode for models that otherwise emit thinking-only output."""
        if "qwen3" not in model_name.lower():
            return messages

        directive = (
            "/no_think\nAnswer directly. Do not output hidden reasoning, thinking traces, <think>, or <thought> blocks."
        )
        prepared = [dict(message) for message in messages]
        if prepared and prepared[0].get("role") == "system":
            content = str(prepared[0].get("content", ""))
            if "/no_think" not in content:
                prepared[0]["content"] = f"{directive}\n{content}".strip()
            return prepared

        return [{"role": "system", "content": directive}, *prepared]

    @staticmethod
    def _strip_hidden_reasoning(text: str) -> str:
        """Remove common hidden-reasoning blocks from non-streaming model output."""
        import re

        cleaned = re.sub(
            r"<(think|thought)\b[^>]*>.*?</\1>",
            "",
            text or "",
            flags=re.IGNORECASE | re.DOTALL,
        )
        cleaned = re.sub(
            r"---\s*Thinking Process\s*---.*?---\s*End of Thinking\*?\s*---",
            "",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        return cleaned.strip()

    def _apply_dynamic_inference_config(self, loaded_profile, prompt_or_messages, kwargs):
        import hashlib

        model_name = loaded_profile.name
        thinking_config = None
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 8192)

        if ":" in model_name:
            base_model, spec = model_name.split(":", 1)
            budget = None

            if spec.isdigit():
                budget = max(int(spec), 1024)
            else:
                ratios = {"high": 0.8, "medium": 0.5, "low": 0.2}
                ratio = ratios.get(spec.lower())
                if ratio:
                    budget = max(int(max_tokens * ratio), 1024)

            if budget:
                thinking_config = {"type": "enabled", "budget_tokens": budget}
                temperature = 1.0  # Required for thinking mode
                model_name = base_model  # Only strip if it's a thinking config spec

        if isinstance(prompt_or_messages, list) and len(prompt_or_messages) > 0:
            first_user_text = str(prompt_or_messages[0].get("content", ""))
        else:
            first_user_text = str(prompt_or_messages)

        fingerprint_input = f"antigravity_k_59cf53e54c78_{first_user_text[:30]}"
        fingerprint = hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest()[:6]
        attribution = f"\nx-antigravity-k-agent: id={fingerprint}; cch=00000;"

        return model_name, temperature, thinking_config, attribution

    def _do_anthropic_stream(self, loaded: LoadedModel, prompt: str, **kwargs):
        anthropic = import_module("anthropic")

        from ..config import config

        api_key = config._raw.get("api_keys", {}).get("anthropic", "")
        if not api_key or api_key == "sk-ant-your-key-here":
            yield "[Error] Anthropic API Key not found in config.yaml"
            return

        client = anthropic.Anthropic(api_key=api_key)

        system_prompt = kwargs.get("system_prompt", "")
        raw_messages = kwargs.get("raw_messages", [{"role": "user", "content": prompt}])

        model_name, temperature, thinking_config, attribution = self._apply_dynamic_inference_config(
            loaded.profile, raw_messages, kwargs
        )

        request_params = self._build_anthropic_request_params(
            raw_messages,
            system_prompt,
            attribution,
            model_name,
            temperature,
            thinking_config,
            kwargs,
        )

        try:
            with client.messages.stream(**request_params) as stream:
                for text in stream.text_stream:
                    yield text
        except Exception as e:
            logger.exception("Anthropic API generation failed")
            yield f"[API Error for {model_name}] {e}"

    def _build_anthropic_request_params(
        self,
        raw_messages: list[Message],
        system_prompt: str,
        attribution: str,
        model_name: str,
        temperature: float,
        thinking_config,
        kwargs: Payload,
    ) -> Payload:
        """Format messages, manage cache_control blocks, and build API request params.

        Extracted from _do_anthropic_stream for testability.
        """
        # Format messages for Anthropic (only user/assistant roles).
        anthropic_msgs = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in raw_messages
            if msg["role"] in ("user", "assistant")
        ]

        # Intelligent Context Cache: Anthropic allows max 4 cache_control blocks.
        cache_blocks = []
        system_blocks = []
        if system_prompt:
            system_blocks.append(
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            )
            cache_blocks.append(system_blocks[0])

        for msg in anthropic_msgs:
            if isinstance(msg["content"], list):
                for block in msg["content"]:
                    if isinstance(block, dict) and "cache_control" in block:
                        cache_blocks.append(block)

        if len(cache_blocks) > 4:
            keep_first = cache_blocks[0]
            keep_last = cache_blocks[-3:]
            to_keep = {id(keep_first)} | {id(b) for b in keep_last}
            for block in cache_blocks:
                if id(block) not in to_keep:
                    block.pop("cache_control", None)

        # Agent Footprint & Fingerprinting.
        if system_blocks:
            system_blocks[0]["text"] += attribution  # type: ignore[operator]
        else:
            system_blocks.append(
                {
                    "type": "text",
                    "text": attribution,
                    "cache_control": {"type": "ephemeral"},
                }
            )

        request_params = {
            "max_tokens": kwargs.get("max_tokens", 8192),
            "system": system_blocks if system_blocks else system_prompt,
            "messages": anthropic_msgs,
            "model": model_name,
            "temperature": temperature,
        }
        if thinking_config:
            request_params["thinking"] = thinking_config
        return request_params

    def _prepare_stream_messages(self, loaded: LoadedModel, prompt: str, kwargs: Payload) -> list[Message]:
        """Build and normalize the message list for an Ollama/OpenRouter stream request."""
        raw_messages = kwargs.get("raw_messages")
        if isinstance(raw_messages, list):
            api_msgs = [dict(message) for message in raw_messages if isinstance(message, dict)]
            sys_msg = str(kwargs.get("system_prompt", ""))
            if sys_msg:
                api_msgs.insert(0, {"role": "system", "content": sys_msg})
        else:
            api_msgs = [{"role": "user", "content": prompt}]

        # Normalize: ensure content is a string (flatten list-of-parts).
        normalized: list[Message] = []
        for msg in api_msgs:
            content = msg.get("content", "")
            if isinstance(content, list):
                parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        parts.append(part.get("text", ""))
                    elif isinstance(part, str):
                        parts.append(part)
                content = " ".join(parts)
            normalized.append({**msg, "content": content})

        normalized = self._suppress_model_thinking(loaded.profile.name, normalized)
        _, _, _, attribution = self._apply_dynamic_inference_config(loaded.profile, normalized, kwargs)

        if normalized and isinstance(normalized[0].get("content"), str):
            normalized = list(normalized)
            normalized[0] = {**normalized[0], "content": normalized[0]["content"] + f"\n{attribution}"}

        return normalized

    def _build_stream_request(self, loaded: LoadedModel, api_msgs: list[Message], kwargs: Payload, is_openrouter: bool):
        """Construct the HTTP request (URL + body + headers) for streaming.

        Returns ``(request, model_name)``.
        """
        import json
        import urllib.request

        from ..config import config

        base_url = config.model.api_base.rstrip("/")
        api_key = config.model.api_key

        model_name, temperature, _, _ = self._apply_dynamic_inference_config(loaded.profile, api_msgs, kwargs)

        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        if is_openrouter:
            headers["HTTP-Referer"] = "https://github.com/sumkbs-kbs/antigravity-k"
            headers["X-Title"] = "Antigravity-K"
            url = f"{base_url}/chat/completions"
            data = {
                "model": model_name,
                "stream": True,
                "temperature": temperature,
                "max_tokens": kwargs.get("max_tokens", 4096),
                "messages": api_msgs,
            }
        else:
            native_base = self._ollama_native_base(config.model.api_base)
            url = f"{native_base}/api/chat"
            data = {
                "model": model_name,
                "stream": True,
                "keep_alive": "30m",
                "options": {
                    "num_ctx": 32768,
                    "num_predict": kwargs.get("max_tokens", 4096),
                    "temperature": temperature,
                    "repeat_penalty": 1.3,
                },
                "messages": api_msgs,
            }

        req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers)
        return req, model_name

    def _do_ollama_stream(self, loaded: LoadedModel, prompt: str, **kwargs):
        """스트리밍 생성 로직.

        Ollama Native API(/api/chat)와 OpenAI 호환 SSE(/v1/chat/completions)를
        api_base에 따라 자동 선택합니다.
        """
        import json
        from urllib.error import HTTPError

        is_openrouter = self._is_openrouter()
        api_msgs = self._prepare_stream_messages(loaded, prompt, kwargs)
        req, model_name = self._build_stream_request(loaded, api_msgs, kwargs, is_openrouter)

        try:
            if is_openrouter:
                # OpenAI 호환 SSE 스트리밍 파싱 (data: {...} \n\n)
                with safe_urlopen(req, timeout=300) as response:
                    buffer = ""
                    for byte_chunk in response:
                        buffer += byte_chunk.decode("utf-8")
                        while "\n\n" in buffer:
                            line, buffer = buffer.split("\n\n", 1)
                            line = line.strip()
                            if not line or not line.startswith("data: "):
                                continue
                            payload = line[6:].strip()
                            if payload == "[DONE]":
                                break
                            try:
                                chunk = json.loads(payload)
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue
            else:
                # Ollama Native API 스트리밍 파싱 (줄 단위 JSON)
                with safe_urlopen(req, timeout=300) as response:
                    for raw_line in response:
                        decoded_line = raw_line.decode("utf-8").strip()
                        if not decoded_line:
                            continue
                        try:
                            chunk = json.loads(decoded_line)
                            if "message" in chunk:
                                msg = chunk["message"]
                                if "content" in msg and msg["content"]:
                                    yield msg["content"]
                        except json.JSONDecodeError:
                            continue
        except HTTPError as e:
            try:
                error_body = e.read().decode("utf-8")
            except Exception:
                logger.exception("Unhandled exception")
                error_body = ""
            logger.error("Local API stream failed with HTTPError: %s - %s", e, error_body)
            yield f"[API Error for {loaded.profile.name}] {e} - {error_body}"
        except Exception as e:
            logger.exception("Local API stream failed")
            yield f"[API Error for {loaded.profile.name}] {e}"

    # ─── 상태 조회 ───────────────────────────────────────────────────

    def status(self) -> Payload:
        """현재 로드 상태 반환."""
        loaded_models = []
        total_memory = 0.0
        provider_capabilities = self.provider_capabilities()

        for name, loaded in self._loaded.items():
            total_memory += loaded.actual_memory_gb
            loaded_models.append(
                {
                    "name": name,
                    "role": loaded.profile.role,
                    "memory_gb": loaded.actual_memory_gb,
                    "loaded_at": loaded.loaded_at,
                    "last_used_at": loaded.last_used_at,
                },
            )

        return {
            "loaded_models": loaded_models,
            "total_loaded_gb": round(total_memory, 1),
            "max_allowed_gb": self._mem_config.max_loaded_gb,
            "available_gb": round(self._mem_config.max_loaded_gb - total_memory, 1),
            "auto_unload": self._mem_config.auto_unload,
            "provider_capabilities": provider_capabilities,
            "routing": self.router.status(),
        }

    def provider_capabilities(self, *, refresh: bool = False) -> dict[str, ProviderCapability]:
        capabilities: dict[str, ProviderCapability] = {}
        for profile in self._registry.list_models():
            capabilities[profile.name] = self._provider_capability_for_profile(profile, refresh=refresh)
        return capabilities

    def long_context_plan(self, name: str, *, refresh: bool = False) -> LongContextExecutionPlan | None:
        capability = self.provider_capability(name, refresh=refresh)
        if capability is None:
            return None
        plan = capability.get("long_context_plan")
        if plan is not None:
            return plan
        profile = self._registry.get_model(name)
        if profile is None:
            return None
        budget = context_budget_for_model(getattr(self._registry, "_raw", {}), profile.name)
        return build_long_context_plan(capability.get("long_context"), budget)

    def provider_capability(self, name: str, *, refresh: bool = False) -> ProviderCapability | None:
        profile = self._registry.get_model(name)
        if profile is None:
            return None
        return self._provider_capability_for_profile(profile, refresh=refresh)

    def _provider_capability_for_profile(self, profile: ModelProfile, *, refresh: bool) -> ProviderCapability:
        capability = self._capability_probe.observe(profile, refresh=refresh)
        budget = context_budget_for_model(getattr(self._registry, "_raw", {}), profile.name)
        capability["long_context_plan"] = build_long_context_plan(capability.get("long_context"), budget)
        self.router.set_provider_capability(profile.name, capability)
        return capability

    def loaded_names(self) -> list[str]:
        """현재 로드된 모델 이름 목록."""
        return list(self._loaded.keys())

    def get_model_info(self) -> Payload:
        """모델 정보를 반환합니다 (status()의 별칭 — slash_commands/self_capability 호환).

        Returns:
            status()와 동일한 구조의 모델 상태 dict.
        """
        return self.status()

    def is_loaded(self, name: str) -> bool:
        """Check if loaded.

        Args:
            name (str): str name.

        Returns:
            bool: The bool result.

        """
        from ..config import config

        if name in self._loaded:
            return True
        profile = self._registry.get_model(name)
        if profile and getattr(profile, "provider", "") in {"mlx", "lmstudio", "lm_studio"}:
            return True
        # Check Ollama active models dynamically (Ollama 엔진일 때만 — OpenRouter는 원격이므로 로컬 tags 조회 무의미)
        if (config.model.api_engine or "").lower() == "ollama":
            if profile and getattr(profile, "backend", "ollama") == "ollama":
                try:
                    import json
                    import urllib.request

                    native_base = self._ollama_native_base(config.model.api_base)
                    req = urllib.request.Request(f"{native_base}/api/tags")
                    with safe_urlopen(req, timeout=2) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        for m in data.get("models", []):
                            m_name = m.get("name", "")
                            # e.g. "deepseek-r1:70b" or "deepseek-r1" match
                            if m_name == name or m_name.startswith(name + ":") or name.startswith(m_name + ":"):
                                return True
                except Exception:
                    logger.warning("예외 발생 (silent swallow 제거)", exc_info=True)
        return False

    # ─── 내부 메서드 ─────────────────────────────────────────────────

    def _ensure_memory(self, needed_gb: float) -> None:
        """필요한 메모리 확보 (MemoryPolicy에 위임)."""
        self._memory_policy.ensure_memory(
            needed_gb=needed_gb,
            loaded_models=self._loaded,
            unload_fn=self.unload,
        )

    def _load_mlx_model(self, profile: ModelProfile) -> tuple[Any, Any]:
        """MLX 모델 실제 로드 (Mac 전용, Windows에서는 더미 반환)."""
        import platform

        if profile.provider == "transformers" or (
            profile.provider == "unsloth"
            and (
                (Path(profile.repo) / "adapter_config.json").is_file()
                or ((Path(profile.repo) / "config.json").is_file() and any(Path(profile.repo).glob("*.safetensors")))
            )
        ):
            return self._load_transformers_model(profile)

        if profile.provider != "mlx" or platform.system() != "Darwin":
            logger.info("[%s] 외부 API 어댑터 모드를 사용합니다.", profile.name)
            return _OllamaModel(profile.name), _OllamaTokenizer(profile.name)

        if profile.role == "embedding":
            return self._load_embedding_model(profile)

        try:
            load = import_module("mlx_lm").__dict__["load"]

            model, tokenizer, *_ = load(profile.repo)
            return model, tokenizer
        except ImportError:
            if profile.provider == "mlx":
                raise RuntimeError("mlx-lm is required for direct MLX inference; install the mlx extra first")
            logger.warning("mlx_lm 미설치. Ollama 어댑터 반환.")
            return _OllamaModel(profile.name), _OllamaTokenizer(profile.name)

    def _load_transformers_model(self, profile: ModelProfile) -> tuple[Any, Any]:
        model_path = Path(profile.repo)
        load_path = profile.repo
        adapter_config_path = model_path / "adapter_config.json"
        adapter_base = ""
        if adapter_config_path.is_file():
            try:
                raw_config = json.loads(adapter_config_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, ValueError) as exc:
                raise RuntimeError(f"Unsloth adapter 설정을 읽지 못했습니다: {adapter_config_path}") from exc
            if isinstance(raw_config, dict) and isinstance(raw_config.get("base_model_name_or_path"), str):
                adapter_base = raw_config["base_model_name_or_path"]
            if not adapter_base:
                raise RuntimeError("Unsloth adapter에 base_model_name_or_path가 없습니다.")
            load_path = adapter_base

        try:
            transformers = import_module("transformers")
            tokenizer = transformers.AutoTokenizer.from_pretrained(load_path, local_files_only=True)
            model = transformers.AutoModelForCausalLM.from_pretrained(
                load_path,
                torch_dtype="auto",
                local_files_only=True,
                use_safetensors=True,
            )
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            raise RuntimeError(
                f"Transformers 모델 '{load_path}'을 직접 로드하지 못했습니다. "
                "transformers와 torch가 설치되어 있는지 확인하세요."
            ) from exc

        if adapter_base:
            try:
                peft = import_module("peft")
                model = peft.PeftModel.from_pretrained(model, profile.repo, local_files_only=True)
            except (ImportError, OSError, RuntimeError, ValueError) as exc:
                raise RuntimeError("Unsloth LoRA를 적용하려면 peft가 필요합니다.") from exc
        return model, tokenizer

    def _load_embedding_model(self, profile: ModelProfile) -> tuple[Any, Any]:
        """임베딩 모델 로드 (Mac 전용)."""
        try:
            SentenceTransformer = import_module("sentence_transformers").__dict__["SentenceTransformer"]

            model = SentenceTransformer(profile.repo)
            return model, None
        except (ImportError, Exception):
            logger.exception("임베딩 모델 로드 실패 (%s). 더미 임베딩 반환.")
            return _OllamaModel(profile.name), None


# ─── Ollama 어댑터 (Windows/Linux/비-Mac 개발용) ──────────────────────────────────────
# Dev shim classes (_OllamaModel, _OllamaTokenizer) moved to
# provider_adapters/dev_shims.py. Re-imported here so all existing references
# (including `type(loaded.model).__name__` string checks in inference_providers)
# keep resolving identically.
from antigravity_k.engine.provider_adapters.dev_shims import (  # noqa: E402,F401
    _OllamaModel,
    _OllamaTokenizer,
)
