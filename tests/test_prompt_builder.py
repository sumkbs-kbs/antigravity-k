"""Tests for prompt_builder — PromptBuilder: role prompts, tool guides, structured prompts."""

from __future__ import annotations

import datetime

from antigravity_k.engine.prompt_builder import PromptBuilder

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


def _make_valid_prompts_dir(tmp_path):
    """Create a minimal prompts/ directory with role and persona files."""
    roles_dir = tmp_path / "roles"
    roles_dir.mkdir(parents=True)
    (roles_dir / "worker.md").write_text(
        "---\ntype: role\n---\n## Worker Prompt\nYou are a worker.\n", encoding="utf-8"
    )
    (roles_dir / "default.md").write_text(
        "---\ntype: role\n---\n## Default Prompt\nYou are a default.\n", encoding="utf-8"
    )
    (tmp_path / "persona.md").write_text("---\ntype: persona\n---\n## Persona\nBe concise.\n", encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


class TestInit:
    def test_default_prompts_dir_exists(self, tmp_path):
        """Builder resolves the prompts directory and does not crash."""
        builder = PromptBuilder(prompts_dir=str(tmp_path))
        assert builder._dir == str(tmp_path)

    def test_prompts_dir_not_found_logs_warning(self):
        """Non-existent prompts directory logs a warning but does not crash."""
        builder = PromptBuilder(prompts_dir="/nonexistent/path")
        assert builder._dir == "/nonexistent/path"
        # Cache is empty
        assert builder._cache == {}


# ---------------------------------------------------------------------------
# _load
# ---------------------------------------------------------------------------


class TestLoad:
    def test_load_existing_file(self, tmp_path):
        builder = PromptBuilder(prompts_dir=str(tmp_path))
        (tmp_path / "test.md").write_text("hello world", encoding="utf-8")
        assert builder._load("test.md") == "hello world"

    def test_load_caches_result(self, tmp_path):
        builder = PromptBuilder(prompts_dir=str(tmp_path))
        (tmp_path / "cached.md").write_text("content", encoding="utf-8")
        assert builder._load("cached.md") == "content"
        # Modify file — cached version should still be returned
        (tmp_path / "cached.md").write_text("modified", encoding="utf-8")
        assert builder._load("cached.md") == "content"

    def test_load_file_not_found_returns_none(self, tmp_path):
        builder = PromptBuilder(prompts_dir=str(tmp_path))
        assert builder._load("nonexistent.md") is None

    def test_load_strips_yaml_frontmatter(self, tmp_path):
        builder = PromptBuilder(prompts_dir=str(tmp_path))
        content = "---\ntitle: test\n---\nbody text"
        (tmp_path / "front.md").write_text(content, encoding="utf-8")
        assert builder._load("front.md") == "body text"

    def test_load_yaml_frontmatter_no_closing(self, tmp_path):
        """If the YAML block does not close, entire file is returned as-is."""
        builder = PromptBuilder(prompts_dir=str(tmp_path))
        (tmp_path / "bad.md").write_text("---\nno close", encoding="utf-8")
        assert builder._load("bad.md") == "---\nno close"


# ---------------------------------------------------------------------------
# role_prompt
# ---------------------------------------------------------------------------


class TestRolePrompt:
    def test_role_prompt_found(self, tmp_path):
        prompts_dir = _make_valid_prompts_dir(tmp_path)
        builder = PromptBuilder(prompts_dir=str(prompts_dir))
        result = builder.role_prompt("WORKER")
        assert "## Worker Prompt" in result

    def test_role_prompt_fallback_to_default(self, tmp_path):
        """Unknown role falls back to default.md."""
        prompts_dir = _make_valid_prompts_dir(tmp_path)
        builder = PromptBuilder(prompts_dir=str(prompts_dir))
        result = builder.role_prompt("NONEXISTENT")
        assert "## Default Prompt" in result

    def test_role_prompt_no_files_returns_inline(self):
        """When no prompt files exist, return inline fallback."""
        builder = PromptBuilder(prompts_dir="/nonexistent/path")
        result = builder.role_prompt("CEO")
        assert "acting as CEO" in result


# ---------------------------------------------------------------------------
# persona_prompt
# ---------------------------------------------------------------------------


class TestPersonaPrompt:
    def test_persona_found(self, tmp_path):
        prompts_dir = _make_valid_prompts_dir(tmp_path)
        builder = PromptBuilder(prompts_dir=str(prompts_dir))
        result = builder.persona_prompt()
        assert "Be concise." in result
        assert "[CORE DIRECTIVE" in result

    def test_persona_not_found_returns_empty(self):
        builder = PromptBuilder(prompts_dir="/nonexistent")
        assert builder.persona_prompt() == ""


# ---------------------------------------------------------------------------
# tool_guide
# ---------------------------------------------------------------------------


class TestToolGuide:
    def test_tool_guide_contains_current_time(self):
        builder = PromptBuilder(prompts_dir="/nonexistent")
        now = datetime.datetime(2026, 7, 18, 10, 30)
        result = builder.tool_guide(tool_schemas=[], current_time=now)
        assert "2026년 07월 18일 10시 30분" in result

    def test_tool_guide_lists_schema(self):
        builder = PromptBuilder(prompts_dir="/nonexistent")
        schemas = [
            {
                "name": "web_search",
                "description": "Search the web",
                "input_schema": {
                    "type": "object",
                    "required": ["query"],
                    "properties": {"query": {"type": "string"}},
                },
            },
        ]
        result = builder.tool_guide(tool_schemas=schemas)
        assert "**web_search**" in result
        assert "query (string, required)" in result

    def test_tool_guide_without_properties(self):
        """Schema without properties does not crash."""
        builder = PromptBuilder(prompts_dir="/nonexistent")
        schemas = [{"name": "simple_tool", "description": "A simple tool", "input_schema": {}}]
        result = builder.tool_guide(tool_schemas=schemas)
        assert "**simple_tool**" in result


# ---------------------------------------------------------------------------
# structured_prompt
# ---------------------------------------------------------------------------


class TestStructuredPrompt:
    def test_basic_structure(self):
        builder = PromptBuilder(prompts_dir="/nonexistent")
        result = builder.structured_prompt(
            role="분석가",
            task="지금 날씨를 알려주세요.",
        )
        assert "[ROLE]" in result
        assert "분석가" in result
        assert "[TASK]" in result
        assert "지금 날씨를 알려주세요." in result
        assert "[CONSTRAINTS]" in result

    def test_with_context(self):
        builder = PromptBuilder(prompts_dir="/nonexistent")
        result = builder.structured_prompt(
            role="분석가",
            task="분석해주세요.",
            context="참고: 오늘은 화요일입니다.",
        )
        assert "[CONTEXT]" in result
        assert "화요일" in result

    def test_with_custom_constraints(self):
        builder = PromptBuilder(prompts_dir="/nonexistent")
        result = builder.structured_prompt(
            role="분석가",
            task="분석해주세요.",
            constraints=["한국어", "간결하게"],
        )
        assert "한국어" in result
        assert "간결하게" in result

    def test_with_output_format(self):
        builder = PromptBuilder(prompts_dir="/nonexistent")
        result = builder.structured_prompt(
            role="분석가",
            task="분석해주세요.",
            output_format="Markdown table",
        )
        assert "[OUTPUT FORMAT]" in result
        assert "Markdown table" in result

    def test_with_few_shot(self):
        builder = PromptBuilder(prompts_dir="/nonexistent")
        result = builder.structured_prompt(
            role="분석가",
            task="분석해주세요.",
            few_shot=[{"input": "안녕", "output": "Hello"}],
        )
        assert "[EXAMPLES]" in result
        assert "안녕" in result
        assert "Hello" in result

    def test_with_planning_mode(self):
        builder = PromptBuilder(prompts_dir="/nonexistent")
        result = builder.structured_prompt(
            role="분석가",
            task="분석해주세요.",
            planning_mode=True,
        )
        assert "[PLANNING_MODE]" in result
        assert "[APPROVAL REQUIRED]" in result

    def test_with_artifact_formatting(self):
        builder = PromptBuilder(prompts_dir="/nonexistent")
        result = builder.structured_prompt(
            role="분석가",
            task="분석해주세요.",
            artifact_formatting=True,
        )
        assert "[ARTIFACTS]" in result
        assert "implementation_plan.md" in result


# ---------------------------------------------------------------------------
# artifact_formatting_rules / planning_mode_instructions
# ---------------------------------------------------------------------------


class TestArtifactMethods:
    def test_artifact_formatting_rules_has_required_sections(self):
        builder = PromptBuilder(prompts_dir="/nonexistent")
        result = builder.artifact_formatting_rules()
        assert "Overview" in result
        assert "Technical Approach" in result
        assert "Implementation Steps" in result
        assert "Task List" in result
        assert "Timeline" in result
        assert "render_diffs" in result
        assert "mermaid" in result

    def test_planning_mode_instructions_has_approval_marker(self):
        builder = PromptBuilder(prompts_dir="/nonexistent")
        result = builder.planning_mode_instructions()
        assert "[APPROVAL REQUIRED]" in result
        assert "PLAN" in result
        assert "BUILD" in result


# ---------------------------------------------------------------------------
# get_task_few_shots
# ---------------------------------------------------------------------------


class TestTaskFewShots:
    def test_search_type_returns_examples(self):
        builder = PromptBuilder(prompts_dir="/nonexistent")
        examples = builder.get_task_few_shots("SEARCH")
        assert len(examples) >= 1
        assert "삼성전자" in examples[0]["input"]

    def test_code_type_returns_examples(self):
        builder = PromptBuilder(prompts_dir="/nonexistent")
        examples = builder.get_task_few_shots("CODE")
        assert len(examples) >= 1
        assert "피보나치" in examples[0]["input"]

    def test_unknown_type_returns_empty(self):
        builder = PromptBuilder(prompts_dir="/nonexistent")
        assert builder.get_task_few_shots("UNKNOWN") == []


# ---------------------------------------------------------------------------
# clear_cache
# ---------------------------------------------------------------------------


class TestClearCache:
    def test_clear_cache_empties_cache(self, tmp_path):
        builder = PromptBuilder(prompts_dir=str(tmp_path))
        (tmp_path / "test.md").write_text("data", encoding="utf-8")
        builder._load("test.md")
        assert len(builder._cache) == 1
        builder.clear_cache()
        assert len(builder._cache) == 0
