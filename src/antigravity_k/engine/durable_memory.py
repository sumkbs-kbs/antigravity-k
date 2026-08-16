from collections.abc import Callable
from typing import Any

from antigravity_k.engine.memory_provider import MemoryProvider, MemoryScope, normalize_memory_scope


class DurableMemoryProvider(MemoryProvider):
    def __init__(
        self,
        provider_name: str,
        clear_all: Callable[[], int],
        export_all: Callable[[], list[dict[str, Any]]] | None = None,
        redact_all: Callable[[], int] | None = None,
        retention: Callable[[int], int] | None = None,
    ):
        self._provider_name = provider_name
        self._clear_all = clear_all
        self._export_all = export_all
        self._redact_all = redact_all
        self._retention = retention

    @property
    def name(self) -> str:
        return self._provider_name

    def prefetch(self, query: str, session_id: str | None = None) -> str:
        return ""

    def sync_turn(
        self,
        user_message: str,
        assistant_response: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        return None

    def clear(self, scope: MemoryScope = "all") -> int:
        if normalize_memory_scope(scope) == "all":
            return self._clear_all()
        return 0

    def export(self, scope: MemoryScope = "all") -> list[dict[str, Any]]:
        if normalize_memory_scope(scope) == "all" and self._export_all is not None:
            return self._export_all()
        return []

    def redact(self, scope: MemoryScope = "all") -> int:
        if normalize_memory_scope(scope) == "all" and self._redact_all is not None:
            return self._redact_all()
        return 0

    def apply_retention(self, max_age_days: int) -> int:
        if max_age_days < 0:
            raise ValueError("max_age_days must be non-negative")
        return self._retention(max_age_days) if self._retention is not None else 0
