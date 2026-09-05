from collections.abc import Iterator
from pathlib import Path
from typing import cast, override
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from antigravity_k.engine.global_memory_provider import GlobalMemoryProvider
from antigravity_k.engine.memory_contracts import (
    JsonValue,
    MemoryFact,
    MemoryFactAuthority,
    MemoryProvider,
)
from antigravity_k.engine.memory_provider import EpisodicMemoryProvider, MemoryManager
from antigravity_k.engine.preference_memory import PreferenceFactStore
from antigravity_k.engine.project_memory import ProjectMemoryProvider


class _NoDeleteProvider(MemoryProvider):
    @property
    @override
    def name(self) -> str:
        return "plain"

    @override
    def prefetch(self, query: str, session_id: str | None = None) -> str:
        return ""

    @override
    def sync_turn(
        self,
        user_message: str,
        assistant_response: str,
        *,
        metadata: dict[str, JsonValue] | None = None,
    ) -> None:
        return None


class _CallSpy:
    def __init__(self, return_value: object = None) -> None:
        self.return_value: object = return_value
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def __call__(self, *args: object, **kwargs: object) -> object:
        self.calls.append((args, kwargs))
        return self.return_value

    def assert_called_with(self, *args: object, **kwargs: object) -> None:
        assert self.calls and self.calls[-1] == (args, kwargs)


class _MemoryManagerDouble:
    def __init__(self, ranked_facts: list[tuple[MemoryFact, float]]) -> None:
        self.ranked_facts: _CallSpy = _CallSpy(ranked_facts)
        self.delete_entry: _CallSpy = _CallSpy(True)


def test_project_delete_entry(tmp_path: Path) -> None:
    provider = ProjectMemoryProvider(tmp_path)
    provider.sync_turn("프로젝트 결정: db = postgresql", "")
    provider.sync_turn("프로젝트 사실: api_style = rest", "")
    assert provider.delete_entry("decision:db") is True
    facts = {fact.key for fact in provider.authoritative_facts()}
    assert not any(key.endswith(":db") for key in facts)
    assert any(key.endswith(":api_style") for key in facts)
    assert provider.delete_entry("decision:db") is False
    assert provider.delete_entry("api_style") is True
    assert provider.delete_entry("missing") is False
    assert provider.delete_entry("bogus:key") is False


def test_preference_store_delete(tmp_path: Path) -> None:
    store = PreferenceFactStore(tmp_path)
    assert store.update("lang", "python", MemoryFactAuthority.DURABLE_PREFERENCE) is True
    assert store.delete("lang") is True
    assert store.get("lang") is None
    assert store.delete("lang") is False


def test_global_delete_entry(tmp_path: Path) -> None:
    provider = GlobalMemoryProvider(memory_dir=str(tmp_path))
    provider.set_identity_fact("name", "Alice")
    provider.sync_turn(
        "plain message",
        "",
        metadata={"learned_preference_facts": {"task_domain": "backend engineering"}},
    )
    assert provider.delete_entry("identity:name") is True
    assert provider.get_identity_fact("name") is None
    assert provider.delete_entry("identity:name") is False
    assert provider.delete_entry("preference:task_domain") is True
    assert provider.get_preference_fact("task_domain") is None
    assert provider.delete_entry("preference:task_domain") is False
    assert provider.delete_entry("garbage") is False


def test_global_delete_category_entry(tmp_path: Path) -> None:
    provider = GlobalMemoryProvider(memory_dir=str(tmp_path))
    provider.add_fact("uses chroma for vector search")
    assert provider.delete_entry("category:facts:uses chroma for vector search") is True
    assert provider.get_all()["facts"] == []
    assert provider.delete_entry("category:facts:missing") is False
    assert provider.delete_entry("category:patterns:anything") is False


def test_episodic_delete_entry(tmp_path: Path) -> None:
    provider = EpisodicMemoryProvider(persist_dir=str(tmp_path))
    provider.sync_turn("first question", "first answer")
    provider.sync_turn("second question", "second answer")
    assert provider.delete_entry("episode:0") is True
    remaining = provider.export()
    assert len(remaining) == 1
    assert remaining[0]["user"] == "second question"
    assert provider.delete_entry("episode:5") is False
    assert provider.delete_entry("episode:abc") is False
    assert provider.delete_entry("other") is False
    assert provider.delete_entry("episode:0") is True
    assert provider.export() == []


def test_manager_delete_entry_routes(tmp_path: Path) -> None:
    manager = MemoryManager(project_root=str(tmp_path))
    global_provider = GlobalMemoryProvider(memory_dir=str(tmp_path / "global"))
    manager.add_provider(global_provider)
    manager.add_provider(_NoDeleteProvider())
    global_provider.set_identity_fact("name", "Alice")
    assert manager.delete_entry("global", "identity:name") is True
    assert manager.delete_entry("global", "identity:name") is False
    assert manager.delete_entry("plain", "anything") is False
    assert manager.delete_entry("unknown", "anything") is False


def test_manager_ranked_facts(tmp_path: Path) -> None:
    manager = MemoryManager(project_root=str(tmp_path))
    project_provider = ProjectMemoryProvider(tmp_path)
    project_provider.sync_turn("프로젝트 결정: db = postgresql", "")
    global_provider = GlobalMemoryProvider(memory_dir=str(tmp_path / "global"))
    global_provider.set_identity_fact("name", "Alice")
    manager.add_provider(project_provider)
    manager.add_provider(global_provider)
    ranked = manager.ranked_facts()
    assert len(ranked) == 2
    assert ranked[0][0].key.startswith("identity:")
    assert ranked[0][1] > ranked[1][1]
    assert len(manager.ranked_facts(top_k=1)) == 1


@pytest.fixture
def memory_client() -> Iterator[tuple[TestClient, _MemoryManagerDouble]]:
    from antigravity_k.api.server import app
    from antigravity_k.config import config

    fake_manager = _MemoryManagerDouble([
        (
            MemoryFact(
                key="identity:name",
                value="Alice",
                source="global",
                scope="global",
                authority=MemoryFactAuthority.DURABLE_IDENTITY,
                observed_at=1000.0,
            ),
            81.25,
        ),
    ])
    with patch("antigravity_k.api.routes.system_api._get_memory_manager", return_value=fake_manager):
        with TestClient(app) as client:
            if config.security.access_pin:
                client.headers.update({"X-Access-Pin": config.security.access_pin})
            yield client, fake_manager


def test_ranked_memory_facts_endpoint(memory_client: tuple[TestClient, _MemoryManagerDouble]) -> None:
    client, fake_manager = memory_client
    response = client.get("/api/memory/ranked")
    assert response.status_code == 200
    body = cast(dict[str, object], response.json())
    facts = cast(list[dict[str, object]], body["facts"])
    assert len(facts) == 1
    fact = facts[0]
    assert fact["key"] == "identity:name"
    assert fact["authority"] == 80
    assert fact["score"] == 81.25
    fake_manager.ranked_facts.assert_called_with(top_k=20)


def test_ranked_memory_facts_clamps_top_k(memory_client: tuple[TestClient, _MemoryManagerDouble]) -> None:
    client, fake_manager = memory_client
    _ = client.get("/api/memory/ranked?top_k=0")
    fake_manager.ranked_facts.assert_called_with(top_k=1)
    _ = client.get("/api/memory/ranked?top_k=999")
    fake_manager.ranked_facts.assert_called_with(top_k=100)


def test_delete_memory_entry_endpoint(memory_client: tuple[TestClient, _MemoryManagerDouble]) -> None:
    client, fake_manager = memory_client
    response = client.delete("/api/memory/entries?provider=project&key=decision:db")
    assert response.status_code == 200
    assert response.json() == {"provider": "project", "key": "decision:db", "deleted": True}
    fake_manager.delete_entry.assert_called_with("project", "decision:db")


def test_delete_memory_entry_not_found(memory_client: tuple[TestClient, _MemoryManagerDouble]) -> None:
    client, fake_manager = memory_client
    fake_manager.delete_entry.return_value = False
    response = client.delete("/api/memory/entries?provider=global&key=identity:missing")
    assert response.status_code == 200
    assert response.json()["deleted"] is False
