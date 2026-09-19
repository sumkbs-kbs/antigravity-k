"""테스트: System API — Skills 브라우저·설치·게시 스위트.
============================================
지연 임포트되는 Installer/MarketClient/Registry/Publisher를 소스 모듈 패치로 격리해
엔드포인트 계약(응답 매핑, 필수값 검증, 권한 게이트, 변경 탐지)을 검증한다.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Protocol, cast, final, override

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from antigravity_k.api.routes import system_api
from antigravity_k.api.server import app

JsonObject = dict[str, object]


class ResponseLike(Protocol):
    status_code: int

    def json(self) -> object: ...


@final
class SkillLoaderStub:
    _skills: list[JsonObject]

    def __init__(self, skills: list[JsonObject]) -> None:
        self._skills = skills

    def list_skills(self) -> list[JsonObject]:
        return self._skills


class RegistryStub:
    def __init__(self) -> None:
        self.installed: list[InstalledSkillStub] = []
        self.mcp_servers: list[JsonObject] = []
        self.install_result: JsonObject = {}
        self.remove_result: JsonObject = {}

    def list_installed(self) -> list[InstalledSkillStub]:
        return self.installed

    def list_skills_with_mcp(self) -> list[JsonObject]:
        return self.mcp_servers

    def install(self, package_name: str) -> JsonObject:
        return {"success": True, "package": package_name, **self.install_result}

    def remove(self, skill_name: str) -> JsonObject:
        return {"success": False, "skill_name": skill_name, **self.remove_result}


@final
class InstalledSkillStub:
    skill_name: str
    version: str
    is_loaded: bool
    mcp_server_id: str | None
    security_findings: list[str]

    def __init__(
        self,
        skill_name: str,
        version: str,
        is_loaded: bool,
        mcp_server_id: str | None,
        security_findings: list[str],
    ) -> None:
        self.skill_name = skill_name
        self.version = version
        self.is_loaded = is_loaded
        self.mcp_server_id = mcp_server_id
        self.security_findings = security_findings


@final
class SearchResultStub:
    _result: JsonObject

    def __init__(self, result: JsonObject) -> None:
        self._result = result

    def to_dict(self) -> JsonObject:
        return self._result


def _json(response: ResponseLike) -> JsonObject:
    value = response.json()
    if not isinstance(value, dict):
        raise AssertionError(f"expected JSON object, got {type(value).__name__}")
    return cast(JsonObject, value)


def _as_object(value: object) -> JsonObject:
    if not isinstance(value, dict):
        raise AssertionError(f"expected object, got {type(value).__name__}")
    return cast(JsonObject, value)


def _make_publish_result(**overrides: object) -> PublishResultStub:
    base: JsonObject = {
        "success": True,
        "action": "published",
        "skill_name": "s",
        "package_name": "@antigravity-k/skill-s",
        "version": "0.1.0",
        "npm_url": "https://www.npmjs.com/package/@antigravity-k/skill-s",
        "pr_url": None,
        "errors": [],
        "warnings": [],
    }
    base.update(overrides)
    return PublishResultStub(**base)


@final
class PublishResultStub:
    success: bool
    action: str
    skill_name: str
    package_name: str
    version: str
    npm_url: str | None
    pr_url: str | None
    errors: list[str]
    warnings: list[str]

    def __init__(self, **values: object) -> None:
        self.success = cast(bool, values.get("success", False))
        self.action = cast(str, values.get("action", ""))
        self.skill_name = cast(str, values.get("skill_name", ""))
        self.package_name = cast(str, values.get("package_name", ""))
        self.version = cast(str, values.get("version", ""))
        self.npm_url = cast(str | None, values.get("npm_url"))
        self.pr_url = cast(str | None, values.get("pr_url"))
        self.errors = cast(list[str], values.get("errors", []))
        self.warnings = cast(list[str], values.get("warnings", []))

    def summary(self) -> str:
        return "summary-ok"


@final
class ValidationStub:
    valid: bool
    has_skill_md: bool
    has_readme: bool
    version: str
    tool_count: int
    _warnings: list[str]

    def __init__(self) -> None:
        self.valid = True
        self.has_skill_md = True
        self.has_readme = False
        self.version = "0.1.0"
        self.tool_count = 2
        self._warnings = []

    @property
    def warnings(self) -> list[str]:
        return self._warnings


@pytest.fixture
def client() -> Iterator[TestClient]:
    from antigravity_k.config import config

    headers = {"X-Access-Pin": config.security.access_pin}
    with TestClient(app, raise_server_exceptions=False) as test_client:
        test_client.headers.update(headers)
        yield test_client


@pytest.fixture
def no_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    def allow(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(system_api, "_require_allowed", allow)


def _clear_skills_cache() -> Iterator[None]:
    """@cached(ttl=60) 라우트의 테스트 간 응답 재사용을 막는다.

    invalidate_tag는 async라 동기 테스트에서 직접 호출할 수 없어
    태그 인덱스와 엔트리를 동기적으로 비운다.
    """
    from antigravity_k.engine.api_cache import api_cache

    tag_index = cast(dict[str, set[str]], getattr(api_cache, "_tag_index"))
    entries = cast(dict[str, object], getattr(api_cache, "_entries"))
    keys = tag_index.pop("skills", set())
    for key in keys:
        _ = entries.pop(key, None)
    yield
    _ = tag_index.pop("skills", set())


_clear_skills_cache = pytest.fixture(autouse=True)(_clear_skills_cache)


@pytest.fixture
def loader(monkeypatch: pytest.MonkeyPatch) -> SkillLoaderStub:
    sl = SkillLoaderStub([{"id": "demo", "source": "global"}])
    monkeypatch.setattr(system_api, "__get_skill_loader", lambda: sl)
    return sl


# ─── 목록/검색 ────────────────────────────────────────────────────


class TestSkillsListing:
    def test_list_ok(self, client: TestClient, loader: SkillLoaderStub) -> None:
        body = _json(client.get("/api/system/skills"))
        del loader

        assert body == {"ok": True, "skills": [{"id": "demo", "source": "global"}]}

    def test_installed_maps_registry_fields(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        loader: SkillLoaderStub,
    ) -> None:
        variant = InstalledSkillStub(
            skill_name="code-review",
            version="1.2.0",
            is_loaded=True,
            mcp_server_id="srv-9",
            security_findings=["pin"],
        )
        registry = RegistryStub()
        registry.installed = [variant]

        def make_registry(**_kwargs: object) -> RegistryStub:
            return registry

        monkeypatch.setattr(
            "antigravity_k.engine.skill_market_registry.SkillMarketRegistry",
            make_registry,
        )

        body = _json(client.get("/api/system/skills/installed"))
        del loader

        installed = cast(list[JsonObject], body["installed"])
        assert installed[0] == {
            "name": "code-review",
            "version": "1.2.0",
            "is_loaded": True,
            "mcp_server_id": "srv-9",
            "security_issues": ["pin"],
        }

    def test_mcp_servers_passthrough(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        registry = RegistryStub()
        registry.mcp_servers = [{"name": "fs", "status": "up"}]

        def make_registry() -> RegistryStub:
            return registry

        monkeypatch.setattr("antigravity_k.tools.mcp_tool_loader.MCPServerRegistry", make_registry)

        body = _json(client.get("/api/system/skills/mcp"))
        assert body["servers"] == [{"name": "fs", "status": "up"}]

    def test_search_formats_results(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        class ClientStub:
            def search(self, _query: str, limit: int) -> list[SearchResultStub]:
                return [SearchResultStub({"name": "@antigravity-k/skill-x"})][:limit]

        client_stub = ClientStub()

        def make_client(**_kwargs: object) -> ClientStub:
            return client_stub

        monkeypatch.setattr("antigravity_k.engine.skill_market_client.SkillMarketClient", make_client)

        body = _json(client.get("/api/system/skills/search", params={"q": "x", "limit": 5}))

        results = cast(list[JsonObject], body["results"])
        assert body["count"] == 1 and results[0]["name"] == "@antigravity-k/skill-x"


# ─── 설치/제거 ────────────────────────────────────────────────────


class TestInstallRemove:
    def test_install_requires_package_name(self, client: TestClient) -> None:
        body = _json(client.post("/api/system/skills/install", json={}))
        assert body == {"ok": False, "error": "package_name is required"}

    def test_install_rejects_non_string_package_name(self, client: TestClient) -> None:
        response = client.post("/api/system/skills/install", json={"package_name": 123})

        assert response.status_code == 400

    def test_install_success_mapping(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        loader: SkillLoaderStub,
        no_gate: None,
    ) -> None:
        registry = RegistryStub()

        def make_registry(**_kwargs: object) -> RegistryStub:
            return registry

        monkeypatch.setattr(
            "antigravity_k.engine.skill_market_registry.SkillMarketRegistry",
            make_registry,
        )

        body = _json(client.post("/api/system/skills/install", json={"package_name": "@antigravity-k/skill-x"}))
        del loader, no_gate

        result = _as_object(body["result"])
        assert body["ok"] is True and cast(str, result["package"]).endswith("skill-x")

    def test_install_gate_denial_raises_403(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        def deny(*_args: object, **_kwargs: object) -> None:
            raise HTTPException(status_code=403, detail="denied")

        monkeypatch.setattr(system_api, "_require_allowed", deny)

        assert client.post("/api/system/skills/install", json={"package_name": "x"}).status_code == 403

    def test_remove_requires_skill_name(self, client: TestClient) -> None:
        body = _json(client.post("/api/system/skills/remove", json={}))
        assert body == {"ok": False, "error": "skill_name is required"}

    def test_remove_rejects_non_string_skill_name(self, client: TestClient) -> None:
        response = client.post("/api/system/skills/remove", json={"skill_name": 123})

        assert response.status_code == 400

    def test_remove_success_mapping(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        loader: SkillLoaderStub,
        no_gate: None,
    ) -> None:
        registry = RegistryStub()
        registry.remove_result = {"reason": "not installed"}

        def make_registry(**_kwargs: object) -> RegistryStub:
            return registry

        monkeypatch.setattr(
            "antigravity_k.engine.skill_market_registry.SkillMarketRegistry",
            make_registry,
        )

        body = _json(client.post("/api/system/skills/remove", json={"skill_name": "ghost"}))
        del loader, no_gate

        result = _as_object(body["result"])
        assert body["ok"] is False and result["reason"] == "not installed"


# ─── 로컬 스킬 & 게시 ─────────────────────────────────────────────


class FakePublisher:
    """market_dir/skills_dir과 검증 결과를 주입하는 가짜."""

    market_dir: Path | None
    skills_dir: Path | None
    _valid: ValidationStub

    def __init__(
        self,
        market_dir: Path | None,
        skills_dir: Path | None,
        valid: ValidationStub | None = None,
    ) -> None:
        self.market_dir = market_dir
        self.skills_dir = skills_dir
        self._valid = valid or ValidationStub()

    def _validate_for_publish(self, _skill_dir: Path, _name: str) -> ValidationStub:
        return self._valid

    def publish_to_npm(
        self,
        _name: str,
        _version: str | None = None,
        _tag: str = "latest",
        _dry_run: bool = False,
    ) -> PublishResultStub:
        return _make_publish_result()

    def publish_to_github(
        self,
        _name: str,
        _repo: str,
        _base_branch: str = "main",
        _draft: bool = False,
        _title: str | None = None,
        _body: str | None = None,
        _dry_run: bool = False,
    ) -> PublishResultStub:
        return _make_publish_result(action="github-pr", pr_url=None)


class TestLocalSkills:
    def test_local_lists_market_then_agent_dirs(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        no_gate: None,
    ) -> None:
        market = tmp_path / "market" / "m-skill"
        local = tmp_path / "skills" / "l-skill"
        market.mkdir(parents=True)
        local.mkdir(parents=True)

        publisher = FakePublisher(market_dir=tmp_path / "market", skills_dir=tmp_path / "skills")

        def make_publisher(*, project_root: str) -> FakePublisher:
            del project_root
            return publisher

        monkeypatch.setattr("antigravity_k.engine.skill_publisher.SkillPublisher", make_publisher)
        monkeypatch.chdir(tmp_path)

        body = _json(client.get("/api/system/skills/local"))

        skills = cast(list[JsonObject], body["skills"])
        sources = {cast(str, skill["name"]): cast(str, skill["source"]) for skill in skills}
        assert sources == {"m-skill": "market", "l-skill": "local"}
        assert body["count"] == 2
        del no_gate

    def test_local_check_detects_new_since_timestamp(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        no_gate: None,
    ) -> None:
        import os
        import time

        skill = tmp_path / "skills" / "fresh"
        skill.mkdir(parents=True)
        future = time.time() + 10_000
        os.utime(skill, (future, future))

        publisher = FakePublisher(market_dir=tmp_path / "nope", skills_dir=tmp_path / "skills")

        def make_publisher(*, project_root: str) -> FakePublisher:
            del project_root
            return publisher

        monkeypatch.setattr("antigravity_k.engine.skill_publisher.SkillPublisher", make_publisher)
        monkeypatch.chdir(tmp_path)

        body = _json(client.get("/api/system/skills/local/check", params={"since": "2026-01-01T00:00:00Z"}))

        assert body["has_changes"] is True
        new_skills = cast(list[JsonObject], body["new"])
        assert new_skills[0]["name"] == "fresh"
        assert cast(str, body["checked_at"]).endswith("Z")
        del no_gate

    def test_local_check_bad_since_treated_as_epoch(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        no_gate: None,
    ) -> None:
        skill = tmp_path / "skills" / "any"
        skill.mkdir(parents=True)
        publisher = FakePublisher(market_dir=tmp_path / "nope", skills_dir=tmp_path / "skills")

        def make_publisher(*, project_root: str) -> FakePublisher:
            del project_root
            return publisher

        monkeypatch.setattr("antigravity_k.engine.skill_publisher.SkillPublisher", make_publisher)
        monkeypatch.chdir(tmp_path)

        body = _json(client.get("/api/system/skills/local/check", params={"since": "not-a-date"}))

        new_skills = cast(list[JsonObject], body["new"])
        assert new_skills[0]["name"] == "any"  # epoch 이후 전부 신규 취급
        del no_gate


class TestPublishEndpoints:
    def test_npm_requires_skill_name(self, client: TestClient) -> None:
        body = _json(client.post("/api/system/skills/publish-npm", json={}))
        assert body == {"ok": False, "error": "skill_name is required"}

    def test_npm_rejects_non_string_skill_name(self, client: TestClient) -> None:
        response = client.post("/api/system/skills/publish-npm", json={"skill_name": 123})

        assert response.status_code == 400

    def test_github_rejects_non_string_skill_name(self, client: TestClient) -> None:
        response = client.post(
            "/api/system/skills/publish-github",
            json={"skill_name": 123, "repo": "org/repo"},
        )

        assert response.status_code == 400

    def test_github_requires_repo_unless_dry_run(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        no_gate: None,
    ) -> None:
        class DryRunPublisher(FakePublisher):
            @override
            def publish_to_github(self, *_args: object, **_kwargs: object) -> PublishResultStub:
                return _make_publish_result(action="dry-run", pr_url=None)

        publisher = DryRunPublisher(market_dir=None, skills_dir=None)

        def make_publisher(*, project_root: str) -> DryRunPublisher:
            del project_root
            return publisher

        monkeypatch.setattr(
            "antigravity_k.engine.skill_publisher.SkillPublisher",
            make_publisher,
        )

        dry = _json(
            client.post(
                "/api/system/skills/publish-github",
                json={"skill_name": "s", "repo": "", "dry_run": True},
            )
        )
        without_repo = _json(client.post("/api/system/skills/publish-github", json={"skill_name": "s", "repo": ""}))
        del no_gate

        assert dry["ok"] is True
        assert without_repo["ok"] is False

    def test_npm_publish_result_mapping(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        no_gate: None,
    ) -> None:
        class NpmPublisher(FakePublisher):
            @override
            def publish_to_npm(
                self,
                name: str,
                version: str | None = None,
                tag: str = "latest",
                dry_run: bool = False,
            ) -> PublishResultStub:
                del version, dry_run
                return _make_publish_result(skill_name=name, tag_used=tag)

        publisher = NpmPublisher(market_dir=None, skills_dir=None)

        def make_publisher(*, project_root: str) -> NpmPublisher:
            del project_root
            return publisher

        monkeypatch.setattr(
            "antigravity_k.engine.skill_publisher.SkillPublisher",
            make_publisher,
        )

        body = _json(
            client.post(
                "/api/system/skills/publish-npm",
                json={"skill_name": "s", "tag": "beta"},
            )
        )
        result = _as_object(body["publish_result"])
        del no_gate

        assert body["ok"] is True
        assert result["summary"] == "summary-ok"
        assert cast(str, result["npm_url"]).endswith("skill-s")

    def test_github_publish_pr_url_mapping(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        no_gate: None,
    ) -> None:
        class GithubPublisher(FakePublisher):
            @override
            def publish_to_github(
                self,
                name: str,
                repo: str,
                base_branch: str = "main",
                draft: bool = False,
                title: str | None = None,
                body: str | None = None,
                dry_run: bool = False,
            ) -> PublishResultStub:
                del repo, base_branch, draft, title, body, dry_run
                return _make_publish_result(
                    action="github-pr",
                    package_name=name,
                    pr_url="https://github.com/org/repo/pull/7",
                )

        publisher = GithubPublisher(market_dir=None, skills_dir=None)

        def make_publisher(*, project_root: str) -> GithubPublisher:
            del project_root
            return publisher

        monkeypatch.setattr(
            "antigravity_k.engine.skill_publisher.SkillPublisher",
            make_publisher,
        )

        body = _json(
            client.post(
                "/api/system/skills/publish-github",
                json={"skill_name": "s", "repo": "org/repo"},
            )
        )
        result = _as_object(body["publish_result"])
        del no_gate

        assert cast(str, result["pr_url"]).endswith("pull/7")
        assert result["action"] == "github-pr"
