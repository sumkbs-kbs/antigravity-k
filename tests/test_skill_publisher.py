"""Tests for SkillPublisher — 로컬 스킬 publish/npm/GitHub PR.

Phase 1 D17: npm publish + GitHub PR 배포 검증.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from antigravity_k.engine.skill_publisher import (
    JsonValue,
    PublishResult,
    PublishValidation,
    SkillPublisher,
)


def _validate_for_publish(
    publisher: SkillPublisher,
    skill_dir: Path,
    skill_name: str,
) -> PublishValidation:
    method = cast(
        Callable[[Path, str], PublishValidation],
        getattr(publisher, "_validate_for_publish"),
    )
    return method(skill_dir, skill_name)


def _validate_package_name(publisher: SkillPublisher, package_name: str) -> bool:
    method = cast(Callable[[str], bool], getattr(publisher, "_validate_package_name"))
    return method(package_name)


def _prepare_package(
    publisher: SkillPublisher,
    skill_dir: Path,
    dest: Path,
    package_name: str,
    version: str,
    validation: PublishValidation,
) -> tuple[bool, str]:
    method = cast(
        Callable[[Path, Path, str, str, PublishValidation], tuple[bool, str]],
        getattr(publisher, "_prepare_package"),
    )
    return method(skill_dir, dest, package_name, version, validation)


def _generate_package_json(
    publisher: SkillPublisher,
    skill_dir: Path,
    package_name: str,
    version: str,
    validation: PublishValidation,
) -> dict[str, JsonValue]:
    method = cast(
        Callable[[Path, str, str, PublishValidation], dict[str, JsonValue]],
        getattr(publisher, "_generate_package_json"),
    )
    return method(skill_dir, package_name, version, validation)


def _parse_frontmatter(publisher: SkillPublisher, content: str) -> dict[str, JsonValue]:
    method = cast(Callable[[str], dict[str, JsonValue]], getattr(publisher, "_parse_frontmatter"))
    return method(content)


def _find_skill_dir(publisher: SkillPublisher, skill_name: str) -> Path | None:
    method = cast(Callable[[str], Path | None], getattr(publisher, "_find_skill_dir"))
    return method(skill_name)

# ─── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def tmp_skills(tmp_path: Path) -> Path:
    """임시 스킬 디렉토리 구조를 생성합니다."""
    skills_dir = tmp_path / ".agent" / "skills"
    skill_dir = skills_dir / "test-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)

    # SKILL.md (frontmatter 포함)
    skill_md = skill_dir / "SKILL.md"
    _ = skill_md.write_text(
        "---\n"
        + "name: test-skill\n"
        + "version: 1.2.3\n"
        + "description: A test skill for publisher unit tests\n"
        + "allowed-tools:\n"
        + "  - read_file\n"
        + "  - grep_search\n"
        + "---\n\n"
        + "# Test Skill\n\n"
        + "This is a test skill.\n",
        encoding="utf-8",
    )

    # .agk_meta.json
    meta = skill_dir / ".agk_meta.json"
    _ = meta.write_text(
        json.dumps(
            {
                "name": "@antigravity-k/skill-test-skill",
                "version": "1.2.3",
                "description": "Test skill meta",
                "installed_at": "2026-01-01T00:00:00",
            }
        ),
        encoding="utf-8",
    )

    # references/
    ref_dir = skill_dir / "references"
    ref_dir.mkdir()
    ref_file = ref_dir / "guide.md"
    _ = ref_file.write_text("# Reference Guide\n", encoding="utf-8")

    return skills_dir


@pytest.fixture
def publisher(tmp_path: Path) -> SkillPublisher:
    """SkillPublisher 인스턴스 (임시 프로젝트 루트)."""
    return SkillPublisher(project_root=str(tmp_path))


# ─── Tests: _validate_for_publish ────────────────────────────────────


class TestD17_ValidateForPublish:
    """SkillPublisher._validate_for_publish() 검증."""

    def test_validate_valid_skill(self, publisher: SkillPublisher, tmp_skills: Path):
        skill_dir = tmp_skills / "test-skill"
        result = _validate_for_publish(publisher, skill_dir, "test-skill")
        assert result.valid, f"Expected valid, got: {result.reason}"
        assert result.skill_name == "test-skill"
        assert result.has_skill_md is True
        assert result.version == "1.2.3"
        assert result.tool_count == 2

    def test_validate_missing_skill_md(self, publisher: SkillPublisher, tmp_path: Path):
        """SKILL.md가 없으면 invalid."""
        empty_dir = tmp_path / ".agent" / "skills" / "no-skill"
        empty_dir.mkdir(parents=True)
        result = _validate_for_publish(publisher, empty_dir, "no-skill")
        assert not result.valid
        assert "SKILL.md not found" in result.reason

    def test_validate_no_frontmatter_version(self, publisher: SkillPublisher, tmp_path: Path):
        """frontmatter에 version이 없으면 기본 버전 사용."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir(parents=True)
        skill_md = skill_dir / "SKILL.md"
        _ = skill_md.write_text(
            "---\nname: my-skill\n---\n\nContent here.\n",
            encoding="utf-8",
        )
        result = _validate_for_publish(publisher, skill_dir, "my-skill")
        assert result.valid
        assert result.version == "1.0.0"  # 기본값

    def test_validate_warns_missing_readme(self, publisher: SkillPublisher, tmp_skills: Path):
        """README.md가 없으면 warning."""
        skill_dir = tmp_skills / "test-skill"
        result = _validate_for_publish(publisher, skill_dir, "test-skill")
        assert result.valid
        # README.md 없음은 warning이지만 유효성에는 영향 없음
        assert result.has_readme is False

    def test_validate_package_name_valid(self, publisher: SkillPublisher):
        assert _validate_package_name(publisher, "code-review") is True
        assert _validate_package_name(publisher, "my-skill-v2") is True
        assert _validate_package_name(publisher, "Code_Review") is False  # 대문자
        assert _validate_package_name(publisher, "") is False  # 빈 문자열


# ─── Tests: _prepare_package ─────────────────────────────────────────


class TestD17_PreparePackage:
    """패키지 준비 검증."""

    def test_prepare_creates_package_json(self, publisher: SkillPublisher, tmp_skills: Path, tmp_path: Path):
        skill_dir = tmp_skills / "test-skill"
        dest = Path(tmp_path) / "pkg"
        dest.mkdir()

        validation = _validate_for_publish(publisher, skill_dir, "test-skill")
        ok, err = _prepare_package(publisher, skill_dir, dest, "@antigravity-k/skill-test-skill", "1.2.3", validation)
        assert ok, f"Prepare failed: {err}"

        # package.json 생성 확인
        pkg_json = dest / "package.json"
        assert pkg_json.exists()
        loaded = cast(object, json.loads(pkg_json.read_text(encoding="utf-8")))
        pkg = cast(dict[str, object], loaded)
        assert pkg["name"] == "@antigravity-k/skill-test-skill"
        assert pkg["version"] == "1.2.3"
        agk_meta = cast(dict[str, object], pkg["antigravityK"])
        assert agk_meta["skill"] is True
        assert "read_file" in cast(list[object], agk_meta["requiredTools"])

    def test_prepare_copies_skill_md(self, publisher: SkillPublisher, tmp_skills: Path, tmp_path: Path):
        skill_dir = tmp_skills / "test-skill"
        dest = Path(tmp_path) / "pkg"
        dest.mkdir()

        validation = _validate_for_publish(publisher, skill_dir, "test-skill")
        ok, err = _prepare_package(publisher, skill_dir, dest, "@antigravity-k/skill-test-skill", "1.2.3", validation)
        assert ok, f"Prepare failed: {err}"

        assert (dest / "SKILL.md").exists()
        assert "Test Skill" in (dest / "SKILL.md").read_text(encoding="utf-8")

    def test_prepare_generates_readme(self, publisher: SkillPublisher, tmp_skills: Path, tmp_path: Path):
        skill_dir = tmp_skills / "test-skill"
        dest = Path(tmp_path) / "pkg"
        dest.mkdir()

        validation = _validate_for_publish(publisher, skill_dir, "test-skill")
        ok, err = _prepare_package(publisher, skill_dir, dest, "@antigravity-k/skill-test-skill", "1.2.3", validation)
        assert ok, f"Prepare failed: {err}"

        readme = dest / "README.md"
        assert readme.exists()
        content = readme.read_text(encoding="utf-8")
        assert "Test Skill" in content

    def test_prepare_copies_references(self, publisher: SkillPublisher, tmp_skills: Path, tmp_path: Path):
        skill_dir = tmp_skills / "test-skill"
        dest = Path(tmp_path) / "pkg"
        dest.mkdir()

        validation = _validate_for_publish(publisher, skill_dir, "test-skill")
        ok, err = _prepare_package(publisher, skill_dir, dest, "@antigravity-k/skill-test-skill", "1.2.3", validation)
        assert ok, f"Prepare failed: {err}"

        assert (dest / "references" / "guide.md").exists()

    def test_prepare_creates_npmignore(self, publisher: SkillPublisher, tmp_skills: Path, tmp_path: Path):
        skill_dir = tmp_skills / "test-skill"
        dest = Path(tmp_path) / "pkg"
        dest.mkdir()

        validation = _validate_for_publish(publisher, skill_dir, "test-skill")
        ok, err = _prepare_package(publisher, skill_dir, dest, "@antigravity-k/skill-test-skill", "1.2.3", validation)
        assert ok, f"Prepare failed: {err}"

        npmignore = dest / ".npmignore"
        assert npmignore.exists()
        assert "node_modules/" in npmignore.read_text(encoding="utf-8")


# ─── Tests: _generate_package_json ──────────────────────────────────


class TestD17_GeneratePackageJson:
    """package.json 생성 검증."""

    def test_generates_minimal(self, publisher: SkillPublisher, tmp_skills: Path):
        skill_dir = tmp_skills / "test-skill"
        validation = _validate_for_publish(publisher, skill_dir, "test-skill")
        pkg = _generate_package_json(publisher, skill_dir, "@antigravity-k/skill-test-skill", "1.2.3", validation)

        assert pkg["name"] == "@antigravity-k/skill-test-skill"
        assert pkg["version"] == "1.2.3"
        agk_meta = cast(dict[str, object], pkg["antigravityK"])
        assert agk_meta["skill"] is True
        assert agk_meta["displayName"] == "Test Skill"
        assert pkg["private"] is False

    def test_merges_existing_package_json(self, publisher: SkillPublisher, tmp_path: Path):
        """기존 package.json이 있으면 병합."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir(parents=True)
        _ = (skill_dir / "SKILL.md").write_text(
            "---\nname: my-skill\n---\n\nContent\n",
            encoding="utf-8",
        )
        _ = (skill_dir / "package.json").write_text(
            json.dumps(
                {
                    "license": "Apache-2.0",
                    "scripts": {"test": "echo ok"},
                    "engines": {"node": ">=18"},
                }
            ),
            encoding="utf-8",
        )

        validation = _validate_for_publish(publisher, skill_dir, "my-skill")
        pkg = _generate_package_json(publisher, skill_dir, "@antigravity-k/skill-my-skill", "2.0.0", validation)

        # 병합됨
        assert pkg["license"] == "Apache-2.0"
        scripts = cast(dict[str, object], pkg["scripts"])
        engines = cast(dict[str, object], pkg["engines"])
        assert scripts["test"] == "echo ok"
        assert engines["node"] == ">=18"
        # AGK 메타데이터 추가됨
        assert cast(dict[str, object], pkg["antigravityK"])["skill"] is True


# ─── Tests: publish_to_npm (dry-run) ────────────────────────────────


class TestD17_PublishToNpm:
    """npm publish 검증 (dry-run 모드)."""

    def test_dry_run_success(self, tmp_skills: Path):
        publisher = SkillPublisher(project_root=str(tmp_skills.parent.parent))
        result = publisher.publish_to_npm("test-skill", dry_run=True)
        assert result.success, f"Dry run failed: {'; '.join(result.errors)}"
        assert result.action == "npm_publish"
        assert result.skill_name == "test-skill"
        assert result.package_name == "@antigravity-k/skill-test-skill"

    def test_dry_run_unknown_skill(self, publisher: SkillPublisher):
        result = publisher.publish_to_npm("nonexistent-skill", dry_run=True)
        assert not result.success
        assert any("찾을 수 없습니다" in e for e in result.errors)


# ─── Tests: publish_to_github (dry-run) ─────────────────────────────


class TestD17_PublishToGithub:
    """GitHub PR publish 검증 (dry-run 모드)."""

    def test_dry_run_success(self, tmp_skills: Path):
        publisher = SkillPublisher(project_root=str(tmp_skills.parent.parent))
        result = publisher.publish_to_github(
            "test-skill",
            repo="org/skills-repo",
            dry_run=True,
        )
        assert result.success, f"Dry run failed: {'; '.join(result.errors)}"
        assert result.action == "github_pr"
        assert result.skill_name == "test-skill"

    def test_dry_run_unknown_skill(self, publisher: SkillPublisher):
        result = publisher.publish_to_github(
            "nonexistent-skill",
            repo="org/skills-repo",
            dry_run=True,
        )
        assert not result.success
        assert any("찾을 수 없습니다" in e for e in result.errors)


# ─── Tests: _parse_frontmatter ──────────────────────────────────────


class TestD17_ParseFrontmatter:
    """YAML frontmatter 파싱 검증."""

    def test_parse_valid_frontmatter(self, publisher: SkillPublisher):
        content = "---\nname: test-skill\nversion: 1.0.0\ndescription: A test\n---\n\n# Content\n"
        fm = _parse_frontmatter(publisher, content)
        assert fm.get("name") == "test-skill"
        assert fm.get("version") == "1.0.0"

    def test_parse_no_frontmatter(self, publisher: SkillPublisher):
        content = "# Just content\n\nNo frontmatter here.\n"
        fm = _parse_frontmatter(publisher, content)
        assert fm == {}

    def test_parse_empty_frontmatter(self, publisher: SkillPublisher):
        content = "---\n---\n\nContent\n"
        fm = _parse_frontmatter(publisher, content)
        assert fm == {}

    def test_parse_complex_yaml(self, publisher: SkillPublisher):
        """allowed-tools 리스트 파싱."""
        content = (
            "---\n"
            "name: complex-skill\n"
            "version: 3.0.0\n"
            "allowed-tools:\n"
            "  - read_file\n"
            "  - grep_search\n"
            "  - glob_search\n"
            "description: Complex test\n"
            "---\n"
        )
        fm = _parse_frontmatter(publisher, content)
        assert fm.get("name") == "complex-skill"
        tools = fm.get("allowed-tools", [])
        assert isinstance(tools, list)
        assert len(tools) == 3
        assert "read_file" in tools


# ─── Tests: _find_skill_dir ─────────────────────────────────────────


class TestD17_FindSkillDir:
    """스킬 디렉토리 검색 검증."""

    def test_find_market_dir(self, publisher: SkillPublisher, tmp_skills: Path):
        """market/ 디렉토리 우선 검색."""
        publisher.market_dir = tmp_skills / "market"
        publisher.market_dir.mkdir(parents=True, exist_ok=True)
        skill_dir = publisher.market_dir / "market-skill"
        skill_dir.mkdir()

        result = _find_skill_dir(publisher, "market-skill")
        assert result == skill_dir

    def test_find_skills_dir(self, publisher: SkillPublisher, tmp_skills: Path):
        """market/에 없으면 .agent/skills/에서 검색."""
        publisher.market_dir = tmp_skills / "market"
        publisher.market_dir.mkdir(parents=True, exist_ok=True)
        publisher.skills_dir = tmp_skills

        skill_dir = tmp_skills / "local-skill"
        skill_dir.mkdir()

        result = _find_skill_dir(publisher, "local-skill")
        assert result == skill_dir

    def test_find_not_found(self, publisher: SkillPublisher):
        """존재하지 않는 스킬 → None."""
        result = _find_skill_dir(publisher, "no-skill-here")
        assert result is None

    def test_find_prefers_market(self, publisher: SkillPublisher, tmp_path: Path):
        """동일 이름이 market과 skills 양쪽에 있으면 market 우선."""
        skills_dir = tmp_path / ".agent" / "skills"
        skills_dir.mkdir(parents=True)
        market_dir = skills_dir / "market"
        market_dir.mkdir()

        (market_dir / "shared-skill").mkdir()
        (skills_dir / "shared-skill").mkdir()

        publisher.market_dir = market_dir
        publisher.skills_dir = skills_dir

        result = _find_skill_dir(publisher, "shared-skill")
        assert result == market_dir / "shared-skill"


# ─── Tests: PublishResult ───────────────────────────────────────────


class TestD17_PublishResult:
    """PublishResult 데이터 모델 검증."""

    def test_has_error(self):
        r = PublishResult(success=True)
        assert not r.has_error

        r = PublishResult(success=False)
        assert r.has_error

        r = PublishResult(success=True, errors=["something"])
        assert r.has_error

    def test_summary_npm_success(self):
        r = PublishResult(
            success=True,
            action="npm_publish",
            skill_name="test",
            package_name="@antigravity-k/skill-test",
            version="1.0.0",
            npm_url="https://www.npmjs.com/package/@antigravity-k/skill-test",
        )
        s = r.summary()
        assert "✅" in s
        assert "@antigravity-k/skill-test@1.0.0" in s

    def test_summary_github_success(self):
        r = PublishResult(
            success=True,
            action="github_pr",
            skill_name="test-skill",
            pr_url="https://github.com/org/repo/pull/42",
        )
        s = r.summary()
        assert "✅" in s
        assert "PR" in s

    def test_summary_failure(self):
        r = PublishResult(
            success=False,
            skill_name="broken",
            errors=["npm publish failed"],
        )
        s = r.summary()
        assert "❌" in s
        assert "broken" in s
