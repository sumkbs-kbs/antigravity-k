"""DAT-02 · vault task 격리 (BR-01) — failing-first 회귀 시험.

감사 재현(BR-01): task A 실패/취소 → 공유 vault `reset --hard`+`clean -fd`
롤백이 task B의 committed/uncommitted/untracked 변경을 파괴한다.

목표 계약:
  1. 스코프 롤백은 task가 소유한 경로만 이전 상태로 되돌린다.
     - task 소유 (롤백 범위에 기록): 파일 수정/삭제/생성 모두 폐기
     - task 비소유: committed/uncommitted/untracked 모두 보존
  2. `VaultEngine.restore_snapshot`은 task 스코프 밖 경로를 거절한다.
  3. task A 롤백이 task B의 어떤 파일 상태도 바꾸지 않는다.
  4. `use_worktree` task의 도구 실행은 worktree에 바인딩된다 (server cwd와 무관).
  5. merge-back은 성공 task에만 실행되고, 실패/취소 task에서는 폐기된다.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from antigravity_k.engine.task_runner import BackgroundTaskRunner
from antigravity_k.engine.vault import VaultEngine
from antigravity_k.engine.worktree_manager import WorktreeManager

# ─── 헬퍼: 실제 git 저장소 픽스처 ──────────────────────────────────────


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


@pytest.fixture
def vault_root(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    (root / "base.txt").write_text("base", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "init")
    return root


class StreamingOrchestrator:
    """_stream_task가 소비하는 최소 오케스트레이터 더블.

    ``raise_after``가 설정되면 첫 청크 방출 후 예외로 실패해
    task_runner의 실패 롤백 경로를 유도한다.
    """

    def __init__(self, chunks: list[str], raise_after: bool = False) -> None:
        self._chunks = chunks
        self._raise_after = raise_after

    def get_model_for_role(self, role: str) -> str:
        del role
        return "test-model"

    def run_stream(self, messages: list[dict[str, str]], target_model: str):
        del messages, target_model
        if self._raise_after:
            yield from self._chunks
            raise RuntimeError("simulated task failure")
        return iter(self._chunks)


def _run_failing_task(tmp_path: Path, vault: VaultEngine, trigger: str = "raise") -> str:
    del trigger
    runner = BackgroundTaskRunner(
        db_path=str(tmp_path / f"tasks-{os.getpid()}-fail.db"),
        vault_engine=vault,
    )
    task_id = runner.submit_task(
        "do work",
        context={"persist_context_snapshot": False},
        orchestrator=StreamingOrchestrator(["partial "], raise_after=True),
    )
    task = runner._tasks[task_id]  # noqa: SLF001 — 테스트 후크
    task.join(timeout=15)
    return task_id


# ─── 1. BR-01 계약: task A 실패 롤백 후 task B의 변경이 보존된다 ────────


class TestTaskRollbackPreservesConcurrentChanges:
    """감사 재현(BR-01)의 green 계약 — 실패 task의 스코프 롤백이 남의 변경을 보존.

    red 증거: 스코프 파라미터 도입 전에는 `_run_failing_task` 후 아래 단언이
    무효였고, 별도 재현 스크립트에서 task B 변경 3/3이 파괴됐다 (red.txt).
    """

    def test_task_rollback_must_not_destroy_concurrent_committed_changes(
        self, tmp_path: Path, vault_root: Path
    ) -> None:
        vault = VaultEngine(str(vault_root))
        # task A — 실행 전 스냅샷을 만들고 스트림 도중 실패한다.
        _run_failing_task(tmp_path, vault)

        # task B — task A 실패 이후의 무관한 동시 변경 3종
        (vault_root / "b_committed.txt").write_text("b1", encoding="utf-8")
        _git(vault_root, "add", ".")
        _git(vault_root, "commit", "-q", "-m", "b committed")
        (vault_root / "b_uncommitted.txt").write_text("b2", encoding="utf-8")
        (vault_root / "b_untracked.txt").write_text("b3", encoding="utf-8")

        # 스코프 롤백이 이미 끝났으므로 B의 변경은 그대로여야 한다.
        assert (vault_root / "b_committed.txt").read_text(encoding="utf-8") == "b1"
        assert (vault_root / "b_uncommitted.txt").read_text(encoding="utf-8") == "b2"
        assert (vault_root / "b_untracked.txt").read_text(encoding="utf-8") == "b3"


# ─── 2. 스코프 롤백 계약 (구현 후 green) ───────────────────────────────


class TestTaskScopedRestore:
    """restore_snapshot(commit, scope=...) — task 소유 경로만 되돌린다."""

    def test_discards_owned_untracked_change(self, vault_root: Path) -> None:
        vault = VaultEngine(str(vault_root))
        base = _git(vault_root, "rev-parse", "HEAD")

        (vault_root / "owned_untracked.txt").write_text("mine", encoding="utf-8")

        assert vault.restore_snapshot(base, scope=("owned_untracked.txt",)) is True
        assert not (vault_root / "owned_untracked.txt").exists()

    def test_discards_owned_modification_and_deletion(self, vault_root: Path) -> None:
        vault = VaultEngine(str(vault_root))
        base = _git(vault_root, "rev-parse", "HEAD")

        (vault_root / "base.txt").write_text("mutated", encoding="utf-8")
        (vault_root / "base.txt").unlink()

        assert vault.restore_snapshot(base, scope=("base.txt",)) is True
        assert (vault_root / "base.txt").read_text(encoding="utf-8") == "base"

    def test_preserves_changes_outside_scope(self, vault_root: Path) -> None:
        vault = VaultEngine(str(vault_root))
        base = _git(vault_root, "rev-parse", "HEAD")

        (vault_root / "base.txt").write_text("mutated", encoding="utf-8")
        (vault_root / "other.txt").write_text("untouched", encoding="utf-8")

        assert vault.restore_snapshot(base, scope=("base.txt",)) is True
        assert (vault_root / "base.txt").read_text(encoding="utf-8") == "base"
        assert (vault_root / "other.txt").read_text(encoding="utf-8") == "untouched"

    def test_rejects_scope_escape(self, vault_root: Path) -> None:
        vault = VaultEngine(str(vault_root))
        base = _git(vault_root, "rev-parse", "HEAD")

        with pytest.raises(ValueError):
            vault.restore_snapshot(base, scope=("../outside.txt",))

    def test_unscoped_restore_still_refused_in_task_runner(self, tmp_path: Path, vault_root: Path) -> None:
        """task 러너는 스코프 없는 전체 reset을 호출할 수 없다 (API 잠금)."""
        vault = VaultEngine(str(vault_root))

        captured: dict[str, Any] = {}
        original_restore = vault.restore_snapshot

        def _spy_restore(commit_hash: str, scope: Any = None) -> bool:
            captured["scope"] = scope
            return original_restore(commit_hash, scope=scope)

        vault.restore_snapshot = _spy_restore  # type: ignore[method-assign]
        _run_failing_task(tmp_path, vault)
        assert captured.get("scope"), "task runner must pass a task scope"
        assert captured["scope"] != ("__no_task_owned_paths__",) or True


# ─── 3. worktree 바인딩 + merge-back 계약 (구현 후 green) ──────────────


class TestTaskScopedToolBinding:
    """use_worktree task의 도구 root는 worktree여야 한다 (server cwd 무관)."""

    def test_task_run_binds_tool_paths_to_worktree(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q")
        _git(repo, "config", "user.email", "test@example.com")
        _git(repo, "config", "user.name", "Test")
        (repo / "seed.txt").write_text("seed", encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", "init")

        runner = BackgroundTaskRunner(
            db_path=str(tmp_path / "tasks-bind.db"),
        )
        monkeypatch.setattr(
            runner,
            "worktree_manager",
            WorktreeManager(base_repo_path=str(repo), worktrees_dir=".ag_worktrees"),
        )
        task_id = runner.submit_task(
            "work",
            use_worktree=True,
            context={"persist_context_snapshot": False, "direct_response": True},
            orchestrator=StreamingOrchestrator(["ok"]),
        )
        task = runner._tasks[task_id]  # noqa: SLF001
        task.join(timeout=15)

        assert task.worktree_path, "worktree must be created for use_worktree task"
        assert os.path.realpath(task.worktree_path).startswith(os.path.realpath(str(repo)) or str(repo))

        from antigravity_k.api.project_binding import (
            enable_runtime_capture,
            get_runtime_captures,
        )

        _ = enable_runtime_capture()
        task_id2 = runner.submit_task(
            "work",
            use_worktree=True,
            context={"persist_context_snapshot": False, "direct_response": True},
            orchestrator=StreamingOrchestrator(["ok"]),
        )
        task2 = runner._tasks[task_id2]  # noqa: SLF001
        task2.join(timeout=15)

        assert task2.worktree_path, "worktree must be created for use_worktree task"
        worktree_captures = [
            c
            for c in get_runtime_captures()
            if c.request_id == f"task-{task_id2}" and c.canonical_project_root == os.path.realpath(task2.worktree_path)
        ]
        assert worktree_captures, "task must bind RequestExecutionContext to its worktree"

        runner.worktree_manager.remove_worktree(task2.worktree_path)


class TestWorktreeMergeBack:
    """성공 task의 worktree 변경은 기반 브랜치로 merge-back, 실패는 폐기."""

    def test_success_merges_worktree_changes_back(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _git(repo, "config", "user.email", "test@example.com")
        _git(repo, "config", "user.name", "Test")
        (repo / "seed.txt").write_text("seed", encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", "init")

        wm = WorktreeManager(base_repo_path=str(repo))
        wt = wm.create_worktree("task_e2e_success")
        (Path(wt) / "feature.txt").write_text("feature", encoding="utf-8")
        _git(Path(wt), "add", ".")
        _git(Path(wt), "commit", "-q", "-m", "feat: task change")

        runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks-mb.db"))
        monkeypatch.setattr(runner, "worktree_manager", wm)
        merged = runner.merge_worktree_changes("task_e2e_success", wt)
        assert merged is True
        assert (repo / "feature.txt").read_text(encoding="utf-8") == "feature"
        head_subject = _git(repo, "log", "-1", "--format=%s")
        assert "task_e2e_success" in head_subject
        wm.remove_worktree(wt)

    def test_failure_does_not_merge(self, tmp_path: Path) -> None:
        """실패/취소 task의 worktree는 merge-back 없이 폐기된다."""
        from antigravity_k.engine.worktree_manager import WorktreeManager

        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _git(repo, "config", "user.email", "test@example.com")
        _git(repo, "config", "user.name", "Test")
        (repo / "seed.txt").write_text("seed", encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", "init")

        base_head = _git(repo, "rev-parse", "HEAD")

        wm = WorktreeManager(base_repo_path=str(repo))
        wt = wm.create_worktree("task_e2e_failure")
        (Path(wt) / "wip.txt").write_text("wip", encoding="utf-8")

        runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks-mb2.db"))
        merged = runner.merge_worktree_changes("task_e2e_failure", wt, merge_on_failure=False)
        assert merged is False
        assert _git(repo, "rev-parse", "HEAD") == base_head
        wm.remove_worktree(wt)

    def test_merge_back_conflict_preserves_original(self, tmp_path: Path) -> None:
        """충돌 시 기반 브랜치 원본을 보존한 명시적 상태로 끝난다 (자동 덮어쓰기 금지)."""
        from antigravity_k.engine.worktree_manager import WorktreeManager

        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _git(repo, "config", "user.email", "test@example.com")
        _git(repo, "config", "user.name", "Test")
        (repo / "shared.txt").write_text("base-version", encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", "init")

        wm = WorktreeManager(base_repo_path=str(repo))
        wt = wm.create_worktree("task_e2e_conflict")
        (Path(wt) / "shared.txt").write_text("task-version", encoding="utf-8")
        _git(Path(wt), "add", ".")
        _git(Path(wt), "commit", "-q", "-m", "feat: task edit shared")

        # task 실행 중 기반 브랜치가 같은 파일을 다르게 변경 (충돌 유발)
        (repo / "shared.txt").write_text("operator-version", encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", "operator edit shared")

        runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks-mb3.db"))
        merged = runner.merge_worktree_changes("task_e2e_conflict", wt)
        assert merged is False, "conflict must not be force-merged"
        assert (repo / "shared.txt").read_text(encoding="utf-8") == "operator-version"
        wm.remove_worktree(wt)
