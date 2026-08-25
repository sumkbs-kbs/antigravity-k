"""테스트: Git API 엔드포인트 통합 계약.
==================================
실제 git 리포지토리(tmp_path)를 대상으로 status/log/diff/stage/commit/
branch/graph/file-content/stash 흐름과 헬퍼 엣지를 검증한다.
"""

import subprocess

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from antigravity_k.api.routes import git_api
from antigravity_k.api.server import app
from antigravity_k.config import config


def _git_raw(args: list[str], cwd):
    subprocess.run(["git"] + args, cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path, monkeypatch, request):
    import re

    unique = re.sub(r"[^a-zA-Z0-9]", "-", request.node.name)[:40]
    """프로젝트 루트=tmp_path, 커밋 1개 있는 git 리포지토리."""
    project_root = tmp_path
    repo_dir = project_root / f"repo-{unique}"
    repo_dir.mkdir()

    _git_raw(["init", "-b", "main"], str(repo_dir))
    _git_raw(["config", "user.name", "tester"], str(repo_dir))
    _git_raw(["config", "user.email", "tester@example.com"], str(repo_dir))
    (repo_dir / "hello.txt").write_text("line1\n", encoding="utf-8")
    _git_raw(["add", "."], str(repo_dir))
    _git_raw(["commit", "-m", "init"], str(repo_dir))

    monkeypatch.setattr(git_api.config.paths, "project_root", project_root)
    yield repo_dir  # .name이 캐시 키 분리용 고유 cwd 이름을 제공한다


@pytest.fixture
def no_gate(monkeypatch):
    """행복경로 테스트용: 권한 게이트를 통과시킨다(차단 계약은 별도 스위트 담당)."""
    monkeypatch.setattr(git_api, "_require_allowed", lambda *a, **k: None)


@pytest.fixture
def client():
    headers = {"X-Access-Pin": config.security.access_pin}
    with TestClient(app, raise_server_exceptions=False) as test_client:
        test_client.headers.update(headers)
        yield test_client


# ─── /api/git/status ─────────────────────────────────────────────


class TestStatus:
    def test_clean_repo_reports_zero_counts(self, client, repo):
        response = client.get("/api/git/status", params={"path": repo.name})
        body = response.json()

        assert body["ok"] is True
        assert body["branch"] == "main"
        assert body["upstream"] is None
        assert body["counts"]["total"] == 0

    def test_mixed_changes_are_counted(self, client, repo):
        (repo / "hello.txt").write_text("line1\nline2\n", encoding="utf-8")
        (repo / "new.txt").write_text("new\n", encoding="utf-8")

        body = client.get("/api/git/status", params={"path": repo.name}).json()

        assert body["counts"]["unstaged"] >= 1
        assert body["counts"]["untracked"] == 1
        names = {f["file_path"] for f in body["files"]}
        assert "new.txt" in names


# ─── /api/git/log · graph ────────────────────────────────────────


class TestLogAndGraph:
    def test_log_returns_structured_commits(self, client, repo):
        body = client.post("/api/git/log", json={"path": repo.name, "count": 5}).json()

        assert body["ok"] is True
        assert body["count"] == 1
        commit = body["commits"][0]
        assert commit["message"] == "init"
        assert commit["author_name"] == "tester"
        assert len(commit["hash"]) == 40

    def test_graph_nodes_carry_graph_prefix(self, client, repo):
        body = client.get("/api/git/graph", params={"path": repo.name}).json()

        assert body["ok"] is True
        assert body["count"] >= 1
        assert body["nodes"][0]["graph"].startswith("*")


# ─── diff · add · unstage · commit ───────────────────────────────


class TestChangeFlow:
    def test_diff_unstaged_then_staged(self, client, repo):
        (repo / "hello.txt").write_text("line1\nline2\n", encoding="utf-8")

        unstaged = client.post("/api/git/diff", json={"path": repo.name}).json()
        assert "+line2" in unstaged["diff"]
        assert unstaged["staged"] is False

        _git_raw(["add", "hello.txt"], str(repo))
        staged = client.post("/api/git/diff", json={"path": repo.name, "staged": True}).json()
        assert "+line2" in staged["diff"]

    def test_add_specific_files(self, client, repo, no_gate):
        (repo / "b.txt").write_text("b\n", encoding="utf-8")
        (repo / "c.txt").write_text("c\n", encoding="utf-8")

        body = client.post("/api/git/add", json={"path": repo.name, "files": ["b.txt", "c.txt"]}).json()

        assert body["ok"] is True
        status = subprocess.run(["git", "status", "--short"], cwd=repo, capture_output=True, text=True).stdout
        assert "A  b.txt" in status
        assert "A  c.txt" in status

    def test_add_without_files_reports_error(self, client, repo):
        body = client.post("/api/git/add", json={"path": repo.name, "files": []}).json()
        assert body["ok"] is False

    def test_unstage_all(self, client, repo, no_gate):
        (repo / "hello.txt").write_text("changed\n", encoding="utf-8")
        _git_raw(["add", "."], str(repo))

        body = client.post("/api/git/unstage", json={"path": repo.name, "files": []}).json()

        assert body["ok"] is True
        status = subprocess.run(["git", "status", "--short"], cwd=repo, capture_output=True, text=True).stdout
        staged_lines = [line for line in status.splitlines() if line.startswith("M ")]
        assert staged_lines == []
        assert any(line.startswith(" M") for line in status.splitlines())

    def test_commit_requires_message(self, client, repo):
        body = client.post("/api/git/commit", json={"path": repo.name, "message": "  "}).json()
        assert body["ok"] is False

    def test_commit_creates_revision(self, client, repo, no_gate):
        (repo / "hello.txt").write_text("v2\n", encoding="utf-8")

        body = client.post(
            "/api/git/commit",
            json={"path": repo.name, "message": "update hello", "stage_all": True},
        ).json()

        assert body["ok"] is True
        log = client.post("/api/git/log", json={"path": repo.name}).json()
        assert log["commits"][0]["message"] == "update hello"


# ─── branches ────────────────────────────────────────────────────


class TestBranches:
    def test_branch_lifecycle_roundtrip(self, client, repo, no_gate):
        created = client.post("/api/git/branch/create", json={"path": repo.name, "name": "feature/x"}).json()
        assert created["ok"] is True

        listing = client.get("/api/git/branches", params={"path": repo.name}).json()
        by_name = {b["name"]: b for b in listing["branches"]}
        assert by_name["feature/x"]["is_current"] is True
        assert listing["current"] == "feature/x"

        switched = client.post("/api/git/checkout", json={"path": repo.name, "name": "main"}).json()
        assert switched["ok"] is True

        deleted = client.post("/api/git/branch/delete", json={"path": repo.name, "name": "feature/x"}).json()
        assert deleted["ok"] is True

    def test_create_requires_name(self, client, repo):
        body = client.post("/api/git/branch/create", json={"path": repo.name, "name": " "}).json()
        assert body["ok"] is False

    def test_checkout_requires_name(self, client, repo):
        body = client.post("/api/git/checkout", json={"path": repo.name, "name": ""}).json()
        assert body["ok"] is False


# ─── file-content · stash ────────────────────────────────────────


class TestContentAndStash:
    def test_file_content_at_head(self, client, repo):
        body = client.get("/api/git/file-content", params={"path": repo.name, "file": "hello.txt"}).json()

        assert body["ok"] is True
        assert body["content"] == "line1\n"
        assert body["ref"] == "HEAD"

    def test_stash_list_empty_is_ok(self, client, repo):
        body = client.get("/api/git/stash/list", params={"path": repo.name}).json()

        assert body == {"ok": True, "stashes": []}


# ─── 헬퍼 엣지 ────────────────────────────────────────────────────


class TestHelpers:
    def test_parse_status_line_variants(self):
        renamed = git_api._parse_status_line("R  old.txt -> new.txt")
        assert renamed["is_renamed"] is True
        assert renamed["old_path"] == "old.txt"
        assert renamed["file_path"] == "new.txt"

        normal = git_api._parse_status_line(" M src/main.py")
        assert normal["is_renamed"] is False
        assert normal["staged_status"] == "unchanged"
        assert normal["unstaged_status"] == "modified"

        assert git_api._parse_status_line("") is None
        assert git_api._parse_status_line("# branch info") is None

    def test_status_char_unknown_fallback(self):
        assert git_api._status_char("X") == "unknown"

    def test_git_missing_directory_is_400(self, tmp_path, monkeypatch):
        monkeypatch.setattr(git_api.config.paths, "project_root", tmp_path)

        with pytest.raises(HTTPException) as error:
            git_api._git(["status"], cwd="ghost-dir")

        assert error.value.status_code == 400

    def test_git_command_failure_maps_to_400(self, tmp_path, monkeypatch):
        monkeypatch.setattr(git_api.config.paths, "project_root", tmp_path)

        with pytest.raises(HTTPException) as error:
            git_api._git(["show", "HEAD"], cwd=".")  # 커밋 없는 저장소

        assert error.value.status_code == 400

    def test_git_timeout_maps_to_408(self, tmp_path, monkeypatch):
        monkeypatch.setattr(git_api.config.paths, "project_root", tmp_path)

        with pytest.raises(HTTPException) as error:
            git_api._git(["status"], cwd=".", timeout=0)

        assert error.value.status_code == 408

    def test_git_binary_absent_maps_to_400(self, tmp_path, monkeypatch):
        monkeypatch.setattr(git_api.config.paths, "project_root", tmp_path)

        def raise_file_not_found(*args, **kwargs):
            raise FileNotFoundError("git")

        monkeypatch.setattr(git_api.subprocess, "run", raise_file_not_found)

        with pytest.raises(HTTPException) as error:
            git_api._git(["status"], cwd=".")

        assert error.value.status_code == 400
