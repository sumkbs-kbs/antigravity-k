"""Antigravity-K: 모델 레지스트리.

config.yaml에서 모델 프로필을 읽어 카탈로그로 관리합니다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from antigravity_k.engine.provider_adapters.base_adapter import BaseProviderAdapter
from antigravity_k.engine.provider_adapters.openai_adapter import OpenAIAdapter


@dataclass
class ModelProfile:
    """하나의 모델 프로필."""

    name: str
    repo: str
    role: str  # reasoning | coding | embedding | vision
    quantization: str = ""
    estimated_memory_gb: float = 0.0
    context_length: int = 0
    dimensions: int = 0
    description: str = ""
    # ─── 멀티 프로바이더 지원 (작업 1) ───
    # provider: ollama | openrouter | nim | anthropic | mlx (빈 값이면 _infer_provider로 추론)
    provider: str = ""
    # api_base: per-model 오버라이드 (빈 값이면 providers 섹션의 기본 base_url 사용)
    api_base: str = ""
    # api_key_env: 이 모델이 사용할 환경변수명 (예: "NVIDIA_API_KEY"). 빈 값이면 providers 기본값 사용.
    api_key_env: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "ModelProfile":
        """From Dict.

        Args:
            data (dict): dict data.

        Returns:
            'ModelProfile': The 'modelprofile' result.

        """
        profile = cls(
            name=data.get("name", ""),
            repo=data.get("repo", ""),
            role=data.get("role", ""),
            quantization=data.get("quantization", ""),
            estimated_memory_gb=data.get("estimated_memory_gb", 0.0),
            context_length=data.get("context_length", 0),
            dimensions=data.get("dimensions", 0),
            description=data.get("description", ""),
            provider=data.get("provider", ""),
            api_base=data.get("api_base", ""),
            api_key_env=data.get("api_key_env", ""),
        )
        # provider가 명시되지 않았으면 이름/repo에서 자동 추론
        if not profile.provider:
            profile.provider = _infer_provider(profile.name, profile.repo, profile.estimated_memory_gb)
        return profile

    @property
    def backend(self) -> str:
        """backend 속성 — provider의 alias.

        model_manager.py:1068의 getattr(profile, "backend", "ollama") 코드와의
        하위 호환성을 위해 제공됨.
        """
        return self.provider or "ollama"

    def to_dict(self) -> dict:
        """To Dict.

        Returns:
            dict: The dict result.

        """
        result = {
            "name": self.name,
            "repo": self.repo,
            "role": self.role,
            "estimated_memory_gb": self.estimated_memory_gb,
            "provider": self.provider,
        }
        if self.quantization:
            result["quantization"] = self.quantization
        if self.context_length:
            result["context_length"] = self.context_length
        if self.dimensions:
            result["dimensions"] = self.dimensions
        if self.description:
            result["description"] = self.description
        if self.api_base:
            result["api_base"] = self.api_base
        if self.api_key_env:
            result["api_key_env"] = self.api_key_env
        return result


# ─── Provider 추론 헬퍼 (작업 1) ──────────────────────────────────────


# 알려진 OpenRouter 슬래시 프리픽스 (provider/model 형식)
_OPENROUTER_PREFIXES = frozenset(
    {
        "openai/",
        "anthropic/",
        "google/",
        "meta-llama/",
        "mistralai/",
        "cohere/",
        "qwen/",
        "deepseek/",
        "x-ai/",
        "amazon/",
        "microsoft/",
    }
)

# NVIDIA NIM(build.nvidia.com) 모델 식별자
_NIM_PREFIXES = frozenset(
    {
        "nvidia/",
        "meta/llama",  # NIM 카탈로그의 meta/llama-* 시리즈
        "deepseek-ai/",
        "microsoft/phi",
    }
)


def _infer_provider(name: str, repo: str, estimated_memory_gb: float = 0.0) -> str:
    """모델 이름/repo에서 provider를 추론합니다.

    명시적 provider 필드가 없을 때 사용되는 휴리스틱:
      - 로컬 Ollama 모델: ":tag" 형식 (예: "qwen3.6:latest") 또는 메모리 > 0
      - NVIDIA NIM: nvidia/, meta/llama, deepseek-ai/, microsoft/phi 접두사
      - OpenRouter: openai/, anthropic/, google/, qwen/ 등 슬래시 프리픽스
      - Anthropic 직접: claude-* 이름 (OpenRouter 경유가 아닌 경우)
      - 기본값: config.model.api_engine (호환성)

    Args:
        name: 모델 이름 (예: "qwen3.6:latest", "openai/gpt-4o", "nvidia/llama-3.1-nemotron-70b-instruct")
        repo: 리포지토리 식별자
        estimated_memory_gb: 예상 메모리 (0보다 크면 로컬 모델로 간주)

    Returns:
        provider 문자열: ollama | openrouter | nim | anthropic | mlx
    """
    name_lower = (name or "").lower()
    repo_lower = (repo or "").lower()

    # 1. 로컬 Ollama 모델: ":tag" 형식이거나 메모리 > 0 (원격 API 모델은 메모리 0)
    # 단, ":free" 접미사는 OpenRouter 무료 모델이므로 제외
    if ":" in name_lower and "/" not in name_lower and not name_lower.endswith(":free"):
        return "ollama"
    if estimated_memory_gb > 0 and "/" not in name_lower:
        return "ollama"

    # 2. OpenRouter 무료 모델: ":free" 접미사는 항상 OpenRouter (NIM은 :free 안 씀)
    if name_lower.endswith(":free"):
        return "openrouter"

    # 3. Anthropic 직접 호출 대상 (claude-* 이름, 단 openrouter/ 프리픽스 제외)
    if name_lower.startswith("claude-") and "anthropic/" not in repo_lower:
        return "anthropic"

    # 3.5 Google Gemini 직접 (gemini- 접두사, google/ 프리픽스 없음)
    if name_lower.startswith("gemini-") and not name_lower.startswith("google/"):
        return "gemini"

    # 3.6 ZAI/Zhipu 직접 (glm- 접두사)
    if name_lower.startswith("glm-") or name_lower.startswith("glm"):
        return "zai"

    # 3.7 OpenAI 직접 (gpt- 접두사, openai/ 프리픽스 없음 → OpenRouter가 아닌 직접)
    if name_lower.startswith("gpt-") and not name_lower.startswith("openai/"):
        return "openai"
    if name_lower.startswith("o1") or name_lower.startswith("o3") or name_lower.startswith("o4"):
        if not name_lower.startswith("openai/"):
            return "openai"

    # 4. NVIDIA NIM 카탈로그 식별자
    for prefix in _NIM_PREFIXES:
        if name_lower.startswith(prefix) or repo_lower.startswith(prefix):
            # 단, OpenRouter에도 같은 이름이 있을 수 있으므로 repo 기반 우선순위 확인
            # nvidia/ 접두사는 확실히 NIM
            if prefix == "nvidia/":
                return "nim"
            # meta/, deepseek-ai/, microsoft/phi는 명시적 판단이 필요 —
            # config의 provider 섹션에서 NIM base를 쓰는지로 최종 결정되므로
            # 여기서는 휴리스틱만 제공. 실제 config에서 provider: nim 명시 권장.
            return "nim"

    # 4. OpenRouter 슬래시 프리픽스
    for prefix in _OPENROUTER_PREFIXES:
        if name_lower.startswith(prefix) or repo_lower.startswith(prefix):
            return "openrouter"

    # 5. 기본값: 빈 문자열 (ModelManager가 config.model.api_engine으로 폴백)
    return ""


@dataclass
class DefaultModels:
    """서버 시작 시 기본 활성 모델."""

    reasoning: str | None = None
    coding: str | None = None
    embedding: str | None = None
    vision: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "DefaultModels":
        """From Dict.

        Args:
            data (dict): dict data.

        Returns:
            'DefaultModels': The 'defaultmodels' result.

        """
        return cls(**{k: data.get(k) for k in ("reasoning", "coding", "embedding", "vision")})


@dataclass
class MemoryConfig:
    """메모리 관리 설정."""

    total_system_gb: float = 128.0
    max_loaded_gb: float = 100.0
    system_reserve_gb: float = 16.0
    auto_unload: bool = True
    unload_cooldown_sec: int = 30

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryConfig":
        """From Dict.

        Args:
            data (dict): dict data.

        Returns:
            'MemoryConfig': The 'memoryconfig' result.

        """
        return cls(
            total_system_gb=data.get("total_system_gb", 128.0),
            max_loaded_gb=data.get("max_loaded_gb", 100.0),
            system_reserve_gb=data.get("system_reserve_gb", 16.0),
            auto_unload=data.get("auto_unload", True),
            unload_cooldown_sec=data.get("unload_cooldown_sec", 30),
        )


@dataclass
class ServerConfig:
    """Server runtime configuration (host, port, workers)."""

    host: str = "127.0.0.1"
    port: int = 8000
    workers: int = 1
    log_level: str = "info"
    enable_caveman_compression: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "ServerConfig":
        """From Dict.

        Args:
            data (dict): dict data.

        Returns:
            'ServerConfig': The 'serverconfig' result.

        """
        return cls(
            host=data.get("host", "127.0.0.1"),
            port=data.get("port", 8000),
            workers=data.get("workers", 1),
            log_level=data.get("log_level", "info"),
            enable_caveman_compression=data.get("enable_caveman_compression", False),
        )


class ModelRegistry:
    """config.yaml 기반 모델 카탈로그.

    list_models(), get_model(name), find_by_role(role), get_default(role) 제공.
    """

    def __init__(self, config_path: str | None = None):
        """Initialize the ModelRegistry.

        Args:
            config_path (str | None): str | None config path.

        """
        if config_path is None:
            project_root = Path(__file__).resolve().parents[3]
            config_path = str(project_root / "config.yaml")
        self._config_path = config_path
        self._models: dict[str, ModelProfile] = {}
        self._defaults = DefaultModels()
        self._memory = MemoryConfig()
        self._server = ServerConfig()
        self._providers: dict[str, dict] = {}
        self._raw: dict = {}
        self._load_config()

    def _load_config(self) -> None:
        path = Path(self._config_path)
        if not path.exists():
            raise FileNotFoundError(f"설정 파일 없음: {path}")
        with open(path, encoding="utf-8") as f:
            self._raw = yaml.safe_load(f) or {}

        self._models.clear()
        for role, items in self._raw.get("models", {}).items():
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                item.setdefault("role", role)
                p = ModelProfile.from_dict(item)
                if p.name:
                    self._models[p.name] = p

        self._defaults = DefaultModels.from_dict(self._raw.get("defaults", {}))
        self._memory = MemoryConfig.from_dict(self._raw.get("memory", {}))
        self._server = ServerConfig.from_dict(self._raw.get("server", {}))
        # providers 섹션 로드 (멀티 프로바이더 지원 — 작업 1)
        providers_raw = self._raw.get("providers", {})
        self._providers = providers_raw if isinstance(providers_raw, dict) else {}

    def reload(self) -> None:
        """설정 핫 리로드."""
        self._load_config()

    def list_models(self) -> list[ModelProfile]:
        """List Models.

        Returns:
            list[ModelProfile]: The list[modelprofile] result.

        """
        return list(self._models.values())

    def get_model(self, name: str) -> ModelProfile | None:
        """Retrieve model.

        Args:
            name (str): str name.

        Returns:
            ModelProfile | None: The modelprofile | none result.

        """
        return self._models.get(name)

    def get_adapter_for_model(self, name: str) -> BaseProviderAdapter | None:
        """주어진 모델이 어떤 API 규격을 사용하는지에 따라 적절한 변환 어댑터를 반환합니다.

        기본적으로 Claude가 아닌 모든 모델은 OpenAIAdapter(OpenRouter, Ollama 호환)를 통과합니다.
        """
        model = self.get_model(name)
        if not model:
            return None

        # 예시 로직: 이름이나 레포에 'claude'가 없으면 범용 OpenAI 규격으로 취급
        if "claude" not in model.name.lower() and "anthropic" not in model.repo.lower():
            return OpenAIAdapter()

        return None

    # ─── 멀티 프로바이더 조회 API (작업 1) ──────────────────────────────

    @property
    def providers(self) -> dict[str, dict]:
        """providers 섹션 반환 (ollama/openrouter/nim/anthropic/mlx 별 base_url, api_key_env 등)."""
        return self._providers

    def get_provider_config(self, provider: str) -> dict:
        """특정 provider의 설정(base_url, api_key_env, rate_limit 등)을 반환합니다.

        Args:
            provider: provider 이름 (ollama/openrouter/nim/anthropic/mlx)

        Returns:
            provider 설정 dict. 없으면 빈 dict.
        """
        return self._providers.get(provider, {}) if isinstance(self._providers, dict) else {}

    def resolve_endpoint(self, name: str) -> tuple[str, str, str]:
        """모델의 실제 API 엔드포인트와 키를 해석합니다 (멀티 프로바이더 핵심).

        우선순위:
          1. ModelProfile.api_base / api_key_env (per-model 오버라이드)
          2. providers[profile.provider].base_url / api_key_env (provider 기본값)
          3. config.model.api_base / api_key (전역 폴백 — 하위 호환)

        Args:
            name: 모델 이름

        Returns:
            (base_url, api_key_env_or_value, provider) 튜플.
            api_key는 실제 값이 아니라 환경변수명을 반환 — 호출자가 os.environ에서 조회.
        """
        import os

        from antigravity_k.config import config as app_config

        profile = self.get_model(name)
        provider = profile.provider if profile else ""

        # per-model 오버라이드
        if profile and profile.api_base:
            base_url = profile.api_base
            key_env = profile.api_key_env
        elif provider and provider in self._providers:
            prov_cfg = self._providers[provider]
            base_url = prov_cfg.get("base_url", "")
            key_env = prov_cfg.get("api_key_env", "")
        else:
            # 전역 config로 폴백 (레거시 단일 프로바이더 호환)
            base_url = app_config.model.api_base
            key_env = ""
            provider = app_config.model.api_engine or "ollama"

        # API 키 해석: 환경변수명이 있으면 조회, 없으면 전역 config 키 사용
        if key_env and key_env in os.environ:
            api_key = os.environ[key_env]
        elif provider == "ollama":
            api_key = os.environ.get("OLLAMA_API_KEY", "") or "ollama"
        elif profile and profile.api_key_env and profile.api_key_env in os.environ:
            api_key = os.environ[profile.api_key_env]
        else:
            api_key = app_config.model.api_key

        return base_url, api_key, provider

    def find_by_role(self, role: str) -> list[ModelProfile]:
        """Find by role.

        Args:
            role (str): str role.

        Returns:
            list[ModelProfile]: The list[modelprofile] result.

        """
        return [m for m in self._models.values() if m.role == role]

    def get_default(self, role: str) -> ModelProfile | None:
        """Retrieve default.

        Args:
            role (str): str role.

        Returns:
            ModelProfile | None: The modelprofile | none result.

        """
        name = getattr(self._defaults, role, None)
        return self._models.get(name) if name else None

    def model_exists(self, name: str) -> bool:
        """Model Exists.

        Args:
            name (str): str name.

        Returns:
            bool: The bool result.

        """
        return name in self._models

    @property
    def defaults(self) -> DefaultModels:
        """Defaults.

        Returns:
            DefaultModels: The defaultmodels result.

        """
        return self._defaults

    @property
    def memory_config(self) -> MemoryConfig:
        """Memory Config.

        Returns:
            MemoryConfig: The memoryconfig result.

        """
        return self._memory

    @property
    def server_config(self) -> ServerConfig:
        """Server Config.

        Returns:
            ServerConfig: The serverconfig result.

        """
        return self._server

    @property
    def model_cache_path(self) -> Path:
        """Model Cache Path.

        Returns:
            Path: The path result.

        """
        paths = self._raw.get("paths", {})
        cache = paths.get("model_cache", "~/.cache/antigravity-k/models")
        return Path(os.path.expanduser(cache))

    def summary(self) -> str:
        """Summary.

        Returns:
            str: The str result.

        """
        lines = ["=== Model Registry ==="]
        roles: dict[str, list[ModelProfile]] = {}
        for m in self._models.values():
            roles.setdefault(m.role, []).append(m)
        for role, models in sorted(roles.items()):
            default_name = getattr(self._defaults, role, None)
            lines.append(f"\n[{role}] ({len(models)}개)")
            for m in models:
                marker = " ★" if m.name == default_name else ""
                mem = f"{m.estimated_memory_gb}GB"
                lines.append(f"  - {m.name} ({mem}){marker}")
        lines.append(f"\n메모리 한도: {self._memory.max_loaded_gb}GB")
        return "\n".join(lines)
