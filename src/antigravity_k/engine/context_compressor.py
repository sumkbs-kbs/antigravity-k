"""
Antigravity-K: Context Compressor (Memory Pruning + RAG Retrieval)
==================================================================
Monitors conversation history and automatically compresses or prunes
older messages into semantic summaries to prevent context window bloat
and reduce LLM hallucinations in long-running tasks.

격차 해소: 컨텍스트 윈도우 한계를 LLM 요약 + RAG 검색으로 보상
"""

import json
import logging
import os
from typing import List, Dict, Optional, Callable

logger = logging.getLogger("antigravity_k.context_compressor")


class ContextCompressor:
    def __init__(
        self,
        token_limit: int = 8000,
        keep_last_n: int = 10,
        summarize_fn: Optional[Callable[[str], str]] = None,
        rag_search_fn: Optional[Callable[[str, int], str]] = None,
        persistence_dir: Optional[str] = None,
    ):
        """
        Args:
            token_limit: 메시지 히스토리의 토큰 한도
            keep_last_n: 항상 유지할 최근 메시지 수
            summarize_fn: LLM 요약 함수 (prompt -> summary)
            rag_search_fn: RAG 검색 함수 (query, n_results) -> context_str
        """
        self.token_limit = token_limit
        self.keep_last_n = keep_last_n
        self._summarize_fn = summarize_fn
        self._rag_search_fn = rag_search_fn

        self.persistence_dir = persistence_dir
        self._memory_file = None
        if self.persistence_dir:
            os.makedirs(self.persistence_dir, exist_ok=True)
            self._memory_file = os.path.join(
                self.persistence_dir, "long_term_memory.json"
            )

        # 시맨틱 메모리: pruning된 메시지 요약을 보존
        self._pruned_summaries: List[str] = self._load_memory()

    def _load_memory(self) -> List[str]:
        if not self._memory_file or not os.path.exists(self._memory_file):
            return []
        try:
            with open(self._memory_file, "r", encoding="utf-8") as f:
                return json.load(f).get("pruned_summaries", [])
        except Exception as e:
            logger.warning(f"Failed to load long term memory: {e}")
        return []

    def _save_memory(self):
        if not self._memory_file:
            return
        try:
            with open(self._memory_file, "w", encoding="utf-8") as f:
                json.dump(
                    {"pruned_summaries": self._pruned_summaries},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception as e:
            logger.warning(f"Failed to save long term memory: {e}")

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation."""
        return len(text) // 4

    def needs_compression(self, messages: List[Dict[str, str]]) -> bool:
        total_tokens = sum(self.estimate_tokens(m.get("content", "")) for m in messages)
        return total_tokens > self.token_limit

    def compress(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Compresses the message history by keeping the system prompt,
        summarizing the middle (via LLM if available), and keeping
        the most recent N messages intact.
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

        # LLM 기반 요약 (사용 가능한 경우)
        summary_text = self._summarize_old_messages(old_msgs)

        # 요약을 영구 메모리에도 보존
        if summary_text and summary_text not in self._pruned_summaries:
            self._pruned_summaries.append(summary_text)
            # 최대 10개 요약만 유지
            if len(self._pruned_summaries) > 10:
                self._pruned_summaries = self._pruned_summaries[-10:]
            self._save_memory()

        summary_msg = {"role": "system", "content": summary_text}
        compressed = system_msgs + [summary_msg] + recent_msgs
        return compressed

    def enrich_with_rag(
        self,
        messages: List[Dict[str, str]],
        user_query: str,
        max_rag_chars: int = 4000,
    ) -> List[Dict[str, str]]:
        """
        RAG 검색 결과를 메시지에 주입합니다.

        사용자 질문과 관련된 코드 청크를 VectorStore에서 검색하여
        시스템 메시지로 추가합니다.
        """
        if not self._rag_search_fn:
            return messages

        try:
            rag_context = self._rag_search_fn(user_query, 5)
            if not rag_context or len(rag_context.strip()) < 20:
                return messages
        except Exception as e:
            logger.warning(f"[Compressor] RAG search failed: {e}")
            return messages

        # 토큰 예산 확인
        current_tokens = sum(
            self.estimate_tokens(m.get("content", "")) for m in messages
        )
        rag_tokens = self.estimate_tokens(rag_context)

        if current_tokens + rag_tokens > self.token_limit:
            # 예산 초과 시 RAG 결과를 잘라서 주입
            available_chars = max((self.token_limit - current_tokens) * 4, 500)
            rag_context = rag_context[:available_chars]

        # 시스템 메시지 뒤에 RAG 컨텍스트 삽입
        rag_msg = {
            "role": "system",
            "content": (
                "[코드베이스 컨텍스트] 아래는 사용자 질문과 관련된 프로젝트 코드입니다. "
                "이 정보를 참고하여 정확한 답변을 생성하세요.\n\n" + rag_context
            ),
        }

        # 시스템 메시지 바로 뒤에 삽입
        result = []
        system_inserted = False
        for m in messages:
            result.append(m)
            if m.get("role") == "system" and not system_inserted:
                result.append(rag_msg)
                system_inserted = True

        if not system_inserted:
            result.insert(0, rag_msg)

        logger.info(f"[Compressor] RAG context injected: {len(rag_context)} chars")
        return result

    def inject_memory(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        과거 pruning된 요약을 현재 대화에 재주입합니다 (장기 기억).
        """
        if not self._pruned_summaries:
            return messages

        memory_text = "[장기 기억] 이전 대화에서의 핵심 내용:\n" + "\n".join(
            f"- {s}" for s in self._pruned_summaries[-3:]
        )

        memory_msg = {"role": "system", "content": memory_text}

        # 첫 시스템 메시지 뒤에 삽입
        result = []
        inserted = False
        for m in messages:
            result.append(m)
            if m.get("role") == "system" and not inserted:
                result.append(memory_msg)
                inserted = True

        return result if inserted else [memory_msg] + messages

    def get_pruned_summaries(self) -> List[str]:
        """보존된 과거 요약을 반환합니다."""
        return list(self._pruned_summaries)

    def _summarize_old_messages(self, old_msgs: List[Dict[str, str]]) -> str:
        """오래된 메시지를 LLM으로 요약하거나 휴리스틱 요약합니다."""
        if not old_msgs:
            return ""

        # LLM 요약 가능 시
        if self._summarize_fn:
            combined = "\n".join(
                f"[{m.get('role', '?')}]: {m.get('content', '')[:200]}"
                for m in old_msgs
            )
            prompt = (
                "아래 대화 기록을 3줄 이내로 핵심만 요약해주세요. "
                "특히 사용자의 결정사항, 아키텍처 선택, 변경된 파일을 포함하세요.\n\n"
                + combined[:2000]
            )
            try:
                summary = self._summarize_fn(prompt)
                if summary and len(summary.strip()) > 20:
                    return (
                        f"[대화 요약 — {len(old_msgs)}개 메시지 압축]\n"
                        + summary.strip()
                    )
            except Exception as e:
                logger.warning(f"[Compressor] LLM summarization failed: {e}")

        # 폴백: 휴리스틱 요약
        key_msgs = []
        for m in old_msgs:
            content = m.get("content", "")
            role = m.get("role", "")
            # 사용자 메시지와 도구 결과는 핵심 정보로 간주
            if role in ("user", "tool") and content:
                key_msgs.append(f"[{role}]: {content[:100]}")

        if key_msgs:
            return f"[대화 요약 — {len(old_msgs)}개 메시지 압축]\n" + "\n".join(
                key_msgs[:5]
            )

        return (
            f"[System Note: {len(old_msgs)} older messages were pruned for "
            "context efficiency. The agent has already explored previous steps.]"
        )
