"""테스트: Vault API — Wiki CRUD·트리·검색·동기화 통합 계약.
============================================
실제 git 기반 VaultEngine(tmp_path, RAG off)으로 엔드포인트 흐름을 검증한다.
"""

import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from antigravity_k.api.server import app
from antigravity_k.engine.vault import VaultEngine


def _git(args: list[str], cwd: str) -> None:
    _ = subprocess.run(
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
def vault(tmp_path: Path) -> Path:
    vdir = tmp_path / "vault"
    vdir.mkdir()
    _git(["init", "-b", "main"], str(vdir))
    return vdir


@pytest.fixture
def engine(vault: Path) -> VaultEngine:
    return VaultEngine(vault_path=str(vault), sync_rag=False)


@pytest.fixture
def client(engine: VaultEngine, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    from antigravity_k.api.dependencies import get_vault_engine
    from antigravity_k.config import config as app_config

    headers = {"X-Access-Pin": app_config.security.access_pin}
    app.dependency_overrides[get_vault_engine] = lambda: engine
    _ = monkeypatch

    test_client = TestClient(app, raise_server_exceptions=False)
    test_client.headers.update(headers)
    yield test_client

    _ = app.dependency_overrides.pop(get_vault_engine, None)


def _json(response: Response) -> dict[str, object]:
    return cast(dict[str, object], response.json())


HEADERS = {}


class TestVaultConfig:
    def test_config_returns_engine_path(self, client: TestClient, vault: Path) -> None:
        body = _json(client.get("/api/vault/config"))

        assert body["ok"] is True
        assert body["vault_path"] == str(vault)

    def test_config_without_engine(self, client: TestClient) -> None:
        from antigravity_k.api.dependencies import get_vault_engine

        app.dependency_overrides[get_vault_engine] = lambda: None
        body = _json(client.get("/api/vault/config"))

        assert body == {"ok": False, "vault_path": None, "message": "VaultEngine not available"}

    def test_config_rejects_non_string_path(self, client: TestClient) -> None:
        response = client.post("/api/vault/config", json={"vault_path": 123})

        assert response.status_code == 400


class TestVaultTree:
    def test_tree_lists_md_files_and_hides_dotfiles(self, client: TestClient, vault: Path) -> None:
        _ = (vault / "note.md").write_text("hello", encoding="utf-8")
        _ = (vault / ".hidden").mkdir()

        body = _json(client.get("/api/vault/tree"))

        tree = cast(list[dict[str, object]], body["tree"])
        names = [e["name"] for e in tree]
        assert "note.md" in names
        assert ".hidden" not in names
        assert body["vault_path"] == str(vault)


class TestVaultReadWrite:
    def test_write_then_read_roundtrip(self, client: TestClient) -> None:
        write_body = client.post(
            "/api/vault/write",
            json={"path": "notes/idea.md", "content": "---\ntitle: 아이디어\n---\n내용", "metadata": {}},
        )
        write_body = _json(write_body)
        assert write_body == {"ok": True, "path": "notes/idea.md"}

        read_body = _json(client.get("/api/vault/read", params={"path": "notes/idea.md"}))
        metadata = cast(dict[str, object], read_body["metadata"])
        assert metadata.get("title") == "아이디어"
        assert "내용" in cast(str, read_body["content"])

    def test_read_missing_note_is_404(self, client: TestClient) -> None:
        response = client.get("/api/vault/read", params={"path": "ghost.md"})
        assert response.status_code == 404

    @pytest.mark.parametrize("bad_path", ["../escape.md", "a/../../b.md"])
    def test_path_traversal_rejected(self, client: TestClient, bad_path: str) -> None:
        read_response = client.get("/api/vault/read", params={"path": bad_path})
        assert read_response.status_code == 400, f"{bad_path} via get"

        write_response = client.post(
            "/api/vault/write",
            json={"path": bad_path, "content": "x"},
        )
        assert write_response.status_code == 400, f"{bad_path} via post"

    def test_write_requires_path(self, client: TestClient) -> None:
        response = client.post("/api/vault/write", json={"content": "no path"})
        assert response.status_code == 400

    def test_write_rejects_non_string_content(self, client: TestClient) -> None:
        response = client.post("/api/vault/write", json={"path": "note.md", "content": 123})

        assert response.status_code == 400

    def test_write_rejects_non_object_metadata(self, client: TestClient) -> None:
        response = client.post("/api/vault/write", json={"path": "note.md", "metadata": []})

        assert response.status_code == 400


class TestVaultSync:
    def test_sync_returns_commit_hash(self, client: TestClient, vault: Path) -> None:
        _ = (vault / "sync-me.md").write_text("---\ntitle: s\n---\nbody", encoding="utf-8")

        body = _json(client.post("/api/vault/sync"))

        assert body["ok"] is True
        assert isinstance(body["commit"], str) and len(body["commit"]) >= 7


# ─── /v1/notes/search ────────────────────────────────────────────


class TestNotesSearch:
    def test_empty_query_is_unprocessable(self, client: TestClient) -> None:
        assert client.get("/v1/notes/search").status_code == 422

    def test_keyword_results_returned(self, client: TestClient, engine: VaultEngine) -> None:
        from unittest.mock import MagicMock

        vector_store = MagicMock()
        engine.vector_store = vector_store
        search = cast(MagicMock, getattr(vector_store, "search"))
        search.return_value = []
        engine.write_note("kw.md", {"title": "키워드"}, "고유 키워드 조합 사과바나나", commit_message="add")

        body = _json(client.get("/v1/notes/search", params={"q": "사과바나나"}))

        assert body["query"] == "사과바나나"
        keyword_results = cast(list[str], body["keyword_results"])
        assert any("kw.md" in r for r in keyword_results)
