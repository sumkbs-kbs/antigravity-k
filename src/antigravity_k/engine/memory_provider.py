"""
MemoryProvider — 플러그인 기반 에이전트 메모리 시스템
=====================================================
Hermes Agent의 memory_manager.py 패턴을 Antigravity-K에 이식.

아키텍처:
- MemoryProvider (ABC): 메모리 제공자 인터페이스
- BuiltinMemoryProvider: SessionManager 기반 내장 메모리
- MemoryManager: 여러 메모리 제공자를 오케스트레이션

핵심 라이프사이클:
  세션 시작 → prefetch(query) → 대화 진행 → sync_turn(user, assistant) → 세션 종료

사용법:
    manager = MemoryManager()
    manager.add_provider(BuiltinMemoryProvider(session_manager))

    # 대화 시작 시 관련 기억 회상
    recalled = manager.prefetch_all("이전에 논의한 아키텍처")

    # 각 턴 종료 시 기억 동기화
    manager.sync_all(user_message, assistant_response)
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

logger = logging.getLogger("antigravity_k.engine.memory_provider")


# ── 메모리 제공자 인터페이스 ──

class MemoryProvider(ABC):
    """메모리 제공자 추상 인터페이스.

    모든 제공자는 이 인터페이스를 구현해야 합니다.
    - prefetch: 쿼리 기반 관련 기억 회상
    - sync_turn: 턴 종료 시 기억 저장
    - get_tool_schemas: 제공자가 노출하는 도구 스키마
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """제공자 이름 (예: 'builtin', 'vector', 'rag')."""
        ...

    @property
    def is_external(self) -> bool:
        """외부 제공자인지 여부. True이면 1개만 등록 가능."""
        return False

    @abstractmethod
    def prefetch(self, query: str, session_id: Optional[str] = None) -> str:
        """쿼리에 관련된 기억을 회상합니다.

        Returns:
            시스템 프롬프트에 주입할 컨텍스트 문자열.
            빈 문자열이면 관련 기억 없음.
        """
        ...

    @abstractmethod
    def sync_turn(
        self,
        user_message: str,
        assistant_response: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """대화 턴을 기억에 동기화합니다."""
        ...

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """제공자가 노출하는 도구 스키마.

        기본값은 빈 리스트 (도구 없음).
        외부 메모리 제공자가 memory_store/memory_recall 등을 노출할 때 오버라이드.
        """
        return []

    def on_session_switch(self, new_session_id: str) -> None:
        """세션 전환 시 호출됩니다. 기본값은 no-op."""
        pass


# ── 내장 메모리 제공자 (SessionManager 래핑) ──

class BuiltinMemoryProvider(MemoryProvider):
    """SessionManager의 Working Memory를 MemoryProvider 인터페이스로 래핑.

    SessionManager의 기존 기능을 그대로 활용하면서,
    MemoryManager의 통합 라이프사이클에 참여할 수 있게 합니다.
    """

    def __init__(self, session_manager):
        self._session_manager = session_manager

    @property
    def name(self) -> str:
        return "builtin"

    def prefetch(self, query: str, session_id: Optional[str] = None) -> str:
        """Working Memory에서 관련 기억을 회상합니다."""
        try:
            memories = self._session_manager.get_working_memory()
            if not memories:
                return ""

            # 쿼리 키워드 기반 단순 필터링
            query_lower = query.lower()
            relevant = []
            for key, value in memories.items():
                if (
                    query_lower in str(key).lower()
                    or query_lower in str(value).lower()
                ):
                    relevant.append(f"- {key}: {value}")

            if not relevant:
                # 전체 Working Memory 요약 반환
                items = [f"- {k}: {v}" for k, v in list(memories.items())[:10]]
                if items:
                    return "[Working Memory]\n" + "\n".join(items)
                return ""

            return "[Relevant Memory]\n" + "\n".join(relevant)
        except Exception as e:
            logger.debug(f"BuiltinMemoryProvider.prefetch error: {e}")
            return ""

    def sync_turn(
        self,
        user_message: str,
        assistant_response: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """턴 정보를 SessionManager에 동기화합니다."""
        try:
            self._session_manager.add_turn(
                role="user", content=user_message
            )
            self._session_manager.add_turn(
                role="assistant", content=assistant_response
            )
        except Exception as e:
            logger.debug(f"BuiltinMemoryProvider.sync_turn error: {e}")

    def on_session_switch(self, new_session_id: str) -> None:
        """세션 전환 시 SessionManager의 세션을 전환합니다."""
        try:
            self._session_manager.start_session(resume=True)
        except Exception as e:
            logger.debug(f"BuiltinMemoryProvider.on_session_switch error: {e}")


# ── 메모리 매니저 (오케스트레이터) ──

class MemoryManager:
    """여러 메모리 제공자를 통합 관리하는 오케스트레이터.

    Hermes Agent 패턴:
    - 내장 제공자: 제한 없이 여러 개 등록 가능
    - 외부 제공자: 최대 1개만 (스키마 충돌 방지)
    - prefetch_all(): 모든 제공자에서 병렬 회상
    - sync_all(): 모든 제공자에 턴 동기화
    """

    MAX_EXTERNAL_PROVIDERS = 1

    def __init__(self):
        self._providers: List[MemoryProvider] = []
        self._external_count = 0

    @property
    def providers(self) -> List[MemoryProvider]:
        return list(self._providers)

    def add_provider(self, provider: MemoryProvider) -> None:
        """메모리 제공자를 등록합니다.

        외부 제공자는 최대 1개만 등록 가능합니다.

        Raises:
            ValueError: 외부 제공자 한도 초과 시
        """
        if provider.is_external:
            if self._external_count >= self.MAX_EXTERNAL_PROVIDERS:
                raise ValueError(
                    f"외부 메모리 제공자는 최대 {self.MAX_EXTERNAL_PROVIDERS}개만 "
                    f"등록할 수 있습니다. 현재: {self._external_count}"
                )
            self._external_count += 1

        self._providers.append(provider)
        logger.info(f"Memory provider registered: {provider.name} (external={provider.is_external})")

    def remove_provider(self, name: str) -> bool:
        """이름으로 메모리 제공자를 제거합니다."""
        for i, p in enumerate(self._providers):
            if p.name == name:
                removed = self._providers.pop(i)
                if removed.is_external:
                    self._external_count -= 1
                logger.info(f"Memory provider removed: {name}")
                return True
        return False

    def prefetch_all(self, query: str, session_id: Optional[str] = None) -> str:
        """모든 제공자에서 관련 기억을 회상합니다.

        각 제공자의 결과를 결합하여 하나의 컨텍스트 문자열로 반환합니다.
        """
        if not self._providers:
            return ""

        parts = []
        for provider in self._providers:
            try:
                start = time.time()
                result = provider.prefetch(query, session_id)
                elapsed = time.time() - start
                if result and result.strip():
                    parts.append(result.strip())
                    logger.debug(f"Memory prefetch [{provider.name}]: {len(result)} chars in {elapsed:.2f}s")
            except Exception as e:
                logger.warning(f"Memory prefetch error [{provider.name}]: {e}")

        return "\n\n".join(parts) if parts else ""

    def sync_all(
        self,
        user_message: str,
        assistant_response: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """모든 제공자에 턴 데이터를 동기화합니다."""
        for provider in self._providers:
            try:
                provider.sync_turn(
                    user_message, assistant_response, metadata=metadata
                )
            except Exception as e:
                logger.warning(f"Memory sync error [{provider.name}]: {e}")

    def on_session_switch(self, new_session_id: str) -> None:
        """세션 전환을 모든 제공자에 전파합니다."""
        for provider in self._providers:
            try:
                provider.on_session_switch(new_session_id)
            except Exception as e:
                logger.warning(f"Session switch error [{provider.name}]: {e}")

    def get_all_tool_schemas(self) -> List[Dict[str, Any]]:
        """모든 제공자의 도구 스키마를 수집합니다."""
        schemas = []
        for provider in self._providers:
            try:
                schemas.extend(provider.get_tool_schemas())
            except Exception as e:
                logger.warning(f"Tool schema error [{provider.name}]: {e}")
        return schemas

    def get_stats(self) -> Dict[str, Any]:
        """메모리 시스템 통계를 반환합니다."""
        return {
            "total_providers": len(self._providers),
            "external_providers": self._external_count,
            "provider_names": [p.name for p in self._providers],
        }
