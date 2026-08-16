import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from antigravity_k.engine.memory_provider import (
    EpisodicMemoryProvider,
    GlobalMemoryProvider,
    MemoryManager,
    WorkingMemoryBuffer,
)
from antigravity_k.engine.session_manager import SessionManager


def test_memory_export_redacts_secret_values(tmp_path: Path):
    secret = "API_" + "KEY=sk-proj-" + "a" * 24
    session = SessionManager(base_dir=str(tmp_path / "sessions"))
    session.start_session(project_path=str(tmp_path), resume=False)
    session.add_turn([{"role": "user", "content": secret}])
    episodic = EpisodicMemoryProvider(persist_dir=str(tmp_path / "episodic"))
    episodic.sync_turn(secret, "answer")
    global_memory = GlobalMemoryProvider(memory_dir=str(tmp_path / "global"))
    global_memory.add_preference(secret)
    working = WorkingMemoryBuffer()
    working.sync_turn(secret, "answer")

    manager = MemoryManager()
    from antigravity_k.engine.memory_provider import BuiltinMemoryProvider

    manager.add_provider(BuiltinMemoryProvider(session))
    manager.add_provider(episodic)
    manager.add_provider(working)
    manager.add_provider(global_memory)

    exported = manager.export("all")

    assert secret not in json.dumps(exported, ensure_ascii=False)
    assert "<REDACTED>" in json.dumps(exported, ensure_ascii=False)


def test_global_identity_is_exported_and_redacted_on_disk(tmp_path: Path):
    secret = "TOKEN=identity-secret-123456"
    memory_dir = tmp_path / "global"
    provider = GlobalMemoryProvider(memory_dir=str(memory_dir))
    provider.set_identity_fact("private_token", secret)

    exported = provider.export("global")
    changed = provider.redact("global")
    reloaded = GlobalMemoryProvider(memory_dir=str(memory_dir))

    assert {"category": "identity", "key": "private_token", "value": secret} in exported
    assert changed == 1
    assert reloaded.get_identity_fact("private_token") == "TOKEN=<REDACTED>"


def test_global_clear_removes_identity_across_restart(tmp_path: Path):
    memory_dir = tmp_path / "global"
    provider = GlobalMemoryProvider(memory_dir=str(memory_dir))
    provider.sync_turn("내 이름은 김철수야", "안녕하세요")

    deleted = provider.clear("global")
    reloaded = GlobalMemoryProvider(memory_dir=str(memory_dir))

    assert deleted == 1
    assert reloaded.get_identity_fact("name") is None
    assert "김철수" not in reloaded.prefetch("날씨")


def test_global_retention_expires_old_identity_and_keeps_recent_identity(tmp_path: Path):
    old_dir = tmp_path / "old-global"
    old_provider = GlobalMemoryProvider(memory_dir=str(old_dir))
    old_provider.set_identity_fact("name", "Old Name")
    os.utime(old_dir / "identity.json", (1, 1))

    recent_dir = tmp_path / "recent-global"
    recent_provider = GlobalMemoryProvider(memory_dir=str(recent_dir))
    recent_provider.set_identity_fact("name", "Recent Name")

    assert old_provider.apply_retention(1) == 1
    assert recent_provider.apply_retention(1) == 0
    assert GlobalMemoryProvider(memory_dir=str(old_dir)).get_identity_fact("name") is None
    assert GlobalMemoryProvider(memory_dir=str(recent_dir)).get_identity_fact("name") == "Recent Name"


def test_preference_fact_is_exported_and_redacted_on_disk(tmp_path: Path):
    # Given: a structured task-domain preference contains a secret-like value.
    secret = "TOKEN=preference-secret-123456"
    memory_dir = tmp_path / "global"
    provider = GlobalMemoryProvider(memory_dir=str(memory_dir))
    provider.sync_turn(
        "u",
        "a",
        metadata={"learned_preference_facts": {"task_domain": secret}},
    )

    # When: the global compliance lifecycle exports and redacts memory.
    exported = provider.export("global")
    changed = provider.redact("global")
    reloaded = GlobalMemoryProvider(memory_dir=str(memory_dir))

    # Then: the typed fact is visible to export but redacted durably on disk.
    assert any(item.get("category") == "preference_fact" and item.get("value") == secret for item in exported)
    assert changed == 1
    assert reloaded.get_preference_fact("task_domain") == "TOKEN=<REDACTED>"


def test_global_clear_removes_preference_facts_across_restart(tmp_path: Path):
    # Given: one durable explicit preference exists.
    memory_dir = tmp_path / "global"
    provider = GlobalMemoryProvider(memory_dir=str(memory_dir))
    provider.sync_turn("앞으로 답변은 간결하게 해줘", "알겠습니다")

    # When: global memory is cleared.
    deleted = provider.clear("global")
    reloaded = GlobalMemoryProvider(memory_dir=str(memory_dir))

    # Then: the keyed preference is gone after restart.
    assert deleted == 1
    assert reloaded.get_preference_fact("response_detail") is None


def test_global_retention_expires_old_preference_facts(tmp_path: Path):
    # Given: an old durable preference file.
    memory_dir = tmp_path / "global"
    provider = GlobalMemoryProvider(memory_dir=str(memory_dir))
    provider.sync_turn("앞으로 답변은 상세하게 해줘", "알겠습니다")
    os.utime(memory_dir / "preference_facts.json", (1, 1))

    # When: retention removes data older than one day.
    deleted = provider.apply_retention(1)

    # Then: the preference stays removed after restart.
    assert deleted == 1
    assert GlobalMemoryProvider(memory_dir=str(memory_dir)).get_preference_fact("response_detail") is None


def test_episodic_recall_survives_korean_particle_variation(tmp_path: Path):
    # Given: a prior turn where the user stated a personal fact (subject particle 은).
    episodic = EpisodicMemoryProvider(persist_dir=str(tmp_path / "episodic"))
    episodic.sync_turn("내 이름은 김철수야", "안녕하세요 김철수님.")

    # When: a later turn asks the same concept with a different particle (이).
    recall = episodic.prefetch("내 이름이 뭐야?")

    # Then: the stored fact is recalled despite the particle mismatch, so a multi-turn
    # agent can answer "김철수" instead of forgetting the user's name.
    assert "김철수" in recall


def test_episodic_consolidation_protects_durable_preference_from_decay(tmp_path: Path):
    # Given: a small-capacity memory that already holds a durable user preference.
    episodic = EpisodicMemoryProvider(max_episodes=5, persist_dir=str(tmp_path / "episodic"))
    episodic.sync_turn("나는 들여쓰기에 탭을 사용해", "탭 스타일로 맞추겠습니다.")

    # When: enough filler episodes accumulate to trigger consolidation (capacity + 10%).
    for i in range(8):
        episodic.sync_turn(f"filler turn {i}", f"filler answer {i}")

    # Then: the stated preference survives consolidation because durable-fact episodes
    # are importance-boosted and not evicted as mere low-recency noise.
    recall = episodic.prefetch("들여쓰기")
    assert "탭" in recall


def test_memory_redact_updates_persistent_providers(tmp_path: Path):
    secret = "TOKEN=supersecret123456"
    session = SessionManager(base_dir=str(tmp_path / "sessions"))
    session.start_session(project_path=str(tmp_path), resume=False)
    session.add_turn([{"role": "user", "content": secret}])
    episodic = EpisodicMemoryProvider(persist_dir=str(tmp_path / "episodic"))
    episodic.sync_turn(secret, "answer")
    manager = MemoryManager()
    from antigravity_k.engine.memory_provider import BuiltinMemoryProvider

    manager.add_provider(BuiltinMemoryProvider(session))
    manager.add_provider(episodic)

    report = manager.redact("all")

    assert report["builtin"] > 0
    assert report["episodic"] > 0
    assert secret not in json.dumps(session.export_memory("all"), ensure_ascii=False)
    assert secret not in json.dumps(episodic.export("all"), ensure_ascii=False)


def test_session_retention_removes_only_old_inactive_sessions(tmp_path: Path):
    base_dir = tmp_path / "sessions"
    manager = SessionManager(base_dir=str(base_dir))
    manager.start_session(project_path=str(tmp_path / "old"), resume=False)
    old_path = base_dir / f"{manager._session_id}.json"
    manager.start_session(project_path=str(tmp_path / "current"), resume=False)
    os.utime(old_path, (1, 1))

    assert manager.apply_retention(1) == 1
    assert not old_path.exists()
    assert list(base_dir.glob("*.json"))


def test_vault_export_excludes_assets_by_default_and_redacts_opt_in(tmp_path: Path):
    from antigravity_k.engine.vault import VaultEngine

    secret = "TOKEN=supersecret123456"
    vault = VaultEngine(str(tmp_path / "vault"), sync_rag=False)
    note_path = vault.vault_path / "private.md"
    note_path.write_text(f"---\ntitle: private\n---\n{secret}", encoding="utf-8")

    metadata_only = vault.export_notes()
    redacted = vault.export_notes(include_assets=True, redact=True)

    assert "content" not in metadata_only[0]
    assert secret not in json.dumps(redacted, ensure_ascii=False)
    assert "<REDACTED>" in redacted[0]["content"]


@pytest.mark.asyncio
async def test_memory_compliance_routes_return_audited_contract(monkeypatch):
    from antigravity_k.api.routes import system_api

    manager = MagicMock()
    manager.export.return_value = {"scope": "all", "providers": {}}
    manager.redact.return_value = {"builtin": 2}
    manager.apply_retention.return_value = {"builtin": 1}
    audit = MagicMock()
    monkeypatch.setattr(system_api, "_get_memory_manager", lambda: manager)
    monkeypatch.setattr(system_api, "get_audit_logger", lambda: audit)
    monkeypatch.setattr(system_api, "get_vault_engine", lambda: None)

    exported = await system_api.export_memory()

    class Request:
        async def json(self):
            return {"scope": "all"}

    redacted = await system_api.redact_memory(Request())

    class RetentionRequest:
        async def json(self):
            return {"max_age_days": 30}

    retained = await system_api.apply_memory_retention(RetentionRequest())

    assert exported["vault"]["included"] is False
    assert redacted["changed"] == {"builtin": 2}
    assert retained["deleted"] == {"builtin": 1}
    assert [call.args[0] for call in audit.log_event.call_args_list] == [
        "memory_export",
        "memory_redact",
        "memory_retention",
    ]
