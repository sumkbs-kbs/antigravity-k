import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from antigravity_k.api.server import app
from antigravity_k.config import config
from antigravity_k.engine.vault import VaultEngine
from antigravity_k.engine.vault_privacy_contracts import (
    VaultPrivacyAction,
    VaultPrivacyError,
    VaultPrivacyFailure,
    VaultPrivacyMutation,
)


class _MockMethod(Protocol):
    return_value: object
    call_args: object

    def __call__(self, *args: object, **kwargs: object) -> object: ...

    def assert_called_once(self) -> None: ...

    def assert_called_once_with(self, *args: object, **kwargs: object) -> None: ...


def _mock_method(mock: MagicMock, name: str) -> _MockMethod:
    return cast(_MockMethod, cast(object, getattr(mock, name)))


def _response_json(response: object) -> dict[str, object]:
    json_method = cast(Callable[[], object], cast(object, getattr(response, "json")))
    return cast(dict[str, object], json_method())


def _seed_vault(tmp_path: Path, content: str = "private payload") -> tuple[VaultEngine, Path]:
    vault = VaultEngine(str(tmp_path / "vault"), sync_rag=False)
    note = vault.vault_path / "private.md"
    _ = note.write_text(f"---\ntitle: Private\n---\n\n{content}\n", encoding="utf-8")
    _ = subprocess.run(["git", "add", "private.md"], cwd=vault.vault_path, check=True)
    _ = subprocess.run(
        ["git", "-c", "user.name=AGK Test", "-c", "user.email=test@agk.local", "commit", "-m", "seed"],
        cwd=vault.vault_path,
        check=True,
        capture_output=True,
    )
    return vault, note


def _authenticate(client: TestClient) -> None:
    if config.security.access_pin:
        client.headers.update({"X-Access-Pin": config.security.access_pin})


def test_vault_redact_rejects_missing_confirmation() -> None:
    # Given: an authenticated request without the explicit consent token.
    with TestClient(app) as client:
        if config.security.access_pin:
            client.headers.update({"X-Access-Pin": config.security.access_pin})

        # When: the caller requests an active-corpus redaction.
        response = client.post(
            "/api/memory/vault/redact",
            json={"paths": ["private.md"], "values": ["secret"]},
        )

    # Then: boundary parsing rejects it before any Vault mutation can run.
    assert response.status_code == 422


def test_vault_redact_rejects_empty_value() -> None:
    # Given: a confirmed request with an unsafe empty replacement target.
    with TestClient(app) as client:
        _authenticate(client)

        # When: the request crosses the API validation boundary.
        response = client.post(
            "/api/memory/vault/redact",
            json={
                "paths": ["private.md"],
                "values": [""],
                "confirmation": "REDACT_VAULT_ACTIVE_CORPUS",
            },
        )

    # Then: validation rejects it before the Vault dependency is resolved.
    assert response.status_code == 422


def test_vault_redact_replaces_values_and_preserves_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a committed Vault note containing an explicitly selected secret.
    vault, note = _seed_vault(tmp_path, "account secret-123")
    from antigravity_k.api.routes import vault_privacy

    monkeypatch.setattr(vault_privacy, "get_vault_engine", lambda: vault, raising=False)

    # When: the authenticated caller confirms an exact-value redaction.
    with TestClient(app) as client:
        if config.security.access_pin:
            client.headers.update({"X-Access-Pin": config.security.access_pin})
        response = client.post(
            "/api/memory/vault/redact",
            json={
                "paths": ["private.md"],
                "values": ["secret-123"],
                "confirmation": "REDACT_VAULT_ACTIVE_CORPUS",
            },
        )

    # Then: the active note is safe while the reported snapshot remains restorable.
    assert response.status_code == 200
    payload = _response_json(response)
    assert "secret-123" not in note.read_text(encoding="utf-8")
    assert "<REDACTED>" in note.read_text(encoding="utf-8")
    historical = subprocess.run(
        ["git", "show", f"{payload['snapshot_commit']}:private.md"],
        cwd=vault.vault_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "secret-123" in historical.stdout
    assert payload["history_retained_for_rollback"] is True


def test_vault_purge_removes_selected_note_and_preserves_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: one committed note selected for active-corpus removal.
    vault, note = _seed_vault(tmp_path)
    from antigravity_k.api.routes import vault_privacy

    monkeypatch.setattr(vault_privacy, "get_vault_engine", lambda: vault)

    # When: the caller supplies the purge-specific confirmation token.
    with TestClient(app) as client:
        _authenticate(client)
        response = client.post(
            "/api/memory/vault/purge",
            json={
                "paths": ["private.md"],
                "confirmation": "PURGE_VAULT_ACTIVE_CORPUS",
            },
        )

    # Then: the active file is gone and its pre-mutation snapshot is explicit.
    assert response.status_code == 200
    payload = _response_json(response)
    assert not note.exists()
    historical = subprocess.run(
        ["git", "show", f"{payload['snapshot_commit']}:private.md"],
        cwd=vault.vault_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "private payload" in historical.stdout
    assert payload["history_retained_for_rollback"] is True


def test_vault_restore_recovers_selected_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a safe temporary Vault whose current HEAD deleted a prior note.
    vault, note = _seed_vault(tmp_path)
    snapshot = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=vault.vault_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    note.unlink()
    _ = subprocess.run(["git", "add", "--all"], cwd=vault.vault_path, check=True)
    _ = subprocess.run(
        ["git", "commit", "-m", "remove note"],
        cwd=vault.vault_path,
        check=True,
        capture_output=True,
    )
    from antigravity_k.api.routes import vault_privacy
    from antigravity_k.knowledge import wiki as wiki_module

    monkeypatch.setattr(vault_privacy, "get_vault_engine", lambda: vault)
    vault.sync_rag = True
    vault.vector_store = MagicMock()
    vault.chunker = MagicMock()
    _mock_method(vault.chunker, "chunk_document").return_value = [
        {"id": "restored", "text": "private payload", "metadata": {}}
    ]
    wiki = MagicMock()
    monkeypatch.setattr(wiki_module, "LLMWiki", lambda: wiki)

    # When: the caller confirms restoring that exact Git snapshot.
    with TestClient(app) as client:
        _authenticate(client)
        response = client.post(
            "/api/memory/vault/restore",
            json={
                "snapshot_commit": snapshot,
                "paths": ["private.md"],
                "confirmation": "RESTORE_VAULT_SNAPSHOT",
            },
        )

    # Then: the selected snapshot becomes active and the note is recovered.
    assert response.status_code == 200
    assert _response_json(response)["restored"] is True
    assert note.exists()
    _mock_method(vault.vector_store, "delete_file_chunks_strict").assert_called_once_with("private.md")
    _mock_method(vault.vector_store, "upsert_chunks").assert_called_once()
    _mock_method(wiki, "add_entry").assert_called_once()


def test_default_memory_purge_does_not_touch_vault(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: an unrelated Vault note and a regular memory manager.
    _, note = _seed_vault(tmp_path)
    from antigravity_k.api.routes import system_api

    manager = MagicMock()
    _mock_method(manager, "clear").return_value = {"builtin": 1}
    monkeypatch.setattr(system_api, "_get_memory_manager", lambda: manager)
    monkeypatch.setattr(
        system_api,
        "get_vault_engine",
        lambda: pytest.fail("default purge must not access Vault"),
    )

    # When: the caller invokes the ordinary all-scope memory purge.
    with TestClient(app) as client:
        _authenticate(client)
        response = client.request("DELETE", "/api/memory", json={"scope": "all"})

    # Then: only the memory manager is cleared and the Vault note remains.
    assert response.status_code == 200
    _mock_method(manager, "clear").assert_called_once_with("all")
    assert note.exists()


def test_vault_redact_rolls_back_when_mutation_commit_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a committed secret and a simulated privacy commit failure.
    vault, note = _seed_vault(tmp_path, "rollback-secret")
    original_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=vault.vault_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    from antigravity_k.engine import vault_privacy

    def fail_commit(*_args: object, **_kwargs: object) -> str:
        raise VaultPrivacyError(VaultPrivacyFailure.GIT_FAILURE, "simulated commit failure")

    monkeypatch.setattr(vault_privacy, "_commit_mutation", fail_commit)

    # When: the service changes the file but cannot commit the mutation.
    with pytest.raises(VaultPrivacyError):
        _ = vault.apply_privacy_mutation(
            VaultPrivacyMutation(
                action=VaultPrivacyAction.REDACT,
                paths=("private.md",),
                values=("rollback-secret",),
            ),
        )

    # Then: both the file and Git HEAD are restored to the pre-mutation snapshot.
    current_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=vault.vault_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert "rollback-secret" in note.read_text(encoding="utf-8")
    assert current_head == original_head


def test_vault_redact_replaces_rag_and_wiki_derivatives(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a Vault note mirrored into RAG and Wiki derivative stores.
    vault, _ = _seed_vault(tmp_path, "derived-secret")
    vault.sync_rag = True
    vault.vector_store = MagicMock()
    vault.chunker = MagicMock()
    _mock_method(vault.chunker, "chunk_document").return_value = [
        {"id": "safe", "text": "<REDACTED>", "metadata": {}}
    ]
    wiki = MagicMock()
    from antigravity_k.knowledge import wiki as wiki_module

    monkeypatch.setattr(wiki_module, "LLMWiki", lambda: wiki)

    # When: exact-value redaction updates the active Vault corpus.
    _ = vault.apply_privacy_mutation(
        VaultPrivacyMutation(
            action=VaultPrivacyAction.REDACT,
            paths=("private.md",),
            values=("derived-secret",),
        ),
    )

    # Then: old derivatives are removed and only redacted content is reindexed.
    source_url = str(vault.vault_path / "private.md")
    _mock_method(vault.vector_store, "delete_file_chunks_strict").assert_called_once_with("private.md")
    _mock_method(vault.vector_store, "upsert_chunks").assert_called_once()
    _mock_method(wiki, "delete_vault_sources").assert_called_once_with((source_url,))
    _mock_method(wiki, "add_entry").assert_called_once()
    assert "derived-secret" not in str(_mock_method(vault.chunker, "chunk_document").call_args)
    assert "derived-secret" not in str(_mock_method(wiki, "add_entry").call_args)
