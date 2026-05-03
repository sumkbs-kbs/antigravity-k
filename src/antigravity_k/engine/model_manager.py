"""
Antigravity-K: 모델 매니저
런타임 모델 로드/언로드/핫스왑 + 메모리 자동 관리
"""
from __future__ import annotations
import gc
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Optional

from .model_registry import ModelProfile, ModelRegistry
from .model_router import ModelRouter, AllModelsUnavailableError
from .usage_tracker import UsageTracker

logger = logging.getLogger("antigravity_k.model_manager")


@dataclass
class LoadedModel:
    """현재 메모리에 로드된 모델 정보"""
    profile: ModelProfile
    model: Any = None           # mlx_lm 모델 객체
    tokenizer: Any = None       # 토크나이저
    loaded_at: float = 0.0      # 로드 시각 (timestamp)
    last_used_at: float = 0.0   # 마지막 사용 시각
    actual_memory_gb: float = 0.0

    def touch(self):
        """사용 시각 갱신 (LRU용)"""
        self.last_used_at = time.time()


class ModelManager:
    """
    동적 모델 로드/언로드 매니저.

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
        router: Optional[ModelRouter] = None, 
        tracker: Optional[UsageTracker] = None
    ):
        self._registry = registry
        self._loaded: OrderedDict[str, LoadedModel] = OrderedDict()
        self._mem_config = registry.memory_config
        
        # 9Router 패턴 통합
        self.router = router or ModelRouter(registry)
        self.tracker = tracker or UsageTracker()

    # ─── 핵심 API ────────────────────────────────────────────────────

    def load(self, name: str) -> LoadedModel:
        """모델을 메모리에 로드"""
        # 이미 로드됨
        if name in self._loaded:
            loaded = self._loaded[name]
            loaded.touch()
            logger.info(f"[{name}] 이미 로드됨, 재사용")
            return loaded

        # 레지스트리에서 프로필 확인
        profile = self._registry.get_model(name)
        if profile is None:
            raise ValueError(
                f"모델 '{name}'이 config.yaml에 등록되어 있지 않습니다.\n"
                f"등록된 모델: {[m.name for m in self._registry.list_models()]}"
            )

        # 메모리 확보
        self._ensure_memory(profile.estimated_memory_gb)

        # 실제 모델 로드
        logger.info(f"[{name}] 로드 시작 (예상 {profile.estimated_memory_gb}GB)...")
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
        logger.info(f"[{name}] 로드 완료 ✓")
        return loaded

    def unload(self, name: str) -> bool:
        """모델을 메모리에서 해제"""
        if name not in self._loaded:
            logger.warning(f"[{name}] 로드되지 않은 모델")
            return False

        loaded = self._loaded.pop(name)
        # 모델 객체 해제
        del loaded.model
        del loaded.tokenizer
        gc.collect()

        logger.info(f"[{name}] 언로드 완료 ({loaded.actual_memory_gb}GB 해제)")
        return True

    def swap(self, new_name: str, role: Optional[str] = None) -> LoadedModel:
        """같은 역할의 모델 교체 (기존 언로드 → 새 모델 로드)"""
        new_profile = self._registry.get_model(new_name)
        if new_profile is None:
            raise ValueError(f"모델 '{new_name}'이 등록되어 있지 않습니다.")

        target_role = role or new_profile.role

        # 같은 역할로 로드된 기존 모델 찾아서 언로드
        to_unload = [
            name for name, loaded in self._loaded.items()
            if loaded.profile.role == target_role and name != new_name
        ]
        for name in to_unload:
            logger.info(f"[{name}] → [{new_name}] 교체를 위해 언로드")
            self.unload(name)

        return self.load(new_name)

    def get(self, name: str) -> LoadedModel:
        """로드된 모델 반환 (없으면 자동 로드)"""
        if name in self._loaded:
            loaded = self._loaded[name]
            loaded.touch()
            return loaded
        return self.load(name)

    def get_by_role(self, role: str) -> Optional[LoadedModel]:
        """역할별로 현재 로드된 모델 반환"""
        for loaded in self._loaded.values():
            if loaded.profile.role == role:
                loaded.touch()
                return loaded
        # 로드된 게 없으면 기본 모델 로드 시도
        default = self._registry.get_default(role)
        if default:
            return self.load(default.name)
        return None

    def prefetch(self, name: str) -> bool:
        """
        런타임 지연을 방지하기 위해 사전에 모델을 로드합니다.
        필요한 메모리가 확보 가능할 때만 로드하며, 이미 로드되어 있다면 무시합니다.
        """
        if name in self._loaded:
            return True
            
        profile = self._registry.get_model(name)
        if profile is None:
            logger.warning(f"Prefetch 실패: '{name}' 모델을 찾을 수 없습니다.")
            return False
            
        # 메모리 여유 체크
        current_used = sum(m.actual_memory_gb for m in self._loaded.values())
        if current_used + profile.estimated_memory_gb > self._mem_config.max_loaded_gb:
            logger.warning(f"Prefetch 보류: [{name}] 로드를 위한 메모리 부족 예상")
            if self._mem_config.auto_unload:
                logger.info(f"[{name}] 프리패치를 위해 기존 모델 자동 교체 시도")
                try:
                    self.load(name)
                    return True
                except MemoryError:
                    return False
            return False
            
        try:
            self.load(name)
            return True
        except Exception as e:
            logger.error(f"Prefetch 실패 [{name}]: {e}")
            return False

    # ─── 추론 API (9Router 연동) ─────────────────────────────────────

    def generate(self, prompt: str, target: str, **kwargs) -> str:
        """
        텍스트 생성 수행.
        
        Args:
            prompt: 입력 프롬프트
            target: 단일 모델 이름 또는 라우팅 콤보 이름
            **kwargs: max_tokens, temperature 등 생성 파라미터
            
        Returns:
            생성된 텍스트
        """
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
                
                # 라우팅된 모델의 fallback_depth (라우터 내부에서 인덱스로 추적하려면 라우터를 직접 사용해야 하므로 대략적으로 계산하거나 생략 가능.
                # ModelRouter의 combo를 확인하여 인덱스를 fallback depth로 추정)
                combo = self.router.get_combo(target)
                if used_model in combo.models:
                    fallback_depth = combo.models.index(used_model)
            else:
                # 단일 모델 직접 지정인 경우
                profile = self.router.route_single(target)
                used_model = profile.name
        except AllModelsUnavailableError as e:
            logger.error(f"추론 실패 (모든 모델 비가용): {e}")
            raise

        try:
            # 모델 로드 (메모리 관리 포함)
            loaded = self.get(used_model)
            
            # 실제 추론 수행 (Mac MLX 또는 Windows 더미)
            response_text = self._do_generate(loaded, prompt, **kwargs)
            
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
                combo_name=combo_name,
                fallback_depth=fallback_depth
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
                combo_name=combo_name,
                fallback_depth=fallback_depth
            )
            
            # 라우터에 실패 보고 (쿨다운 적용)
            self.router.mark_failure(used_model, reason=error_msg)
            
            # 콤보 라우팅인 경우 재귀적으로 다음 모델 시도
            if combo_name:
                logger.warning(f"[{used_model}] 실패 ({error_msg}), 콤보[{combo_name}]의 다음 모델로 폴백 시도합니다...")
                return self.generate(prompt, combo_name, **kwargs)
            else:
                logger.error(f"[{used_model}] 단일 모델 추론 실패: {error_msg}")
                raise

    def stream_generate(self, prompt: str, target: str, **kwargs):
        """
        텍스트 생성 수행 (스트리밍).
        """
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
                if used_model in combo.models:
                    fallback_depth = combo.models.index(used_model)
            else:
                profile = self.router.route_single(target)
                used_model = profile.name
        except AllModelsUnavailableError as e:
            logger.error(f"추론 실패 (모든 모델 비가용): {e}")
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
                combo_name=combo_name,
                fallback_depth=fallback_depth
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
                combo_name=combo_name,
                fallback_depth=fallback_depth
            )
            self.router.mark_failure(used_model, reason=error_msg)
            
            if combo_name:
                logger.warning(f"[{used_model}] 실패 ({error_msg}), 콤보[{combo_name}]의 다음 모델로 폴백 시도합니다...")
                yield from self.stream_generate(prompt, combo_name, **kwargs)
            else:
                logger.error(f"[{used_model}] 단일 모델 추론 실패: {error_msg}")
                raise

    def _do_generate(self, loaded: LoadedModel, prompt: str, **kwargs) -> str:
        """내부 텍스트 생성 로직 분리"""
        import platform
        from ..config import config
        if loaded.profile.name.startswith("claude"):
            result = ""
            for chunk in self._do_anthropic_stream(loaded, prompt, **kwargs):
                result += chunk
            return result
            
        if config.model.force_api or platform.system() != "Darwin" or isinstance(loaded.model, _OllamaModel):
            # 외부 API (Ollama/LM Studio) 기반 추론
            return self._do_ollama_generate(loaded, prompt, **kwargs)
            
        # Mac 실제 MLX 환경 (추후 mlx_lm.generate 구현)
        try:
            from mlx_lm import generate as mlx_generate
            # 기본 파라미터
            max_tokens = kwargs.get("max_tokens", 1024)
            temp = kwargs.get("temperature", 0.7)
            
            return mlx_generate(
                model=loaded.model,
                tokenizer=loaded.tokenizer,
                prompt=prompt,
                max_tokens=max_tokens
            )
        except ImportError:
            return f"[Simulated MLX] {loaded.profile.name} processed: {prompt[:30]}"

    def _do_stream_generate(self, loaded: LoadedModel, prompt: str, **kwargs):
        """내부 텍스트 생성 로직 분리 (스트리밍)"""
        import platform
        from ..config import config
        if loaded.profile.name.startswith("claude"):
            yield from self._do_anthropic_stream(loaded, prompt, **kwargs)
            return
            
        if config.model.force_api or platform.system() != "Darwin" or isinstance(loaded.model, _OllamaModel):
            # 외부 API (Ollama/LM Studio) 스트리밍 추론
            yield from self._do_ollama_stream(loaded, prompt, **kwargs)
            return
            
        # Mac 실제 MLX 환경 (추후 mlx_lm.stream_generate 구현)
        try:
            from mlx_lm import stream_generate as mlx_stream_generate
            max_tokens = kwargs.get("max_tokens", 1024)
            temp = kwargs.get("temperature", 0.7)
            
            yield from mlx_stream_generate(
                model=loaded.model,
                tokenizer=loaded.tokenizer,
                prompt=prompt,
                max_tokens=max_tokens
            )
        except ImportError:
            words = f"[Simulated MLX Stream] {loaded.profile.name} processed: {prompt[:30]}".split()
            for word in words:
                time.sleep(0.05)
                yield word + " "

    def _do_ollama_generate(self, loaded: LoadedModel, prompt: str, **kwargs) -> str:
        """OpenAI 호환 HTTP API (LM Studio, Ollama 등)를 통한 생성 로직"""
        import urllib.request
        import json
        from ..config import config
        
        base_url = config.model.api_base.rstrip('/')
        url = f"{base_url}/chat/completions"
        api_key = config.model.api_key
        
        data = {
            "model": loaded.profile.name,
            "stream": False,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 8192)
        }
        
        if "raw_messages" in kwargs:
            sys_msg = kwargs.get("system_prompt", "")
            if sys_msg:
                api_msgs = [{"role": "system", "content": sys_msg}] + kwargs["raw_messages"]
            else:
                api_msgs = kwargs["raw_messages"]
            data["messages"] = api_msgs
        else:
            data["messages"] = [{"role": "user", "content": prompt}]
        
        req = urllib.request.Request(
            url, 
            data=json.dumps(data).encode("utf-8"), 
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as response:
                result = json.loads(response.read().decode("utf-8"))
                content = result["choices"][0]["message"]["content"]
                logger.debug(f"Ollama response content ({len(content)} chars): {content[:200]}")
                return content
        except Exception as e:
            logger.error(f"Local API generation failed: {e}")
            return f"[API Error for {loaded.profile.name}] {e}"


    def _apply_dynamic_inference_config(self, loaded_profile, prompt_or_messages, kwargs):
        import hashlib
        model_name = loaded_profile.name
        thinking_config = None
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 8192)
        
        if ":" in model_name:
            base_model, spec = model_name.split(":", 1)
            model_name = base_model
            
            if spec.isdigit():
                budget = max(int(spec), 1024)
            else:
                ratios = {"high": 0.8, "medium": 0.5, "low": 0.2}
                ratio = ratios.get(spec.lower())
                if ratio:
                    budget = max(int(max_tokens * ratio), 1024)
                else:
                    budget = None
                    
            if budget:
                thinking_config = {"type": "enabled", "budget_tokens": budget}
                temperature = 1.0  # Required for thinking mode

        if isinstance(prompt_or_messages, list) and len(prompt_or_messages) > 0:
            first_user_text = str(prompt_or_messages[0].get("content", ""))
        else:
            first_user_text = str(prompt_or_messages)
            
        fingerprint_input = f"antigravity_k_59cf53e54c78_{first_user_text[:30]}"
        fingerprint = hashlib.sha256(fingerprint_input.encode('utf-8')).hexdigest()[:6]
        attribution = f"\nx-antigravity-k-agent: id={fingerprint}; cch=00000;"
        
        return model_name, temperature, thinking_config, attribution

    def _do_anthropic_stream(self, loaded: LoadedModel, prompt: str, **kwargs):
        import anthropic
        import hashlib
        from ..config import config
        api_key = config.config.get("api_keys", {}).get("anthropic")
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
            system_blocks.append({"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}})
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
            system_blocks.append({"type": "text", "text": attribution, "cache_control": {"type": "ephemeral"}})
        
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
            logger.error(f"Anthropic API generation failed: {e}")
            yield f"[API Error for {model_name}] {e}"

    def _do_ollama_stream(self, loaded: LoadedModel, prompt: str, **kwargs):
        """OpenAI 호환 HTTP API (LM Studio, Ollama 등)를 통한 스트리밍 생성 로직"""
        import urllib.request
        import json
        from ..config import config
        
        base_url = config.model.api_base.rstrip('/')
        url = f"{base_url}/chat/completions"
        api_key = config.model.api_key
        
        if "raw_messages" in kwargs:
            sys_msg = kwargs.get("system_prompt", "")
            if sys_msg:
                api_msgs = [{"role": "system", "content": sys_msg}] + kwargs["raw_messages"]
            else:
                api_msgs = kwargs["raw_messages"]
        else:
            api_msgs = [{"role": "user", "content": prompt}]
            
        model_name, temperature, thinking_config, attribution = self._apply_dynamic_inference_config(
            loaded.profile, api_msgs, kwargs
        )
        
        # W-7 수정: 원본 메시지 오염 방지를 위해 복사 후 attribution 추가
        if api_msgs and isinstance(api_msgs[0].get("content"), str):
            api_msgs = list(api_msgs)  # shallow copy of list
            api_msgs[0] = {**api_msgs[0], "content": api_msgs[0]["content"] + f"\n{attribution}"}
            
        data = {
            "model": model_name,
            "stream": True,
            "keep_alive": "30m",
            "temperature": temperature,
            "max_tokens": kwargs.get("max_tokens", 8192),
            "messages": api_msgs
        }
        
        req = urllib.request.Request(
            url, 
            data=json.dumps(data).encode("utf-8"), 
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as response:
                for line in response:
                    line = line.decode("utf-8").strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        try:
                            chunk = json.loads(line[6:])
                            delta = chunk["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"Local API stream failed: {e}")
            yield f"[API Error for {loaded.profile.name}] {e}"

    # ─── 상태 조회 ───────────────────────────────────────────────────

    def status(self) -> dict:
        """현재 로드 상태 반환"""
        loaded_models = []
        total_memory = 0.0

        for name, loaded in self._loaded.items():
            total_memory += loaded.actual_memory_gb
            loaded_models.append({
                "name": name,
                "role": loaded.profile.role,
                "memory_gb": loaded.actual_memory_gb,
                "loaded_at": loaded.loaded_at,
                "last_used_at": loaded.last_used_at,
            })

        return {
            "loaded_models": loaded_models,
            "total_loaded_gb": round(total_memory, 1),
            "max_allowed_gb": self._mem_config.max_loaded_gb,
            "available_gb": round(self._mem_config.max_loaded_gb - total_memory, 1),
            "auto_unload": self._mem_config.auto_unload,
        }

    def loaded_names(self) -> list[str]:
        """현재 로드된 모델 이름 목록"""
        return list(self._loaded.keys())

    def is_loaded(self, name: str) -> bool:
        if name in self._loaded:
            return True
        # Check Ollama active models dynamically
        profile = self._registry.get_model(name)
        if profile and getattr(profile, "backend", "ollama") == "ollama":
            try:
                import urllib.request
                import json
                req = urllib.request.Request("http://localhost:11434/api/ps")
                with urllib.request.urlopen(req, timeout=2) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    for m in data.get("models", []):
                        m_name = m.get("name", "")
                        # e.g. "deepseek-r1:70b" or "deepseek-r1" match
                        if m_name == name or m_name.startswith(name + ":"):
                            return True
            except Exception:
                pass
        return False

    # ─── 내부 메서드 ─────────────────────────────────────────────────

    def _ensure_memory(self, needed_gb: float) -> None:
        """필요한 메모리 확보 (자동 언로드)"""
        if not self._mem_config.auto_unload:
            return

        current_used = sum(m.actual_memory_gb for m in self._loaded.values())
        available = self._mem_config.max_loaded_gb - current_used

        if available >= needed_gb:
            return

        # LRU: 가장 오래 사용하지 않은 모델부터 언로드
        sorted_models = sorted(
            self._loaded.items(),
            key=lambda x: x[1].last_used_at,
        )

        for name, loaded in sorted_models:
            if available >= needed_gb:
                break
                
            elapsed_sec = time.time() - loaded.last_used_at
            if elapsed_sec < self._mem_config.unload_cooldown_sec:
                logger.warning(
                    f"[{name}] 쿨다운({self._mem_config.unload_cooldown_sec}초) 경과 전이지만 "
                    f"메모리 부족으로 강제 언로드 시도 (경과: {elapsed_sec:.1f}초)"
                )
            else:
                logger.info(
                    f"[{name}] 메모리 확보를 위해 자동 언로드 "
                    f"({loaded.actual_memory_gb}GB)"
                )
                
            available += loaded.actual_memory_gb
            self.unload(name)

        if available < needed_gb:
            raise MemoryError(
                f"메모리 부족: 필요 {needed_gb}GB, "
                f"사용 가능 {available:.1f}GB "
                f"(한도 {self._mem_config.max_loaded_gb}GB)"
            )

    def _load_mlx_model(self, profile: ModelProfile) -> tuple[Any, Any]:
        """MLX 모델 실제 로드 (Mac 전용, Windows에서는 더미 반환)"""
        import platform
        from ..config import config
        
        if config.model.force_api or platform.system() != "Darwin":
            logger.info(
                f"[{profile.name}] 외부 API 어댑터 모드를 사용합니다."
            )
            return _OllamaModel(profile.name), _OllamaTokenizer(profile.name)

        if profile.role == "embedding":
            return self._load_embedding_model(profile)

        try:
            from mlx_lm import load
            model, tokenizer = load(profile.repo)
            return model, tokenizer
        except ImportError:
            logger.warning("mlx_lm 미설치. Ollama 어댑터 반환.")
            return _OllamaModel(profile.name), _OllamaTokenizer(profile.name)

    def _load_embedding_model(self, profile: ModelProfile) -> tuple[Any, Any]:
        """임베딩 모델 로드 (Mac 전용)"""
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(profile.repo)
            return model, None
        except (ImportError, Exception) as e:
            logger.warning(f"임베딩 모델 로드 실패 ({e}). 더미 임베딩 반환.")
            return _OllamaModel(profile.name), None


# ─── Ollama 어댑터 (Windows/Linux/비-Mac 개발용) ──────────────────────────────────────

class _OllamaModel:
    """Windows에서 Ollama API 연동을 위한 더미 모델 객체"""
    def __init__(self, name: str):
        self.name = name
    def __repr__(self):
        return f"OllamaModel({self.name})"


class _OllamaTokenizer:
    """Windows에서 토큰 길이 어림잡기용 가짜 토크나이저"""
    
    eos_token_id = 100000
    chat_template = None
    bos_token = ""
    eos_token = ""
    
    def __init__(self, name: str):
        self.name = name
    def encode(self, text: str, **kwargs) -> list[int]:
        # 토큰 수는 임시로 단어 수의 1.3배 정도로 계산
        import math
        return list(range(max(1, math.ceil(len(text.split()) * 1.3))))
    def decode(self, tokens: list[int], **kwargs) -> str:
        return "[Decoded by OllamaTokenizer]"
    def get_vocab(self):
        return {}
    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
        # OpenAI API나 로컬 API는 직접 messages 배열을 받을 수 있지만
        # BaseAgent가 프롬프트 구성을 위해 이 함수를 호출하므로 단순 텍스트로 합쳐서 반환
        text = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            text += f"{role}: {content}\n"
        return text
