"""Worktree 고아 복구 리허설 테스트 (DAT-02 수용기준 4).

크래시 뒤 남는 orphan worktree 정리 경로를 검증한다:
- list_worktrees: porcelain 파싱, git 실패 시 조용한 빈 목록
- sweep_orphan_worktrees: 보존 우선 원칙 (dirty/미판정 = 제외), dry-run 기본,
  실제 제거는 force remove 경유
- docs/runbooks/worktree_orphan_recovery.md runbook 존재 + 필수 섹션
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from antigravity_k.engine.worktree_manager import WorktreeManager

RUNBOOK_PATH = Path("docs/runbooks/worktree_orphan_recovery.md")


@pytest.fixture
def real_repo(tmp_path: Path) -> str:
    """실제 git 저장소 fixture — sweep은 git 상태를 보므로 mock이 아닌 실 repo로 검증."""
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }

    def git(*args: str, cwd: Path | None = None) -> None:
        subprocess.run(["git", *args], cwd=cwd or repo, check=True, capture_output=True, env=env)

    git("init", "-q")
    (repo / "seed.txt").write_text("seed\n")
    git("add", ".")
    git("commit", "-q", "-m", "seed")
    return str(repo)


@pytest.fixture
def real_manager(real_repo: str) -> WorktreeManager:
    return WorktreeManager(base_repo_path=real_repo, worktrees_dir=".ag_worktrees")


def _make_orphan(manager: WorktreeManager, name: str, old: bool = True) -> str:
    """정리 대상 조건을 만족하는 worktree를 만든다 (clean + 오래된 mtime)."""
    path = manager.create_worktree(name)
    if old:
        stale = __import__("time").time() - 30 * 86_400
        os.utime(path, (stale, stale))
    return path


class TestListWorktrees:
    def test_lists_registered_worktrees(self, real_manager: WorktreeManager) -> None:
        real_manager.create_worktree("wt-a")
        entries = real_manager.list_worktrees()
        paths = [e.get("path", "") for e in entries]
        assert any(p.endswith("wt-a") for p in paths)
        # 메인 repo와 방금 만든 worktree가 모두 보인다
        assert len(entries) >= 2

    def test_git_failure_returns_empty(self, real_manager: WorktreeManager) -> None:
        with mock.patch(
            "antigravity_k.engine.worktree_manager.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "git"),
        ):
            assert real_manager.list_worktrees() == []


class TestSweepOrphanWorktrees:
    def test_dry_run_lists_without_removing(self, real_manager: WorktreeManager) -> None:
        path = _make_orphan(real_manager, "wt-orphan")
        targets = real_manager.sweep_orphan_worktrees(older_than_days=7, dry_run=True)
        assert path in targets
        assert os.path.isdir(path), "dry-run은 아무것도 지우면 안 된다"

    def test_young_worktree_is_preserved(self, real_manager: WorktreeManager) -> None:
        real_manager.create_worktree("wt-young")  # mtime = 지금
        assert real_manager.sweep_orphan_worktrees(older_than_days=7, dry_run=True) == []

    def test_dirty_worktree_is_never_swept(self, real_manager: WorktreeManager) -> None:
        path = _make_orphan(real_manager, "wt-dirty")
        (Path(path) / "uncommitted.txt").write_text("precious\n")
        assert real_manager.sweep_orphan_worktrees(older_than_days=7, dry_run=True) == []

    def test_main_repo_and_outside_dir_excluded(self, real_manager: WorktreeManager) -> None:
        targets = real_manager.sweep_orphan_worktrees(older_than_days=0, dry_run=True)
        assert real_manager.base_repo_path not in targets

    def test_actual_removal_removes_target(self, real_manager: WorktreeManager) -> None:
        path = _make_orphan(real_manager, "wt-gone")
        removed = real_manager.sweep_orphan_worktrees(older_than_days=7, dry_run=False)
        assert path in removed
        assert not os.path.exists(path)

    def test_undeterminable_status_is_preserved(self, real_manager: WorktreeManager) -> None:
        """git status가 실패하면 dirty로 간주해 보존한다 (보존 우선 원칙)."""
        path = _make_orphan(real_manager, "wt-unk")
        real_repo = real_manager.base_repo_path
        calls = {"n": 0}
        real_run = subprocess.run

        def flaky_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            # sweep는 `git -C <path> status` 형태로 호출 — -C 뒤 인자로 대상 식별
            if "status" in cmd and "-C" in cmd and cmd[cmd.index("-C") + 1].endswith("wt-unk"):
                calls["n"] += 1
                raise subprocess.CalledProcessError(1, "git")
            return real_run(cmd, **kwargs)  # type: ignore[arg-type]

        with mock.patch("antigravity_k.engine.worktree_manager.subprocess.run", side_effect=flaky_run):
            targets = real_manager.sweep_orphan_worktrees(older_than_days=7, dry_run=True)
        assert calls["n"] >= 1
        assert path not in targets
        del real_repo

    def test_rehearsal_end_to_end(self, real_manager: WorktreeManager) -> None:
        """리허설: 고아 2개(오래됨/최신) + dirty 1개 → 오래되고 clean한 것만 정리."""
        old = _make_orphan(real_manager, "wt-old")
        real_manager.create_worktree("wt-recent")
        dirty = _make_orphan(real_manager, "wt-dirty2")
        (Path(dirty) / "wip.txt").write_text("wip\n")

        removed = real_manager.sweep_orphan_worktrees(older_than_days=7, dry_run=False)
        assert old in removed
        assert not os.path.exists(old)
        assert os.path.isdir(str(Path(dirty))), "dirty는 보존"
        recent = Path(str(real_manager.worktrees_dir)) / "wt-recent"
        assert recent.is_dir(), "최신 worktree는 보존"


class TestRunbook:
    def test_runbook_exists_with_required_sections(self) -> None:
        assert RUNBOOK_PATH.is_file(), f"runbook 없음: {RUNBOOK_PATH}"
        text = RUNBOOK_PATH.read_text(encoding="utf-8")
        for section in ("증상", "진단", "복구", "정리", "리허설"):
            assert section in text, f"runbook에 '{section}' 섹션 없음"
