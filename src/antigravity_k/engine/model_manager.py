"""Antigravity-K: 모델 매니저.

런타임 모델 로드/언로드/핫스왑 + 메모리 자동 관리
"""

from __future__ import annotations

import gc
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from .collective_intelligence import CollectiveIntelligenceEngine
from .memory_policy import MemoryPolicy
from .model_registry import ModelProfile, ModelRegistry
from .model_router import AllModelsUnavailableError, ModelRouter, RouteStrategy
from .usage_tracker import UsageTracker

logger = logging.getLogger("antigravity_k.model_manager")


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

    def reload(self) -> None:
        """설정 파일 변경 후 레지스트리 및 라우터를 핫 리로드합니다."""
        self._registry.reload()
        self.router.reload()
        self._mem_config = self._registry.memory_config
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
        gc.collect()

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
            name for name, loaded in self._loaded.items() if loaded.profile.role == target_role and name != new_name
        ]
        for name in to_unload:
            logger.info("[%s] → [%s] 교체를 위해 언로드", name, new_name)
            self.unload(name)

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
            if loaded.profile.role == role:
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
        if isinstance(agent_models, dict):
            for key in (role_name, role_name.upper(), role_name.lower(), "default"):
                value = agent_models.get(key)
                if isinstance(value, str) and value:
                    return value

        default = self._registry.get_default(default_role)
        if default:
            return default.name
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
                    self.load(name)
                    return True
                except MemoryError:
                    return False
            return False

        try:
            self.load(name)
            return True
        except Exception:
            logger.exception("Prefetch 실패 [%s]", name)
            return False

    # ─── 추론 API (9Router 연동) ─────────────────────────────────────

    def generate(self, prompt: str, target: str, **kwargs) -> str:
        """텍스트 생성 수행.

        Args:
            prompt: 입력 프롬프트
            target: 단일 모델 이름 또는 라우팅 콤보 이름
            **kwargs: max_tokens, temperature 등 생성 파라미터

        Returns:
            생성된 텍스트

        """
        collective_internal = bool(kwargs.pop("_collective_internal", False))
        combo = self.router.get_combo(target)
        if combo and combo.strategy == RouteStrategy.COLLECTIVE and not collective_internal:
            return self.generate_collective(prompt, target, **kwargs)

        start_time = time.time()
        fallback_depth = 0
        used_model = None
        combo_name = None

        # 타겟이 콤보인지 확인
        try:
            # 콤보 라우팅 시도
            if self.router.get_combo(target):
                combo_name = target
                # 라우터에서 사용 가능한 모델 프로필 가져오기 (폴백/라운드로빈 적용)
                profile = self.router.route(target)
                used_model = profile.name

                # 라우팅된 모델의 fallback_depth (라우터 내부에서 인덱스로 추적하려면 라우터를 직접 사용해야 하므로 대략적으로 계산하거나 생략 가능.  # noqa: E501
                # ModelRouter의 combo를 확인하여 인덱스를 fallback depth로 추정)
                combo = self.router.get_combo(target)
                if combo is not None and used_model in combo.models:
                    fallback_depth = combo.models.index(used_model)
            else:
                # 단일 모델 직접 지정인 경우
                profile = self.router.route_single(target)
                used_model = profile.name
        except AllModelsUnavailableError as e:
            logger.error("추론 실패 (모든 모델 비가용): %s", e)
            raise

        try:
            # 모델 로드 (메모리 관리 포함)
            loaded = self.get(used_model)

            # 실제 추론 수행 (Mac MLX 또는 Windows 더미)
            response_text = self._do_generate(loaded, prompt, **kwargs)
            response_text = self._strip_hidden_reasoning(response_text)

            # 토큰 수 대략적 계산 (실제로는 토크나이저 사용)
            tokens_in = len(loaded.tokenizer.encode(prompt)) if loaded.tokenizer else len(prompt) // 4
            tokens_out = len(loaded.tokenizer.encode(response_text)) if loaded.tokenizer else len(response_text) // 4
            latency_ms = (time.time() - start_time) * 1000

            # 사용량 기록 (성공)
            self.tracker.record(
                model_name=used_model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=latency_ms,
                success=True,
                combo_name=combo_name or "",
                fallback_depth=fallback_depth,
            )

            # Tracing: LLM 추론 span 기록 (작업 E — 관측가능성)
            self._trace_llm_call(
                model=used_model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=latency_ms,
                success=True,
                combo=combo_name,
            )

            # 콤보 라우팅 중 성공했으므로 해당 모델을 복구 상태로 마킹 (UnavailabilityTracker)
            self.router.mark_recovered(used_model)

            return response_text

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            error_msg = str(e)

            # 사용량 기록 (실패)
            self.tracker.record(
                model_name=used_model,
                latency_ms=latency_ms,
                success=False,
                error=error_msg,
                combo_name=combo_name or "",
                fallback_depth=fallback_depth,
            )

            # Tracing: 실패 span 기록
            self._trace_llm_call(
                model=used_model,
                latency_ms=latency_ms,
                success=False,
                error=error_msg,
                combo=combo_name,
            )

            # 라우터에 실패 보고 (쿨다운 적용)
            self.router.mark_failure(used_model, reason=error_msg)

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

    def generate_collective(self, prompt: str, target: str, **kwargs) -> str:
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

        def generate_fn(model_or_combo: str, phase_prompt: str, phase_kwargs: dict) -> str:
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

    def stream_generate(self, prompt: str, target: str, **kwargs):
        """텍스트 생성 수행 (스트리밍)."""
        collective_internal = bool(kwargs.pop("_collective_internal", False))
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
                full_text += chunk
                yield chunk

            # Record usage after completion
            tokens_in = len(loaded.tokenizer.encode(prompt)) if loaded.tokenizer else len(prompt) // 4
            tokens_out = len(loaded.tokenizer.encode(full_text)) if loaded.tokenizer else len(full_text) // 4
            latency_ms = (time.time() - start_time) * 1000

            self.tracker.record(
                model_name=used_model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=latency_ms,
                success=True,
                combo_name=combo_name or "",
                fallback_depth=fallback_depth,
            )
            self.router.mark_recovered(used_model)

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            error_msg = str(e)

            self.tracker.record(
                model_name=used_model,
                latency_ms=latency_ms,
                success=False,
                error=error_msg,
                combo_name=combo_name or "",
                fallback_depth=fallback_depth,
            )
            self.router.mark_failure(used_model, reason=error_msg)

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

    def _collective_config(self) -> dict:
        raw = getattr(self._registry, "_raw", {})
        cfg = raw.get("collective_intelligence", {})
        return cfg if isinstance(cfg, dict) else {}

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

    def _do_generate(self, loaded: LoadedModel, prompt: str, **kwargs) -> str:
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
            return provider.generate(loaded, prompt, **kwargs)

        # 폴백: 레거시 인라인 경로 (provider 결정 실패 시)
        return self._do_ollama_generate(loaded, prompt, **kwargs)

    def _do_stream_generate(self, loaded: LoadedModel, prompt: str, **kwargs):
        """내부 텍스트 생성 로직 (스트리밍) — per-model provider 위임 (작업 2)."""
        if self._uses_anthropic_direct(loaded):
            yield from self._do_anthropic_stream(loaded, prompt, **kwargs)
            return

        provider = self._get_provider(loaded)
        if provider is not None:
            yield from provider.stream_generate(loaded, prompt, **kwargs)
            return

        # 폴백: 레거시 인라인 경로
        yield from self._do_ollama_stream(loaded, prompt, **kwargs)

    def _trace_llm_call(
        self,
        model: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        latency_ms: float = 0.0,
        success: bool = True,
        error: str = "",
        combo: str | None = None,
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

            span = Span(
                name=f"llm:{model}",
                span_type="llm_inference",
                start_time=time.time() - (latency_ms / 1000),
                end_time=time.time(),
                duration_ms=latency_ms,
                token_count=tokens_in + tokens_out,
                status="ok" if success else "error",
                error_message=error[:200] if error else "",
                attributes={"model": model, "combo": combo or ""},
                input_data={"tokens_in": tokens_in} if tokens_in else {},
                output_data={"tokens_out": tokens_out} if tokens_out else {},
            )
            # 활성 trace가 있으면 span 추가
            if tracer._active_trace:
                tracer._active_trace.add_span(span)
            elif tracer._span_stack:
                tracer._span_stack[-1].add_span(span)
        except Exception:
            logger.debug("Tracing span add failed (non-critical)", exc_info=True)

    def _get_provider(self, loaded: LoadedModel):
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
            with urllib.request.urlopen(req, timeout=300) as response:
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
    def _suppress_model_thinking(model_name: str, messages: list[dict]) -> list[dict]:
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
        import anthropic

        from ..config import config

        api_key = config._raw.get("api_keys", {}).get("anthropic", "")
        if not api_key or api_key == "sk-ant-your-key-here":
            yield "[Error] Anthropic API Key not found in config.yaml"
            return

        client = anthropic.Anthropic(api_key=api_key)

        system_prompt = kwargs.get("system_prompt", "")
        raw_messages = kwargs.get("raw_messages", [{"role": "user", "content": prompt}])

        # 1. Apply Dynamic Inference Config (Not-Claude-Code-Emulator Pattern)
        model_name, temperature, thinking_config, attribution = self._apply_dynamic_inference_config(
            loaded.profile, raw_messages, kwargs
        )

        # Format messages for anthropic
        anthropic_msgs = []
        for msg in raw_messages:
            if msg["role"] in ["user", "assistant"]:
                anthropic_msgs.append({"role": msg["role"], "content": msg["content"]})

        # 2. Intelligent Context Cache Limit Manager
        # Anthropic allows max 4 cache_control blocks. We keep the first and the last 3.
        cache_blocks = []

        # Convert system prompt to block format for caching
        system_blocks = []
        if system_prompt:
            system_blocks.append(
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                },
            )
            cache_blocks.append(system_blocks[0])

        for msg in anthropic_msgs:
            if isinstance(msg["content"], list):
                for block in msg["content"]:
                    if isinstance(block, dict) and "cache_control" in block:
                        cache_blocks.append(block)
            elif isinstance(msg["content"], str) and msg["role"] == "user":
                # Automatically add cache_control to recent long user messages if we wanted to
                pass

        if len(cache_blocks) > 4:
            keep_first = cache_blocks[0]
            keep_last = cache_blocks[-3:]
            to_keep = set([id(keep_first)] + [id(b) for b in keep_last])

            for block in cache_blocks:
                if id(block) not in to_keep:
                    del block["cache_control"]

        # 3. Agent Footprint & Fingerprinting
        if system_blocks:
            system_blocks[0]["text"] += attribution
        else:
            system_blocks.append(
                {
                    "type": "text",
                    "text": attribution,
                    "cache_control": {"type": "ephemeral"},
                },
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

        try:
            with client.messages.stream(**request_params) as stream:
                for text in stream.text_stream:
                    yield text
        except Exception as e:
            logger.exception("Anthropic API generation failed")
            yield f"[API Error for {model_name}] {e}"

    def _do_ollama_stream(self, loaded: LoadedModel, prompt: str, **kwargs):
        """스트리밍 생성 로직.

        Ollama Native API(/api/chat)와 OpenAI 호환 SSE(/v1/chat/completions)를
        api_base에 따라 자동 선택합니다.
        """
        import json
        import urllib.request

        from ..config import config

        base_url = config.model.api_base.rstrip("/")
        api_key = config.model.api_key

        is_openrouter = self._is_openrouter()

        if "raw_messages" in kwargs:
            sys_msg = kwargs.get("system_prompt", "")
            if sys_msg:
                api_msgs = [{"role": "system", "content": sys_msg}] + kwargs["raw_messages"]
            else:
                api_msgs = kwargs["raw_messages"]
        else:
            if isinstance(prompt, list):
                api_msgs = prompt
            else:
                api_msgs = [{"role": "user", "content": prompt}]

        # Normalize messages (string content 보장)
        normalized_msgs = []
        for msg in api_msgs:
            content = msg.get("content", "")
            if isinstance(content, list):
                str_content = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        str_content.append(part.get("text", ""))
                    elif isinstance(part, str):
                        str_content.append(part)
                content = " ".join(str_content)
            normalized_msgs.append({**msg, "content": content})
        api_msgs = normalized_msgs

        api_msgs = self._suppress_model_thinking(loaded.profile.name, api_msgs)

        model_name, temperature, thinking_config, attribution = self._apply_dynamic_inference_config(
            loaded.profile, api_msgs, kwargs
        )

        if api_msgs and isinstance(api_msgs[0].get("content"), str):
            api_msgs = list(api_msgs)
            api_msgs[0] = {
                **api_msgs[0],
                "content": api_msgs[0]["content"] + f"\n{attribution}",
            }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        # OpenRouter 전용 헤더 (식별용)
        if is_openrouter:
            headers["HTTP-Referer"] = "https://github.com/sumkbs-kbs/antigravity-k"
            headers["X-Title"] = "Antigravity-K"

        if is_openrouter:
            # OpenAI 호환 SSE 스트리밍 (/v1/chat/completions)
            url = f"{base_url}/chat/completions"
            data = {
                "model": model_name,
                "stream": True,
                "temperature": temperature,
                "max_tokens": kwargs.get("max_tokens", 4096),
                "messages": api_msgs,
            }
        else:
            # Ollama Native API 스트리밍 (/api/chat) — /v1 접미사 정규화
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

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers=headers,
        )
        try:
            if is_openrouter:
                # OpenAI 호환 SSE 스트리밍 파싱 (data: {...} \n\n)
                with urllib.request.urlopen(req, timeout=300) as response:
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
                with urllib.request.urlopen(req, timeout=300) as response:
                    in_reasoning = False
                    for line in response:
                        line = line.decode("utf-8").strip()
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                            if "message" in chunk:
                                msg = chunk["message"]
                                if "content" in msg and msg["content"]:
                                    if in_reasoning:
                                        in_reasoning = False
                                    yield msg["content"]
                        except json.JSONDecodeError:
                            continue
        except urllib.error.HTTPError as e:
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

    def status(self) -> dict:
        """현재 로드 상태 반환."""
        loaded_models = []
        total_memory = 0.0

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
        }

    def loaded_names(self) -> list[str]:
        """현재 로드된 모델 이름 목록."""
        return list(self._loaded.keys())

    def get_model_info(self) -> dict:
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
        # Check Ollama active models dynamically (Ollama 엔진일 때만 — OpenRouter는 원격이므로 로컬 tags 조회 무의미)
        if (config.model.api_engine or "").lower() == "ollama":
            profile = self._registry.get_model(name)
            if profile and getattr(profile, "backend", "ollama") == "ollama":
                try:
                    import json
                    import urllib.request

                    native_base = self._ollama_native_base(config.model.api_base)
                    req = urllib.request.Request(f"{native_base}/api/tags")
                    with urllib.request.urlopen(req, timeout=2) as resp:
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

        from ..config import config

        if config.model.force_api or platform.system() != "Darwin":
            logger.info("[%s] 외부 API 어댑터 모드를 사용합니다.", profile.name)
            return _OllamaModel(profile.name), _OllamaTokenizer(profile.name)

        if profile.role == "embedding":
            return self._load_embedding_model(profile)

        try:
            from mlx_lm import load

            model, tokenizer, *_ = load(profile.repo)
            return model, tokenizer
        except ImportError:
            logger.warning("mlx_lm 미설치. Ollama 어댑터 반환.")
            return _OllamaModel(profile.name), _OllamaTokenizer(profile.name)

    def _load_embedding_model(self, profile: ModelProfile) -> tuple[Any, Any]:
        """임베딩 모델 로드 (Mac 전용)."""
        try:
            from sentence_transformers import SentenceTransformer

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
