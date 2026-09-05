"""GlobalMemoryProvider 단위 테스트 (작업 A).

글로벌 메모리 영속화, 회상, sync_turn 학습, 프로젝트 간 공유를 검증합니다.
"""

from pathlib import Path

import pytest

from antigravity_k.engine.memory_provider import (
    GlobalMemoryProvider,
    MemoryManager,
    WorkingMemoryBuffer,
)


@pytest.fixture
def provider(tmp_path: Path) -> GlobalMemoryProvider:
    """각 테스트마다 임시 디렉토리를 사용하는 GlobalMemoryProvider."""
    return GlobalMemoryProvider(memory_dir=str(tmp_path))


class TestGlobalMemoryProviderBasics:
    """기본 속성 검증."""

    def test_name_is_global(self, provider: GlobalMemoryProvider) -> None:
        assert provider.name == "global"

    def test_initial_memory_empty(self, provider: GlobalMemoryProvider) -> None:
        all_mem = provider.get_all()
        assert all_mem["preferences"] == []
        assert all_mem["patterns"] == []
        assert all_mem["facts"] == []

    def test_initial_prefetch_returns_empty(self, provider: GlobalMemoryProvider) -> None:
        assert provider.prefetch("any query") == ""


class TestAddPreference:
    """선호도 추가 검증."""

    def test_add_preference(self, provider: GlobalMemoryProvider) -> None:
        provider.add_preference("한국어 응답 선호")
        all_mem = provider.get_all()
        assert "한국어 응답 선호" in all_mem["preferences"]

    def test_add_duplicate_preference_ignored(self, provider: GlobalMemoryProvider) -> None:
        provider.add_preference("tabs 사용")
        provider.add_preference("tabs 사용")  # 중복
        assert len(provider.get_all()["preferences"]) == 1

    def test_add_empty_preference_ignored(self, provider: GlobalMemoryProvider) -> None:
        provider.add_preference("")
        assert len(provider.get_all()["preferences"]) == 0


class TestAddFact:
    """사실 추가 검증."""

    def test_add_fact(self, provider: GlobalMemoryProvider) -> None:
        provider.add_fact("사용자는 React 선호")
        assert "사용자는 React 선호" in provider.get_all()["facts"]

    def test_add_duplicate_fact_ignored(self, provider: GlobalMemoryProvider) -> None:
        provider.add_fact("fact1")
        provider.add_fact("fact1")
        assert len(provider.get_all()["facts"]) == 1


class TestPrefetch:
    """회상 로직 검증."""

    def test_prefetch_returns_relevant(self, provider: GlobalMemoryProvider) -> None:
        provider.add_preference("한국어 응답 선호")
        provider.add_preference("type hints 필수")
        result = provider.prefetch("한국어로 답변해줘")
        assert "한국어" in result
        assert "[Global User Memory]" in result

    def test_prefetch_no_match_returns_prefs(self, provider: GlobalMemoryProvider) -> None:
        provider.add_preference("tabs 사용")
        result = provider.prefetch("completely unrelated query xyz")
        # 관련 항목 없으면 상위 선호도 표시
        assert "tabs" in result

    def test_prefetch_empty_memory_returns_empty(self, provider: GlobalMemoryProvider) -> None:
        assert provider.prefetch("anything") == ""


class TestSyncTurn:
    """sync_turn 학습 검증."""

    def test_sync_turn_no_metadata_noop(self, provider: GlobalMemoryProvider) -> None:
        provider.sync_turn("user msg", "assistant resp")
        assert provider.get_all()["preferences"] == []
        assert provider.get_all()["patterns"] == []

    def test_sync_turn_learns_preferences(self, provider: GlobalMemoryProvider) -> None:
        provider.sync_turn("user msg", "assistant resp", metadata={"learned_preferences": ["Python 3.12 선호"]})
        assert "Python 3.12 선호" in provider.get_all()["preferences"]

    def test_sync_turn_learns_patterns(self, provider: GlobalMemoryProvider) -> None:
        provider.sync_turn("user msg", "assistant resp", metadata={"learned_patterns": ["항상 docstring 추가"]})
        assert "항상 docstring 추가" in provider.get_all()["patterns"]

    def test_sync_turn_duplicate_not_added(self, provider: GlobalMemoryProvider) -> None:
        provider.sync_turn("u", "a", metadata={"learned_preferences": ["pref1"]})
        provider.sync_turn("u", "a", metadata={"learned_preferences": ["pref1"]})
        assert len(provider.get_all()["preferences"]) == 1


class TestPersistence:
    """디스크 영속화 검증 (프로젝트 간 공유 핵심)."""

    def test_preferences_persisted_to_disk(self, provider: GlobalMemoryProvider, tmp_path: Path) -> None:
        provider.add_preference("persisted pref")
        # 새 인스턴스가 같은 디렉토리에서 로드
        provider2 = GlobalMemoryProvider(memory_dir=str(tmp_path))
        assert "persisted pref" in provider2.get_all()["preferences"]

    def test_facts_persisted_to_disk(self, provider: GlobalMemoryProvider, tmp_path: Path) -> None:
        provider.add_fact("persisted fact")
        provider2 = GlobalMemoryProvider(memory_dir=str(tmp_path))
        assert "persisted fact" in provider2.get_all()["facts"]

    def test_max_entries_enforced(self, tmp_path: Path) -> None:
        provider = GlobalMemoryProvider(memory_dir=str(tmp_path), max_entries=3)
        for i in range(5):
            provider.add_preference(f"pref_{i}")
        # 최근 3개만 유지
        prefs = provider.get_all()["preferences"]
        assert len(prefs) == 3
        assert "pref_4" in prefs
        assert "pref_0" not in prefs


class TestMemoryManagerIntegration:
    """MemoryManager 통합 검증."""

    def test_manager_prefetch_includes_global(self, provider: GlobalMemoryProvider) -> None:
        provider.add_preference("한국어 선호")
        manager = MemoryManager()
        manager.add_provider(provider)
        result = manager.prefetch_all("한국어")
        assert "한국어" in result


class TestIdentityFactExtraction:
    def test_sync_turn_extracts_user_name_into_durable_identity_facts(self, provider: GlobalMemoryProvider) -> None:
        # Given: a turn where the user states their name in natural Korean.
        provider.sync_turn("내 이름은 김철수야", "안녕하세요!")

        # When / Then: the name is extracted into keyed identity facts (not a decaying
        # episode) so it survives consolidation and persists across projects.
        assert provider.get_identity_fact("name") == "김철수"

    def test_identity_facts_persist_across_instances(self, provider: GlobalMemoryProvider, tmp_path: Path) -> None:
        # Given: one instance learns the name.
        provider.sync_turn("my name is Alice", "hello Alice")

        # When: a fresh instance loads the same memory dir.
        provider2 = GlobalMemoryProvider(memory_dir=str(tmp_path))

        # Then: the identity fact is durable across process restarts.
        assert provider2.get_identity_fact("name") == "Alice"

    def test_name_conflict_resolves_to_latest_value(self, provider: GlobalMemoryProvider) -> None:
        # Given: the user corrects their name in a later turn.
        provider.sync_turn("내 이름은 김철수야", "ok")
        provider.sync_turn("내 이름은 이영희로 바꿨어", "ok")

        # Then: conflict resolution keeps the latest stated value, not both.
        assert provider.get_identity_fact("name") == "이영희"

    def test_prefetch_always_includes_identity_facts(self, provider: GlobalMemoryProvider) -> None:
        # Given: a name was learned but the current query shares no keywords.
        provider.sync_turn("내 이름은 김철수야", "ok")

        # When: an unrelated query is prefetched.
        recall = provider.prefetch("날씨 어때")

        # Then: the identity fact surfaces regardless, because personalization context
        # is high-importance and relevant to every personalized response.
        assert "김철수" in recall

    def test_no_false_positive_on_unrelated_message(self, provider: GlobalMemoryProvider) -> None:
        # Given: a message that does not state an identity fact.
        provider.sync_turn("오늘 날씨 정말 좋다", "네, 맑네요.")

        # Then: nothing is extracted.
        assert provider.get_identity_fact("name") is None


class TestWorkingMemoryBuffer:
    def test_pinned_turn_survives_non_pinned_evictions(self):
        # Given: an early assistant instruction is pinned in a small buffer.
        buffer = WorkingMemoryBuffer(max_turns=2)
        buffer.sync_turn("discard user", "retain assistant")
        buffer.pin_turn(1)
        buffer.sync_turn("middle user", "middle assistant")

        # When: a later turn requires two non-pinned evictions.
        buffer.sync_turn("latest user", "latest assistant")

        # Then: the pinned instruction remains available to the next model call.
        assert "retain assistant" in [turn["content"] for turn in buffer.get_recent(3)]

    def test_prefetch_marks_pinned_turn_in_recent_slice(self):
        # Given: the pinned turn is inside the recent context slice but not at index zero.
        buffer = WorkingMemoryBuffer(max_turns=6)
        for index in range(6):
            buffer.sync_turn(f"user {index}", f"assistant {index}")
        buffer.pin_turn(11)

        # When: working memory is formatted for model-context injection.
        recalled = buffer.prefetch("anything")

        # Then: the pin signal stays attached to its absolute turn index.
        assert "📌 assistant: assistant 5" in recalled
