"""Base worker interface for swarm mode."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class WorkerConfig:
    """Configuration for a single worker."""

    name: str = ""
    enabled: bool = True
    params: dict = field(default_factory=dict)


@dataclass
class WorkerResult:
    worker: str
    status: str  # "success" | "failed"
    duration: float = 0.0
    data: dict = field(default_factory=dict)
    error: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


class BaseWorker(ABC):
    """Abstract base class for all swarm workers."""

    def __init__(self, config: dict):
        self.config = config
        self.name = self.__class__.__name__
        # LLM backend info (passed from orchestrator)
        self._llm_backend: str = "local"
        self._llm_config: dict = {}
        self._prompt_history: list[dict[str, Any]] = []

    @abstractmethod
    def execute(self) -> WorkerResult:
        """Execute the worker and return results."""
        pass

    def call_llm(self, prompt: str, system: str = "", model: str = "") -> str:
        """Wrapper for llm_client.call_llm with worker context."""
        from llm_client import call_llm as _call_llm

        result = _call_llm(prompt, system=system, model=model, config=self._llm_config)
        self._prompt_history.append({"prompt": prompt[:200], "result": result[:200]})
        return result

    def get_backend(self) -> str:
        """Get current LLM backend ('local', 'openrouter', 'error')."""
        return self._llm_backend

    def get_llm_strategy(self) -> str:
        """Get current LLM strategy."""
        return self._llm_config.get("strategy", "local_first_or_fallback")
