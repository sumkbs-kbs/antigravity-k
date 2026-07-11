"""MemoryProvider — 플러그인 기반 에이전트 메모리 시스템.

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
from typing import Any

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
    def prefetch(self, query: str, session_id: str | None = None) -> str:
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
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """대화 턴을 기억에 동기화합니다."""
        ...

    def get_tool_schemas(self) -> list[dict[str, Any]]:
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
        """Initialize the BuiltinMemoryProvider.

        Args:
            session_manager: session manager.

        """
        self._session_manager = session_manager

    @property
    def name(self) -> str:
        """Name.

        Returns:
            str: The str result.

        """
        return "builtin"

    def prefetch(self, query: str, session_id: str | None = None) -> str:
        """Working Memory에서 관련 기억을 회상합니다."""
        try:
            memories = self._session_manager.get_working_memory()
            if not memories:
                return ""

            # 쿼리 키워드 기반 단순 필터링
            query_lower = query.lower()
            relevant = []
            for key, value in memories.items():
                if query_lower in str(key).lower() or query_lower in str(value).lower():
                    relevant.append(f"- {key}: {value}")

            if not relevant:
                # 전체 Working Memory 요약 반환
                items = [f"- {k}: {v}" for k, v in list(memories.items())[:10]]
                if items:
                    return "[Working Memory]\n" + "\n".join(items)
                return ""

            return "[Relevant Memory]\n" + "\n".join(relevant)
        except Exception as e:
            logger.exception("Unhandled exception")
            logger.debug("BuiltinMemoryProvider.prefetch error: %s", e)
            return ""

    def sync_turn(
        self,
        user_message: str,
        assistant_response: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """턴 정보를 SessionManager에 동기화합니다."""
        try:
            self._session_manager.add_turn(role="user", content=user_message)
            self._session_manager.add_turn(role="assistant", content=assistant_response)
        except Exception as e:
            logger.exception("Unhandled exception")
            logger.debug("BuiltinMemoryProvider.sync_turn error: %s", e)

    def on_session_switch(self, new_session_id: str) -> None:
        """세션 전환 시 SessionManager의 세션을 전환합니다."""
        try:
            self._session_manager.start_session(resume=True)
        except Exception as e:
            logger.exception("Unhandled exception")
            logger.debug("BuiltinMemoryProvider.on_session_switch error: %s", e)


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

    def __init__(self) -> None:
        """Initialize the MemoryManager."""
        self._providers: list[MemoryProvider] = []
        self._external_count = 0

    @property
    def providers(self) -> list[MemoryProvider]:
        """Providers.

        Returns:
            list[MemoryProvider]: The list[memoryprovider] result.

        """
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
                    f"등록할 수 있습니다. 현재: {self._external_count}",
                )
            self._external_count += 1

        self._providers.append(provider)
        logger.info(
            "Memory provider registered: %s (external=%s)",
            provider.name,
            provider.is_external,
        )

    def remove_provider(self, name: str) -> bool:
        """이름으로 메모리 제공자를 제거합니다."""
        for i, p in enumerate(self._providers):
            if p.name == name:
                removed = self._providers.pop(i)
                if removed.is_external:
                    self._external_count -= 1
                logger.info("Memory provider removed: %s", name)
                return True
        return False

    def prefetch_all(self, query: str, session_id: str | None = None) -> str:
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
                    logger.debug(
                        "Memory prefetch [%s]: %s chars in %ss",
                        provider.name,
                        len(result),
                        elapsed,
                    )
            except Exception:
                logger.exception("Memory prefetch error [%s]", provider.name)

        return "\n\n".join(parts) if parts else ""

    def sync_all(
        self,
        user_message: str,
        assistant_response: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """모든 제공자에 턴 데이터를 동기화합니다."""
        for provider in self._providers:
            try:
                provider.sync_turn(user_message, assistant_response, metadata=metadata)
            except Exception:
                logger.exception("Memory sync error [%s]", provider.name)

    def on_session_switch(self, new_session_id: str) -> None:
        """세션 전환을 모든 제공자에 전파합니다."""
        for provider in self._providers:
            try:
                provider.on_session_switch(new_session_id)
            except Exception:
                logger.exception("Session switch error [%s]", provider.name)

    def get_all_tool_schemas(self) -> list[dict[str, Any]]:
        """모든 제공자의 도구 스키마를 수집합니다."""
        schemas = []
        for provider in self._providers:
            try:
                schemas.extend(provider.get_tool_schemas())
            except Exception:
                logger.exception("Tool schema error [%s]", provider.name)
        return schemas

    def get_stats(self) -> dict[str, Any]:
        """메모리 시스템 통계를 반환합니다."""
        return {
            "total_providers": len(self._providers),
            "external_providers": self._external_count,
            "provider_names": [p.name for p in self._providers],
        }


# ── 에피소딕 메모리 제공자 (4-Tier Cognitive Memory Layer 2) ──


class EpisodicMemoryProvider(MemoryProvider):
    """과거 이벤트/대화를 시간순으로 저장하고 회상하는 에피소딕 메모리.

    인간의 일화적 기억(Episodic Memory)을 모델링합니다.
    - 시간순 이벤트 시퀀스 저장
    - 키워드 기반 관련 에피소드 회상
    - 오래된 기억 자동 감쇠(decay) + 요약 통합(consolidation)

    사용법:
        episodic = EpisodicMemoryProvider(max_episodes=200)
        manager.add_provider(episodic)
    """

    def __init__(self, max_episodes: int = 200, decay_threshold: float = 0.3, persist_dir: str | None = None):
        """Initialize the EpisodicMemoryProvider.

        Args:
            max_episodes (int): int max episodes.
            decay_threshold (float): float decay threshold.
            persist_dir: 디스크 영속화 디렉토리 (작업 3). None이면 ~/.antigravity-k/memory.

        """
        import os

        self._episodes: list[dict[str, Any]] = []
        self._max_episodes = max_episodes
        self._decay_threshold = decay_threshold
        self._access_counts: dict[int, int] = {}  # episode_id → access count
        # 작업 3: 디스크 영속화 — 재시작 후에도 에피소드 유지
        self._persist_dir = persist_dir or os.path.join(os.path.expanduser("~"), ".antigravity-k", "memory")
        self._persist_path = os.path.join(self._persist_dir, "episodes.json")
        os.makedirs(self._persist_dir, exist_ok=True)
        self._load()

    @property
    def name(self) -> str:
        """Name.

        Returns:
            str: The str result.

        """
        return "episodic"

    def prefetch(self, query: str, session_id: str | None = None) -> str:
        """쿼리와 관련된 과거 에피소드를 회상합니다."""
        if not self._episodes:
            return ""

        query_lower = query.lower()
        scored = []

        for i, ep in enumerate(self._episodes):
            score = 0.0
            content = (ep.get("user", "") + " " + ep.get("assistant", "")).lower()

            # 키워드 매칭 점수
            query_words = query_lower.split()
            for word in query_words:
                if len(word) > 1 and word in content:
                    score += 1.0

            # 시간 감쇠 (최근 에피소드일수록 높은 점수)
            recency = (i + 1) / len(self._episodes)  # 0~1, 최근이 1에 가까움
            score *= 0.5 + 0.5 * recency

            # 접근 빈도 부스트 (자주 회상된 기억은 강화)
            access = self._access_counts.get(i, 0)
            score *= 1.0 + 0.1 * min(access, 5)

            if score > 0:
                scored.append((score, i, ep))

        if not scored:
            return ""

        # 상위 5개 에피소드 반환
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:5]

        # 접근 카운트 증가
        for _, idx, _ in top:
            self._access_counts[idx] = self._access_counts.get(idx, 0) + 1

        lines = ["[Episodic Memory — 관련 과거 경험]"]
        for score, _, ep in top:
            ts = ep.get("timestamp", "")[:16]
            user_summary = ep["user"][:80] + "..." if len(ep.get("user", "")) > 80 else ep.get("user", "")
            asst_summary = (
                ep["assistant"][:120] + "..." if len(ep.get("assistant", "")) > 120 else ep.get("assistant", "")
            )
            lines.append(f"  [{ts}] Q: {user_summary}")
            lines.append(f"           A: {asst_summary}")

        return "\n".join(lines)

    def sync_turn(
        self,
        user_message: str,
        assistant_response: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """대화 턴을 에피소드로 저장합니다."""
        from datetime import datetime as _dt

        episode = {
            "user": user_message,
            "assistant": assistant_response,
            "timestamp": _dt.now().isoformat(),
            "metadata": metadata or {},
        }
        self._episodes.append(episode)

        # 용량 초과 시 오래된 저관련 에피소드 감쇠
        if len(self._episodes) > self._max_episodes:
            self._consolidate()
        else:
            self._save()  # 작업 3: 디스크 영속화

    def _consolidate(self):
        """메모리 통합: 오래되고 접근 빈도 낮은 에피소드 제거."""
        if len(self._episodes) <= self._max_episodes:
            return

        # 접근 빈도가 낮은 오래된 에피소드부터 제거
        scored_indices = []
        for i in range(len(self._episodes)):
            access = self._access_counts.get(i, 0)
            recency = (i + 1) / len(self._episodes)
            importance = access * 0.5 + recency * 0.5
            scored_indices.append((importance, i))

        scored_indices.sort(key=lambda x: x[0])

        # 하위 20% 제거
        remove_count = len(self._episodes) - self._max_episodes + int(self._max_episodes * 0.1)
        remove_indices = set(idx for _, idx in scored_indices[:remove_count])

        self._episodes = [ep for i, ep in enumerate(self._episodes) if i not in remove_indices]
        # 접근 카운트 재인덱싱
        new_counts = {}
        new_idx = 0
        for i in range(len(self._episodes) + remove_count):
            if i not in remove_indices:
                if i in self._access_counts:
                    new_counts[new_idx] = self._access_counts[i]
                new_idx += 1
        self._access_counts = new_counts

        logger.info(
            "[EpisodicMemory] Consolidation: %s개 에피소드 감쇠, 남은: %s",
            remove_count,
            len(self._episodes),
        )
        self._save()

    def _load(self):
        """디스크에서 에피소드를 로드합니다 (작업 3)."""
        import json
        import os

        if not os.path.exists(self._persist_path):
            return
        try:
            with open(self._persist_path, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    self._episodes = data[-self._max_episodes :]
                    logger.info("[EpisodicMemory] 디스크에서 %s개 에피소드 로드", len(self._episodes))
        except Exception:
            logger.warning("[EpisodicMemory] 로드 실패 (non-critical)", exc_info=True)

    def _save(self):
        """에피소드를 디스크에 저장합니다 (작업 3)."""
        import json

        try:
            with open(self._persist_path, "w", encoding="utf-8") as f:
                json.dump(self._episodes, f, ensure_ascii=False, indent=2)
        except Exception:
            logger.warning("[EpisodicMemory] 저장 실패 (non-critical)", exc_info=True)

    def get_stats(self) -> dict[str, Any]:
        """Retrieve stats.

        Returns:
            dict[str, Any]: The dict[str, any] result.

        """
        return {
            "total_episodes": len(self._episodes),
            "max_episodes": self._max_episodes,
            "most_accessed": sorted(self._access_counts.items(), key=lambda x: x[1], reverse=True)[:5],
        }


# ── 워킹 메모리 버퍼 (4-Tier Cognitive Memory Layer 1) ──


class WorkingMemoryBuffer(MemoryProvider):
    """슬라이딩 윈도우 기반 워킹 메모리.

    현재 세션의 최근 대화를 제한된 크기로 유지합니다.
    컨텍스트 윈도우 관리를 지능적으로 수행합니다.

    - 최근 N턴 유지 (FIFO)
    - 중요 턴은 고정(pin) 가능
    - 세션별 독립 관리
    """

    def __init__(self, max_turns: int = 20):
        """Initialize the WorkingMemoryBuffer.

        Args:
            max_turns (int): int max turns.

        """
        self._turns: list[dict[str, str]] = []
        self._pinned: set = set()  # 고정된 턴 인덱스
        self._max_turns = max_turns

    @property
    def name(self) -> str:
        """Name.

        Returns:
            str: The str result.

        """
        return "working_memory"

    def prefetch(self, query: str, session_id: str | None = None) -> str:
        """워킹 메모리에서 최근 컨텍스트를 반환합니다."""
        if not self._turns:
            return ""

        lines = ["[Working Memory — 최근 대화 컨텍스트]"]
        for i, turn in enumerate(self._turns[-10:]):  # 최근 10턴만
            prefix = "📌 " if i in self._pinned else ""
            lines.append(f"  {prefix}{turn['role']}: {turn['content'][:100]}")

        return "\n".join(lines)

    def sync_turn(
        self,
        user_message: str,
        assistant_response: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """턴을 워킹 메모리에 추가합니다."""
        self._turns.append({"role": "user", "content": user_message})
        self._turns.append({"role": "assistant", "content": assistant_response})

        # 윈도우 초과 시 오래된 비고정 턴 제거
        while len(self._turns) > self._max_turns * 2:
            # 고정되지 않은 가장 오래된 턴 제거
            for i in range(len(self._turns)):
                if i not in self._pinned:
                    self._turns.pop(i)
                    break
            else:
                # 모두 고정이면 가장 오래된 것 강제 제거
                self._turns.pop(0)

    def pin_turn(self, turn_index: int):
        """특정 턴을 고정하여 감쇠되지 않도록 합니다."""
        self._pinned.add(turn_index)

    def get_recent(self, n: int = 5) -> list[dict[str, str]]:
        """최근 N개 턴을 반환합니다."""
        return self._turns[-n * 2 :]

    def clear(self):
        """워킹 메모리를 초기화합니다."""
        self._turns.clear()
        self._pinned.clear()


# ── Cross-Project 글로벌 메모리 제공자 (P2-3) ──


class GlobalMemoryProvider(MemoryProvider):
    """사용자 단위 글로벌 메모리 — 모든 프로젝트에 걸쳐 공유 (P2-3).

    ~/.antigravity-k/memory/ 에 저장되는 사용자 코딩 스타일, 선호 라이브러리,
    반복 패턴, 자주 하는 요청 등을 영속화합니다. Cursor Memory / Claude Projects 대응.

    다른 MemoryProvider(세션/프로젝트 단위)와 달리, 이 제공자는 사용자 홈 디렉토리에
    저장되므로 프로젝트를 바꿔도 동일한 선호도가 유지됩니다.

    저장 카테고리:
      - preferences: 사용자 선호 (예: "tabs 사용", "한국어 응답 선호")
      - patterns: 반복 코딩 패턴 (예: "항상 type hints 추가")
      - facts: 학습한 사실 (예: "이 사용자는 React 선호")
    """

    def __init__(self, memory_dir: str | None = None, max_entries: int = 200):
        """Initialize the GlobalMemoryProvider.

        Args:
            memory_dir: 메모리 저장 디렉토리 (기본: ~/.antigravity-k/memory)
            max_entries: 카테고리당 최대 항목 수

        """
        import os

        self._memory_dir = memory_dir or os.path.join(os.path.expanduser("~"), ".antigravity-k", "memory")
        self._max_entries = max_entries
        os.makedirs(self._memory_dir, exist_ok=True)
        self._memory: dict[str, list[str]] = self._load()

    @property
    def name(self) -> str:
        return "global"

    def _load(self) -> dict[str, list[str]]:
        """디스크에서 글로벌 메모리를 로드합니다."""
        import json
        import os

        result: dict[str, list[str]] = {"preferences": [], "patterns": [], "facts": []}
        for category in result:
            path = os.path.join(self._memory_dir, f"{category}.json")
            if os.path.exists(path):
                try:
                    with open(path, encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            result[category] = data[-self._max_entries :]
                except Exception:
                    logger.warning("[GlobalMemory] %s 로드 실패", category, exc_info=True)
        return result

    def _save_category(self, category: str) -> None:
        """특정 카테고리를 디스크에 저장합니다."""
        import json
        import os

        path = os.path.join(self._memory_dir, f"{category}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._memory.get(category, []), f, ensure_ascii=False, indent=2)
        except Exception:
            logger.warning("[GlobalMemory] %s 저장 실패", category, exc_info=True)

    def prefetch(self, query: str, session_id: str | None = None) -> str:
        """쿼리와 관련된 글로벌 기억을 회상합니다.

        단순 키워드 매칭으로 관련 항목을 찾아 컨텍스트로 반환합니다.
        """
        if not any(self._memory.values()):
            return ""

        query_lower = query.lower()
        relevant: list[str] = []

        for category, entries in self._memory.items():
            for entry in entries:
                # 쿼리 키워드가 항목에 포함되면 관련성 있다고 판단
                entry_lower = entry.lower()
                words = query_lower.split()
                if any(w in entry_lower for w in words if len(w) > 2):
                    relevant.append(f"[{category}] {entry}")

        if not relevant:
            # 관련 항목이 없으면 상위 선호도만 표시
            prefs = self._memory.get("preferences", [])[:3]
            if prefs:
                relevant = [f"[preferences] {p}" for p in prefs]

        if relevant:
            return "[Global User Memory]\n" + "\n".join(relevant[:10])
        return ""

    def sync_turn(
        self,
        user_message: str,
        assistant_response: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """대화 턴에서 학습 가능한 패턴을 추출하여 글로벌 메모리에 저장합니다.

        현재는 메타데이터로 명시적으로 전달된 preference/pattern만 저장.
        향후 LLM 기반 자동 추출 확장 가능.
        """
        if not metadata:
            return

        # 명시적 preference 추가
        new_prefs = metadata.get("learned_preferences", [])
        for pref in new_prefs:
            if pref and pref not in self._memory["preferences"]:
                self._memory["preferences"].append(pref)
                if len(self._memory["preferences"]) > self._max_entries:
                    self._memory["preferences"] = self._memory["preferences"][-self._max_entries :]
                self._save_category("preferences")

        # 명시적 pattern 추가
        new_patterns = metadata.get("learned_patterns", [])
        for pattern in new_patterns:
            if pattern and pattern not in self._memory["patterns"]:
                self._memory["patterns"].append(pattern)
                self._save_category("patterns")

    def add_preference(self, preference: str) -> None:
        """사용자 선호를 직접 추가합니다 (API/슬래시 명령어용)."""
        if preference and preference not in self._memory["preferences"]:
            self._memory["preferences"].append(preference)
            if len(self._memory["preferences"]) > self._max_entries:
                self._memory["preferences"] = self._memory["preferences"][-self._max_entries :]
            self._save_category("preferences")
            logger.info("[GlobalMemory] 선호도 추가: %s", preference[:50])

    def add_fact(self, fact: str) -> None:
        """학습한 사실을 추가합니다."""
        if fact and fact not in self._memory["facts"]:
            self._memory["facts"].append(fact)
            if len(self._memory["facts"]) > self._max_entries:
                self._memory["facts"] = self._memory["facts"][-self._max_entries :]
            self._save_category("facts")

    def get_all(self) -> dict[str, list[str]]:
        """전체 글로벌 메모리를 반환합니다 (디버그/API용)."""
        return dict(self._memory)
