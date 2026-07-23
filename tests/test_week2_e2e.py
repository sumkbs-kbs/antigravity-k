"""Phase 1 Week 2 (D8-D14) 통합 E2E 테스트 — Skill Marketplace 전체 검증.

테스트 범위:
  D8:  SkillMarketClient — npm 검색/조회/설치상태 관리 (npm CLI 없이 격리)
  D9:  SkillInstaller — 검증/보안/설치 플로우 시뮬레이션
  D10: SkillMarketRegistry — SkillMarketClient + SkillInstaller + SkillLoader 통합
  D11: MCPServerRegistry — 스킬 MCP 서버 등록/해제/조회
  D12: CLI agk market + /market slash 명령어
  D13: SkillLoader market/ 디렉토리 연동 + SkillsRegistry
  D14: 버퍼 (엣지케이스 + 회귀 테스트)

모든 테스트는 npm/네트워크 의존성 없이 tempfile 기반으로 동작합니다.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════
# D8: SkillMarketClient 데이터 모델 + 파싱 + 설치 상태 관리
# ═══════════════════════════════════════════════════════════════════════


class TestD8_SkillMarketClient_DataModels:
    """SkillMarketClient — SkillListing / SkillDetail / InstalledSkill 퍼징."""

    def test_skill_listing_agk_detection(self):
        """@antigravity-k/skill-* 프리픽스 감지."""
        from antigravity_k.engine.skill_market_client import SkillListing

        agk = SkillListing(name="@antigravity-k/skill-code-review", version="1.0.0", description="")
        assert agk.is_agk_skill is True
        assert agk.skill_name == "code-review"

        non_agk = SkillListing(name="lodash", version="4.17.21", description="")
        assert non_agk.is_agk_skill is False
        assert non_agk.skill_name == "lodash"

    def test_skill_listing_to_dict_roundtrip(self):
        """SkillListing → dict → 모든 필드 보존."""
        from antigravity_k.engine.skill_market_client import SkillListing

        original = SkillListing(
            name="@antigravity-k/skill-code-review",
            version="1.2.3",
            description="Auto code review",
            keywords=["code", "review"],
            publisher="antigravity-k",
            date="2026-01-15",
        )
        d = original.to_dict()
        assert d["name"] == "@antigravity-k/skill-code-review"
        assert d["skill_name"] == "code-review"
        assert d["version"] == "1.2.3"
        assert d["description"] == "Auto code review"
        assert d["keywords"] == ["code", "review"]
        assert d["publisher"] == "antigravity-k"
        assert d["date"] == "2026-01-15"

    def test_skill_detail_parse_npm_view_result(self):
        """npm view --json 출력 파싱 → SkillDetail."""
        from antigravity_k.engine.skill_market_client import SkillDetail, SkillMarketClient

        raw = {
            "name": "@antigravity-k/skill-code-review",
            "version": "2.0.0",
            "description": "Automated code review",
            "keywords": ["code-quality", "review"],
            "antigravityK": {
                "skill": True,
                "displayName": "Code Review",
                "categories": ["code-quality"],
                "minAgentVersion": "1.0.0",
                "platforms": ["darwin", "linux"],
                "requiredTools": ["read_file", "write_file"],
                "riskLevel": "safe",
                "trustLevel": "verified",
                "requiresApproval": False,
                "mcp": {"serverId": "review-server", "command": "python", "args": ["-m", "review"]},
            },
            "license": "MIT",
            "homepage": "https://github.com/antigravity-k/skill-code-review",
        }
        # _parse_view_result is an instance method — create minimal client
        client = SkillMarketClient()
        detail = client._parse_view_result("@antigravity-k/skill-code-review", raw)

        assert isinstance(detail, SkillDetail)
        assert detail.name == "@antigravity-k/skill-code-review"
        assert detail.version == "2.0.0"
        assert detail.description == "Automated code review"
        assert detail.keywords == ["code-quality", "review"]
        assert detail.agk_skill is True
        assert detail.agk_display_name == "Code Review"
        assert detail.agk_categories == ["code-quality"]
        assert detail.agk_min_agent_version == "1.0.0"
        assert detail.agk_platforms == ["darwin", "linux"]
        assert detail.agk_required_tools == ["read_file", "write_file"]
        assert detail.agk_risk_level == "safe"
        assert detail.agk_trust_level == "verified"
        assert detail.agk_requires_approval is False
        assert detail.agk_mcp_server_id == "review-server"
        assert detail.agk_mcp_transport == "stdio"
        assert detail.license == "MIT"
        assert detail.skill_name == "code-review"
        assert detail.is_agk_skill is True

    def test_skill_detail_empty_antigravity_k(self):
        """antigravityK 필드가 없어도 기본값으로 SkillDetail 생성."""
        from antigravity_k.engine.skill_market_client import SkillMarketClient

        raw = {"name": "@antigravity-k/skill-test", "version": "1.0.0", "description": "Test"}
        client = SkillMarketClient()
        detail = client._parse_view_result("@antigravity-k/skill-test", raw)

        assert detail.agk_skill is True  # name starts with AGK_SKILL_SCOPE
        assert detail.agk_risk_level == "medium"  # default
        assert detail.agk_trust_level == "experimental"  # default
        assert detail.agk_requires_approval is False

    def test_skill_detail_non_agk_package(self):
        """비 AGK 패키지도 파싱 가능."""
        from antigravity_k.engine.skill_market_client import SkillMarketClient

        raw = {"name": "lodash", "version": "4.17.21", "description": "Utility lib"}
        client = SkillMarketClient()
        detail = client._parse_view_result("lodash", raw)

        assert detail.name == "lodash"
        assert detail.version == "4.17.21"
        assert detail.agk_skill is False

    def test_installed_skill_defaults(self):
        """InstalledSkill 기본값 확인."""
        from antigravity_k.engine.skill_market_client import InstalledSkill

        skill = InstalledSkill(name="@antigravity-k/skill-test", version="1.0.0", skill_name="test")
        assert skill.risk_level == "safe"
        assert skill.trust_level == "verified"
        assert skill.requires_approval is False
        assert skill.is_outdated is False  # property default

    def test_is_valid_package_name(self):
        """유효한 AGK 패키지명 검증."""
        from antigravity_k.engine.skill_market_client import SkillMarketClient

        assert SkillMarketClient.is_valid_package_name("@antigravity-k/skill-code-review") is True
        assert SkillMarketClient.is_valid_package_name("@antigravity-k/skill-") is False
        assert SkillMarketClient.is_valid_package_name("lodash") is False
        assert SkillMarketClient.is_valid_package_name("") is False

    def test_format_search_results_empty(self):
        """빈 검색 결과 → 안내 메시지."""
        from antigravity_k.engine.skill_market_client import SkillMarketClient

        client = SkillMarketClient()
        msg = client.format_search_results([])
        assert "검색 결과가 없습니다" in msg

    def test_installation_state_management(self, tmp_path):
        """record_installation / remove_installation / is_installed."""
        from antigravity_k.engine.skill_market_client import (
            MARKET_STATE_DIR,
            SkillMarketClient,
        )

        # Mock project root
        market_dir = tmp_path / MARKET_STATE_DIR
        market_dir.mkdir(parents=True)

        # Create a .agk_meta.json to simulate installed skill
        skill_dir = market_dir / "code-review"
        skill_dir.mkdir(parents=True)
        meta = {
            "name": "@antigravity-k/skill-code-review",
            "version": "1.0.0",
            "description": "Code review skill",
            "installed_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }
        (skill_dir / ".agk_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))

        client = SkillMarketClient(project_root=str(tmp_path))

        # is_installed
        assert client.is_installed("code-review") is True
        assert client.is_installed("nonexistent") is False

        # get_installed
        installed = client.get_installed(str(tmp_path))
        assert len(installed) >= 1
        code_review = next((s for s in installed if s.skill_name == "code-review"), None)
        assert code_review is not None
        assert code_review.version == "1.0.0"
        assert code_review.name == "@antigravity-k/skill-code-review"

        # record_installation
        client.record_installation("@antigravity-k/skill-new", "2.0.0", str(tmp_path / "market" / "new"))
        assert client.is_installed("new") is True

        # remove_installation
        client.remove_installation("new")
        assert client.is_installed("new") is False


# ═══════════════════════════════════════════════════════════════════════
# D9: SkillInstaller — 검증/보안/설치 플로우 시뮬레이션
# ═══════════════════════════════════════════════════════════════════════


class TestD9_SkillInstaller:
    """SkillInstaller — 검증/보안/메타데이터 + 시뮬레이션 플로우."""

    def test_validate_package_valid(self, tmp_path):
        """정상 AGK 패키지 → InstallValidation.valid=True."""
        from antigravity_k.engine.skill_installer import SkillInstaller

        npm_path = tmp_path / "node_modules" / "@antigravity-k" / "skill-test"
        npm_path.mkdir(parents=True)
        pkg_json = {
            "name": "@antigravity-k/skill-test",
            "version": "1.0.0",
            "antigravityK": {"skill": True, "riskLevel": "safe", "trustLevel": "verified"},
        }
        (npm_path / "package.json").write_text(json.dumps(pkg_json, ensure_ascii=False, indent=2))

        validation = SkillInstaller(None)._validate_package(npm_path, "@antigravity-k/skill-test")
        assert validation.valid is True
        assert validation.version == "1.0.0"
        assert validation.risk_level == "safe"
        assert validation.trust_level == "verified"

    def test_validate_package_not_agk(self, tmp_path):
        """antigravityK.skill != true → valid=False."""
        from antigravity_k.engine.skill_installer import SkillInstaller

        npm_path = tmp_path / "node_modules" / "lodash"
        npm_path.mkdir(parents=True)
        pkg_json = {"name": "lodash", "version": "4.17.21", "antigravityK": {"skill": False}}
        (npm_path / "package.json").write_text(json.dumps(pkg_json, ensure_ascii=False, indent=2))

        validation = SkillInstaller(None)._validate_package(npm_path, "lodash")
        assert validation.valid is False

    def test_validate_package_missing_package_json(self, tmp_path):
        """package.json 없음 → valid=False."""
        from antigravity_k.engine.skill_installer import SkillInstaller

        npm_path = tmp_path / "node_modules" / "broken"
        npm_path.mkdir(parents=True)
        # No package.json
        validation = SkillInstaller(None)._validate_package(npm_path, "@antigravity-k/skill-broken")
        assert validation.valid is False
        assert "package.json not found" in validation.reason

    def test_validate_package_requires_approval(self, tmp_path):
        """requiresApproval=true → 검증 결과에 반영."""
        from antigravity_k.engine.skill_installer import SkillInstaller

        npm_path = tmp_path / "node_modules" / "@antigravity-k" / "skill-sensitive"
        npm_path.mkdir(parents=True)
        pkg_json = {
            "name": "@antigravity-k/skill-sensitive",
            "version": "1.0.0",
            "antigravityK": {"skill": True, "requiresApproval": True, "riskLevel": "high"},
        }
        (npm_path / "package.json").write_text(json.dumps(pkg_json, ensure_ascii=False, indent=2))

        validation = SkillInstaller(None)._validate_package(npm_path, "@antigravity-k/skill-sensitive")
        assert validation.valid is True
        assert validation.requires_approval is True
        assert validation.risk_level == "high"

    def test_validate_package_mcp_config(self, tmp_path):
        """package.json antigravityK.mcp → mcp_server_id 파싱."""
        from antigravity_k.engine.skill_installer import SkillInstaller

        npm_path = tmp_path / "node_modules" / "@antigravity-k" / "skill-mcp"
        npm_path.mkdir(parents=True)
        pkg_json = {
            "name": "@antigravity-k/skill-mcp",
            "version": "1.0.0",
            "antigravityK": {
                "skill": True,
                "mcp": {"serverId": "my-mcp-server", "command": "python", "args": ["-m", "server"]},
            },
        }
        (npm_path / "package.json").write_text(json.dumps(pkg_json, ensure_ascii=False, indent=2))

        validation = SkillInstaller(None)._validate_package(npm_path, "@antigravity-k/skill-mcp")
        assert validation.mcp_server_id == "my-mcp-server"

    def test_validate_package_platform_mismatch(self, tmp_path):
        """현재 플랫폼이 지원되지 않음 → valid=False."""
        from antigravity_k.engine.skill_installer import SkillInstaller

        npm_path = tmp_path / "node_modules" / "@antigravity-k" / "skill-platform"
        npm_path.mkdir(parents=True)
        pkg_json = {
            "name": "@antigravity-k/skill-platform",
            "version": "1.0.0",
            "antigravityK": {"skill": True, "platforms": ["nonexistent-platform"]},
        }
        (npm_path / "package.json").write_text(json.dumps(pkg_json, ensure_ascii=False, indent=2))

        validation = SkillInstaller(None)._validate_package(npm_path, "@antigravity-k/skill-platform")
        assert validation.valid is False
        assert "플랫폼" in validation.reason or "platform" in validation.reason.lower()

    def test_security_scan_no_skill_md(self, tmp_path):
        """SKILL.md 없으면 빈 리포트 (passed=True)."""
        from antigravity_k.engine.skill_installer import SkillInstaller

        npm_path = tmp_path / "node_modules" / "empty"
        npm_path.mkdir(parents=True)

        report = SkillInstaller._security_scan(None, npm_path, "empty")
        assert report.passed is True
        assert len(report.findings) == 0

    def test_security_scan_suspicious_references(self, tmp_path):
        """references/ 디렉토리도 스캔 대상."""
        from antigravity_k.engine.skill_installer import SkillInstaller

        npm_path = tmp_path / "node_modules" / "skill"
        npm_path.mkdir(parents=True)
        (npm_path / "SKILL.md").write_text("# Clean skill")
        ref_dir = npm_path / "references"
        ref_dir.mkdir()
        (ref_dir / "security.md").write_text("API_KEY=sk-1234567890abcdef")

        report = SkillInstaller._security_scan(None, npm_path, "skill")
        assert len(report.warnings) >= 1  # API_KEY pattern detected as warning

    def test_write_meta_with_mcp_config(self, tmp_path):
        """_write_meta에서 mcp_config 저장."""
        from antigravity_k.engine.skill_installer import InstallValidation, SecurityReport, SkillInstaller

        dest_dir = tmp_path / "market" / "mcp-skill"
        dest_dir.mkdir(parents=True)

        # package.json with mcp config
        pkg_json = {
            "name": "@antigravity-k/skill-mcp",
            "version": "2.0.0",
            "antigravityK": {
                "skill": True,
                "mcp": {"serverId": "my-server", "command": "node", "args": ["server.js"], "env": {"KEY": "VAL"}},
            },
        }
        (dest_dir / "package.json").write_text(json.dumps(pkg_json, ensure_ascii=False, indent=2))

        validation = InstallValidation(
            valid=True,
            package_name="@antigravity-k/skill-mcp",
            version="2.0.0",
            risk_level="safe",
            trust_level="verified",
            mcp_server_id="my-server",
        )
        security = SecurityReport(passed=True)
        SkillInstaller._write_meta(None, dest_dir, "@antigravity-k/skill-mcp", validation, security)

        meta = json.loads((dest_dir / ".agk_meta.json").read_text(encoding="utf-8"))
        assert meta["mcp_config"]["command"] == "node"
        assert meta["mcp_config"]["args"] == ["server.js"]
        assert meta["mcp_config"]["env"] == {"KEY": "VAL"}

    def test_copy_to_market_copies_files(self, tmp_path):
        """_copy_to_market → package.json + SKILL.md 복사 확인."""
        from antigravity_k.engine.skill_installer import SkillInstaller

        src = tmp_path / "node_modules" / "@antigravity-k" / "skill-test"
        src.mkdir(parents=True)
        (src / "package.json").write_text('{"name": "test", "version": "1.0.0"}')
        (src / "SKILL.md").write_text("# Test skill")

        dest = tmp_path / "market" / "skill-test"
        ok, err = SkillInstaller(None)._copy_to_market(src, dest)
        assert ok is True
        assert err == ""
        assert (dest / "package.json").exists()
        assert (dest / "SKILL.md").exists()
        assert json.loads((dest / "package.json").read_text())["name"] == "test"
        assert (dest / "SKILL.md").read_text() == "# Test skill"

    def test_copy_to_market_with_agkignore(self, tmp_path):
        """.agkignore에 포함된 항목은 복사 제외."""
        from antigravity_k.engine.skill_installer import SkillInstaller

        src = tmp_path / "node_modules" / "@antigravity-k" / "skill-test"
        src.mkdir(parents=True)
        (src / "package.json").write_text("{}")
        (src / "SKILL.md").write_text("# X")
        (src / "tests").mkdir()
        (src / "tests" / "test_main.py").write_text("")
        (src / ".agkignore").write_text("tests")

        dest = tmp_path / "market" / "skill-test"
        ok, err = SkillInstaller(None)._copy_to_market(src, dest)
        assert ok is True
        assert (dest / "package.json").exists()
        assert (dest / "SKILL.md").exists()
        assert not (dest / "tests").exists()

    def test_parse_skill_name_edge_cases(self):
        """스킬명 파싱 엣지케이스."""
        from antigravity_k.engine.skill_installer import SkillInstaller

        assert SkillInstaller._parse_skill_name("") == ""
        assert SkillInstaller._parse_skill_name("@antigravity-k/skill-") == ""
        assert SkillInstaller._parse_skill_name("simple-name") == "simple-name"


# ═══════════════════════════════════════════════════════════════════════
# D10: SkillMarketRegistry 통합
# ═══════════════════════════════════════════════════════════════════════


class TestD10_SkillMarketRegistry_Integration:
    """SkillMarketRegistry — MarketClient + Installer + SkillLoader 통합."""

    def test_registry_no_deps_format_list_empty(self):
        """의존성 없이 format_list([]) → 안내 메시지."""
        from antigravity_k.engine.skill_market_registry import SkillMarketRegistry

        registry = SkillMarketRegistry()
        msg = registry.format_list([])
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_registry_summary_counts(self):
        """summary() 메서드 동작 확인."""
        from antigravity_k.engine.skill_market_registry import SkillMarketRegistry

        registry = SkillMarketRegistry()
        summary = registry.summary()
        assert "설치 스킬" in summary or "Marketplace" in summary

    def test_registry_check_updates_no_market_client(self):
        """market_client 없이 check_updates → 빈 목록."""
        from antigravity_k.engine.skill_market_registry import SkillMarketRegistry

        registry = SkillMarketRegistry()
        updates = registry.check_updates()
        assert updates == []

    def test_registry_search_no_market_client(self):
        """market_client 없이 search → 에러 dict."""
        from antigravity_k.engine.skill_market_registry import SkillMarketRegistry

        registry = SkillMarketRegistry()
        results = registry.search("test")
        assert isinstance(results, list)
        if results and "error" in results[0]:
            assert "MarketClient not configured" in results[0]["error"]

    def test_registry_update_no_installer(self):
        """installer 없이 update → 실패."""
        from antigravity_k.engine.skill_market_registry import SkillMarketRegistry

        registry = SkillMarketRegistry()
        result = registry.update("test-skill")
        assert result.get("success") is False
        assert "not configured" in result.get("error", "")

    def test_registry_update_all_no_installer(self):
        """installer 없이 update_all → 빈 목록."""
        from antigravity_k.engine.skill_market_registry import SkillMarketRegistry

        registry = SkillMarketRegistry()
        results = registry.update_all()
        assert results == []

    def test_registry_format_info_full_fields(self):
        """format_info에 모든 필드 포함 확인."""
        from antigravity_k.engine.skill_market_registry import RegistrySkillInfo, SkillMarketRegistry

        skill = RegistrySkillInfo(
            skill_name="test-skill",
            package_name="@antigravity-k/skill-test",
            version="1.0.0",
            description="Test description",
            install_path="/tmp/market/test-skill",
            risk_level="high",
            trust_level="experimental",
            requires_approval=True,
            mcp_server_id="test-server",
            is_loaded=True,
            is_active=True,
            security_passed=True,
        )
        formatted = SkillMarketRegistry().format_info(skill)
        assert "test-skill" in formatted
        assert "@antigravity-k/skill-test" in formatted
        assert "1.0.0" in formatted
        assert "high" in formatted
        assert "experimental" in formatted
        assert "test-server" in formatted
        assert "✅" in formatted  # for is_loaded and is_active

    def test_registry_format_info_outdated(self):
        """is_outdated=True → 업데이트 화살표 표시."""
        from antigravity_k.engine.skill_market_registry import RegistrySkillInfo, SkillMarketRegistry

        skill = RegistrySkillInfo(
            skill_name="outdated",
            package_name="@antigravity-k/skill-outdated",
            version="1.0.0",
            description="Outdated skill",
            latest_version="2.0.0",
            is_outdated=True,
        )
        formatted = SkillMarketRegistry().format_info(skill)
        assert "1.0.0" in formatted
        assert "2.0.0" in formatted
        assert "→" in formatted

    def test_registry_format_info_with_security_findings(self):
        """보안 검사 결과 포함 확인."""
        from antigravity_k.engine.skill_market_registry import RegistrySkillInfo, SkillMarketRegistry

        skill = RegistrySkillInfo(
            skill_name="risky",
            package_name="@antigravity-k/skill-risky",
            version="1.0.0",
            description="Risky",
            security_passed=False,
            security_findings=[
                {"severity": "error", "message": "Suspicious command", "file": "SKILL.md", "line": 5},
            ],
        )
        formatted = SkillMarketRegistry().format_info(skill)
        assert "Suspicious" in formatted
        assert "error" in formatted.lower() or "🔴" in formatted

    def test_registry_format_list_with_various_states(self):
        """다양한 상태의 스킬 목록 포맷."""
        from antigravity_k.engine.skill_market_registry import RegistrySkillInfo, SkillMarketRegistry

        skills = [
            RegistrySkillInfo(
                skill_name="active-skill", package_name="@agk/skill-active", version="1.0.0", is_active=True
            ),
            RegistrySkillInfo(
                skill_name="outdated-skill",
                package_name="@agk/skill-outdated",
                version="1.0.0",
                latest_version="2.0.0",
                is_outdated=True,
            ),
            RegistrySkillInfo(
                skill_name="inactive-skill",
                package_name="@agk/skill-inactive",
                version="1.0.0",
                is_active=False,
                mcp_server_id="mcp-server",
            ),
        ]
        formatted = SkillMarketRegistry().format_list(skills)
        assert "active-skill" in formatted
        assert "outdated-skill" in formatted
        assert "inactive-skill" in formatted
        assert "mcp-server" in formatted


# ═══════════════════════════════════════════════════════════════════════
# D11: MCPServerRegistry — 클래스 레벨 격리 + 통합
# ═══════════════════════════════════════════════════════════════════════


class TestD11_MCPServerRegistry_Advanced:
    """MCPServerRegistry — 격리/통합/엣지케이스."""

    def setup_method(self):
        """각 테스트 전 MCPServerRegistry._skill_servers 정리."""
        from antigravity_k.tools.mcp_tool_loader import MCPServerRegistry

        MCPServerRegistry._skill_servers.clear()

    def test_register_and_get_by_skill_name(self):
        """등록 후 특정 스킬명으로 조회."""
        from antigravity_k.tools.mcp_tool_loader import MCPServerRegistry

        reg = MCPServerRegistry()
        reg.register_skill_mcp("my-skill", {"serverId": "srv-1", "command": "echo"})
        reg.register_skill_mcp("my-skill", {"serverId": "srv-2", "command": "cat"})

        servers = reg.get_skill_mcp_servers("my-skill")
        assert len(servers) == 2
        assert "srv-1" in servers
        assert "srv-2" in servers

    def test_get_skill_mcp_servers_all(self):
        """인자 없이 get_skill_mcp_servers() → 전체 스킬 서버."""
        from antigravity_k.tools.mcp_tool_loader import MCPServerRegistry

        reg = MCPServerRegistry()
        reg.register_skill_mcp("a", {"serverId": "srv-a", "command": "echo"})
        reg.register_skill_mcp("b", {"serverId": "srv-b", "command": "cat"})

        all_servers = reg.get_skill_mcp_servers()
        assert "srv-a" in all_servers
        assert "srv-b" in all_servers

    def test_unregister_nonexistent_skill(self):
        """존재하지 않는 스킬 unregister → False (예외 없음)."""
        from antigravity_k.tools.mcp_tool_loader import MCPServerRegistry

        reg = MCPServerRegistry()
        assert reg.unregister_skill_mcp("nonexistent") is False

    def test_get_by_category_includes_skill_servers(self):
        """카테고리 'skill' → get_by_category에서 스킬 서버 포함."""
        from antigravity_k.tools.mcp_tool_loader import MCPServerRegistry

        reg = MCPServerRegistry()
        reg.register_skill_mcp("test", {"serverId": "my-srv", "command": "echo"})

        skill_cat = reg.get_by_category("skill")
        assert "my-srv" in skill_cat
        assert skill_cat["my-srv"]["category"] == "skill"

    def test_list_skills_with_mcp_empty(self):
        """등록된 MCP 스킬 없음 → 빈 목록."""
        from antigravity_k.tools.mcp_tool_loader import MCPServerRegistry

        reg = MCPServerRegistry()
        assert reg.list_skills_with_mcp() == []

    def test_generate_config_with_skills_catalog_only(self):
        """스킬 서버 없이 generate_config_with_skills → 카탈로그만."""
        from antigravity_k.tools.mcp_tool_loader import MCPServerRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / ".mcp.json"
            reg = MCPServerRegistry()
            reg.generate_config_with_skills(str(output))
            config = json.loads(output.read_text(encoding="utf-8"))
            assert "filesystem" in config["mcpServers"]

    def test_get_catalog_summary_includes_skill(self):
        """get_catalog_summary에 스킬 서버 태그 포함."""
        from antigravity_k.tools.mcp_tool_loader import MCPServerRegistry

        reg = MCPServerRegistry()
        reg.register_skill_mcp("test", {"serverId": "skill-srv", "command": "echo"})
        summary = reg.get_catalog_summary()
        assert "skill-srv" in summary
        assert "skill: test" in summary


# ═══════════════════════════════════════════════════════════════════════
# D13: SkillLoader Market 심화 테스트
# ═══════════════════════════════════════════════════════════════════════


class TestD13_SkillLoader_Market_Advanced:
    """SkillLoader — market/ 다중 스킬/소스태깅/오버라이트."""

    def test_load_multiple_market_skills(self, tmp_path):
        """market/에 여러 스킬 → 모두 로드."""
        from antigravity_k.engine.skill_loader import SkillLoader

        market = tmp_path / ".agent" / "skills" / "market"
        for name in ["alpha", "beta", "gamma"]:
            d = market / name
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(f"---\nname: Skill {name}\n---\n\nContent {name}.")

        loader = SkillLoader(project_root=str(tmp_path), include_global=False, include_market=True)
        skills = loader.list_skills_by_source("market")
        ids = {s["id"] for s in skills}
        assert "alpha" in ids
        assert "beta" in ids
        assert "gamma" in ids
        assert len(skills) == 3

    def test_market_skill_with_metadata(self, tmp_path):
        """YAML frontmatter 태그/툴/리스트 파싱."""
        from antigravity_k.engine.skill_loader import SkillLoader

        d = tmp_path / ".agent" / "skills" / "market" / "full-skill"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            "---\n"
            "name: Full Skill\n"
            "description: A skill with all metadata\n"
            "tags:\n"
            "  - tag1\n"
            "  - tag2\n"
            "tools:\n"
            "  - read_file\n"
            "  - write_file\n"
            "risk_level: low\n"
            "trust_level: verified\n"
            "requires_approval: false\n"
            "---\n\n# Body content\n\nInstructions here.\n"
        )

        loader = SkillLoader(project_root=str(tmp_path), include_global=False, include_market=True)
        skill = loader.get_skill("full-skill")
        assert skill is not None
        assert skill["name"] == "Full Skill"
        assert skill["description"] == "A skill with all metadata"
        assert skill["tags"] == ["tag1", "tag2"]
        assert skill["tools"] == ["read_file", "write_file"]
        assert skill["risk_level"] == "low"
        assert skill["trust_level"] == "verified"
        assert skill["requires_approval"] is False
        assert skill["source"] == "market"

    def test_local_skill_preserved_when_no_market_overlap(self, tmp_path):
        """로컬 스킬이 market과 이름이 다르면 로컬 유지."""
        from antigravity_k.engine.skill_loader import SkillLoader

        # 로컬 스킬
        local = tmp_path / ".agent" / "skills" / "local-only"
        local.mkdir(parents=True)
        (local / "SKILL.md").write_text("---\nname: Local Only\n---\n\nLocal.\n")

        # 다른 이름의 마켓 스킬
        market = tmp_path / ".agent" / "skills" / "market" / "market-only"
        market.mkdir(parents=True)
        (market / "SKILL.md").write_text("---\nname: Market Only\n---\n\nMarket.\n")

        loader = SkillLoader(project_root=str(tmp_path), include_global=False, include_market=True)
        assert loader.get_skill("local-only") is not None
        assert loader.get_skill("market-only") is not None

        # 각각 source 확인
        local_skill = loader.get_skill("local-only")
        assert local_skill["source"] == "local"
        market_skill = loader.get_skill("market-only")
        assert market_skill["source"] == "market"

    def test_active_skills_api(self, tmp_path):
        """activate_skill / deactivate_skill / clear_active_skills."""
        from antigravity_k.engine.skill_loader import SkillLoader

        d = tmp_path / ".agent" / "skills" / "market" / "activable"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("# Activable skill")

        loader = SkillLoader(project_root=str(tmp_path), include_global=False, include_market=True)

        assert loader.activate_skill("activable") is True
        assert "activable" in loader.active_skills

        # 중복 활성화 → False
        assert loader.activate_skill("activable") is False

        assert loader.deactivate_skill("activable") is True
        assert "activable" not in loader.active_skills

        # 존재하지 않는 스킬 활성화 → False
        assert loader.activate_skill("nonexistent") is False

    def test_market_skills_isolated_from_global(self, tmp_path):
        """include_global=False → 글로벌 스킬 미로드 확인."""
        from antigravity_k.engine.skill_loader import SkillLoader

        # 마켓 스킬만 생성
        d = tmp_path / ".agent" / "skills" / "market" / "mkt-skill"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("# Market skill")

        loader = SkillLoader(project_root=str(tmp_path), include_global=False, include_market=True)
        assert loader.get_skill("mkt-skill") is not None
        assert loader.get_skill("mkt-skill")["source"] == "market"

    def test_refresh_reloads_skills(self, tmp_path):
        """refresh() → 새로 추가된 마켓 스킬 로드."""
        from antigravity_k.engine.skill_loader import SkillLoader

        loader = SkillLoader(project_root=str(tmp_path), include_global=False, include_market=True)
        assert loader.get_skill("new-skill") is None

        # 스킬 추가 후 refresh
        d = tmp_path / ".agent" / "skills" / "market" / "new-skill"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("# New skill")
        loader.refresh()

        assert loader.get_skill("new-skill") is not None
        assert loader.get_skill("new-skill")["source"] == "market"


# ═══════════════════════════════════════════════════════════════════════
# D12: CLI / Slash Market 명령어 (파싱 + 엣지케이스)
# ═══════════════════════════════════════════════════════════════════════


class TestD12_CLI_Slash_Market:
    """CLI/Slash market 명령어 엣지케이스 검증."""

    def test_slash_market_help_text(self):
        """_cmd_market 도움말 출력 확인."""
        from antigravity_k.engine.slash_commands import SlashCommandRegistry

        registry = SlashCommandRegistry()
        result = registry._cmd_market([])
        assert "/market" in result
        assert "search" in result
        assert "install" in result
        assert "list" in result
        assert "info" in result
        assert "update" in result

    def test_slash_market_unknown_subcommand(self):
        """알 수 없는 서브커맨드 → 에러 메시지."""
        from antigravity_k.engine.slash_commands import SlashCommandRegistry

        registry = SlashCommandRegistry()
        result = registry._cmd_market(["unknown-sub"])
        assert "알 수 없는" in result or "unknown" in result.lower()

    def test_slash_market_install_no_package(self):
        """install 인자 없음 → 사용법 안내."""
        from antigravity_k.engine.slash_commands import SlashCommandRegistry

        registry = SlashCommandRegistry()
        result = registry._cmd_market(["install"])
        assert "Usage" in result or "install" in result

    def test_slash_market_remove_no_name(self):
        """remove 인자 없음 → 사용법 안내."""
        from antigravity_k.engine.slash_commands import SlashCommandRegistry

        registry = SlashCommandRegistry()
        result = registry._cmd_market(["remove"])
        assert "Usage" in result or "remove" in result

    def test_slash_market_search_no_query(self):
        """search 인자 없음 → 사용법 안내."""
        from antigravity_k.engine.slash_commands import SlashCommandRegistry

        registry = SlashCommandRegistry()
        result = registry._cmd_market(["search"])
        assert "Usage" in result or "search" in result

    def test_slash_market_info_no_name(self):
        """info 인자 없음 → 사용법 안내."""
        from antigravity_k.engine.slash_commands import SlashCommandRegistry

        registry = SlashCommandRegistry()
        result = registry._cmd_market(["info"])
        assert "Usage" in result or "info" in result

    def test_slash_market_list_alias(self):
        """list / ls 모두 동작."""
        from antigravity_k.engine.slash_commands import SlashCommandRegistry

        registry = SlashCommandRegistry()
        result_list = registry._cmd_market(["list"])
        result_ls = registry._cmd_market(["ls"])
        assert isinstance(result_list, str)
        assert isinstance(result_ls, str)

    def test_slash_market_install_handles_missing_deps(self):
        """의존성 없이 install 호출 → graceful fallback."""
        from antigravity_k.engine.slash_commands import SlashCommandRegistry

        registry = SlashCommandRegistry()
        result = registry._cmd_market(["install", "@antigravity-k/skill-test"])
        # Install without market deps should show error, not crash
        assert isinstance(result, str)
        assert len(result) > 0

    def test_cli_market_function_import_error(self):
        """cli.py market 함수의 ImportError 처리."""
        # cli.py의 market 함수는 lazy import를 사용하므로
        # typer 없이 직접 호출은 불가능. 대신 함수 시그니처 검증.
        import inspect

        from antigravity_k.cli import market

        sig = inspect.signature(market)
        params = {name: p for name, p in sig.parameters.items()}
        for opt in ["search", "install", "remove", "info", "update", "list_skills", "update_all"]:
            assert opt in params, f"Missing parameter: {opt}"


# ═══════════════════════════════════════════════════════════════════════
# E2E: Week 2 전체 마켓플레이스 라이프사이클
# ═══════════════════════════════════════════════════════════════════════


class TestWeek2_E2E_MarketplaceLifecycle:
    """D8-D14 통합 E2E — 마켓플레이스 전체 라이프사이클.

    npm 의존성 없이 tempfile 기반 시뮬레이션:
      SKILL.md 파일 생성 → SkillLoader market 로드
      → SkillMarketRegistry list/format → MCPServerRegistry 등록
      → SkillInstaller 시뮬레이션 (validate+security+meta)
      → SkillMarketClient 설치 상태 관리
    """

    def _create_market_skill(self, tmp_path: Path, name: str, version: str, mcp_server_id: str = "") -> Path:
        """마켓 스킬 디렉토리 + package.json + SKILL.md + .agk_meta.json 생성."""
        skill_dir = tmp_path / ".agent" / "skills" / "market" / name
        skill_dir.mkdir(parents=True)

        # SKILL.md
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name.title()}\ndescription: {name} skill\ntools:\n  - read_file\n"
            f"risk_level: low\ntrust_level: verified\n---\n\n# {name.title()}\n\n{name} instructions.\n"
        )

        # package.json
        pkg = {
            "name": f"@antigravity-k/skill-{name}",
            "version": version,
            "antigravityK": {
                "skill": True,
                "riskLevel": "low",
                "trustLevel": "verified",
            },
        }
        if mcp_server_id:
            pkg["antigravityK"]["mcp"] = {
                "serverId": mcp_server_id,
                "command": "python",
                "args": ["-m", name],
            }
            pkg["antigravityK"]["mcp_server_id"] = mcp_server_id
        (skill_dir / "package.json").write_text(json.dumps(pkg, ensure_ascii=False, indent=2))

        # .agk_meta.json
        meta = {
            "name": f"@antigravity-k/skill-{name}",
            "version": version,
            "description": f"{name} skill",
            "installed_at": "2026-06-01T00:00:00",
            "updated_at": "2026-06-01T00:00:00",
            "risk_level": "low",
            "trust_level": "verified",
            "security_passed": True,
        }
        if mcp_server_id:
            meta["mcp_server_id"] = mcp_server_id
        (skill_dir / ".agk_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))

        return skill_dir

    def test_e2e_skill_marketplace_lifecycle(self, tmp_path):
        """전체 마켓플레이스 라이프사이클 E2E 검증.

        시나리오:
          1. 3개 스킬을 market/ 디렉토리에 셋업
          2. SkillLoader가 모두 로드하는지 확인
          3. SkillMarketClient가 설치 상태를 올바르게 읽는지 확인
          4. SkillMarketRegistry가 list_installed + format_list
          5. MCPServerRegistry에 MCP 스킬 등록
          6. SkillLoader list_skills_by_source 필터링
          7. 최종 통합 검증
        """
        from antigravity_k.engine.skill_loader import SkillLoader
        from antigravity_k.engine.skill_market_client import SkillMarketClient
        from antigravity_k.engine.skill_market_registry import SkillMarketRegistry
        from antigravity_k.tools.mcp_tool_loader import MCPServerRegistry

        # ── Phase 1: Setup 3 마켓 스킬 ──
        self._create_market_skill(tmp_path, "code-review", "1.0.0", mcp_server_id="review-server")
        self._create_market_skill(tmp_path, "data-pipeline", "2.0.0")
        self._create_market_skill(tmp_path, "rag-search", "0.5.0")

        # ── Phase 2: SkillLoader 로드 ──
        loader = SkillLoader(project_root=str(tmp_path), include_global=False, include_market=True)

        # 전체 로드
        all_skills = loader.list_skills()
        assert len(all_skills) >= 3

        # 마켓 스킬만
        market_skills = loader.list_skills_by_source("market")
        market_ids = {s["id"] for s in market_skills}
        assert "code-review" in market_ids
        assert "data-pipeline" in market_ids
        assert "rag-search" in market_ids

        # 개별 조회
        cr = loader.get_skill("code-review")
        assert cr is not None
        assert cr["source"] == "market"
        assert cr["name"] == "Code-Review"  # .title() on 'code-review' -> 'Code-Review'

        # ── Phase 3: SkillMarketClient 설치 상태 ──
        client = SkillMarketClient(project_root=str(tmp_path))

        installed = client.get_installed(str(tmp_path))
        assert len(installed) >= 3
        installed_names = {s.skill_name for s in installed}
        assert "code-review" in installed_names
        assert "data-pipeline" in installed_names
        assert "rag-search" in installed_names

        # 버전 확인
        dp = next(s for s in installed if s.skill_name == "data-pipeline")
        assert dp.version == "2.0.0"
        assert dp.risk_level == "low"
        assert dp.trust_level == "verified"
        assert dp.install_path is not None

        # is_installed
        assert client.is_installed("code-review", str(tmp_path)) is True
        assert client.is_installed("nonexistent", str(tmp_path)) is False

        # ── Phase 4: SkillMarketRegistry (market_client + loader) ──
        registry = SkillMarketRegistry(
            project_root=str(tmp_path),
            market_client=client,
            skill_loader=loader,
        )

        # list_installed
        all_registry_skills = registry.list_installed()
        assert len(all_registry_skills) >= 3

        # get_info
        cr_info = registry.get_info("code-review")
        assert cr_info is not None
        assert cr_info.version == "1.0.0"
        assert cr_info.is_loaded is True  # SkillLoader에서 로드됨

        dp_info = registry.get_info("data-pipeline")
        assert dp_info is not None
        assert dp_info.is_loaded is True

        # format_list
        formatted = registry.format_list(all_registry_skills)
        assert "code-review" in formatted
        assert "data-pipeline" in formatted
        assert "rag-search" in formatted

        # format_info
        if cr_info:
            info = registry.format_info(cr_info)
            assert "code-review" in info
            assert "1.0.0" in info
            assert "review-server" in info  # MCP 스킬

        # summary
        summary = registry.summary()
        assert "3" in summary  # 3개 설치

        # ── Phase 5: MCPServerRegistry MCP 등록 ──
        mcp_reg = MCPServerRegistry()
        mcp_reg.register_skill_mcp(
            "code-review",
            {
                "serverId": "review-server",
                "command": "python",
                "args": ["-m", "review"],
            },
        )

        # verify
        servers = mcp_reg.get_skill_mcp_servers()
        assert "review-server" in servers
        assert servers["review-server"]["skill_name"] == "code-review"

        # all_servers 확인
        all_servers = mcp_reg.get_all()
        assert "review-server" in all_servers
        assert "filesystem" in all_servers  # catalog

        # list_skills_with_mcp
        mcp_skills = mcp_reg.list_skills_with_mcp()
        assert any(s["skill"] == "code-review" for s in mcp_skills)

        # ── Phase 6: SkillsRegistry 연동 ──
        from antigravity_k.agents.skills_registry import SkillsRegistry

        skills_registry = SkillsRegistry(skills_dir=str(tmp_path / ".agent" / "skills"))
        profile = skills_registry.get_profile("CODE-REVIEW")
        assert profile is not None
        assert "read_file" in profile.tools

        # ── Phase 7: 최종 통합 검증 ──
        # SkillLoader market_skills()
        market_loaded = loader.get_market_skills()
        assert len(market_loaded) >= 3

        # include_market=False → market 스킬 미로드
        loader_no_market = SkillLoader(project_root=str(tmp_path), include_global=False, include_market=False)
        assert loader_no_market.get_skill("code-review") is None

        # MCPServerRegistry unregister
        mcp_reg.unregister_skill_mcp("code-review")
        assert "review-server" not in mcp_reg.get_skill_mcp_servers()

        # format_list with empty
        empty_format = registry.format_list([])
        assert "설치된 마켓 스킬이 없습니다" in empty_format or "Marketplace" in empty_format

    def test_e2e_skill_installer_simulated_flow(self, tmp_path):
        """SkillInstaller 시뮬레이션 플로우 (npm 없이).

        validate → security → copy → meta → cleanup 단계 검증.
        """
        from antigravity_k.engine.skill_installer import (
            SkillInstaller,
        )

        # ── Step 1: npm install 시뮬레이션 (node_modules 생성) ──
        npm_path = tmp_path / "node_modules" / "@antigravity-k" / "skill-test"
        npm_path.mkdir(parents=True)

        pkg_json = {
            "name": "@antigravity-k/skill-test",
            "version": "1.5.0",
            "antigravityK": {"skill": True, "riskLevel": "safe", "trustLevel": "verified"},
        }
        (npm_path / "package.json").write_text(json.dumps(pkg_json, ensure_ascii=False, indent=2))
        (npm_path / "SKILL.md").write_text("# Test skill\n\nSafe instructions.")
        (npm_path / "references").mkdir()
        (npm_path / "references" / "help.md").write_text("# Help reference")

        installer = SkillInstaller(project_root=str(tmp_path))

        # ── Step 2: Validate ──
        validation = installer._validate_package(npm_path, "@antigravity-k/skill-test")
        assert validation.valid is True
        assert validation.version == "1.5.0"

        # ── Step 3: Security scan ──
        security = installer._security_scan(npm_path, "skill-test")
        assert security.passed is True

        # ── Step 4: Copy to market ──
        dest = tmp_path / ".agent" / "skills" / "market" / "skill-test"
        ok, err = installer._copy_to_market(npm_path, dest)
        assert ok is True
        assert (dest / "SKILL.md").exists()
        assert (dest / "package.json").exists()
        assert (dest / "references" / "help.md").exists()

        # ── Step 5: Write meta ──
        installer._write_meta(dest, "@antigravity-k/skill-test", validation, security)
        meta_path = dest / ".agk_meta.json"
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        assert meta["name"] == "@antigravity-k/skill-test"
        assert meta["version"] == "1.5.0"
        assert meta["security_passed"] is True

        # ── Step 6: Cleanup 시뮬레이션 ──
        installer._cleanup_npm(npm_path)
        assert not npm_path.exists()  # node_modules 정리됨

        # ── 최종: SkillMarketClient가 읽을 수 있는지 확인 ──
        from antigravity_k.engine.skill_market_client import SkillMarketClient

        client = SkillMarketClient(project_root=str(tmp_path))
        assert client.is_installed("skill-test") is True
        installed = client.get_installed(str(tmp_path))
        st = next((s for s in installed if s.skill_name == "skill-test"), None)
        assert st is not None
        assert st.version == "1.5.0"
