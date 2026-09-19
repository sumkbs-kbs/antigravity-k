import json
from unittest.mock import MagicMock, patch

from antigravity_k.engine.context_artifact_store import ContextArtifactStore
from antigravity_k.engine.tool_executor import ToolExecutor
from antigravity_k.engine.tool_guardrails import IDEMPOTENT_TOOL_NAMES
from antigravity_k.engine.tool_masker import CODE_EDIT_TOOLS, PLAN_TOOLS, VERIFICATION_TOOLS
from antigravity_k.tools.context_artifact_tools import ReadContextArtifactTool
from antigravity_k.tools.permission_gate import PermissionGate


def test_default_tool_registration_exposes_context_artifact_reader(tmp_path):
    registry = MagicMock()
    with patch("antigravity_k.engine.tool_executor.ImmuneSystem"):
        executor = ToolExecutor(
            tool_registry=registry,
            permission_gate=MagicMock(spec=PermissionGate),
            project_root=str(tmp_path),
        )

    executor.register_default_tools()

    installed = registry.install_many.call_args.args
    assert any(tool.name == "read_context_artifact" for tool in installed)


def test_context_artifact_reader_remains_available_in_all_context_phases():
    assert "read_context_artifact" in PLAN_TOOLS
    assert "read_context_artifact" in CODE_EDIT_TOOLS
    assert "read_context_artifact" in VERIFICATION_TOOLS
    assert "read_context_artifact" in IDEMPOTENT_TOOL_NAMES


def test_context_artifact_reader_returns_only_requested_chunk(tmp_path):
    store = ContextArtifactStore(tmp_path / ".antigravity" / "context_artifacts")
    artifact = store.store("alpha\nbeta\ngamma", chunk_chars=7)
    tool = ReadContextArtifactTool(tmp_path)

    response = json.loads(tool.execute(ref_id=artifact.ref_id, chunk_index=1))

    assert response["ref_id"] == artifact.ref_id
    assert response["chunk_index"] == 1
    assert response["chunk_count"] == artifact.chunk_count
    assert response["content"] == store.read(artifact.ref_id, chunk_index=1)
