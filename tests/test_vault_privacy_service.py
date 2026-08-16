import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from antigravity_k.engine.vault import VaultEngine
from antigravity_k.engine.vault_privacy import (
    VaultPrivacyAction,
    VaultPrivacyError,
    VaultPrivacyFailure,
    VaultPrivacyMutation,
)


def _seed_vault(tmp_path: Path, content: str) -> tuple[VaultEngine, Path]:
    vault = VaultEngine(str(tmp_path / "vault"), sync_rag=False)
    note = vault.vault_path / "private.md"
    note.write_text(f"---\ntitle: Private\n---\n\n{content}\n", encoding="utf-8")
    subprocess.run(["git", "add", "private.md"], cwd=vault.vault_path, check=True)
    subprocess.run(
        ["git", "-c", "user.name=AGK Test", "-c", "user.email=test@agk.local", "commit", "-m", "seed"],
        cwd=vault.vault_path,
        check=True,
        capture_output=True,
    )
    return vault, note


def test_vault_redact_restores_derivatives_when_commit_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: derivative stores and a Git failure after their redacted update.
    vault, note = _seed_vault(tmp_path, "rollback-secret")
    vault.sync_rag = True
    vault.vector_store = MagicMock()
    vault.chunker = MagicMock(side_effect=lambda *_args: [])
    vault.chunker.chunk_document.side_effect = lambda _path, _metadata, content: [
        {"id": content, "text": content, "metadata": {}}
    ]
    wiki = MagicMock()
    from antigravity_k.engine import vault_privacy
    from antigravity_k.knowledge import wiki as wiki_module

    monkeypatch.setattr(wiki_module, "LLMWiki", lambda: wiki)

    def fail_commit(*_args: object, **_kwargs: object) -> str:
        raise VaultPrivacyError(VaultPrivacyFailure.GIT_FAILURE, "simulated commit failure")

    monkeypatch.setattr(vault_privacy, "_commit_mutation", fail_commit)

    # When: redaction reaches the failed mutation commit.
    with pytest.raises(VaultPrivacyError):
        vault.apply_privacy_mutation(
            VaultPrivacyMutation(
                action=VaultPrivacyAction.REDACT,
                paths=("private.md",),
                values=("rollback-secret",),
            ),
        )

    # Then: raw and derivative stores end with the restored original content.
    assert "rollback-secret" in note.read_text(encoding="utf-8")
    assert "rollback-secret" in vault.chunker.chunk_document.call_args.args[2]
    assert "rollback-secret" in wiki.add_entry.call_args.kwargs["content"]


def test_vault_privacy_refuses_unsafe_restore_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a Vault path that the existing hard-reset safety policy rejects.
    vault, note = _seed_vault(tmp_path, "safety-secret")
    monkeypatch.setattr(vault, "_is_safe_restore_target", lambda: False)

    # When: a privacy mutation would require rollback capability.
    with pytest.raises(VaultPrivacyError) as caught:
        vault.apply_privacy_mutation(
            VaultPrivacyMutation(
                action=VaultPrivacyAction.PURGE,
                paths=("private.md",),
            ),
        )

    # Then: mutation is refused before touching the selected note.
    assert caught.value.failure is VaultPrivacyFailure.UNSAFE_VAULT
    assert note.exists()


def test_vault_restore_rejects_missing_snapshot_path_before_head_moves(tmp_path: Path) -> None:
    # Given: an older snapshot without the requested derivative path.
    vault, _ = _seed_vault(tmp_path, "snapshot content")
    snapshot = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=vault.vault_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    current = vault.vault_path / "current.md"
    current.write_text("current", encoding="utf-8")
    subprocess.run(["git", "add", "current.md"], cwd=vault.vault_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "current head"],
        cwd=vault.vault_path,
        check=True,
        capture_output=True,
    )
    current_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=vault.vault_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    # When: restore names a path absent from the selected snapshot.
    with pytest.raises(VaultPrivacyError) as caught:
        vault.restore_privacy_snapshot(snapshot, ("missing.md",))

    # Then: validation fails without changing the active Git HEAD.
    after = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=vault.vault_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert caught.value.failure is VaultPrivacyFailure.MISSING_NOTE
    assert after == current_head
    assert current.exists()


def test_vault_privacy_rejects_case_variant_internal_path(tmp_path: Path) -> None:
    # Given: a case-variant path that targets the internal Git directory.
    vault, _ = _seed_vault(tmp_path, "safe")

    # When: the path enters the privacy mutation boundary.
    with pytest.raises(VaultPrivacyError) as caught:
        vault.apply_privacy_mutation(
            VaultPrivacyMutation(
                action=VaultPrivacyAction.PURGE,
                paths=(".Git/private.md",),
            ),
        )

    # Then: it is classified as an invalid path rather than a missing note.
    assert caught.value.failure is VaultPrivacyFailure.INVALID_PATH


def test_vault_rollback_leaves_unselected_untracked_note_untracked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: an unrelated untracked note beside a selected committed note.
    vault, _ = _seed_vault(tmp_path, "selected-secret")
    unrelated = vault.vault_path / "unrelated.md"
    unrelated.write_text("unrelated draft", encoding="utf-8")
    from antigravity_k.engine import vault_privacy

    def fail_commit(*_args: object, **_kwargs: object) -> str:
        raise VaultPrivacyError(VaultPrivacyFailure.GIT_FAILURE, "simulated commit failure")

    monkeypatch.setattr(vault_privacy, "_commit_mutation", fail_commit)

    # When: selected-note redaction rolls back after a commit failure.
    with pytest.raises(VaultPrivacyError):
        vault.apply_privacy_mutation(
            VaultPrivacyMutation(
                action=VaultPrivacyAction.REDACT,
                paths=("private.md",),
                values=("selected-secret",),
            ),
        )

    # Then: the unrelated draft remains present and outside Git tracking.
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "unrelated.md"],
        cwd=vault.vault_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert unrelated.read_text(encoding="utf-8") == "unrelated draft"
    assert tracked.returncode != 0


def test_vault_restore_preserves_unselected_files_and_creates_commit(tmp_path: Path) -> None:
    # Given: a purge commit plus newer tracked and untracked unrelated notes.
    vault, selected = _seed_vault(tmp_path, "recover me")
    snapshot = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=vault.vault_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    selected.unlink()
    tracked = vault.vault_path / "tracked.md"
    tracked.write_text("tracked current", encoding="utf-8")
    subprocess.run(["git", "add", "--all"], cwd=vault.vault_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "purge and continue"],
        cwd=vault.vault_path,
        check=True,
        capture_output=True,
    )
    before_restore = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=vault.vault_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    untracked = vault.vault_path / "draft.md"
    untracked.write_text("draft current", encoding="utf-8")

    # When: only the selected note is restored from the privacy snapshot.
    restored = vault.restore_privacy_snapshot(snapshot, ("private.md",))

    # Then: unrelated files survive and Git records a new restore commit.
    after_restore = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=vault.vault_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert restored is True
    assert "recover me" in selected.read_text(encoding="utf-8")
    assert tracked.read_text(encoding="utf-8") == "tracked current"
    assert untracked.read_text(encoding="utf-8") == "draft current"
    assert after_restore not in {snapshot, before_restore}
