from pathlib import Path

from antigravity_k.engine.memory_provider import (
    EpisodicMemoryProvider,
    GlobalMemoryProvider,
    MemoryManager,
)


def _conflicting_manager(tmp_path: Path, *, global_first: bool) -> MemoryManager:
    global_memory = GlobalMemoryProvider(memory_dir=str(tmp_path / "global"))
    global_memory.sync_turn("내 이름은 이영희야", "반갑습니다")
    episodic = EpisodicMemoryProvider(persist_dir=str(tmp_path / "episodic"))
    episodic.sync_turn("내 이름은 김철수야", "안녕하세요 김철수님")
    manager = MemoryManager()
    providers = (global_memory, episodic) if global_first else (episodic, global_memory)
    for provider in providers:
        manager.add_provider(provider)
    return manager


def test_durable_identity_suppresses_stale_episodic_identity(tmp_path: Path) -> None:
    # Given: an old episodic name and a newer durable identity correction.
    episodic = EpisodicMemoryProvider(persist_dir=str(tmp_path / "episodic"))
    episodic.sync_turn("내 이름은 김철수야", "안녕하세요 김철수님")
    global_memory = GlobalMemoryProvider(memory_dir=str(tmp_path / "global"))
    global_memory.sync_turn("내 이름은 이영희야", "반갑습니다")
    manager = MemoryManager()
    manager.add_provider(episodic)
    manager.add_provider(global_memory)

    # When: identity-related context is recalled across providers.
    recalled = manager.prefetch_all("내 이름이 뭐야?")

    # Then: only the authoritative durable value reaches the model context.
    assert "이영희" in recalled
    assert "김철수" not in recalled


def test_current_user_correction_overrides_persisted_identity_before_sync(tmp_path: Path) -> None:
    # Given: every persistent provider still contains the user's old name.
    global_memory = GlobalMemoryProvider(memory_dir=str(tmp_path / "global"))
    global_memory.sync_turn("내 이름은 김철수야", "반갑습니다")
    episodic = EpisodicMemoryProvider(persist_dir=str(tmp_path / "episodic"))
    episodic.sync_turn("내 이름은 김철수야", "안녕하세요 김철수님")
    manager = MemoryManager()
    manager.add_provider(global_memory)
    manager.add_provider(episodic)

    # When: the current request explicitly corrects that identity fact.
    recalled = manager.prefetch_all("내 이름은 이영희로 바꿨어")

    # Then: the current user statement wins even before sync_all persists it.
    assert "이영희" in recalled
    assert "김철수" not in recalled


def test_identity_resolution_preserves_non_conflicting_memory(tmp_path: Path) -> None:
    # Given: an authoritative identity and an unrelated relevant episode.
    global_memory = GlobalMemoryProvider(memory_dir=str(tmp_path / "global"))
    global_memory.sync_turn("내 이름은 이영희야", "반갑습니다")
    episodic = EpisodicMemoryProvider(persist_dir=str(tmp_path / "episodic"))
    episodic.sync_turn("나는 Python을 주로 사용해", "기억할게요")
    manager = MemoryManager()
    manager.add_provider(global_memory)
    manager.add_provider(episodic)

    # When: unrelated project memory is recalled.
    recalled = manager.prefetch_all("Python 프로젝트")

    # Then: conflict filtering retains the unrelated episode and identity fact.
    assert "Python" in recalled
    assert "이영희" in recalled


def test_identity_resolution_is_provider_order_independent(tmp_path: Path) -> None:
    # Given: the same conflict registered in opposite provider orders.
    global_first = _conflicting_manager(tmp_path / "global_first", global_first=True)
    episodic_first = _conflicting_manager(tmp_path / "episodic_first", global_first=False)

    # When: both managers resolve the same query.
    first = global_first.prefetch_all("내 이름이 뭐야?")
    second = episodic_first.prefetch_all("내 이름이 뭐야?")

    # Then: authority, not registration order, determines the selected fact.
    assert "이영희" in first
    assert "이영희" in second
    assert "김철수" not in first
    assert "김철수" not in second


def test_conflict_metadata_is_transparent_without_repeating_stale_value(tmp_path: Path) -> None:
    # Given: a durable identity that conflicts with one episodic record.
    manager = _conflicting_manager(tmp_path, global_first=False)

    # When: the manager formats resolved context for the model.
    recalled = manager.prefetch_all("내 이름이 뭐야?")

    # Then: source/scope/count are visible while the stale value stays suppressed.
    assert "[resolved:identity:name source=global scope=global] 이영희" in recalled
    assert "[memory_conflict key=identity:name suppressed=2]" in recalled
    assert "김철수" not in recalled
