"""Tests for ConfigEditorTool — config.yaml model roster management."""

import os
import shutil
import tempfile
from unittest import mock

import pytest

from antigravity_k.tools.config_editor_tool import ConfigEditorTool

SAMPLE_YAML = (
    "models:\n"
    "  reasoning:\n"
    "    - name: gpt-4\n"
    "      provider: openai\n"
    "  coding:\n"
    "    - name: claude-3\n"
    "      provider: anthropic\n"
    "agent_models:\n"
    "  WORKER: fast-combo\n"
    "combos:\n"
    "  fast-combo:\n"
    "    models: [gpt-4]\n"
    "    strategy: round_robin\n"
)


@pytest.fixture
def config_dir():
    """Create a temp dir with config.yaml inside."""
    tmpdir = tempfile.mkdtemp()
    config_path = os.path.join(tmpdir, "config.yaml")
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(SAMPLE_YAML)
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def tool(config_dir):
    """ConfigEditorTool with cwd pointed to temp dir."""
    t = ConfigEditorTool()
    with mock.patch("antigravity_k.tools.config_editor_tool.os.getcwd", return_value=config_dir):
        yield t


class TestConfigEditorToolInit:
    def test_name(self, tool):
        assert tool.name == "config_model_roster"

    def test_description(self, tool):
        assert "config.yaml" in tool.description

    def test_parameters_schema(self, tool):
        schema = tool.parameters_schema
        assert schema["type"] == "object"
        assert "action" in schema["required"]

    def test_category(self):
        assert ConfigEditorTool.category.name == "SYSTEM"

    def test_risk_level(self):
        assert ConfigEditorTool.risk_level.name == "HIGH"


class TestConfigEditorToolExecute:
    def config_path(self, config_dir):
        return os.path.join(config_dir, "config.yaml")

    def test_add_new_model(self, config_dir, tool):
        tool.execute(
            action="add",
            model_category="reasoning",
            model_data={"name": "gpt-5", "provider": "openai"},
        )
        with open(os.path.join(config_dir, "config.yaml"), encoding="utf-8") as f:
            content = f.read()
        assert "gpt-5" in content
        assert "gpt-4" in content  # original still there

    def test_add_duplicate_model(self, config_dir, tool):
        result = tool.execute(
            action="add",
            model_category="reasoning",
            model_data={"name": "gpt-4", "provider": "openai"},
        )
        assert "already exists" in result.lower()

    def test_remove_existing_model(self, config_dir, tool):
        result = tool.execute(
            action="remove",
            model_category="reasoning",
            model_data={"name": "gpt-4"},
        )
        assert "removed" in result.lower()
        with open(os.path.join(config_dir, "config.yaml"), encoding="utf-8") as f:
            content = f.read()
        # gpt-4 제거됐는지 models.reasoning 섹션에서 확인
        # (combos 섹션에는 여전히 [gpt-4] 참조가 남아있을 수 있음)
        import yaml

        parsed = yaml.safe_load(content)
        assert len(parsed["models"]["reasoning"]) == 0
        assert parsed["models"]["coding"][0]["name"] == "claude-3"

    def test_remove_nonexistent_model(self, config_dir, tool):
        result = tool.execute(
            action="remove",
            model_category="reasoning",
            model_data={"name": "nonexistent-model"},
        )
        assert "not found" in result.lower()

    def test_update_agent_map(self, config_dir, tool):
        result = tool.execute(
            action="update_agent_map",
            target_key="WORKER",
            model_data={"combo_name": "slow-combo"},
        )
        assert "mapped" in result.lower() or "updated" in result.lower()
        with open(os.path.join(config_dir, "config.yaml"), encoding="utf-8") as f:
            content = f.read()
        assert "slow-combo" in content

    def test_update_agent_map_new_key(self, config_dir, tool):
        result = tool.execute(
            action="update_agent_map",
            target_key="NEW_AGENT",
            model_data={"combo_name": "new-combo"},
        )
        assert "mapped" in result.lower() or "updated" in result.lower()

    def test_update_swarm(self, config_dir, tool):
        result = tool.execute(
            action="update_swarm",
            target_key="fast-combo",
            model_data={"models": ["gpt-4", "claude-3"], "strategy": "weighted"},
        )
        assert "updated" in result.lower()
        with open(os.path.join(config_dir, "config.yaml"), encoding="utf-8") as f:
            content = f.read()
        assert "weighted" in content

    def test_update_swarm_new_combo(self, config_dir, tool):
        result = tool.execute(
            action="update_swarm",
            target_key="new-combo",
            model_data={"models": ["gpt-5"], "strategy": "priority"},
        )
        assert "updated" in result.lower()

    def test_file_not_found(self, config_dir):
        """Config file doesn't exist in a different temp dir."""
        empty_dir = tempfile.mkdtemp()
        try:
            t = ConfigEditorTool()
            with (
                mock.patch("antigravity_k.tools.config_editor_tool.os.getcwd", return_value=empty_dir),
                mock.patch("antigravity_k.tools.config_editor_tool.os.path.exists", return_value=False),
            ):
                result = t.execute(action="add", model_category="reasoning", model_data={"name": "test"})
            assert "not found" in result.lower()
        finally:
            shutil.rmtree(empty_dir, ignore_errors=True)

    def test_exception_handling(self):
        t = ConfigEditorTool()
        with (
            mock.patch("antigravity_k.tools.config_editor_tool.os.getcwd", return_value="/nonexistent"),
            mock.patch("antigravity_k.tools.config_editor_tool.os.path.exists", return_value=True),
            mock.patch("builtins.open", side_effect=PermissionError("denied")),
        ):
            result = t.execute(action="add", model_category="reasoning", model_data={"name": "test"})
        assert "denied" in result.lower() or "error" in result.lower() or "fail" in result.lower()
