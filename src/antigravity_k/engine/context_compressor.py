"""
Antigravity-K: Context Compressor (Memory Pruning)
==================================================
Monitors conversation history and automatically compresses or prunes
older messages into semantic summaries to prevent context window bloat
and reduce LLM hallucinations in long-running tasks.
"""

import logging
from typing import List, Dict

logger = logging.getLogger("antigravity_k.context_compressor")


class ContextCompressor:
    def __init__(self, token_limit: int = 8000, keep_last_n: int = 10):
        self.token_limit = token_limit
        self.keep_last_n = keep_last_n

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation."""
        return len(text) // 4

    def needs_compression(self, messages: List[Dict[str, str]]) -> bool:
        total_tokens = sum(self.estimate_tokens(m.get("content", "")) for m in messages)
        return total_tokens > self.token_limit

    def compress(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Compresses the message history by keeping the system prompt,
        summarizing the middle, and keeping the most recent N messages intact.
        """
        if not messages or not self.needs_compression(messages):
            return messages

        logger.info(
            f"[Compressor] Context exceeds limit ({self.token_limit}). Compressing..."
        )

        system_msgs = [m for m in messages if m.get("role") == "system"]
        other_msgs = [m for m in messages if m.get("role") != "system"]

        if len(other_msgs) <= self.keep_last_n:
            return messages

        recent_msgs = other_msgs[-self.keep_last_n :]
        old_msgs = other_msgs[: -self.keep_last_n]

        # In a full implementation, old_msgs would be passed to an LLM for summarization
        # or pushed to GBrain vector store. Here we use a fast heuristic summary.
        summary_text = f"[System Note: {len(old_msgs)} older messages were pruned for context efficiency. The agent has already explored previous steps.]"

        summary_msg = {"role": "system", "content": summary_text}

        compressed = system_msgs + [summary_msg] + recent_msgs
        return compressed
