"""
Antigravity-K: 모델 레지스트리
config.yaml에서 모델 프로필을 읽어 카탈로그로 관리합니다.
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Type
import yaml

from antigravity_k.engine.provider_adapters.base_adapter import BaseProviderAdapter
from antigravity_k.engine.provider_adapters.openai_adapter import OpenAIAdapter


@dataclass
class ModelProfile:
    """하나의 모델 프로필"""

    name: str
    repo: str
    role: str  # reasoning | coding | embedding | vision
    quantization: str = ""
    estimated_memory_gb: float = 0.0
    context_length: int = 0
    dimensions: int = 0
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "ModelProfile":
        return cls(
            name=data.get("name", ""),
            repo=data.get("repo", ""),
            role=data.get("role", ""),
            quantization=data.get("quantization", ""),
            estimated_memory_gb=data.get("estimated_memory_gb", 0.0),
            context_length=data.get("context_length", 0),
            dimensions=data.get("dimensions", 0),
            description=data.get("description", ""),
        )

    def to_dict(self) -> dict:
        result = {
            "name": self.name,
            "repo": self.repo,
            "role": self.role,
            "estimated_memory_gb": self.estimated_memory_gb,
        }
        if self.quantization:
            result["quantization"] = self.quantization
        if self.context_length:
            result["context_length"] = self.context_length
        if self.dimensions:
            result["dimensions"] = self.dimensions
        if self.description:
            result["description"] = self.description
        return result


@dataclass
class DefaultModels:
    """서버 시작 시 기본 활성 모델"""

    reasoning: Optional[str] = None
    coding: Optional[str] = None
    embedding: Optional[str] = None
    vision: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "DefaultModels":
        return cls(
            **{k: data.get(k) for k in ("reasoning", "coding", "embedding", "vision")}
        )


@dataclass
class MemoryConfig:
    """메모리 관리 설정"""

    total_system_gb: float = 128.0
    max_loaded_gb: float = 100.0
    system_reserve_gb: float = 16.0
    auto_unload: bool = True
    unload_cooldown_sec: int = 30

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryConfig":
        return cls(
            total_system_gb=data.get("total_system_gb", 128.0),
            max_loaded_gb=data.get("max_loaded_gb", 100.0),
            system_reserve_gb=data.get("system_reserve_gb", 16.0),
            auto_unload=data.get("auto_unload", True),
            unload_cooldown_sec=data.get("unload_cooldown_sec", 30),
        )


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8000
    workers: int = 1
    log_level: str = "info"
    enable_caveman_compression: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "ServerConfig":
        return cls(
            host=data.get("host", "127.0.0.1"),
            port=data.get("port", 8000),
            workers=data.get("workers", 1),
            log_level=data.get("log_level", "info"),
            enable_caveman_compression=data.get("enable_caveman_compression", False),
        )


class ModelRegistry:
    """
    config.yaml 기반 모델 카탈로그.
    list_models(), get_model(name), find_by_role(role), get_default(role) 제공.
    """

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            project_root = Path(__file__).resolve().parents[3]
            config_path = str(project_root / "config.yaml")
        self._config_path = config_path
        self._models: dict[str, ModelProfile] = {}
        self._defaults = DefaultModels()
        self._memory = MemoryConfig()
        self._server = ServerConfig()
        self._raw: dict = {}
        self._load_config()

    def _load_config(self) -> None:
        path = Path(self._config_path)
        if not path.exists():
            raise FileNotFoundError(f"설정 파일 없음: {path}")
        with open(path, "r", encoding="utf-8") as f:
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

    def reload(self) -> None:
        """설정 핫 리로드"""
        self._load_config()

    def list_models(self) -> list[ModelProfile]:
        return list(self._models.values())

    def get_model(self, name: str) -> Optional[ModelProfile]:
        return self._models.get(name)

    def get_adapter_for_model(self, name: str) -> Optional[BaseProviderAdapter]:
        """
        주어진 모델이 어떤 API 규격을 사용하는지에 따라 적절한 변환 어댑터를 반환합니다.
        기본적으로 Claude가 아닌 모든 모델은 OpenAIAdapter(OpenRouter, Ollama 호환)를 통과합니다.
        """
        model = self.get_model(name)
        if not model:
            return None

        # 예시 로직: 이름이나 레포에 'claude'가 없으면 범용 OpenAI 규격으로 취급
        if "claude" not in model.name.lower() and "anthropic" not in model.repo.lower():
            return OpenAIAdapter()

        return None

    def find_by_role(self, role: str) -> list[ModelProfile]:
        return [m for m in self._models.values() if m.role == role]

    def get_default(self, role: str) -> Optional[ModelProfile]:
        name = getattr(self._defaults, role, None)
        return self._models.get(name) if name else None

    def model_exists(self, name: str) -> bool:
        return name in self._models

    @property
    def defaults(self) -> DefaultModels:
        return self._defaults

    @property
    def memory_config(self) -> MemoryConfig:
        return self._memory

    @property
    def server_config(self) -> ServerConfig:
        return self._server

    @property
    def model_cache_path(self) -> Path:
        paths = self._raw.get("paths", {})
        cache = paths.get("model_cache", "~/.cache/antigravity-k/models")
        return Path(os.path.expanduser(cache))

    def summary(self) -> str:
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
