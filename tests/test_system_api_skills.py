"""테스트: System API — Skills 브라우저·설치·게시 스위트.
============================================
지연 임포트되는 Installer/MarketClient/Registry/Publisher를 소스 모듈 패치로 격리해
엔드포인트 계약(응답 매핑, 필수값 검증, 권한 게이트, 변경 탐지)을 검증한다.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from antigravity_k.api.routes import system_api
from antigravity_k.api.server import app


@pytest.fixture
def client():
    from antigravity_k.config import config

    headers = {"X-Access-Pin": config.security.access_pin}
    with TestClient(app, raise_server_exceptions=False) as test_client:
        test_client.headers.update(headers)
        yield test_client


@pytest.fixture
def no_gate(monkeypatch):
    monkeypatch.setattr(system_api, "_require_allowed", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def _clear_skills_cache():
    """@cached(ttl=60) 라우트의 테스트 간 응답 재사용을 막는다.

    invalidate_tag는 async라 동기 테스트에서 직접 호출할 수 없어
    태그 인덱스와 엔트리를 동기적으로 비운다.
    """
    from antigravity_k.engine.api_cache import api_cache

    keys = api_cache._tag_index.pop("skills", set())
    for key in keys:
        api_cache._entries.pop(key, None)
    yield
    api_cache._tag_index.pop("skills", set())


@pytest.fixture
def loader(monkeypatch):
    sl = MagicMock()
    sl.list_skills.return_value = [{"id": "demo", "source": "global"}]
    monkeypatch.setattr(system_api, "__get_skill_loader", lambda: sl)
    return sl


# ─── 목록/검색 ────────────────────────────────────────────────────


class TestSkillsListing:
    def test_list_ok(self, client, loader):
        body = client.get("/api/system/skills").json()

        assert body == {"ok": True, "skills": [{"id": "demo", "source": "global"}]}

    def test_installed_maps_registry_fields(self, client, monkeypatch, loader):
        variant = SimpleNamespace(
            skill_name="code-review",
            version="1.2.0",
            is_loaded=True,
            mcp_server_id="srv-9",
            security_findings=["pin"],
        )
        registry = MagicMock(list_installed=lambda: [variant])
        monkeypatch.setattr(
            "antigravity_k.engine.skill_market_registry.SkillMarketRegistry",
            lambda **kw: registry,
        )

        body = client.get("/api/system/skills/installed").json()

        assert body["installed"][0] == {
            "name": "code-review",
            "version": "1.2.0",
            "is_loaded": True,
            "mcp_server_id": "srv-9",
            "security_issues": ["pin"],
        }

    def test_mcp_servers_passthrough(self, client, monkeypatch):
        registry = MagicMock(list_skills_with_mcp=lambda: [{"name": "fs", "status": "up"}])
        monkeypatch.setattr("antigravity_k.tools.mcp_tool_loader.MCPServerRegistry", lambda: registry)

        assert client.get("/api/system/skills/mcp").json()["servers"] == [{"name": "fs", "status": "up"}]

    def test_search_formats_results(self, client, monkeypatch):
        client_mock = MagicMock(
            search=lambda q, limit: [SimpleNamespace(to_dict=lambda: {"name": "@antigravity-k/skill-x"})]
        )
        monkeypatch.setattr("antigravity_k.engine.skill_market_client.SkillMarketClient", lambda **kw: client_mock)

        body = client.get("/api/system/skills/search", params={"q": "x", "limit": 5}).json()

        assert body["count"] == 1 and body["results"][0]["name"] == "@antigravity-k/skill-x"


# ─── 설치/제거 ────────────────────────────────────────────────────


class TestInstallRemove:
    def test_install_requires_package_name(self, client):
        body = client.post("/api/system/skills/install", json={}).json()
        assert body == {"ok": False, "error": "package_name is required"}

    def test_install_success_mapping(self, client, monkeypatch, loader, no_gate):
        registry = MagicMock(install=lambda pkg: {"success": True, "package": pkg})
        monkeypatch.setattr(
            "antigravity_k.engine.skill_market_registry.SkillMarketRegistry",
            lambda **kw: registry,
        )

        body = client.post("/api/system/skills/install", json={"package_name": "@antigravity-k/skill-x"}).json()

        assert body["ok"] is True and body["result"]["package"].endswith("skill-x")

    def test_install_gate_denial_raises_403(self, client, monkeypatch):
        def deny(*a, **k):
            raise HTTPException(status_code=403, detail="denied")

        monkeypatch.setattr(system_api, "_require_allowed", deny)

        assert client.post("/api/system/skills/install", json={"package_name": "x"}).status_code == 403

    def test_remove_requires_skill_name(self, client):
        body = client.post("/api/system/skills/remove", json={}).json()
        assert body == {"ok": False, "error": "skill_name is required"}

    def test_remove_success_mapping(self, client, monkeypatch, loader, no_gate):
        registry = MagicMock(remove=lambda name: {"success": False, "reason": "not installed"})
        monkeypatch.setattr(
            "antigravity_k.engine.skill_market_registry.SkillMarketRegistry",
            lambda **kw: registry,
        )

        body = client.post("/api/system/skills/remove", json={"skill_name": "ghost"}).json()

        assert body["ok"] is False and body["result"]["reason"] == "not installed"


# ─── 로컬 스킬 & 게시 ─────────────────────────────────────────────


class FakePublisher:
    """market_dir/skills_dir과 검증 결과를 주입하는 가짜."""

    def __init__(
        self,
        market_dir,
        skills_dir,
        valid=SimpleNamespace(
            valid=True,
            has_skill_md=True,
            has_readme=False,
            version="0.1.0",
            tool_count=2,
            warnings=[],
        ),
    ):
        self.market_dir = market_dir
        self.skills_dir = skills_dir
        self._valid = valid

    def _validate_for_publish(self, skill_dir, name):
        return self._valid

    # 게시 계약
    @staticmethod
    def _npm_result(**kw):
        base = dict(
            success=True,
            action="published",
            skill_name="s",
            package_name="@antigravity-k/skill-s",
            version="0.1.0",
            npm_url="https://www.npmjs.com/package/@antigravity-k/skill-s",
            errors=[],
            warnings=[],
        )
        base.update(kw)
        return SimpleNamespace(summary=lambda: "summary-ok", **base)


class TestLocalSkills:
    def test_local_lists_market_then_agent_dirs(self, client, monkeypatch, tmp_path, no_gate):
        market = tmp_path / "market" / "m-skill"
        local = tmp_path / "skills" / "l-skill"
        market.mkdir(parents=True)
        local.mkdir(parents=True)

        publisher = FakePublisher(market_dir=tmp_path / "market", skills_dir=tmp_path / "skills")
        monkeypatch.setattr(
            "antigravity_k.engine.skill_publisher.SkillPublisher",
            lambda project_root: publisher,
        )
        monkeypatch.chdir(tmp_path)

        body = client.get("/api/system/skills/local").json()

        sources = {s["name"]: s["source"] for s in body["skills"]}
        assert sources == {"m-skill": "market", "l-skill": "local"}
        assert body["count"] == 2

    def test_local_check_detects_new_since_timestamp(self, client, monkeypatch, tmp_path, no_gate):
        import os
        import time

        skill = tmp_path / "skills" / "fresh"
        skill.mkdir(parents=True)
        future = time.time() + 10_000
        os.utime(skill, (future, future))

        publisher = FakePublisher(market_dir=tmp_path / "nope", skills_dir=tmp_path / "skills")
        monkeypatch.setattr(
            "antigravity_k.engine.skill_publisher.SkillPublisher",
            lambda project_root: publisher,
        )
        monkeypatch.chdir(tmp_path)

        body = client.get("/api/system/skills/local/check", params={"since": "2026-01-01T00:00:00Z"}).json()

        assert body["has_changes"] is True
        assert body["new"][0]["name"] == "fresh"
        assert body["checked_at"].endswith("Z")

    def test_local_check_bad_since_treated_as_epoch(self, client, monkeypatch, tmp_path, no_gate):
        skill = tmp_path / "skills" / "any"
        skill.mkdir(parents=True)
        publisher = FakePublisher(market_dir=tmp_path / "nope", skills_dir=tmp_path / "skills")
        monkeypatch.setattr(
            "antigravity_k.engine.skill_publisher.SkillPublisher",
            lambda project_root: publisher,
        )
        monkeypatch.chdir(tmp_path)

        body = client.get("/api/system/skills/local/check", params={"since": "not-a-date"}).json()

        assert body["new"][0]["name"] == "any"  # epoch 이후 전부 신규 취급


class TestPublishEndpoints:
    def test_npm_requires_skill_name(self, client):
        body = client.post("/api/system/skills/publish-npm", json={}).json()
        assert body == {"ok": False, "error": "skill_name is required"}

    def test_github_requires_repo_unless_dry_run(self, client, monkeypatch, no_gate):
        publisher = FakePublisher(market_dir=None, skills_dir=None)
        monkeypatch.setattr(
            "antigravity_k.engine.skill_publisher.SkillPublisher",
            lambda project_root: publisher,
        )
        publisher.publish_to_github = lambda *a, **kw: FakePublisher._npm_result(action="dry-run", pr_url=None)

        dry = client.post(
            "/api/system/skills/publish-github",
            json={"skill_name": "s", "repo": "", "dry_run": True},
        ).json()
        without_repo = client.post("/api/system/skills/publish-github", json={"skill_name": "s", "repo": ""}).json()

        assert dry["ok"] is True
        assert without_repo["ok"] is False

    def test_npm_publish_result_mapping(self, client, monkeypatch, no_gate):
        publisher = FakePublisher(market_dir=None, skills_dir=None)

        def publish_to_npm(name, version=None, tag="latest", dry_run=False):
            return FakePublisher._npm_result(skill_name=name, tag_used=tag)

        publisher.publish_to_npm = publish_to_npm
        monkeypatch.setattr(
            "antigravity_k.engine.skill_publisher.SkillPublisher",
            lambda project_root: publisher,
        )

        body = client.post(
            "/api/system/skills/publish-npm",
            json={"skill_name": "s", "tag": "beta"},
        ).json()

        assert body["ok"] is True
        assert body["publish_result"]["summary"] == "summary-ok"
        assert body["publish_result"]["npm_url"].endswith("skill-s")

    def test_github_publish_pr_url_mapping(self, client, monkeypatch, no_gate):
        publisher = FakePublisher(market_dir=None, skills_dir=None)

        def publish_to_github(name, **kwargs):
            return FakePublisher._npm_result(
                action="github-pr",
                package_name=name,
                pr_url="https://github.com/org/repo/pull/7",
            )

        publisher.publish_to_github = publish_to_github
        monkeypatch.setattr(
            "antigravity_k.engine.skill_publisher.SkillPublisher",
            lambda project_root: publisher,
        )

        body = client.post(
            "/api/system/skills/publish-github",
            json={"skill_name": "s", "repo": "org/repo"},
        ).json()

        assert body["publish_result"]["pr_url"].endswith("pull/7")
        assert body["publish_result"]["action"] == "github-pr"
