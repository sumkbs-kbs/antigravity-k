from pathlib import Path
from types import SimpleNamespace
from typing import Callable, cast

from antigravity_k.engine.memory_provider import (
    EpisodicMemoryProvider,
    GlobalMemoryProvider,
    MemoryManager,
)
from antigravity_k.engine.orchestrator import stream as stream_module
from antigravity_k.engine.preference_memory import extract_explicit_preference_facts

_extract_learned_preferences = cast(
    Callable[[object], dict[str, object] | None],
    getattr(stream_module, "_extract_learned_preferences"),
)


def _preference_manager(tmp_path: Path) -> tuple[MemoryManager, GlobalMemoryProvider]:
    global_memory = GlobalMemoryProvider(memory_dir=str(tmp_path / "global"))
    episodic = EpisodicMemoryProvider(persist_dir=str(tmp_path / "episodic"))
    manager = MemoryManager()
    manager.add_provider(episodic)
    manager.add_provider(global_memory)
    return manager, global_memory


def test_current_user_preference_correction_wins_before_sync(tmp_path: Path) -> None:
    # Given: durable and episodic memory both contain the user's old response style.
    manager, global_memory = _preference_manager(tmp_path)
    global_memory.sync_turn("앞으로 답변은 상세하게 해줘", "알겠습니다")
    episodic = manager.providers[0]
    episodic.sync_turn("앞으로 답변은 상세하게 해줘", "알겠습니다")

    # When: the current request explicitly changes the same preference.
    recalled = manager.prefetch_all("이제부터 답변은 간결하게 해줘")

    # Then: only the current preference reaches the next model context.
    assert "[resolved:preference:response_detail source=current_user scope=session] concise" in recalled
    assert "상세하게" not in recalled


def test_explicit_preference_is_latest_wins_across_restart(tmp_path: Path) -> None:
    # Given: two explicit values for one preference are learned in sequence.
    memory_dir = tmp_path / "global"
    provider = GlobalMemoryProvider(memory_dir=str(memory_dir))
    provider.sync_turn("앞으로 답변은 상세하게 해줘", "알겠습니다")
    provider.sync_turn("이제부터 답변은 간결하게 해줘", "알겠습니다")

    # When: a fresh provider reloads durable preferences.
    recalled = GlobalMemoryProvider(memory_dir=str(memory_dir)).prefetch("새 작업을 시작해줘")

    # Then: the superseded value is absent after process restart.
    assert "[preference:response_detail] concise" in recalled
    assert "detailed" not in recalled


def test_learned_profile_cannot_override_explicit_user_preference(tmp_path: Path) -> None:
    # Given: an explicit preference is followed by contradictory inferred profile metadata.
    provider = GlobalMemoryProvider(memory_dir=str(tmp_path / "global"))
    provider.sync_turn("앞으로 답변은 한국어로 해줘", "알겠습니다")
    provider.sync_turn(
        "unrelated request",
        "response",
        metadata={"learned_preferences": ["영어 응답 선호"]},
    )

    # When: personalization memory is recalled.
    recalled = provider.prefetch("새 작업")

    # Then: explicit intent outranks a statistical inference.
    assert "[preference:response_language] ko" in recalled
    assert "[preference:response_language] en" not in recalled


def test_learned_profile_preference_replaces_same_authority_value(tmp_path: Path) -> None:
    # Given: the inferred dominant language changes over time.
    memory_dir = tmp_path / "global"
    provider = GlobalMemoryProvider(memory_dir=str(memory_dir))
    provider.sync_turn("u", "a", metadata={"learned_preferences": ["한국어 응답 선호"]})
    provider.sync_turn("u", "a", metadata={"learned_preferences": ["영어 응답 선호"]})

    # When: durable memory is reloaded.
    recalled = GlobalMemoryProvider(memory_dir=str(memory_dir)).prefetch("new task")

    # Then: one keyed inferred value remains instead of two conflicting strings.
    assert "[preference:response_language] en" in recalled
    assert "[preference:response_language] ko" not in recalled


def test_structured_learned_preferences_replace_without_prose_parsing(tmp_path: Path) -> None:
    # Given: the profile learner emits stable preference keys rather than display text.
    memory_dir = tmp_path / "global"
    provider = GlobalMemoryProvider(memory_dir=str(memory_dir))
    provider.sync_turn(
        "u",
        "a",
        metadata={"learned_preference_facts": {"response_detail": "detailed"}},
    )

    # When: a later profile observation changes the same keyed inference.
    provider.sync_turn(
        "u",
        "a",
        metadata={"learned_preference_facts": {"response_detail": "concise"}},
    )

    # Then: only the newest structured inferred value survives restart.
    recalled = GlobalMemoryProvider(memory_dir=str(memory_dir)).prefetch("new task")
    assert "[preference:response_detail] concise" in recalled
    assert "[preference:response_detail] detailed" not in recalled


def test_same_preference_is_deduplicated_across_global_and_episode(tmp_path: Path) -> None:
    # Given: the same explicit preference exists in durable and episodic stores.
    manager, global_memory = _preference_manager(tmp_path)
    global_memory.sync_turn("앞으로 답변은 간결하게 해줘", "알겠습니다")
    episodic = manager.providers[0]
    episodic.sync_turn("앞으로 답변은 간결하게 해줘", "알겠습니다")

    # When: memory is assembled for a later unrelated turn.
    recalled = manager.prefetch_all("앞으로 답변은 간결하게 해줘")

    # Then: one canonical fact replaces duplicate source records.
    assert recalled.count("concise") == 1
    assert "[memory_dedupe key=preference:response_detail" in recalled
    assert "[memory_conflict key=preference:response_detail" not in recalled
    assert "간결하게" not in recalled


def test_orchestrator_emits_structured_profile_preference_metadata() -> None:
    # Given: profile statistics have stable dominant values above the learning threshold.
    profile = {
        "stats": {
            "language_pref": {"korean": 4, "english": 1},
            "comm_style": {"concise": 3},
            "skill_level": {"expert": 3},
            "domain": {"backend": 5},
        },
    }
    orchestrator = SimpleNamespace(
        ctx=SimpleNamespace(user_model=SimpleNamespace(_profile=profile)),
    )

    # When: the completed turn prepares metadata for global memory sync.
    metadata = _extract_learned_preferences(orchestrator)

    # Then: persistence receives machine-readable facts instead of display prose.
    assert metadata == {
        "learned_preference_facts": {
            "response_language": "ko",
            "response_detail": "concise",
            "explanation_level": "advanced",
            "task_domain": "backend",
        },
    }


def test_explicit_preference_extraction_ignores_non_response_preferences() -> None:
    # Given: durable wording refers to code style rather than assistant responses.
    messages = (
        "From now on use English variable names",
        "I prefer concise variable names",
        "앞으로 상세한 문서를 작성해줘",
    )

    # When: each message crosses the preference extraction boundary.
    extracted = tuple(extract_explicit_preference_facts(message) for message in messages)

    # Then: none is promoted into response-style personalization.
    assert extracted == ({}, {}, {})
