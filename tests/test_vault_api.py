"""테스트: Vault API — Wiki CRUD·트리·검색·동기화 통합 계약.
============================================
실제 git 기반 VaultEngine(tmp_path, RAG off)으로 엔드포인트 흐름을 검증한다.
"""

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from antigravity_k.api.server import app
from antigravity_k.config import config
from antigravity_k.engine.vault import VaultEngine


def _git(args: list[str], cwd: str):
    subprocess.run(
        ["git"] + args,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        env={
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
            "HOME": str(Path(cwd).parent),
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        },
    )


@pytest.fixture
def vault(tmp_path):
    vdir = tmp_path / "vault"
    vdir.mkdir()
    _git(["init", "-b", "main"], str(vdir))
    _git_raw = None  # placeholder 제거용
    return vdir


@pytest.fixture
def engine(vault):
    return VaultEngine(vault_path=str(vault), sync_rag=False)


@pytest.fixture
def client(engine, monkeypatch):
    from antigravity_k.api.dependencies import get_vault_engine
    from antigravity_k.config import config as app_config

    headers = {"X-Access-Pin": app_config.security.access_pin}
    app.dependency_overrides[get_vault_engine] = lambda: engine
    # set_vault_config의 경로 게이트가 tmp를 허용하도록 프로젝트 루트 확장
    real_root = config.paths.project_root

    class _FlexibleRoot:
        def __str__(self):
            return str(real_root)

    test_client = TestClient(app, raise_server_exceptions=False)
    test_client.headers.update(headers)
    yield test_client

    app.dependency_overrides.pop(get_vault_engine, None)


HEADERS = {}


class TestVaultConfig:
    def test_config_returns_engine_path(self, client, vault):
        body = client.get("/api/vault/config").json()

        assert body["ok"] is True
        assert body["vault_path"] == str(vault)

    def test_config_without_engine(self, client):
        from antigravity_k.api.dependencies import get_vault_engine

        client.app.dependency_overrides[get_vault_engine] = lambda: None
        body = client.get("/api/vault/config").json()

        assert body == {"ok": False, "vault_path": None, "message": "VaultEngine not available"}


class TestVaultTree:
    def test_tree_lists_md_files_and_hides_dotfiles(self, client, vault):
        (vault / "note.md").write_text("hello", encoding="utf-8")
        (vault / ".hidden").mkdir()

        body = client.get("/api/vault/tree").json()

        names = [e["name"] for e in body["tree"]]
        assert "note.md" in names
        assert ".hidden" not in names
        assert body["vault_path"] == str(vault)


class TestVaultReadWrite:
    def test_write_then_read_roundtrip(self, client, vault):
        write_body = client.post(
            "/api/vault/write",
            json={"path": "notes/idea.md", "content": "---\ntitle: 아이디어\n---\n내용", "metadata": {}},
        ).json()
        assert write_body == {"ok": True, "path": "notes/idea.md"}

        read_body = client.get("/api/vault/read", params={"path": "notes/idea.md"}).json()
        assert read_body["metadata"].get("title") == "아이디어"
        assert "내용" in read_body["content"]

    def test_read_missing_note_is_404(self, client):
        response = client.get("/api/vault/read", params={"path": "ghost.md"})
        assert response.status_code == 404

    @pytest.mark.parametrize("bad_path", ["../escape.md", "a/../../b.md"])
    def test_path_traversal_rejected(self, client, bad_path):
        for method, kwargs in [
            ("get", {"params": {"path": bad_path}}),
            ("post", {"json": {"path": bad_path, "content": "x"}}),
        ]:
            if method == "get":
                response = client.get("/api/vault/read", **kwargs)
            else:
                response = client.post("/api/vault/write", **kwargs)
            assert response.status_code == 400, f"{bad_path} via {method}"

    def test_write_requires_path(self, client):
        response = client.post("/api/vault/write", json={"content": "no path"})
        assert response.status_code == 400


class TestVaultSync:
    def test_sync_returns_commit_hash(self, client, vault, engine):
        (vault / "sync-me.md").write_text("---\ntitle: s\n---\nbody", encoding="utf-8")

        body = client.post("/api/vault/sync").json()

        assert body["ok"] is True
        assert isinstance(body["commit"], str) and len(body["commit"]) >= 7


# ─── /v1/notes/search ────────────────────────────────────────────


class TestNotesSearch:
    def test_empty_query_is_unprocessable(self, client):
        assert client.get("/v1/notes/search").status_code == 422

    def test_keyword_results_returned(self, client, vault, engine):
        from unittest.mock import MagicMock

        engine.vector_store = MagicMock()
        engine.vector_store.search.return_value = []
        engine.write_note("kw.md", {"title": "키워드"}, "고유 키워드 조합 사과바나나", commit_message="add")

        body = client.get("/v1/notes/search", params={"q": "사과바나나"}).json()

        assert body["query"] == "사과바나나"
        assert any("kw.md" in r for r in body["keyword_results"])
