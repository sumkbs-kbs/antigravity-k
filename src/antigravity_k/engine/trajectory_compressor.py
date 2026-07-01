"""Trajectory Compressor module."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CompressionResult:
    """Compressionresult."""

    compressed_messages: list[dict]
    user_message: str = ""


class TrajectoryCompressor:
    """Compress long chat trajectories into a compact system summary."""

    def __init__(
        self,
        summarize_fn: Callable[[str], str] | None = None,
        max_messages: int = 40,
        max_chars: int = 80_000,
    ):
        """Initialize the TrajectoryCompressor.

        Args:
            summarize_fn (Callable[[str], str] | None): Callable[[str], str] | None summarize fn.
            max_messages (int): int max messages.
            max_chars (int): int max chars.

        """
        self.summarize_fn = summarize_fn
        self.max_messages = max_messages
        self.max_chars = max_chars

    def should_compress(self, messages: list[dict]) -> bool:
        """Determine whether to compress.

        Args:
            messages (list[dict]): list[dict] messages.

        Returns:
            bool: The bool result.

        """
        total_chars = sum(len(str(message.get("content", ""))) for message in messages)
        return len(messages) > self.max_messages or total_chars > self.max_chars

    def compress(self, messages: list[dict]) -> CompressionResult:
        """Compress.

        Args:
            messages (list[dict]): list[dict] messages.

        Returns:
            CompressionResult: The compressionresult result.

        """
        if not messages:
            return CompressionResult(compressed_messages=[])

        head = messages[:1]
        tail = messages[-10:]
        middle = messages[1:-10]
        summary = self._summarize(middle)

        compressed = list(head)
        if summary:
            compressed.append(
                {
                    "role": "system",
                    "content": f"[Compressed conversation trajectory]\n{summary}",
                },
            )
        compressed.extend(tail)
        return CompressionResult(
            compressed_messages=compressed,
            user_message="🧭 대화 이력이 길어 핵심 궤적을 압축했습니다.",
        )

    def _summarize(self, messages: list[dict]) -> str:
        if not messages:
            return ""

        raw = "\n".join(f"{message.get('role', 'unknown')}: {message.get('content', '')}" for message in messages)
        if self.summarize_fn:
            try:
                return self.summarize_fn(raw)
            except Exception:
                logger.exception("Unhandled exception")
                pass
        return raw[:4000]
