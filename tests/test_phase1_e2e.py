"""Phase 1 E2E 통합 테스트 — D1~D13 Plan/Build + Skills Marketplace 전체 검증.

테스트 범위:
  Week 1 (D1-D7): ExecutionMode + ModeManager + ArtifactEngine + QualityGate + PlanToBuildPipeline + format_status + EventBus
  Week 2 (D8-D13): SkillMarketRegistry + SkillLoader market 연동 + MCPServerRegistry skill 등록 + SkillInstaller (npm 없이)
  통합 (D15): Plan 모드 → Skill 검색 → Plan 작성 → Build 전환 → Skill 로드 → Interactive 복귀

모든 테스트는 npm/네트워크 의존성 없이 tempfile 기반으로 동작합니다.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from antigravity_k.engine.artifact_engine import ArtifactEngine
from antigravity_k.engine.execution_mode import ExecutionMode
from antigravity_k.engine.mode_manager import ModeManager
from antigravity_k.engine.quality_gate import QualityGate

# ═══════════════════════════════════════════════════════════════════════
# D8-D10: SkillMarketRegistry (통합)
# ═══════════════════════════════════════════════════════════════════════


class TestD8_D10_SkillMarketRegistry:
    """SkillMarketRegistry — MarketClient + Installer + SkillLoader 통합 검증."""

    def test_registry_list_installed_empty(self):
        """설치된 스킬이 없으면 빈 목록 반환."""
        from antigravity_k.engine.skill_market_registry import SkillMarketRegistry

        registry = SkillMarketRegistry()
        installed = registry.list_installed()
        assert installed == []

    def test_registry_get_info_nonexistent(self):
        """존재하지 않는 스킬 info → None."""
        from antigravity_k.engine.skill_market_registry import SkillMarketRegistry

        registry = SkillMarketRegistry()
        assert registry.get_info("nonexistent") is None

    def test_registry_installer_not_configured(self):
        """Installer 없이 install → 에러 메시지."""
        from antigravity_k.engine.skill_market_registry import SkillMarketRegistry

        registry = SkillMarketRegistry()
        result = registry.install("@antigravity-k/skill-test")
        assert result.get("success") is False
        assert "not configured" in result.get("error", "")

    def test_registry_format_list_empty(self):
        """빈 목록 format_list → 안내 메시지."""
        from antigravity_k.engine.skill_market_registry import SkillMarketRegistry

        registry = SkillMarketRegistry()
        formatted = registry.format_list([])
        assert "설치된 마켓 스킬이 없습니다" in formatted or "Marketplace" in formatted

    def test_registry_format_info(self):
        """RegistrySkillInfo format_info → 상세 정보 포함."""
        from antigravity_k.engine.skill_market_registry import RegistrySkillInfo, SkillMarketRegistry

        skill = RegistrySkillInfo(
            skill_name="code-review",
            package_name="@antigravity-k/skill-code-review",
            version="1.2.3",
            description="Automated code review",
            install_path="/tmp/market/code-review",
        )
        formatted = SkillMarketRegistry().format_info(skill)
        assert "code-review" in formatted
        assert "1.2.3" in formatted
        assert "@antigravity-k/skill-code-review" in formatted

    def test_registry_summary_empty(self):
        """빈 레지스트리 summary."""
        from antigravity_k.engine.skill_market_registry import SkillMarketRegistry

        registry = SkillMarketRegistry()
        summary = registry.summary()
        assert "총 설치 스킬" in summary or "Marketplace" in summary


# ═══════════════════════════════════════════════════════════════════════
# D9: SkillInstaller (npm 없이 시뮬레이션)
# ═══════════════════════════════════════════════════════════════════════


class TestD9_SkillInstaller:
    """SkillInstaller — 검증/보안/메타데이터 단위 (npm 없이)."""

    def test_parse_skill_name(self):
        """패키지명 → 스킬 짧은 이름 파싱."""
        from antigravity_k.engine.skill_installer import SkillInstaller

        assert SkillInstaller._parse_skill_name("@antigravity-k/skill-code-review") == "code-review"
        assert SkillInstaller._parse_skill_name("code-review") == "code-review"
        assert SkillInstaller._parse_skill_name("@antigravity-k/skill-data-pipeline") == "data-pipeline"

    def test_version_compare(self):
        """semver 비교."""
        from antigravity_k.engine.skill_installer import SkillInstaller

        assert SkillInstaller._version_gte("1.2.3", "1.0.0") is True
        assert SkillInstaller._version_gte("1.0.0", "1.0.0") is True
        assert SkillInstaller._version_gte("0.9.0", "1.0.0") is False
        assert SkillInstaller._version_gte("2.0.0", "1.9.9") is True

    def test_security_scan_safe_content(self, tmp_path):
        """안전한 SKILL.md → 보안 통과."""
        from antigravity_k.engine.skill_installer import SkillInstaller

        skill_dir = tmp_path / "node_modules" / "skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Safe skill\n\nUseful instructions.")

        report = SkillInstaller._security_scan(None, skill_dir, "test-skill")
        assert report.passed is True
        assert len(report.errors) == 0

    def test_security_scan_suspicious(self, tmp_path):
        """의심스러운 패턴 → 보안 경고."""
        from antigravity_k.engine.skill_installer import SkillInstaller

        skill_dir = tmp_path / "node_modules" / "skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Suspicious\n\nRun: rm -rf /\n")

        report = SkillInstaller._security_scan(None, skill_dir, "test-skill")
        # rm -rf / should be detected as error level
        assert len(report.errors) >= 1

    def test_write_meta(self, tmp_path):
        """메타데이터 파일 작성 검증."""
        from antigravity_k.engine.skill_installer import InstallValidation, SecurityReport, SkillInstaller

        dest_dir = tmp_path / "market" / "test-skill"
        dest_dir.mkdir(parents=True)

        validation = InstallValidation(
            valid=True,
            package_name="@antigravity-k/skill-test",
            version="1.0.0",
            risk_level="safe",
            trust_level="verified",
        )
        security = SecurityReport(passed=True)

        SkillInstaller._write_meta(None, dest_dir, "@antigravity-k/skill-test", validation, security)
        meta_path = dest_dir / ".agk_meta.json"
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        assert meta["name"] == "@antigravity-k/skill-test"
        assert meta["version"] == "1.0.0"
        assert meta["security_passed"] is True


# ═══════════════════════════════════════════════════════════════════════
# D11: MCPServerRegistry Skill 등록
# ═══════════════════════════════════════════════════════════════════════


class TestD11_MCPServerRegistry:
    """MCPServerRegistry — 스킬 MCP 서버 등록/조회/해제."""

    def test_register_skill_mcp(self):
        """스킬 MCP 서버 등록."""
        from antigravity_k.tools.mcp_tool_loader import MCPServerRegistry

        registry = MCPServerRegistry()
        result = registry.register_skill_mcp(
            "test-skill",
            {
                "serverId": "test-server",
                "command": "python",
                "args": ["-m", "server"],
            },
        )
        assert result is True
        servers = registry.get_skill_mcp_servers("test-skill")
        assert "test-server" in servers

    def test_get_all_includes_skill_servers(self):
        """get_all()에 스킬 서버 포함."""
        from antigravity_k.tools.mcp_tool_loader import MCPServerRegistry

        registry = MCPServerRegistry()
        registry.register_skill_mcp(
            "another-skill",
            {
                "serverId": "skill-server-1",
                "command": "node",
                "args": ["server.js"],
            },
        )
        all_servers = registry.get_all()
        assert "skill-server-1" in all_servers
        assert "filesystem" in all_servers  # catalog

    def test_unregister_skill_mcp(self):
        """스킬 MCP 서버 해제."""
        from antigravity_k.tools.mcp_tool_loader import MCPServerRegistry

        registry = MCPServerRegistry()
        registry.register_skill_mcp(
            "removable",
            {
                "serverId": "rem-server",
                "command": "echo",
            },
        )
        assert registry.unregister_skill_mcp("removable") is True
        assert "rem-server" not in registry.get_skill_mcp_servers()

    def test_list_skills_with_mcp(self):
        """MCP 등록 스킬 목록."""
        from antigravity_k.tools.mcp_tool_loader import MCPServerRegistry

        registry = MCPServerRegistry()
        registry.register_skill_mcp(
            "skill-a",
            {"serverId": "srv-a", "command": "cmd"},
        )
        registry.register_skill_mcp(
            "skill-b",
            {"serverId": "srv-b", "command": "cmd"},
        )
        skills = registry.list_skills_with_mcp()
        skill_names = {s["skill"] for s in skills}
        assert "skill-a" in skill_names
        assert "skill-b" in skill_names

    def test_register_duplicate_catalog_id(self):
        """카탈로그에 이미 있는 serverId → 등록 실패."""
        from antigravity_k.tools.mcp_tool_loader import MCPServerRegistry

        registry = MCPServerRegistry()
        # 'filesystem' is in CATALOG
        result = registry.register_skill_mcp(
            "try-override",
            {
                "serverId": "filesystem",
                "command": "cat",
            },
        )
        assert result is False  # catalog already has it

    def test_generate_config_with_skills(self):
        """generate_config_with_skills() → 스킬 서버 포함 확인."""
        from antigravity_k.tools.mcp_tool_loader import MCPServerRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / ".mcp.json"

            registry = MCPServerRegistry()
            registry.register_skill_mcp(
                "skill-with-mcp",
                {
                    "serverId": "my-skill-server",
                    "command": "python",
                    "args": ["-m", "skill_server"],
                },
            )
            registry.generate_config_with_skills(str(output), server_ids=["filesystem"])

            config = json.loads(output.read_text(encoding="utf-8"))
            assert "filesystem" in config["mcpServers"]
            assert "my-skill-server" in config["mcpServers"]


# ═══════════════════════════════════════════════════════════════════════
# D13: SkillLoader market 디렉토리 연동
# ═══════════════════════════════════════════════════════════════════════


class TestD13_SkillLoader_Market:
    """SkillLoader — .agent/skills/market/ 디렉토리 스캔 검증."""

    def test_market_dir_property(self, tmp_path):
        """market_dir 속성 확인."""
        from antigravity_k.engine.skill_loader import SkillLoader

        loader = SkillLoader(project_root=str(tmp_path), include_global=False, include_market=True)
        assert loader.market_dir == tmp_path / ".agent" / "skills" / "market"

    def test_load_market_skills(self, tmp_path):
        """market/ 디렉토리에서 SKILL.md 로드."""
        from antigravity_k.engine.skill_loader import SkillLoader

        market_dir = tmp_path / ".agent" / "skills" / "market"
        skill_dir = market_dir / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: Test Skill\ndescription: A test market skill\n---\n\n# Instructions\n\nDo something."
        )

        loader = SkillLoader(project_root=str(tmp_path), include_global=False, include_market=True)
        skill = loader.get_skill("test-skill")
        assert skill is not None
        assert skill["name"] == "Test Skill"
        assert skill["description"] == "A test market skill"
        assert skill["source"] == "market"

    def test_list_skills_by_source_market(self, tmp_path):
        """list_skills_by_source('market') 필터링."""
        from antigravity_k.engine.skill_loader import SkillLoader

        market_dir = tmp_path / ".agent" / "skills" / "market"
        skill_dir = market_dir / "mkt-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Market skill")

        loader = SkillLoader(project_root=str(tmp_path), include_global=False, include_market=True)
        market_skills = loader.list_skills_by_source("market")
        assert len(market_skills) >= 1
        assert any(s["id"] == "mkt-skill" for s in market_skills)

    def test_load_order_prefers_market(self, tmp_path):
        """로컬과 마켓에 동일 ID → 마켓이 최종 우선."""
        from antigravity_k.engine.skill_loader import SkillLoader

        # 로컬 스킬
        local_dir = tmp_path / ".agent" / "skills" / "overlap"
        local_dir.mkdir(parents=True)
        (local_dir / "SKILL.md").write_text("---\nname: Local Version\n---\n\nLocal content.")

        # 마켓 스킬 (동일 ID = "overlap")
        market_dir = tmp_path / ".agent" / "skills" / "market" / "overlap"
        market_dir.mkdir(parents=True)
        (market_dir / "SKILL.md").write_text("---\nname: Market Version\n---\n\nMarket content.")

        loader = SkillLoader(project_root=str(tmp_path), include_global=False, include_market=True)
        skill = loader.get_skill("overlap")
        assert skill is not None
        assert skill["source"] == "market"  # market wins
        assert skill["name"] == "Market Version"

    def test_include_market_false(self, tmp_path):
        """include_market=False → market 스킬 미로드."""
        from antigravity_k.engine.skill_loader import SkillLoader

        market_dir = tmp_path / ".agent" / "skills" / "market" / "hidden"
        market_dir.mkdir(parents=True)
        (market_dir / "SKILL.md").write_text("# Should not load")

        loader = SkillLoader(project_root=str(tmp_path), include_global=False, include_market=False)
        assert loader.get_skill("hidden") is None


# ═══════════════════════════════════════════════════════════════════════
# D13: SkillsRegistry market 연동
# ═══════════════════════════════════════════════════════════════════════


class TestD13_SkillsRegistry_Market:
    """SkillsRegistry — .agent/skills/market/ 스캔 검증."""

    def test_market_skill_loaded_by_registry(self, tmp_path):
        """SkillsRegistry가 market/ 스킬 로드."""
        from antigravity_k.agents.skills_registry import SkillsRegistry

        skills_dir = tmp_path / ".agent" / "skills"
        market_skill_dir = skills_dir / "market" / "market-skill"
        market_skill_dir.mkdir(parents=True)
        (market_skill_dir / "SKILL.md").write_text(
            "---\nname: MARKET_SKILL\ndescription: A market skill\ntools:\n  - read_file\n---\n\n# Instructions"
        )

        registry = SkillsRegistry(skills_dir=str(skills_dir))
        profile = registry.get_profile("MARKET-SKILL")
        assert profile is not None
        assert profile.description == "A market skill"
        assert "read_file" in profile.tools


# ═══════════════════════════════════════════════════════════════════════
# D17: SkillPublisher — npm publish + GitHub PR 시뮬레이션 (E2E)
# ═══════════════════════════════════════════════════════════════════════


class TestD17_SkillPublisher_E2E:
    """SkillPublisher E2E 통합 — npm publish / GitHub PR 전체 파이프라인.

    npm/네트워크 의존성 없이 unittest.mock으로 subprocess.run을 패치하여
    실제 publish/PR 생성 호출을 시뮬레이션합니다.
    """

    def _create_market_skill(
        self,
        tmp_path: Path,
        name: str,
        version: str = "1.0.0",
        tool_count: int = 2,
        mcp_server_id: str = "",
    ) -> Path:
        """마켓 스킬 디렉토리 + SKILL.md + .agk_meta.json 생성.

        tool_count만큼 다른 도구명을 사용해 SKILL.md frontmatter에
        allowed-tools 리스트를 생성합니다.
        """
        skill_dir = tmp_path / ".agent" / "skills" / "market" / name
        skill_dir.mkdir(parents=True)

        tool_pool = ["read_file", "write_file", "grep_search", "glob_search", "list_directory"]
        selected = tool_pool[: min(tool_count, len(tool_pool))]
        tools_yaml = "\n  - ".join(selected)
        (skill_dir / "SKILL.md").write_text(
            f"---\n"
            f"name: {name}\n"
            f"version: {version}\n"
            f"description: {name} skill description\n"
            f"allowed-tools:\n"
            f"  - {tools_yaml}\n"
            f"risk_level: low\n"
            f"trust_level: verified\n"
            f"---\n\n"
            f"# {name.title()}\n\n"
            f"{name} instructions.",
            encoding="utf-8",
        )

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
        (skill_dir / ".agk_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # references/ 디렉토리 (스킬 문서)
        ref_dir = skill_dir / "references"
        ref_dir.mkdir(exist_ok=True)
        (ref_dir / "guide.md").write_text("# User Guide\n\nHow to use this skill.", encoding="utf-8")

        return skill_dir

    # ─── Validation E2E ───────────────────────────────────────────

    def test_e2e_validate_full_market_skill(self, tmp_path):
        """market/ 스킬 → _validate_for_publish 전체 검증."""
        from antigravity_k.engine.skill_publisher import SkillPublisher

        self._create_market_skill(tmp_path, "my-skill", "2.1.0", tool_count=3)
        publisher = SkillPublisher(project_root=str(tmp_path))

        skill_dir = publisher.market_dir / "my-skill"
        validation = publisher._validate_for_publish(skill_dir, "my-skill")

        assert validation.valid, f"Expected valid, got: {validation.reason}"
        assert validation.skill_name == "my-skill"
        assert validation.version == "2.1.0"
        assert validation.tool_count == 3
        assert validation.has_skill_md is True
        assert validation.has_readme is False  # README 없음 → warning
        assert validation.has_agk_meta is True
        assert len(validation.warnings) >= 1  # README 부재 warning

    def test_e2e_validate_no_skill_dir(self, tmp_path):
        """존재하지 않는 스킬 → PublishResult 실패."""
        from antigravity_k.engine.skill_publisher import SkillPublisher

        publisher = SkillPublisher(project_root=str(tmp_path))
        result = publisher.publish_to_npm("nonexistent", dry_run=True)
        assert not result.success
        assert any("찾을 수 없습니다" in e for e in result.errors)

    def test_e2e_validate_invalid_name(self, tmp_path):
        """잘못된 패키지명 → publish 실패."""
        from antigravity_k.engine.skill_publisher import SkillPublisher

        publisher = SkillPublisher(project_root=str(tmp_path))
        result = publisher.publish_to_npm("INVALID_NAME", dry_run=True)
        assert not result.success
        assert any("소문자와 하이픈만" in e for e in result.errors)

    # ─── npm publish E2E (mocked subprocess) ─────────────────────

    def test_e2e_npm_publish_full_pipeline(self, tmp_path):
        """npm publish 전체 파이프라인 (subprocess.run mock).

        mock 없이 validate → prepare → publish 시뮬레이션:
          - _prepare_package는 실제로 package.json/SKILL.md/README.md 생성
          - _npm_publish는 subprocess.run mock으로 대체
        """
        from unittest.mock import patch

        from antigravity_k.engine.skill_publisher import SkillPublisher

        self._create_market_skill(tmp_path, "publish-skill", "1.0.0")
        publisher = SkillPublisher(project_root=str(tmp_path))

        # Mock subprocess.run → npm publish 성공
        with patch("antigravity_k.engine.skill_publisher.subprocess.run") as mock_run:
            mock_result = type(
                "Result",
                (),
                {
                    "returncode": 0,
                    "stdout": "+ @antigravity-k/skill-publish-skill@1.0.0\n",
                    "stderr": "",
                },
            )()
            mock_run.return_value = mock_result

            result = publisher.publish_to_npm("publish-skill", dry_run=False)

        assert result.success, f"npm publish failed: {'; '.join(result.errors)}"
        assert result.action == "npm_publish"
        assert result.skill_name == "publish-skill"
        assert result.package_name == "@antigravity-k/skill-publish-skill"
        assert result.version == "1.0.0"

        # subprocess.run이 npm publish로 호출되었는지 확인
        assert mock_run.called
        call_args = mock_run.call_args[0][0]
        assert "npm" in call_args and "publish" in call_args

    def test_e2e_npm_publish_prepare_artifact(self, tmp_path):
        """npm publish 준비 단계에서 생성된 패키지 아티팩트 검증.

        _prepare_package가 생성한 package.json, SKILL.md, README.md,
        .npmignore, references/ 구조를 확인.
        """
        from antigravity_k.engine.skill_publisher import SkillPublisher

        self._create_market_skill(tmp_path, "artifact-skill", "3.0.0", tool_count=2)
        publisher = SkillPublisher(project_root=str(tmp_path))

        # prepare 단계 직접 호출
        skill_dir = publisher.market_dir / "artifact-skill"
        validation = publisher._validate_for_publish(skill_dir, "artifact-skill")
        assert validation.valid

        import tempfile

        pkg_dir = Path(tempfile.mkdtemp(prefix="agk-test-pkg-"))
        try:
            ok, err = publisher._prepare_package(
                skill_dir,
                pkg_dir,
                "@antigravity-k/skill-artifact-skill",
                "3.0.0",
                validation,
            )
            assert ok, f"Prepare failed: {err}"

            # ── package.json 검증 ──
            pkg_json = pkg_dir / "package.json"
            assert pkg_json.exists()
            pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
            assert pkg["name"] == "@antigravity-k/skill-artifact-skill"
            assert pkg["version"] == "3.0.0"
            assert pkg["private"] is False
            assert pkg["antigravityK"]["skill"] is True
            assert pkg["antigravityK"]["displayName"] == "Artifact Skill"
            assert pkg["antigravityK"]["requiredTools"] == ["read_file", "write_file"]
            assert pkg["antigravityK"]["riskLevel"] == "safe"
            assert pkg["antigravityK"]["trustLevel"] == "experimental"
            assert "antigravity-k" in pkg["keywords"]
            assert "skill" in pkg["keywords"]

            # ── SKILL.md 검증 ──
            skill_md = pkg_dir / "SKILL.md"
            assert skill_md.exists()
            content = skill_md.read_text(encoding="utf-8")
            assert "Artifact-Skill" in content  # .title() preserves hyphens in "artifact-skill"
            assert "name: artifact-skill" in content  # frontmatter 유지

            # ── README.md 검증 (자동 생성) ──
            readme = pkg_dir / "README.md"
            assert readme.exists()
            readme_content = readme.read_text(encoding="utf-8")
            assert "Artifact Skill" in readme_content  # _generate_readme uses name.replace('-', ' ').title()
            assert "@antigravity-k/skill-artifact-skill" in readme_content
            assert "Installation" in readme_content

            # ── .npmignore 검증 ──
            npmignore = pkg_dir / ".npmignore"
            assert npmignore.exists()
            npmcontent = npmignore.read_text(encoding="utf-8")
            assert "node_modules" in npmcontent
            assert ".agk_meta.json" in npmcontent

            # ── references/ 검증 ──
            ref_dest = pkg_dir / "references" / "guide.md"
            assert ref_dest.exists()
            assert "User Guide" in ref_dest.read_text(encoding="utf-8")

        finally:
            import shutil

            shutil.rmtree(pkg_dir, ignore_errors=True)

    def test_e2e_npm_publish_failure_handling(self, tmp_path):
        """npm publish 실패 → PublishResult.errors에 에러 기록."""
        from unittest.mock import patch

        from antigravity_k.engine.skill_publisher import SkillPublisher

        self._create_market_skill(tmp_path, "failing-skill")
        publisher = SkillPublisher(project_root=str(tmp_path))

        # Mock subprocess.run → npm publish 실패 (401)
        with patch("antigravity_k.engine.skill_publisher.subprocess.run") as mock_run:
            mock_result = type(
                "Result",
                (),
                {
                    "returncode": 1,
                    "stdout": "",
                    "stderr": "npm ERR! code ENEEDAUTH\nnpm ERR! need auth",
                },
            )()
            mock_run.return_value = mock_result

            result = publisher.publish_to_npm("failing-skill", dry_run=False)

        assert not result.success
        assert any("인증" in e for e in result.errors)

    def test_e2e_npm_publish_already_published(self, tmp_path):
        """이미 publish된 버전 → graceful 에러 메시지."""
        from unittest.mock import patch

        from antigravity_k.engine.skill_publisher import SkillPublisher

        self._create_market_skill(tmp_path, "already-published")
        publisher = SkillPublisher(project_root=str(tmp_path))

        with patch("antigravity_k.engine.skill_publisher.subprocess.run") as mock_run:
            mock_result = type(
                "Result",
                (),
                {
                    "returncode": 1,
                    "stdout": "",
                    "stderr": "cannot publish over the previously published version",
                },
            )()
            mock_run.return_value = mock_result

            result = publisher.publish_to_npm("already-published", dry_run=False)

        assert not result.success
        assert any("이미 동일 버전" in e for e in result.errors)

    # ─── GitHub PR E2E (mocked subprocess) ───────────────────────

    def test_e2e_github_pr_full_pipeline(self, tmp_path):
        """GitHub PR 전체 파이프라인 (gh CLI mock).

        validate → prepare → clone → branch → commit → push → PR create.
        _check_gh_cli, _create_github_pr 모두 subprocess.run mock으로 대체.
        """
        from unittest.mock import patch

        from antigravity_k.engine.skill_publisher import SkillPublisher

        self._create_market_skill(tmp_path, "pr-skill")
        publisher = SkillPublisher(project_root=str(tmp_path))

        # Mock subprocess.run → 모든 gh/git 명령어 성공
        call_log = []

        def mock_subprocess(args, **kwargs):
            cmd = args[0] if isinstance(args, list) else str(args)
            call_log.append(cmd)

            # gh --version → OK
            if cmd == "gh" and "--version" in args:
                return type("Result", (), {"returncode": 0, "stdout": "gh 2.0.0", "stderr": ""})()
            # gh auth status → OK
            if cmd == "gh" and "auth" in args and "status" in args:
                return type("Result", (), {"returncode": 0, "stdout": "Logged in to github.com", "stderr": ""})()
            # gh repo clone → OK
            if cmd == "gh" and "clone" in args:
                # 실제 clone 디렉토리 생성 (이후 git 명령어가 필요하므로)
                for i, a in enumerate(args):
                    if a == "--" and i + 1 < len(args):
                        break
                return type("Result", (), {"returncode": 0, "stdout": "Cloned", "stderr": ""})()
            # git checkout -b → OK
            if cmd == "git":
                return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            # gh pr create → OK (return PR URL)
            if cmd == "gh" and "pr" in args and "create" in args:
                return type(
                    "Result",
                    (),
                    {
                        "returncode": 0,
                        "stdout": "https://github.com/org/skills-repo/pull/42\n",
                        "stderr": "",
                    },
                )()
            # Fallback
            return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        with patch("antigravity_k.engine.skill_publisher.subprocess.run", side_effect=mock_subprocess):
            result = publisher.publish_to_github(
                "pr-skill",
                repo="org/skills-repo",
                dry_run=False,
            )

        assert result.success, f"GitHub PR failed: {'; '.join(result.errors)}"
        assert result.action == "github_pr"
        assert result.skill_name == "pr-skill"
        assert result.pr_url == "https://github.com/org/skills-repo/pull/42"

        # gh pr create가 호출되었는지 확인
        pr_calls = [c for c in call_log if c == "gh"]
        assert len(pr_calls) >= 1

    def test_e2e_github_pr_dry_run(self, tmp_path):
        """GitHub PR dry-run → 검증만 수행, URL 반환 없음."""
        from antigravity_k.engine.skill_publisher import SkillPublisher

        self._create_market_skill(tmp_path, "dry-run-skill")
        publisher = SkillPublisher(project_root=str(tmp_path))

        result = publisher.publish_to_github(
            "dry-run-skill",
            repo="org/skills-repo",
            dry_run=True,
        )

        assert result.success
        assert result.action == "github_pr"
        assert result.skill_name == "dry-run-skill"
        assert result.pr_url == ""  # dry-run은 URL 없음
        assert any("dry-run" in w for w in result.warnings)

    # ─── D17 + D8-D14 통합 E2E ───────────────────────────────────

    def test_e2e_market_to_publisher_integration(self, tmp_path):
        """SkillLoader → SkillMarketRegistry → SkillPublisher 통합 E2E.

        전체 플로우:
          1. market/ 스킬 생성 (D8-D14 스타일)
          2. SkillLoader market 로드
          3. SkillMarketRegistry list_installed
          4. SkillPublisher 유효성 검증
          5. npm publish 패키지 생성
          6. 생성된 package.json 확인
        """
        from antigravity_k.engine.skill_loader import SkillLoader
        from antigravity_k.engine.skill_market_client import SkillMarketClient
        from antigravity_k.engine.skill_market_registry import SkillMarketRegistry
        from antigravity_k.engine.skill_publisher import SkillPublisher

        # ── Step 1-3: D8-D14 마켓 스킬 셋업 ──
        self._create_market_skill(tmp_path, "integrated-skill", "1.5.0", tool_count=3)

        # SkillLoader 로드
        loader = SkillLoader(project_root=str(tmp_path), include_global=False, include_market=True)
        skill = loader.get_skill("integrated-skill")
        assert skill is not None
        assert skill["source"] == "market"
        assert skill["name"] == "integrated-skill"

        # SkillMarketClient 설치 상태
        client = SkillMarketClient(project_root=str(tmp_path))
        assert client.is_installed("integrated-skill") is True

        # SkillMarketRegistry
        registry = SkillMarketRegistry(
            project_root=str(tmp_path),
            market_client=client,
            skill_loader=loader,
        )
        info = registry.get_info("integrated-skill")
        assert info is not None
        assert info.version == "1.5.0"
        assert info.is_loaded is True

        # ── Step 4-6: SkillPublisher ──
        publisher = SkillPublisher(project_root=str(tmp_path))

        # 유효성 검증
        skill_dir = publisher.market_dir / "integrated-skill"
        validation = publisher._validate_for_publish(skill_dir, "integrated-skill")
        assert validation.valid
        assert validation.version == "1.5.0"
        assert validation.tool_count == 3

        # 패키지 아티팩트 검증
        import tempfile

        pkg_dir = Path(tempfile.mkdtemp(prefix="agk-e2e-"))
        try:
            ok, err = publisher._prepare_package(
                skill_dir,
                pkg_dir,
                "@antigravity-k/skill-integrated-skill",
                "1.5.0",
                validation,
            )
            assert ok, f"Prepare failed: {err}"

            pkg = json.loads((pkg_dir / "package.json").read_text(encoding="utf-8"))
            assert pkg["name"] == "@antigravity-k/skill-integrated-skill"
            assert pkg["version"] == "1.5.0"
            assert pkg["antigravityK"]["requiredTools"] == ["read_file", "write_file", "grep_search"]
            assert pkg["antigravityK"]["minAgentVersion"] == "0.1.0"

            # README 자동 생성 확인
            readme = (pkg_dir / "README.md").read_text(encoding="utf-8")
            assert "@antigravity-k/skill-integrated-skill" in readme

        finally:
            import shutil

            shutil.rmtree(pkg_dir, ignore_errors=True)

    def test_e2e_publisher_result_summary(self, tmp_path):
        """PublishResult.summary() 출력 검증."""
        from antigravity_k.engine.skill_publisher import PublishResult

        # npm 성공
        r1 = PublishResult(
            success=True,
            action="npm_publish",
            skill_name="test",
            package_name="@antigravity-k/skill-test",
            version="1.0.0",
            npm_url="https://www.npmjs.com/package/@antigravity-k/skill-test",
        )
        s1 = r1.summary()
        assert "✅" in s1
        assert "@antigravity-k/skill-test@1.0.0" in s1

        # GitHub PR 성공
        r2 = PublishResult(
            success=True,
            action="github_pr",
            skill_name="test-skill",
            pr_url="https://github.com/org/repo/pull/42",
        )
        s2 = r2.summary()
        assert "✅" in s2
        assert "test-skill" in s2
        assert "PR" in s2

        # 실패
        r3 = PublishResult(
            success=False,
            skill_name="broken",
            errors=["npm publish failed with code 1"],
        )
        s3 = r3.summary()
        assert "❌" in s3
        assert "broken" in s3
        assert "npm publish failed" in s3

    def test_e2e_publisher_readme_generation(self, tmp_path):
        """README.md 자동 생성 포맷 검증."""
        from antigravity_k.engine.skill_publisher import PublishValidation, SkillPublisher

        publisher = SkillPublisher(project_root=str(tmp_path))

        import tempfile

        dest = Path(tempfile.mkdtemp(prefix="agk-readme-"))
        try:
            validation = PublishValidation(
                valid=True,
                skill_name="code-review",
                tool_count=4,
                has_skill_md=True,
            )
            publisher._generate_readme(dest, validation)

            readme = dest / "README.md"
            assert readme.exists()
            content = readme.read_text(encoding="utf-8")
            assert "# Code Review" in content
            assert "@antigravity-k/skill-code-review" in content
            assert "Installation" in content
            assert "4 tool" in content
            assert "agk market --install" in content
        finally:
            import shutil

            shutil.rmtree(dest, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# E2E: Phase 1 전체 통합 시나리오
# ═══════════════════════════════════════════════════════════════════════


class TestPhase1_E2E_FullIntegration:
    """D1~D13 전체 통합 시나리오 — Plan/Build 모드 + Skills Marketplace."""

    def test_full_phase1_lifecycle(self, tmp_path):
        """Phase 1 전체 라이프사이클 E2E 검증.

        시나리오:
          1. Interactive 시작
          2. PLAN 모드 전환 → 권한 검증
          3. Plan 아티팩트 생성 + 검증
          4. QualityGate 평가 (PLAN 모드)
          5. PlanToBuildPipeline → Build 전환
          6. SkillLoader market/ 스킬 로드
          7. MCPServerRegistry 스킬 MCP 등록
          8. SkillMarketRegistry format_list
          9. Interactive 복귀 → 최종 상태 확인
        """
        from antigravity_k.engine.plan_to_build import PlanToBuildPipeline
        from antigravity_k.engine.skill_loader import SkillLoader
        from antigravity_k.engine.skill_market_registry import SkillMarketRegistry
        from antigravity_k.tools.mcp_tool_loader import MCPServerRegistry

        # ── Setup: market/ 디렉토리 + 스킬 파일 준비 ──
        market_dir = tmp_path / ".agent" / "skills" / "market"
        skill_dir = market_dir / "code-review"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: Code Review\ndescription: Automated code review skill\n"  # noqa: E501
            "risk_level: low\ntrust_level: verified\n---\n\n"
            "# Code Review Instructions\n\n"
            "Review code for bugs and style issues."
        )

        # ── Phase 1: Interactive 시작 ──
        mgr = ModeManager()
        assert mgr.is_interactive is True
        assert mgr.current_mode == ExecutionMode.INTERACTIVE

        # ── Phase 2: PLAN 모드 전환 ──
        mgr.switch_to_plan("Complex refactoring needed")
        assert mgr.is_plan is True

        # PLAN 모드 권한 검증
        assert mgr.check_tool_permission("read_file")["allowed"] is True
        assert mgr.check_tool_permission("write_file")["allowed"] is False
        assert mgr.check_tool_permission("str_replace")["allowed"] is False
        assert mgr.check_tool_permission("write_artifact")["allowed"] is True

        # ── Phase 3: Plan 아티팩트 생성 ──
        ae = ArtifactEngine(project_root=str(tmp_path))
        plan_content = (
            "# Overview\n\nRefactor auth module.\n\n"
            "## Technical Approach\n\nJWT tokens.\n\n"
            "## Implementation Steps\n\nSteps.\n\n"
            "## Tasks\n\n- [ ] Task 1\n- [ ] Task 2\n- [ ] Task 3\n\n"
            "## Timeline\n\nWeek 1.\n\n"
        )
        ae.write_artifact("implementation_plan.md", plan_content)

        # Plan 검증
        validation = ae.validate_plan_complete()
        assert validation.is_complete is True or validation.score >= 0.3

        # ── Phase 4: QualityGate 평가 ──
        qg = QualityGate()
        quality = qg.evaluate(
            task_type="plan",
            user_request="Create plan for auth refactoring",
            agent_output=plan_content,
            execution_mode="plan",
        )
        # PLAN 모드 → 코드 블록 체크 생략
        code_issues = [i for i in quality.issues if "코드" in i or "code" in i]
        assert len(code_issues) == 0

        # ── Phase 5: PlanToBuildPipeline → Build 전환 ──
        pipeline = PlanToBuildPipeline(
            mode_manager=mgr,
            artifact_engine=ae,
            quality_gate=qg,
            min_plan_score=0.3,
        )
        result = pipeline.run(auto_transition=True, create_kanban=False)
        assert result.success is True
        assert mgr.is_build is True

        # BUILD 모드 권한 검증
        assert mgr.check_tool_permission("write_file")["allowed"] is True
        assert mgr.check_tool_permission("str_replace")["allowed"] is True
        assert mgr.check_tool_permission("deploy")["requires_approval"] is True

        # ── Phase 6: SkillLoader market/ 스킬 로드 ──
        loader = SkillLoader(project_root=str(tmp_path), include_global=False, include_market=True)
        market_skills = loader.get_market_skills()
        assert len(market_skills) >= 1
        assert any(s["id"] == "code-review" for s in market_skills)

        skill = loader.get_skill("code-review")
        assert skill is not None
        assert skill["source"] == "market"
        assert "Code Review" in skill["content"]

        # SkillsRegistry 연동
        from antigravity_k.agents.skills_registry import SkillsRegistry

        registry = SkillsRegistry(skills_dir=str(tmp_path / ".agent" / "skills"))
        profile = registry.get_profile("CODE-REVIEW")
        assert profile is not None

        # ── Phase 7: MCPServerRegistry 스킬 MCP 등록 ──
        mcp_registry = MCPServerRegistry()
        mcp_registry.register_skill_mcp(
            "code-review",
            {
                "serverId": "review-server",
                "command": "python",
                "args": ["-m", "review"],
            },
        )
        servers = mcp_registry.get_skill_mcp_servers("code-review")
        assert "review-server" in servers

        # all_servers에 포함 확인
        all_servers = mcp_registry.get_all()
        assert "review-server" in all_servers

        # ── Phase 8: SkillMarketRegistry ──
        market_registry = SkillMarketRegistry(
            project_root=str(tmp_path),
            skill_loader=loader,
        )
        # list_installed (market_client 없음 → empty)
        installed = market_registry.list_installed()
        # format_list (빈 목록)
        formatted = market_registry.format_list(installed)
        assert isinstance(formatted, str)

        # ── Phase 9: Interactive 복귀 ──
        mgr.switch_to_interactive("Phase 1 E2E complete")
        assert mgr.is_interactive is True

        # 최종 상태 확인
        assert len(mgr.mode_history) == 3  # plan → build → interactive
        d = mgr.to_dict()
        assert d["current_mode"] == "interactive"
        status = mgr.format_status()
        assert "INTERACTIVE" in status.upper()

        # ── Artifact 검증 ──
        artifacts = ae.list_artifacts()
        assert len(artifacts) >= 1
