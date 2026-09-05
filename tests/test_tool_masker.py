"""Tests for ActiveToolMasker module."""

from antigravity_k.engine.execution_mode import ExecutionMode
from antigravity_k.engine.tool_masker import ActiveToolMasker


class DummyTool:
    def __init__(self, name: str):
        self.name = name


def test_tool_masker_plan_mode():
    masker = ActiveToolMasker(mode=ExecutionMode.PLAN)
    tools = [
        DummyTool("read_file"),
        DummyTool("write_file"),
        DummyTool("grep_search"),
        DummyTool("run_command"),
        DummyTool("git_status"),
    ]
    filtered = masker.filter_tools(tools)
    names = [t.name for t in filtered]
    assert "read_file" in names
    assert "grep_search" in names
    assert "git_status" in names
    assert "write_file" not in names
    assert "run_command" not in names


def test_tool_masker_edit_phase():
    masker = ActiveToolMasker(mode=ExecutionMode.BUILD)
    tools = [
        DummyTool("read_file"),
        DummyTool("write_file"),
        DummyTool("replace_file_content"),
        DummyTool("web_search"),
    ]
    filtered = masker.filter_tools(tools, phase="edit")
    names = [t.name for t in filtered]
    assert "write_file" in names
    assert "replace_file_content" in names
    assert "web_search" not in names


def test_tool_masker_dict_schema():
    masker = ActiveToolMasker(mode=ExecutionMode.PLAN)
    schemas = [
        {"name": "read_file", "description": "Reads file"},
        {"name": "write_file", "description": "Writes file"},
    ]
    filtered = masker.filter_tools(schemas)
    assert len(filtered) == 1
    assert filtered[0]["name"] == "read_file"


def test_tool_masker_maps_runtime_task_types_to_phases():
    masker = ActiveToolMasker(mode=ExecutionMode.BUILD)

    assert masker.phase_for_task_type("coding") == "edit"
    assert masker.phase_for_task_type("CODE") == "edit"
    assert masker.phase_for_task_type("verification") == "test"
    assert masker.phase_for_task_type("simple_chat") is None
