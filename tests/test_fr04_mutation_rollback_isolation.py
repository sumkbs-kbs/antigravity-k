"""FR-04 regression: RSI rollback must only restore mutation-owned writes.

Fixture follows the plan (RP-04): a temp git repo with committed A and B,
a user-dirty B, and a new untracked C. The mutation owns only A.

- failing mutation restores A byte-for-byte; dirty B and untracked C untouched
- a concurrent foreign edit to an owned file is preserved and reported
- a successful mutation keeps only A's new content
- rollback of an empty-ownership snapshot touches nothing
- duplicate rollback calls never raise
- the whole-tree checkout path (``git checkout <commit> -- .``) is gone
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from antigravity_k.engine.meta_architect import ArchitectureProposal, MetaArchitect
from antigravity_k.engine.rsi_sandbox import RSISandbox, ValidationResult


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _run(["git", "init", "-q"], root)
    _run(["git", "config", "user.email", "t@example.com"], root)
    _run(["git", "config", "user.name", "tester"], root)
    (root / "A.py").write_text("A = 'committed'\n", encoding="utf-8")
    (root / "B.py").write_text("B = 'committed'\n", encoding="utf-8")
    _run(["git", "add", "."], root)
    _run(["git", "commit", "-q", "-m", "init"], root)
    # user dirty change on B and a new untracked file C
    (root / "B.py").write_text("B = 'user-dirty'\n", encoding="utf-8")
    (root / "C.py").write_text("C = 'untracked'\n", encoding="utf-8")
    return root


def _run(argv: list[str], cwd: Path) -> None:
    result = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


@pytest.fixture()
def sandbox(repo: Path) -> RSISandbox:
    return RSISandbox(project_root=str(repo), audit_dir=str(repo / ".audit"))


def test_failing_mutation_restores_only_owned_a(repo: Path, sandbox: RSISandbox) -> None:
    with pytest.raises(RuntimeError):
        with sandbox.safe_mutation("own_A_fail"):
            sandbox.write_owned(repo / "A.py", "A = 'mutated'\n")
            raise RuntimeError("validation failed")

    assert (repo / "A.py").read_text(encoding="utf-8") == "A = 'committed'\n"
    assert (repo / "B.py").read_text(encoding="utf-8") == "B = 'user-dirty'\n"
    assert (repo / "C.py").read_text(encoding="utf-8") == "C = 'untracked'\n"
    # dirty/untracked survive in git terms too
    status = subprocess.run(["git", "status", "--porcelain"], cwd=str(repo), capture_output=True, text=True).stdout
    assert " M B.py" in status
    assert "?? C.py" in status


def test_new_owned_file_removed_on_failure(repo: Path, sandbox: RSISandbox) -> None:
    new_file = repo / "prompt_draft.md"
    with pytest.raises(RuntimeError):
        with sandbox.safe_mutation("own_new_fail"):
            sandbox.write_owned(new_file, "draft\n")
            raise RuntimeError("fail")

    assert not new_file.exists()
    assert (repo / "B.py").read_text(encoding="utf-8") == "B = 'user-dirty'\n"


def test_originally_empty_owned_file_restored_empty(repo: Path, sandbox: RSISandbox) -> None:
    empty = repo / "empty_prompt.md"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(RuntimeError):
        with sandbox.safe_mutation("own_empty_fail"):
            sandbox.write_owned(empty, "filled\n")
            raise RuntimeError("fail")

    assert empty.exists()
    assert empty.read_text(encoding="utf-8") == ""


def test_foreign_edit_to_owned_file_preserved_as_conflict(repo: Path, sandbox: RSISandbox) -> None:
    with pytest.raises(RuntimeError):
        with sandbox.safe_mutation("own_conflict"):
            sandbox.write_owned(repo / "A.py", "A = 'mutated'\n")
            # concurrent worker rewrites the same file after our owned write
            (repo / "A.py").write_text("A = 'foreign-edit'\n", encoding="utf-8")
            raise RuntimeError("fail")

    assert (repo / "A.py").read_text(encoding="utf-8") == "A = 'foreign-edit'\n"


def test_unowned_foreign_change_never_rolled_back(repo: Path, sandbox: RSISandbox) -> None:
    with pytest.raises(RuntimeError):
        with sandbox.safe_mutation("no_owned_writes"):
            # mutation writes nothing owned; a user edits B meanwhile
            (repo / "B.py").write_text("B = 'changed-during-mutation'\n", encoding="utf-8")
            raise RuntimeError("fail")

    assert (repo / "B.py").read_text(encoding="utf-8") == "B = 'changed-during-mutation'\n"


def test_successful_mutation_keeps_owned_change_only(repo: Path, sandbox: RSISandbox) -> None:
    with sandbox.safe_mutation("own_success"):
        sandbox.write_owned(repo / "A.py", "A = 'improved'\n")

    assert (repo / "A.py").read_text(encoding="utf-8") == "A = 'improved'\n"
    assert (repo / "B.py").read_text(encoding="utf-8") == "B = 'user-dirty'\n"
    assert (repo / "C.py").read_text(encoding="utf-8") == "C = 'untracked'\n"


def test_duplicate_rollback_is_safe(repo: Path, sandbox: RSISandbox) -> None:
    snapshot = None
    with pytest.raises(RuntimeError):
        with sandbox.safe_mutation("dup") as snap:
            sandbox.write_owned(repo / "A.py", "A = 'mutated'\n")
            snapshot = snap
            raise RuntimeError("fail")
    assert snapshot is not None
    # second, out-of-band rollback call must not raise or corrupt
    assert sandbox.rollback_to(snapshot) is True
    assert (repo / "A.py").read_text(encoding="utf-8") == "A = 'committed'\n"


def test_delegated_meta_architect_write_rolls_back_without_touching_user_files(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine_dir = repo / "src" / "antigravity_k" / "engine"
    engine_dir.mkdir(parents=True)
    target = engine_dir / "owned.py"
    target.write_text("value = 'committed'\n", encoding="utf-8")
    _run(["git", "add", "src/antigravity_k/engine/owned.py"], repo)
    _run(["git", "commit", "-q", "-m", "add owned engine file"], repo)

    monkeypatch.chdir(repo)
    architect = MetaArchitect(project_root=str(repo))
    proposal = ArchitectureProposal("delegated", "test", ["owned.py"], "test", "test")
    monkeypatch.setattr(architect, "_generate_with_self_reward", lambda *_: "value = 'mutated'\n")
    monkeypatch.setattr(
        RSISandbox,
        "validate_mutation",
        lambda *_: {"ast": ValidationResult.PASS, "tests": ValidationResult.FAIL},
    )

    assert architect.execute_proposal(proposal) is False
    assert target.read_text(encoding="utf-8") == "value = 'committed'\n"
    assert (repo / "B.py").read_text(encoding="utf-8") == "B = 'user-dirty'\n"
    assert (repo / "C.py").read_text(encoding="utf-8") == "C = 'untracked'\n"


def test_no_whole_tree_checkout_commands_in_rollback(
    repo: Path, sandbox: RSISandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The shared-checkout recovery commands must never run during rollback."""
    forbidden = {"checkout", "reset", "clean"}
    calls: list[list[str]] = []

    real_run = subprocess.run

    def guard(*args, **kwargs):  # noqa: ANN002, ANN003
        argv = args[0] if args else kwargs.get("args", [])
        if argv and argv[0] == "git":
            calls.append(list(argv))
            assert not (set(forbidden) & set(argv)), f"forbidden git recovery command: {argv}"
        return real_run(*args, **kwargs)

    monkeypatch.setattr("antigravity_k.engine.rsi_sandbox.subprocess.run", guard)
    with pytest.raises(RuntimeError):
        with sandbox.safe_mutation("guard"):
            sandbox.write_owned(repo / "A.py", "A = 'mutated'\n")
            raise RuntimeError("fail")
    assert (repo / "A.py").read_text(encoding="utf-8") == "A = 'committed'\n"
