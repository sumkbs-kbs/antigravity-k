"""
Google Skills 패턴 통합 테스트.

google/skills 저장소(https://github.com/google/skills)의 핵심 패턴을 검증:
1. SKILL.md + references/ 폴더 구조
2. compatibility 필드 (전제 조건)
3. Clarifying Questions 섹션 자동 파싱
4. Validation Logic 섹션 자동 파싱
5. to_metadata / to_metadata_list API
6. get_reference / list_references API
"""

import pytest
from antigravity_k.agents.skills_registry import (
    SkillsRegistry,
)


# ── 픽스처: Google Skills 스타일 스킬 폴더 생성 ──────────────────────


@pytest.fixture
def google_style_skill(tmp_path):
    """google/skills/gemini-api 스타일의 스킬 폴더를 생성합니다."""
    skills_dir = tmp_path / ".agent" / "skills"
    skill_dir = skills_dir / "gemini-api"
    skill_dir.mkdir(parents=True)

    # SKILL.md 작성 (Google Skills 패턴 그대로)
    (skill_dir / "SKILL.md").write_text(
        """---
name: gemini-api
description: Guides the usage of the Gemini API on Agent Platform.
compatibility: Requires active Google Cloud credentials.
tools:
  - search_web
  - run_python
---

# Gemini API in Agent Platform

Access Google's most advanced AI models.

## Clarifying Questions

1. Do you have a Google Cloud project?
2. Which SDK language do you prefer?
3. What model do you want to use?

## Quick Start

Use `google-genai` for Python.

## Validation Logic

- **Project Created:** Does the user have a Project ID?
- **CLI Authenticated:** Does `gcloud config list` show the correct account?
- **Resource Verified:** Can the user access the deployed resource?
""",
        encoding="utf-8",
    )

    # references/ 폴더 작성 (Google Skills 패턴)
    ref_dir = skill_dir / "references"
    ref_dir.mkdir()
    (ref_dir / "text_and_multimodal.md").write_text(
        "# Text & Multimodal\nChat, images, video inputs.",
        encoding="utf-8",
    )
    (ref_dir / "embeddings.md").write_text(
        "# Embeddings\nGenerate text embeddings for search.",
        encoding="utf-8",
    )
    (ref_dir / "safety.md").write_text(
        "# Safety\nResponsible AI filters.",
        encoding="utf-8",
    )

    return skills_dir


@pytest.fixture
def simple_skill(tmp_path):
    """reference/ (단수) 폴더를 사용하는 스킬."""
    skills_dir = tmp_path / ".agent" / "skills"
    skill_dir = skills_dir / "cloud-run"
    skill_dir.mkdir(parents=True)

    (skill_dir / "SKILL.md").write_text(
        """---
name: cloud-run-basics
description: Deploy containerized apps to Cloud Run.
compatibility: gcloud CLI installed.
tools:
  - run_docker
---

# Cloud Run Basics

Deploy containers easily.
""",
        encoding="utf-8",
    )

    # reference/ (단수 폴더도 지원)
    ref_dir = skill_dir / "reference"
    ref_dir.mkdir()
    (ref_dir / "deployment.md").write_text(
        "# Deployment\ngcloud run deploy",
        encoding="utf-8",
    )

    return skills_dir


# ── 1. references/ 폴더 로딩 테스트 ─────────────────────────────


class TestReferencesLoading:
    def test_references_loaded(self, google_style_skill):
        """references/ 폴더의 .md 파일들이 정상 로드되는지 확인."""
        registry = SkillsRegistry(skills_dir=str(google_style_skill))
        profile = registry.get_profile("GEMINI-API")

        assert len(profile.references) == 3
        assert "text_and_multimodal" in profile.references
        assert "embeddings" in profile.references
        assert "safety" in profile.references

    def test_reference_content(self, google_style_skill):
        """참조 문서의 내용이 올바르게 읽혀지는지 확인."""
        registry = SkillsRegistry(skills_dir=str(google_style_skill))
        content = registry.get_reference("GEMINI-API", "embeddings")

        assert content is not None
        assert "Embeddings" in content
        assert "text embeddings" in content

    def test_singular_reference_dir(self, simple_skill):
        """reference/ (단수) 폴더도 지원하는지 확인."""
        registry = SkillsRegistry(skills_dir=str(simple_skill))
        profile = registry.get_profile("CLOUD-RUN")

        assert len(profile.references) == 1
        assert "deployment" in profile.references

    def test_list_references(self, google_style_skill):
        """list_references API가 동작하는지 확인."""
        registry = SkillsRegistry(skills_dir=str(google_style_skill))
        refs = registry.list_references("GEMINI-API")

        assert len(refs) == 3
        assert "embeddings" in refs

    def test_get_reference_nonexistent(self, google_style_skill):
        """존재하지 않는 참조 문서 요청 시 None 반환."""
        registry = SkillsRegistry(skills_dir=str(google_style_skill))
        assert registry.get_reference("GEMINI-API", "nonexistent") is None
        assert registry.get_reference("NONEXISTENT", "anything") is None


# ── 2. compatibility 필드 테스트 ─────────────────────────────


class TestCompatibility:
    def test_compatibility_parsed(self, google_style_skill):
        """YAML frontmatter의 compatibility 필드가 파싱되는지 확인."""
        registry = SkillsRegistry(skills_dir=str(google_style_skill))
        profile = registry.get_profile("GEMINI-API")

        assert profile.compatibility == "Requires active Google Cloud credentials."

    def test_compatibility_empty_when_missing(self, tmp_path):
        """compatibility가 없는 스킬은 빈 문자열로 설정."""
        skills_dir = tmp_path / ".agent" / "skills"
        skill_dir = skills_dir / "simple"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: simple\ndescription: No compat\n---\n# Simple\n",
            encoding="utf-8",
        )
        registry = SkillsRegistry(skills_dir=str(skills_dir))
        profile = registry.get_profile("SIMPLE")
        assert profile.compatibility == ""


# ── 3. Clarifying Questions 섹션 파싱 테스트 ──────────────────


class TestClarifyingQuestions:
    def test_questions_extracted(self, google_style_skill):
        """'## Clarifying Questions' 섹션에서 질문 목록이 추출되는지 확인."""
        registry = SkillsRegistry(skills_dir=str(google_style_skill))
        profile = registry.get_profile("GEMINI-API")

        assert len(profile.clarifying_questions) == 3
        assert any("Google Cloud" in q for q in profile.clarifying_questions)
        assert any("SDK" in q for q in profile.clarifying_questions)

    def test_no_questions_section(self, simple_skill):
        """Clarifying Questions 섹션이 없는 스킬은 빈 리스트."""
        registry = SkillsRegistry(skills_dir=str(simple_skill))
        profile = registry.get_profile("CLOUD-RUN")
        assert profile.clarifying_questions == []


# ── 4. Validation Logic 섹션 파싱 테스트 ──────────────────────


class TestValidationLogic:
    def test_validation_extracted(self, google_style_skill):
        """'## Validation Logic' 섹션에서 검증 항목이 추출되는지 확인."""
        registry = SkillsRegistry(skills_dir=str(google_style_skill))
        profile = registry.get_profile("GEMINI-API")

        assert len(profile.validation_logic) == 3
        assert any("Project" in v for v in profile.validation_logic)
        assert any("CLI" in v for v in profile.validation_logic)

    def test_no_validation_section(self, simple_skill):
        """Validation Logic 섹션이 없으면 빈 리스트."""
        registry = SkillsRegistry(skills_dir=str(simple_skill))
        profile = registry.get_profile("CLOUD-RUN")
        assert profile.validation_logic == []


# ── 5. to_metadata / to_metadata_list API 테스트 ─────────────


class TestMetadataAPI:
    def test_skill_to_metadata(self, google_style_skill):
        """SkillProfile.to_metadata()가 올바른 딕셔너리를 반환하는지 확인."""
        registry = SkillsRegistry(skills_dir=str(google_style_skill))
        profile = registry.get_profile("GEMINI-API")
        meta = profile.to_metadata()

        assert meta["name"] == "GEMINI-API"
        assert meta["has_references"] is True
        assert meta["reference_count"] == 3
        assert meta["has_questions"] is True
        assert meta["has_validation"] is True
        assert meta["compatibility"] == "Requires active Google Cloud credentials."

    def test_registry_to_metadata_list(self, google_style_skill):
        """SkillsRegistry.to_metadata_list()가 전체 목록을 반환하는지 확인."""
        registry = SkillsRegistry(skills_dir=str(google_style_skill))
        meta_list = registry.to_metadata_list()

        assert isinstance(meta_list, list)
        # 기본 프로필 5개 + 동적 1개 = 최소 6개
        assert len(meta_list) >= 6
        names = [m["name"] for m in meta_list]
        assert "GEMINI-API" in names


# ── 6. _extract_section_list 단위 테스트 ─────────────────────


class TestExtractSectionList:
    def test_bold_key_list_pattern(self):
        """- **Key:** Value 패턴이 올바르게 파싱되는지."""
        body = """
## Validation Logic

- **Project Created:** Does the user have a Project ID?
- **Billing Linked:** Is the project linked?

## Next Steps
"""
        items = SkillsRegistry._extract_section_list(body, "Validation Logic")
        assert len(items) == 2
        assert "Project Created:" in items[0]

    def test_numbered_list_pattern(self):
        """번호 매기기 리스트 (1. 2. 3.) 패턴 파싱."""
        body = """
## Clarifying Questions

1. Do you have a Google Account?
2. Are you part of an organization?
3. What do you want to build?

## Prerequisites
"""
        items = SkillsRegistry._extract_section_list(body, "Clarifying Questions")
        assert len(items) == 3
        assert "Google Account" in items[0]

    def test_section_not_found(self):
        """없는 섹션은 빈 리스트."""
        body = "# Hello World\nSome text."
        items = SkillsRegistry._extract_section_list(body, "Nonexistent")
        assert items == []


# ── 7. 기본 프로필 하위호환성 테스트 ─────────────────────────


class TestBackwardCompatibility:
    def test_default_profiles_have_empty_new_fields(self, tmp_path):
        """기존 기본 프로필(PM, BACKEND 등)은 새 필드가 빈 값으로 초기화."""
        skills_dir = tmp_path / ".agent" / "skills"
        registry = SkillsRegistry(skills_dir=str(skills_dir))

        for name in ["PM", "BACKEND", "FRONTEND", "QA", "DEVOPS"]:
            profile = registry.get_profile(name)
            assert profile.compatibility == ""
            assert profile.references == {}
            assert profile.clarifying_questions == []
            assert profile.validation_logic == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
