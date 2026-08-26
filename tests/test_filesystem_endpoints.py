"""테스트: Filesystem API — 워크스페이스 파일 CRUD·검색 통합 계약.
============================================
워크스페이스 루트 경계 보호(403), CRUD 흐름, 이름 변경, 내용 검색을 검증한다.
"""

import pytest
from fastapi.testclient import TestClient

from antigravity_k.api.routes import filesystem
from antigravity_k.api.server import app


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setattr(filesystem, "WORKSPACE_ROOT", str(ws))
    return ws


@pytest.fixture
def client():
    from antigravity_k.config import config

    headers = {"X-Access-Pin": config.security.access_pin}
    with TestClient(app, raise_server_exceptions=False) as test_client:
        test_client.headers.update(headers)
        # TTL 캐시가 테스트 간 응답을 재사용하지 않도록 filesystem 태그를 비운다
        from antigravity_k.engine.api_cache import api_cache

        keys = api_cache._tag_index.pop("filesystem", set())
        for key in keys:
            api_cache._entries.pop(key, None)
        yield test_client
        keys = api_cache._tag_index.pop("filesystem", set())
        for key in keys:
            api_cache._entries.pop(key, None)


# ─── browse / list ───────────────────────────────────────────────


class TestBrowseAndList:
    def test_browse_lists_dirs_and_hides_dotfiles(self, client, workspace):
        (workspace / "subdir").mkdir()
        (workspace / ".secret").mkdir()

        body = client.get("/api/fs/browse", params={"dir": "."}).json()

        names = [e["name"] for e in body["items"]]
        assert "subdir" in names
        assert ".secret" not in names
        assert body["parent"] is not None  # tmp 하위라 부모 존재

    def test_list_returns_relative_paths_sorted_dirs_first(self, client, workspace):
        (workspace / "zdir").mkdir()
        (workspace / "afile.txt").write_text("x", encoding="utf-8")

        body = client.get("/api/fs/list", params={"dir": "."}).json()

        assert body["ok"] is True
        paths = [e["path"] for e in body["items"]]
        assert paths == ["zdir", "afile.txt"]
        assert body["items"][0]["is_dir"] is True

    def test_traversal_outside_workspace_is_403(self, client):
        response = client.get("/api/fs/list", params={"dir": "../../etc"})

        assert response.status_code == 403

    def test_browse_missing_dir_is_404(self, client):
        response = client.get("/api/fs/browse", params={"dir": "no-such-dir"})
        assert response.status_code == 404


# ─── mkdir / delete ──────────────────────────────────────────────


class TestMkdirDelete:
    def test_mkdir_creates_and_duplicate_reports_false(self, client, workspace):
        ok = client.post("/api/fs/mkdir", json={"path": "newdir"}).json()
        dup = client.post("/api/fs/mkdir", json={"path": "newdir"}).json()

        assert ok["ok"] is True
        assert (workspace / "newdir").is_dir()
        assert dup["ok"] is False

    def test_mkdir_root_path_is_400(self, client):
        for bad in (".", ""):
            assert client.post("/api/fs/mkdir", json={"path": bad}).status_code == 400

    def test_delete_file_and_directory(self, client, workspace):
        f = workspace / "doomed.txt"
        f.write_text("bye", encoding="utf-8")
        d = workspace / "doomed-dir"
        d.mkdir()

        assert client.request("DELETE", "/api/fs/delete", json={"path": "doomed.txt"}).json()["ok"] is True
        assert client.request("DELETE", "/api/fs/delete", json={"path": "doomed-dir"}).json()["ok"] is True
        assert not f.exists() and not d.exists()

    def test_delete_root_is_400_and_missing_is_ok_false(self, client):
        root_resp = client.request("DELETE", "/api/fs/delete", json={"path": "."})
        assert root_resp.status_code == 400

        missing = client.request("DELETE", "/api/fs/delete", json={"path": "ghost"}).json()
        assert missing == {"ok": False, "detail": "Path does not exist"}


# ─── write / read / rename ───────────────────────────────────────


class TestWriteReadRename:
    def test_write_creates_parent_dirs_then_read_roundtrip(self, client, workspace):
        write_body = client.post(
            "/api/fs/write",
            json={"path": "deep/nested/file.txt", "content": "본문 내용"},
        ).json()

        assert write_body["ok"] is True
        read_body = client.get("/api/fs/read", params={"file": "deep/nested/file.txt"}).json()
        assert read_body == {"ok": True, "content": "본문 내용"}

    def test_read_missing_file_is_404(self, client):
        assert client.get("/api/fs/read", params={"file": "ghost.txt"}).status_code == 404

    def test_rename_moves_file(self, client, workspace):
        (workspace / "before.txt").write_text("v", encoding="utf-8")

        body = client.post("/api/fs/rename", json={"path": "before.txt", "new_name": "after.txt"}).json()

        assert body["ok"] is True
        assert (workspace / "after.txt").exists()
        assert not (workspace / "before.txt").exists()

    def test_rename_to_existing_name_reports_conflict(self, client, workspace):
        (workspace / "src.txt").write_text("a", encoding="utf-8")
        (workspace / "dst.txt").write_text("b", encoding="utf-8")

        body = client.post("/api/fs/rename", json={"path": "src.txt", "new_name": "dst.txt"}).json()

        assert body["ok"] is False

    def test_rename_missing_source_is_404(self, client):
        response = client.post("/api/fs/rename", json={"path": "ghost.txt", "new_name": "x.txt"})
        assert response.status_code == 404


# ─── content search ──────────────────────────────────────────────


class TestContentSearch:
    def test_short_query_is_400(self, client):
        response = client.post("/api/fs/search", json={"query": "a"})
        assert response.status_code == 400

    def test_finds_matches_with_counts(self, client, workspace):
        (workspace / "hit.md").write_text("고유단어 가 포함된 문서", encoding="utf-8")
        (workspace / "miss.md").write_text("관련 없음", encoding="utf-8")

        body = client.post("/api/fs/search", json={"query": "고유단어"}).json()

        assert body["total_files"] == 1
        assert body["results"][0]["match_count"] >= 1
