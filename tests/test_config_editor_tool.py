"""Tests for ConfigEditorTool — config.yaml model roster management."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Iterator
from typing import Callable, TypedDict, cast
from unittest import mock

import pytest

from antigravity_k.tools.config_editor_tool import ConfigEditorTool


class _ModelEntry(TypedDict):
    name: str
    provider: str


class _ConfigData(TypedDict):
    models: dict[str, list[_ModelEntry]]


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
def config_dir() -> Iterator[str]:
    """Create a temp dir with config.yaml inside."""
    tmpdir = tempfile.mkdtemp()
    config_path = os.path.join(tmpdir, "config.yaml")
    with open(config_path, "w", encoding="utf-8") as f:
        _ = f.write(SAMPLE_YAML)
    try:
        yield tmpdir
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def tool(config_dir: str) -> Iterator[ConfigEditorTool]:
    """ConfigEditorTool with cwd pointed to temp dir."""
    t = ConfigEditorTool()
    with mock.patch("antigravity_k.tools.config_editor_tool.os.getcwd", return_value=config_dir):
        yield t


def _execute(tool: ConfigEditorTool, **kwargs: object) -> str:
    method = cast(Callable[..., str], getattr(tool, "execute"))
    return method(**kwargs)


def _parameters_schema(tool: ConfigEditorTool) -> dict[str, object]:
    return cast(dict[str, object], getattr(tool, "parameters_schema"))


class TestConfigEditorToolInit:
    def test_name(self, tool: ConfigEditorTool):
        assert tool.name == "config_model_roster"

    def test_description(self, tool: ConfigEditorTool):
        assert "config.yaml" in tool.description

    def test_parameters_schema(self, tool: ConfigEditorTool):
        schema = _parameters_schema(tool)
        assert schema["type"] == "object"
        required = cast(list[str], schema["required"])
        assert "action" in required

    def test_category(self):
        assert ConfigEditorTool.category.name == "SYSTEM"

    def test_risk_level(self):
        assert ConfigEditorTool.risk_level.name == "HIGH"


class TestConfigEditorToolExecute:
    def test_add_new_model(self, config_dir: str, tool: ConfigEditorTool):
        _ = _execute(
            tool,
            action="add",
            model_category="reasoning",
            model_data={"name": "gpt-5", "provider": "openai"},
        )
        with open(os.path.join(config_dir, "config.yaml"), encoding="utf-8") as f:
            content = f.read()
        assert "gpt-5" in content
        assert "gpt-4" in content  # original still there

    def test_add_duplicate_model(self, tool: ConfigEditorTool):
        result = _execute(
            tool,
            action="add",
            model_category="reasoning",
            model_data={"name": "gpt-4", "provider": "openai"},
        )
        assert "already exists" in result.lower()

    def test_remove_existing_model(self, config_dir: str, tool: ConfigEditorTool):
        result = _execute(
            tool,
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

        parsed = cast(_ConfigData, yaml.safe_load(content))
        assert len(parsed["models"]["reasoning"]) == 0
        assert parsed["models"]["coding"][0]["name"] == "claude-3"

    def test_remove_nonexistent_model(self, tool: ConfigEditorTool):
        result = _execute(
            tool,
            action="remove",
            model_category="reasoning",
            model_data={"name": "nonexistent-model"},
        )
        assert "not found" in result.lower()

    def test_update_agent_map(self, config_dir: str, tool: ConfigEditorTool):
        result = _execute(
            tool,
            action="update_agent_map",
            target_key="WORKER",
            model_data={"combo_name": "slow-combo"},
        )
        assert "mapped" in result.lower() or "updated" in result.lower()
        with open(os.path.join(config_dir, "config.yaml"), encoding="utf-8") as f:
            content = f.read()
        assert "slow-combo" in content

    def test_update_agent_map_new_key(self, tool: ConfigEditorTool):
        result = _execute(
            tool,
            action="update_agent_map",
            target_key="NEW_AGENT",
            model_data={"combo_name": "new-combo"},
        )
        assert "mapped" in result.lower() or "updated" in result.lower()

    def test_update_swarm(self, config_dir: str, tool: ConfigEditorTool):
        result = _execute(
            tool,
            action="update_swarm",
            target_key="fast-combo",
            model_data={"models": ["gpt-4", "claude-3"], "strategy": "weighted"},
        )
        assert "updated" in result.lower()
        with open(os.path.join(config_dir, "config.yaml"), encoding="utf-8") as f:
            content = f.read()
        assert "weighted" in content

    def test_update_swarm_new_combo(self, tool: ConfigEditorTool):
        result = _execute(
            tool,
            action="update_swarm",
            target_key="new-combo",
            model_data={"models": ["gpt-5"], "strategy": "priority"},
        )
        assert "updated" in result.lower()

    def test_file_not_found(self):
        """Config file doesn't exist in a different temp dir."""
        empty_dir = tempfile.mkdtemp()
        try:
            t = ConfigEditorTool()
            with (
                mock.patch("antigravity_k.tools.config_editor_tool.os.getcwd", return_value=empty_dir),
                mock.patch("antigravity_k.tools.config_editor_tool.os.path.exists", return_value=False),
            ):
                result = _execute(t, action="add", model_category="reasoning", model_data={"name": "test"})
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
            result = _execute(t, action="add", model_category="reasoning", model_data={"name": "test"})
        assert "denied" in result.lower() or "error" in result.lower() or "fail" in result.lower()
