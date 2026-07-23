"""Tests for the SkillMarketClient module."""

import json
import tempfile
from pathlib import Path
from unittest import mock

from antigravity_k.engine.skill_market_client import (
    InstalledSkill,
    SkillDetail,
    SkillListing,
    SkillMarketClient,
)

# ─── Data Model Tests ───────────────────────────────────────────────


class TestSkillListing:
    def test_defaults(self):
        s = SkillListing(name="test", version="1.0.0", description="desc")
        assert s.keywords == []
        assert s.publisher == ""

    def test_skill_name_agk(self):
        s = SkillListing(name="@antigravity-k/skill-review", version="1.0", description="r")
        assert s.skill_name == "review"

    def test_skill_name_plain(self):
        s = SkillListing(name="plain", version="1.0", description="d")
        assert s.skill_name == "plain"

    def test_is_agk_skill_true(self):
        s = SkillListing(name="@antigravity-k/skill-test", version="1.0", description="d")
        assert s.is_agk_skill is True

    def test_is_agk_skill_false(self):
        s = SkillListing(name="other", version="1.0", description="d")
        assert s.is_agk_skill is False

    def test_to_dict(self):
        s = SkillListing(name="test", version="2.0", description="desc", keywords=["a", "b"])
        d = s.to_dict()
        assert d["name"] == "test"
        assert d["skill_name"] == "test"
        assert d["keywords"] == ["a", "b"]


class TestSkillDetail:
    def test_defaults(self):
        d = SkillDetail(name="test", version="1.0", description="desc")
        assert d.skill_name == "test"
        assert d.is_agk_skill is False

    def test_skill_name_agk(self):
        d = SkillDetail(name="@antigravity-k/skill-test", version="1.0", description="d")
        assert d.skill_name == "test"

    def test_is_agk_skill_true_by_flag(self):
        d = SkillDetail(name="plain", version="1.0", description="d", agk_skill=True)
        assert d.is_agk_skill is True

    def test_to_dict(self):
        d = SkillDetail(
            name="test",
            version="1.0",
            description="desc",
            keywords=["k1"],
            agk_skill=True,
            agk_categories=["dev"],
        )
        d2 = d.to_dict()
        assert d2["name"] == "test"
        assert d2["agk"]["skill"] is True
        assert d2["agk"]["categories"] == ["dev"]


class TestInstalledSkill:
    def test_defaults(self):
        s = InstalledSkill(name="test", version="1.0", skill_name="test")
        assert s.is_outdated is False

    def test_to_dict(self):
        s = InstalledSkill(
            name="@antigravity-k/skill-test",
            version="2.0",
            skill_name="test",
            risk_level="safe",
            mcp_server_id="srv",
        )
        d = s.to_dict()
        assert d["name"] == "@antigravity-k/skill-test"
        assert d["mcp_server_id"] == "srv"


# ─── SkillMarketClient: Init ────────────────────────────────────────


class TestClientInit:
    def test_default_project_root(self):
        with mock.patch("antigravity_k.engine.skill_market_client.os.getcwd", return_value="/tmp/proj"):
            c = SkillMarketClient()
            assert c.project_root == "/tmp/proj"

    def test_custom_project_root(self):
        c = SkillMarketClient(project_root="/my/proj")
        assert c.project_root == "/my/proj"

    def test_state_file_path(self):
        with mock.patch("pathlib.Path.home", return_value=Path("/home/user")):
            c = SkillMarketClient(project_root="/proj")
            assert ".antigravity-k/skills-market.json" in str(c._state_file)


# ─── SkillMarketClient: Search ──────────────────────────────────────


class TestSearch:
    @mock.patch("antigravity_k.engine.skill_market_client.SkillMarketClient._run_npm_search")
    def test_search_basic(self, mock_search):
        mock_search.return_value = [
            SkillListing(name="@antigravity-k/skill-review", version="1.0", description="Great code review"),
        ]
        c = SkillMarketClient(project_root="/tmp")
        results = c.search("code review")
        assert len(results) > 0
        assert results[0].name == "@antigravity-k/skill-review"

    @mock.patch("antigravity_k.engine.skill_market_client.SkillMarketClient._run_npm_search")
    def test_search_empty(self, mock_search):
        mock_search.return_value = []
        c = SkillMarketClient(project_root="/tmp")
        results = c.search("nothing")
        assert results == []

    @mock.patch("antigravity_k.engine.skill_market_client.SkillMarketClient._run_npm_search")
    def test_search_agk_priority(self, mock_search):
        mock_search.return_value = [
            SkillListing(name="regular-pkg", version="1.0", description="a regular package"),
            SkillListing(name="@antigravity-k/skill-review", version="1.0", description="Code review skill"),
        ]
        c = SkillMarketClient(project_root="/tmp")
        results = c.search("review")
        # AGK skill should come first
        assert results[0].name == "@antigravity-k/skill-review"

    @mock.patch("antigravity_k.engine.skill_market_client.SkillMarketClient._run_npm_search")
    def test_search_keyword_fallback(self, mock_search):
        # First call returns non-AGK results, second call returns AGK results
        mock_search.side_effect = [
            [SkillListing(name="pkg1", version="1.0", description="test")],
            [SkillListing(name="@antigravity-k/skill-test", version="1.0", description="a test skill")],
        ]
        c = SkillMarketClient(project_root="/tmp")
        results = c.search("test")
        assert len(results) >= 1

    @mock.patch("antigravity_k.engine.skill_market_client.SkillMarketClient._run_npm_search")
    def test_search_scoring(self, mock_search):
        mock_search.return_value = [
            SkillListing(name="other", version="1.0", description="no match"),
            SkillListing(name="@antigravity-k/skill-mymatch", version="1.0", description="mymatch skill"),
        ]
        c = SkillMarketClient(project_root="/tmp")
        results = c.search("mymatch")
        # Description match should boost score
        assert len(results) >= 1


class TestSearchByCategory:
    @mock.patch("antigravity_k.engine.skill_market_client.SkillMarketClient.search")
    def test_search_by_category(self, mock_search):
        mock_search.return_value = [SkillListing(name="test", version="1.0", description="d")]
        c = SkillMarketClient(project_root="/tmp")
        results = c.search_by_category("devops")
        assert len(results) == 1
        # Should call search with "keywords:devops"
        assert "keywords:devops" in mock_search.call_args[0][0]


# ─── SkillMarketClient: Get Detail ──────────────────────────────────


class TestGetDetail:
    @mock.patch("antigravity_k.engine.skill_market_client.subprocess.run")
    def test_get_detail_success(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = json.dumps(
            {
                "name": "@antigravity-k/skill-test",
                "version": "1.0.0",
                "description": "Test skill",
                "keywords": ["skill"],
                "antigravityK": {"skill": True, "displayName": "Test"},
            }
        )
        c = SkillMarketClient(project_root="/tmp")
        detail = c.get_detail("@antigravity-k/skill-test")
        assert detail is not None
        assert detail.version == "1.0.0"
        assert detail.agk_skill is True

    @mock.patch("antigravity_k.engine.skill_market_client.subprocess.run")
    def test_get_detail_version_dict(self, mock_run):
        """nested version dict is handled correctly"""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = json.dumps(
            {
                "name": "@antigravity-k/skill-test",
                "version": {"1.0.0": "latest", "0.9.0": "previous"},
                "dist-tags": {"latest": "1.0.0"},
                "description": "Test",
                "antigravityK": {"skill": True},
            }
        )
        c = SkillMarketClient(project_root="/tmp")
        detail = c.get_detail("@antigravity-k/skill-test")
        assert detail is not None
        assert detail.version == "1.0.0"

    @mock.patch("antigravity_k.engine.skill_market_client.subprocess.run")
    def test_get_detail_description_dict(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = json.dumps(
            {
                "name": "test",
                "version": "1.0.0",
                "description": {"1.0.0": "desc1", "0.9.0": "desc2"},
            }
        )
        c = SkillMarketClient(project_root="/tmp")
        detail = c.get_detail("test")
        assert detail is not None
        assert detail.description in ("desc1", "")

    @mock.patch("antigravity_k.engine.skill_market_client.subprocess.run")
    def test_get_detail_keywords_string(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = json.dumps(
            {
                "name": "test",
                "version": "1.0.0",
                "description": "test",
                "keywords": "skill",
            }
        )
        c = SkillMarketClient(project_root="/tmp")
        detail = c.get_detail("test")
        assert detail is not None
        assert "skill" in detail.keywords

    @mock.patch("antigravity_k.engine.skill_market_client.subprocess.run")
    def test_get_detail_npm_fail(self, mock_run):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "error"
        c = SkillMarketClient(project_root="/tmp")
        detail = c.get_detail("@antigravity-k/skill-nonexistent")
        assert detail is None

    @mock.patch("antigravity_k.engine.skill_market_client.subprocess.run")
    def test_get_detail_timeout(self, mock_run):
        mock_run.side_effect = __import__("subprocess").TimeoutExpired("cmd", 30)
        c = SkillMarketClient(project_root="/tmp")
        detail = c.get_detail("test")
        assert detail is None

    @mock.patch("antigravity_k.engine.skill_market_client.subprocess.run")
    def test_get_detail_file_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError("npm")
        c = SkillMarketClient(project_root="/tmp")
        detail = c.get_detail("test")
        assert detail is None

    @mock.patch("antigravity_k.engine.skill_market_client.subprocess.run")
    def test_get_detail_mcp_config(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = json.dumps(
            {
                "name": "test",
                "version": "1.0.0",
                "description": "test",
                "antigravityK": {
                    "skill": True,
                    "mcp": {"serverId": "srv1", "transport": "streamable-http"},
                },
            }
        )
        c = SkillMarketClient(project_root="/tmp")
        detail = c.get_detail("test")
        assert detail is not None
        assert detail.agk_mcp_server_id == "srv1"
        assert detail.agk_mcp_transport == "streamable-http"

    @mock.patch("antigravity_k.engine.skill_market_client.subprocess.run")
    def test_get_detail_json_decode_error(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "not-json{{{"
        c = SkillMarketClient(project_root="/tmp")
        detail = c.get_detail("test")
        assert detail is None

    @mock.patch("antigravity_k.engine.skill_market_client.subprocess.run")
    def test_get_detail_exception(self, mock_run):
        mock_run.side_effect = RuntimeError("unexpected")
        c = SkillMarketClient(project_root="/tmp")
        detail = c.get_detail("test")
        assert detail is None


# ─── SkillMarketClient: Installed Skills ────────────────────────────


class TestGetInstalled:
    def test_empty_when_no_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            c = SkillMarketClient(project_root=tmpdir)
            installed = c.get_installed()
            assert installed == []

    def test_read_from_market_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            market_dir = Path(tmpdir) / ".agent" / "skills" / "market"
            skill_dir = market_dir / "my-skill"
            skill_dir.mkdir(parents=True)
            meta = {
                "name": "@antigravity-k/skill-my-skill",
                "version": "1.0.0",
                "description": "My skill",
                "installed_at": "2026-01-01T00:00:00",
                "updated_at": "2026-01-01T00:00:00",
                "risk_level": "safe",
                "trust_level": "verified",
            }
            (skill_dir / ".agk_meta.json").write_text(json.dumps(meta))

            c = SkillMarketClient(project_root=tmpdir)
            installed = c.get_installed()
            assert len(installed) == 1
            assert installed[0].skill_name == "my-skill"
            assert installed[0].version == "1.0.0"

    def test_global_state_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / ".antigravity-k"
            state_dir.mkdir(parents=True)
            state_file = state_dir / "skills-market.json"
            state_file.write_text(
                json.dumps(
                    {
                        "installed": {
                            "global-skill": {
                                "name": "@antigravity-k/skill-global-skill",
                                "version": "2.0.0",
                                "install_path": "/some/path",
                                "installed_at": "2026-01-01T00:00:00",
                                "updated_at": "2026-01-01T00:00:00",
                            },
                        },
                    }
                )
            )
            with mock.patch("antigravity_k.engine.skill_market_client.Path.home", return_value=Path(tmpdir)):
                c = SkillMarketClient(project_root="/tmp/other")
                installed = c.get_installed()
                assert len(installed) >= 1
                assert any(s.skill_name == "global-skill" for s in installed)

    def test_corrupted_meta_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            market_dir = Path(tmpdir) / ".agent" / "skills" / "market"
            skill_dir = market_dir / "broken"
            skill_dir.mkdir(parents=True)
            (skill_dir / ".agk_meta.json").write_text("not-json{{{")

            c = SkillMarketClient(project_root=tmpdir)
            installed = c.get_installed()
            assert installed == []


class TestIsInstalled:
    def test_is_installed_true(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            market_dir = Path(tmpdir) / ".agent" / "skills" / "market"
            skill_dir = market_dir / "my-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / ".agk_meta.json").write_text(
                json.dumps(
                    {
                        "name": "test",
                        "version": "1.0.0",
                    }
                )
            )
            c = SkillMarketClient(project_root=tmpdir)
            assert c.is_installed("my-skill") is True

    def test_is_installed_false(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            c = SkillMarketClient(project_root=tmpdir)
            assert c.is_installed("nonexistent") is False


class TestRecordInstallation:
    def test_record_new(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch("antigravity_k.engine.skill_market_client.Path.home", return_value=Path(tmpdir)):
                c = SkillMarketClient(project_root="/proj")
                c.record_installation("@antigravity-k/skill-test", "1.0.0", "/path/to/skill")
                state_file = Path(tmpdir) / ".antigravity-k" / "skills-market.json"
                assert state_file.exists()
                data = json.loads(state_file.read_text(encoding="utf-8"))
                assert "test" in data["installed"]
                assert data["installed"]["test"]["version"] == "1.0.0"

    def test_record_update_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / ".antigravity-k"
            state_dir.mkdir(parents=True)
            state_file = state_dir / "skills-market.json"
            state_file.write_text(
                json.dumps(
                    {
                        "installed": {"test": {"version": "1.0.0", "install_path": "/old"}},
                    }
                )
            )
            with mock.patch("antigravity_k.engine.skill_market_client.Path.home", return_value=Path(tmpdir)):
                c = SkillMarketClient(project_root="/proj")
                c.record_installation("@antigravity-k/skill-test", "2.0.0", "/new")
                data = json.loads(state_file.read_text(encoding="utf-8"))
                assert data["installed"]["test"]["version"] == "2.0.0"
                assert data["installed"]["test"]["install_path"] == "/new"

    def test_record_write_error(self):
        with mock.patch(
            "antigravity_k.engine.skill_market_client.Path.write_text", side_effect=PermissionError("denied")
        ):
            with mock.patch("antigravity_k.engine.skill_market_client.Path.home", return_value=Path("/tmp")):
                c = SkillMarketClient(project_root="/proj")
                c.record_installation("test", "1.0", "/p")  # should not raise


class TestRemoveInstallation:
    def test_remove_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / ".antigravity-k"
            state_dir.mkdir(parents=True)
            state_file = state_dir / "skills-market.json"
            state_file.write_text(
                json.dumps(
                    {
                        "installed": {"skill1": {}, "skill2": {}},
                    }
                )
            )
            with mock.patch("antigravity_k.engine.skill_market_client.Path.home", return_value=Path(tmpdir)):
                c = SkillMarketClient(project_root="/proj")
                c.remove_installation("skill1")
                data = json.loads(state_file.read_text(encoding="utf-8"))
                assert "skill1" not in data["installed"]
                assert "skill2" in data["installed"]

    def test_remove_nonexistent_state_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch("antigravity_k.engine.skill_market_client.Path.home", return_value=Path(tmpdir)):
                c = SkillMarketClient(project_root="/proj")
                c.remove_installation("test")  # should not raise


# ─── SkillMarketClient: Utilities ───────────────────────────────────


class TestIsValidPackageName:
    def test_valid(self):
        assert SkillMarketClient.is_valid_package_name("@antigravity-k/skill-test") is True

    def test_invalid_scope(self):
        assert SkillMarketClient.is_valid_package_name("@other/skill-test") is False

    def test_empty(self):
        assert SkillMarketClient.is_valid_package_name("@antigravity-k/skill-") is False

    def test_no_prefix(self):
        assert SkillMarketClient.is_valid_package_name("plain") is False


class TestFormatSearchResults:
    def test_empty_results(self):
        c = SkillMarketClient(project_root="/tmp")
        result = c.format_search_results([])
        assert "결과가 없습니다" in result

    def test_with_results(self):
        c = SkillMarketClient(project_root="/tmp")
        results = [
            SkillListing(name="@antigravity-k/skill-a", version="1.0", description="Skill A description"),
            SkillListing(name="@antigravity-k/skill-b", version="2.0", description="Skill B"),
        ]
        result = c.format_search_results(results)
        assert "검색 결과" in result
        assert "@antigravity-k/skill-a" in result

    def test_truncates_long_description(self):
        c = SkillMarketClient(project_root="/tmp")
        long_desc = "x" * 200
        results = [SkillListing(name="test", version="1.0", description=long_desc)]
        result = c.format_search_results(results)
        assert "..." in result


# ─── SkillMarketClient: Internal npm search ─────────────────────────


class TestRunNpmSearch:
    @mock.patch("antigravity_k.engine.skill_market_client.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = json.dumps(
            [
                {"name": "@antigravity-k/skill-test", "version": "1.0.0", "description": "Test skill"},
            ]
        )
        c = SkillMarketClient(project_root="/tmp")
        results = c._run_npm_search("test")
        assert len(results) == 1
        assert results[0].name == "@antigravity-k/skill-test"

    @mock.patch("antigravity_k.engine.skill_market_client.subprocess.run")
    def test_npm_error(self, mock_run):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "npm ERR!"
        c = SkillMarketClient(project_root="/tmp")
        results = c._run_npm_search("test")
        assert results == []

    @mock.patch("antigravity_k.engine.skill_market_client.subprocess.run")
    def test_timeout(self, mock_run):
        mock_run.side_effect = __import__("subprocess").TimeoutExpired("cmd", 30)
        c = SkillMarketClient(project_root="/tmp")
        results = c._run_npm_search("test")
        assert results == []

    @mock.patch("antigravity_k.engine.skill_market_client.subprocess.run")
    def test_file_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError("npm")
        c = SkillMarketClient(project_root="/tmp")
        results = c._run_npm_search("test")
        assert results == []

    @mock.patch("antigravity_k.engine.skill_market_client.subprocess.run")
    def test_json_decode_error(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "not-json{{{"
        c = SkillMarketClient(project_root="/tmp")
        results = c._run_npm_search("test")
        assert results == []

    @mock.patch("antigravity_k.engine.skill_market_client.subprocess.run")
    def test_exception(self, mock_run):
        mock_run.side_effect = RuntimeError("unexpected")
        c = SkillMarketClient(project_root="/tmp")
        results = c._run_npm_search("test")
        assert results == []

    @mock.patch("antigravity_k.engine.skill_market_client.subprocess.run")
    def test_not_a_list_response(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = json.dumps({"not": "a list"})
        c = SkillMarketClient(project_root="/tmp")
        results = c._run_npm_search("test")
        assert results == []

    @mock.patch("antigravity_k.engine.skill_market_client.subprocess.run")
    def test_non_dict_item(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = json.dumps(["string", 123, None])
        c = SkillMarketClient(project_root="/tmp")
        results = c._run_npm_search("test")
        assert results == []


# ─── SkillMarketClient: Parse View Result ───────────────────────────


class TestParseViewResult:
    def test_basic(self):
        c = SkillMarketClient(project_root="/tmp")
        raw = {
            "name": "@antigravity-k/skill-test",
            "version": "1.0.0",
            "description": "A test",
            "antigravityK": {"skill": True},
        }
        detail = c._parse_view_result("@antigravity-k/skill-test", raw)
        assert detail.name == "@antigravity-k/skill-test"
        assert detail.version == "1.0.0"
        assert detail.agk_skill is True

    def test_multiple_versions(self):
        c = SkillMarketClient(project_root="/tmp")
        raw = {
            "name": "test",
            "version": {"1.0.0": "latest", "0.9.0": "old"},
            "dist-tags": {"latest": "1.0.0"},
            "description": "test",
        }
        detail = c._parse_view_result("test", raw)
        assert detail.version == "1.0.0"

    def test_antigravityk_not_dict(self):
        c = SkillMarketClient(project_root="/tmp")
        raw = {
            "name": "@antigravity-k/skill-test",
            "version": "1.0.0",
            "description": "d",
            "antigravityK": "invalid",
        }
        detail = c._parse_view_result("@antigravity-k/skill-test", raw)
        assert detail.agk_skill is True  # scope-based fallback
        assert detail.agk_display_name == ""

    def test_mcp_not_dict(self):
        c = SkillMarketClient(project_root="/tmp")
        raw = {
            "name": "test",
            "version": "1.0.0",
            "description": "d",
            "antigravityK": {"skill": True, "mcp": "invalid"},
        }
        detail = c._parse_view_result("test", raw)
        assert detail.agk_mcp_server_id == ""

    def test_license_and_repository(self):
        c = SkillMarketClient(project_root="/tmp")
        raw = {
            "name": "test",
            "version": "1.0.0",
            "description": "d",
            "license": "MIT",
            "repository": {"url": "https://github.com/test/repo"},
            "readmeFilename": "README.md",
            "readme": "# Readme",
        }
        detail = c._parse_view_result("test", raw)
        assert detail.license == "MIT"
        assert "github.com" in detail.repository
        assert detail.has_readme is True
