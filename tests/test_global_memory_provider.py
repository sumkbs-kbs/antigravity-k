"""GlobalMemoryProvider 단위 테스트 (작업 A).

글로벌 메모리 영속화, 회상, sync_turn 학습, 프로젝트 간 공유를 검증합니다.
"""

import pytest

from antigravity_k.engine.memory_provider import (
    GlobalMemoryProvider,
    MemoryManager,
)


@pytest.fixture
def provider(tmp_path):
    """각 테스트마다 임시 디렉토리를 사용하는 GlobalMemoryProvider."""
    return GlobalMemoryProvider(memory_dir=str(tmp_path))


class TestGlobalMemoryProviderBasics:
    """기본 속성 검증."""

    def test_name_is_global(self, provider):
        assert provider.name == "global"

    def test_initial_memory_empty(self, provider):
        all_mem = provider.get_all()
        assert all_mem["preferences"] == []
        assert all_mem["patterns"] == []
        assert all_mem["facts"] == []

    def test_initial_prefetch_returns_empty(self, provider):
        assert provider.prefetch("any query") == ""


class TestAddPreference:
    """선호도 추가 검증."""

    def test_add_preference(self, provider):
        provider.add_preference("한국어 응답 선호")
        all_mem = provider.get_all()
        assert "한국어 응답 선호" in all_mem["preferences"]

    def test_add_duplicate_preference_ignored(self, provider):
        provider.add_preference("tabs 사용")
        provider.add_preference("tabs 사용")  # 중복
        assert len(provider.get_all()["preferences"]) == 1

    def test_add_empty_preference_ignored(self, provider):
        provider.add_preference("")
        assert len(provider.get_all()["preferences"]) == 0


class TestAddFact:
    """사실 추가 검증."""

    def test_add_fact(self, provider):
        provider.add_fact("사용자는 React 선호")
        assert "사용자는 React 선호" in provider.get_all()["facts"]

    def test_add_duplicate_fact_ignored(self, provider):
        provider.add_fact("fact1")
        provider.add_fact("fact1")
        assert len(provider.get_all()["facts"]) == 1


class TestPrefetch:
    """회상 로직 검증."""

    def test_prefetch_returns_relevant(self, provider):
        provider.add_preference("한국어 응답 선호")
        provider.add_preference("type hints 필수")
        result = provider.prefetch("한국어로 답변해줘")
        assert "한국어" in result
        assert "[Global User Memory]" in result

    def test_prefetch_no_match_returns_prefs(self, provider):
        provider.add_preference("tabs 사용")
        result = provider.prefetch("completely unrelated query xyz")
        # 관련 항목 없으면 상위 선호도 표시
        assert "tabs" in result

    def test_prefetch_empty_memory_returns_empty(self, provider):
        assert provider.prefetch("anything") == ""


class TestSyncTurn:
    """sync_turn 학습 검증."""

    def test_sync_turn_no_metadata_noop(self, provider):
        provider.sync_turn("user msg", "assistant resp")
        assert provider.get_all()["preferences"] == []
        assert provider.get_all()["patterns"] == []

    def test_sync_turn_learns_preferences(self, provider):
        provider.sync_turn("user msg", "assistant resp", metadata={"learned_preferences": ["Python 3.12 선호"]})
        assert "Python 3.12 선호" in provider.get_all()["preferences"]

    def test_sync_turn_learns_patterns(self, provider):
        provider.sync_turn("user msg", "assistant resp", metadata={"learned_patterns": ["항상 docstring 추가"]})
        assert "항상 docstring 추가" in provider.get_all()["patterns"]

    def test_sync_turn_duplicate_not_added(self, provider):
        provider.sync_turn("u", "a", metadata={"learned_preferences": ["pref1"]})
        provider.sync_turn("u", "a", metadata={"learned_preferences": ["pref1"]})
        assert len(provider.get_all()["preferences"]) == 1


class TestPersistence:
    """디스크 영속화 검증 (프로젝트 간 공유 핵심)."""

    def test_preferences_persisted_to_disk(self, provider, tmp_path):
        provider.add_preference("persisted pref")
        # 새 인스턴스가 같은 디렉토리에서 로드
        provider2 = GlobalMemoryProvider(memory_dir=str(tmp_path))
        assert "persisted pref" in provider2.get_all()["preferences"]

    def test_facts_persisted_to_disk(self, provider, tmp_path):
        provider.add_fact("persisted fact")
        provider2 = GlobalMemoryProvider(memory_dir=str(tmp_path))
        assert "persisted fact" in provider2.get_all()["facts"]

    def test_max_entries_enforced(self, tmp_path):
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

    def test_manager_prefetch_includes_global(self, provider):
        provider.add_preference("한국어 선호")
        manager = MemoryManager()
        manager.add_provider(provider)
        result = manager.prefetch_all("한국어")
        assert "한국어" in result
