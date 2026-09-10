"""FR-08 regression: the selected project folder must drive request reads.

Covers the deterministic provider-double tier of plan RP-08 (the browser and
live-provider tiers belong to RP-08 manual QA / RP-12):

- session project binding resolves the request canonical root (A vs B)
- a ``read_file`` executed through the permission boundary reads the bound
  project's ``context_probe.txt`` and never the sibling's
- the tool result reaches the next provider call's serialized prompt: the
  A-bound request payload contains marker A and excludes marker B, and the
  converse after switching to B
- an in-flight A request keeps its root snapshot when the session binding
  flips to B mid-flight (context token semantics)
- unbound/unregistered roots fail closed instead of falling back to cwd
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from antigravity_k.api.project_binding import (
    bind_session_active_project,
    get_session_project_bindings,
    resolve_project_execution_context,
)
from antigravity_k.engine.project_registry import ProjectRegistry
from antigravity_k.tools.system_tools import ReadFileTool
from antigravity_k.tools.tool_registry import ToolRegistry

MARKER_A = "PROBE_MARKER_ALPHA_7f3a"
MARKER_B = "PROBE_MARKER_BRAVO_91cd"


@pytest.fixture()
def workspace(tmp_path: Path) -> dict[str, Path]:
    root_a = tmp_path / "projA"
    root_b = tmp_path / "projB"
    root_a.mkdir()
    root_b.mkdir()
    (root_a / "context_probe.txt").write_text(f"secret value = {MARKER_A}\n", encoding="utf-8")
    (root_b / "context_probe.txt").write_text(f"secret value = {MARKER_B}\n", encoding="utf-8")
    return {"a": root_a, "b": root_b}


@pytest.fixture()
def registry(workspace: dict[str, Path], tmp_path: Path) -> tuple[ProjectRegistry, str, str]:
    reg = ProjectRegistry(storage_path=tmp_path / "registry.json")
    proj_a = reg.add_project("projA", str(workspace["a"]))
    proj_b = reg.add_project("projB", str(workspace["b"]))
    return reg, proj_a.id, proj_b.id


@pytest.fixture(autouse=True)
def _allow_test_workspace_roots(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # ARC-01: canonical roots must stay under configured trusted bases; the
    # test workspace is allow-listed explicitly instead of weakening the check.
    monkeypatch.setenv("AGK_ALLOWED_ROOTS", str(tmp_path))


@pytest.fixture(autouse=True)
def _clean_session_bindings():
    get_session_project_bindings().reset_all()
    yield
    get_session_project_bindings().reset_all()


def _tool_registry(fallback_root: str) -> ToolRegistry:
    tr = ToolRegistry(project_root=fallback_root)
    _ = tr.install(ReadFileTool())
    return tr


class TestSessionBoundToolReads:
    def test_bound_project_a_reads_marker_a(self, workspace: dict[str, Path], registry: tuple) -> None:
        reg, proj_a, proj_b = registry
        ctx = resolve_project_execution_context(project_id=proj_a, registry=reg, bind=True)
        assert ctx.canonical_project_root == str(workspace["a"])

        tr = _tool_registry(str(workspace["a"]))
        permission, result = tr.execute_with_permission(
            "read_file", {"file_path": "context_probe.txt"}, objective="read the probe"
        )
        assert permission.name == "ALLOW"
        assert MARKER_A in result
        assert MARKER_B not in result

    def test_switch_to_b_reads_marker_b_and_excludes_a(self, workspace: dict[str, Path], registry: tuple) -> None:
        reg, proj_a, proj_b = registry
        _ = resolve_project_execution_context(project_id=proj_a, registry=reg, bind=True)
        _ = resolve_project_execution_context(project_id=proj_b, registry=reg, bind=True)

        tr = _tool_registry(str(workspace["a"]))
        permission, result = tr.execute_with_permission(
            "read_file", {"file_path": "context_probe.txt"}, objective="read the probe"
        )
        assert permission.name == "ALLOW"
        assert MARKER_B in result
        assert MARKER_A not in result

    def test_session_binding_drives_unqualified_request(self, workspace: dict[str, Path], registry: tuple) -> None:
        reg, proj_a, proj_b = registry
        # Browser "save selection" -> session binding; request body has no project_id.
        _ = bind_session_active_project("sess-fr08", proj_a)
        ctx = resolve_project_execution_context(payload={"session_id": "sess-fr08"}, registry=reg, bind=True)
        assert ctx.canonical_project_root == str(workspace["a"])

    def test_inflight_request_keeps_root_snapshot_when_session_flips(
        self, workspace: dict[str, Path], registry: tuple
    ) -> None:
        reg, proj_a, proj_b = registry
        import contextvars

        # A request lifecycle runs inside its own context (equivalent to a
        # per-request asyncio task): its ContextVar writes stay isolated from
        # later session flips in the ambient context.
        request_a = contextvars.copy_context()

        def start_request_a() -> str:
            _ = resolve_project_execution_context(project_id=proj_a, registry=reg, bind=True)
            tr = _tool_registry(str(workspace["a"]))
            _permission, result = tr.execute_with_permission(
                "read_file", {"file_path": "context_probe.txt"}, objective="request A start"
            )
            return str(result)

        first = request_a.run(start_request_a)
        assert MARKER_A in first

        # Meanwhile the UI switches the session to project B (ambient context).
        _ = bind_session_active_project("other-session", proj_b)
        _ = resolve_project_execution_context(payload={"session_id": "other-session"}, registry=reg, bind=True)

        # The in-flight A request continues — same request context — and must
        # still read A's snapshot, not the freshly bound B.
        def continue_request_a() -> str:
            tr = _tool_registry(str(workspace["a"]))
            _permission, result = tr.execute_with_permission(
                "read_file", {"file_path": "context_probe.txt"}, objective="request A continuation"
            )
            return str(result)

        continued = request_a.run(continue_request_a)
        assert MARKER_A in continued
        assert MARKER_B not in continued

    def test_unregistered_project_fails_closed(self, workspace: dict[str, Path], registry: tuple) -> None:
        reg, _proj_a, _proj_b = registry
        from antigravity_k.api.contracts.errors import ProjectNotFoundError

        with pytest.raises(ProjectNotFoundError):
            _ = resolve_project_execution_context(project_id="does-not-exist", registry=reg, bind=True)

    def test_missing_binding_fails_closed(self, workspace: dict[str, Path], registry: tuple) -> None:
        reg, _proj_a, _proj_b = registry
        from antigravity_k.api.contracts.errors import MissingExecutionContextError

        with pytest.raises(MissingExecutionContextError):
            _ = resolve_project_execution_context(payload={"session_id": "never-bound"}, registry=reg, bind=True)


class TestProviderPayloadCarriesBoundMarker:
    """Deterministic provider double: capture the prompt of the 2nd round.

    Round 1 returns a read_file tool call in the real wire format; the loop
    executes it through the real permission boundary against the bound root;
    round 2's serialized prompt must contain the bound project's marker only.
    """

    @staticmethod
    def _orchestrator(tool_executor_execute) -> MagicMock:
        orch = MagicMock()
        orch.config = {}
        orch.project_root = "/tmp/test"
        orch._skill_prompts_cache = ""
        orch._last_agent_output = ""
        orch.manager = MagicMock()
        orch.manager.is_loaded = True
        orch.manager._registry = MagicMock()
        orch.manager.router = MagicMock()
        orch._prepare_agent_prompt = MagicMock(
            return_value=(
                "delegate_model",
                "system_prompt_part",
                "tool_prompt_part",
                "skill_prompts_part",
                "prompt_str",
                [{"role": "user", "content": "read the probe"}],
            )
        )
        ctx = MagicMock()
        guard_allow = MagicMock()
        guard_allow.allows_execution = True
        ctx.tool_guardrail = MagicMock()
        ctx.tool_guardrail.before_call = MagicMock(return_value=guard_allow)
        guard_after = MagicMock()
        guard_after.action = "allow"
        ctx.tool_guardrail.after_call = MagicMock(return_value=guard_after)
        ctx.tool_guardrail.reset = MagicMock()
        ctx.cognitive_loop = MagicMock()
        ctx.quality_gate = MagicMock()
        quality_result = MagicMock()
        quality_result.user_message = ""
        quality_result.should_retry = False
        ctx.quality_gate.evaluate = MagicMock(return_value=quality_result)
        ctx.decision_anchor = MagicMock()
        ctx.decision_anchor.auto_extract = MagicMock(return_value=None)
        ctx.tool_executor = MagicMock()
        ctx.tool_executor.execute_async = tool_executor_execute
        orch.ctx = ctx
        return orch

    def _run(self, orch: MagicMock, tool_xml: str, captured: list[dict[str, Any]]) -> list[str]:
        from antigravity_k.engine.tool_loop import ToolLoopEngine

        def fake_stream_generate(**kwargs: Any) -> Iterator[str]:
            captured.append(dict(kwargs))
            if len(captured) == 1:
                return iter([tool_xml])
            return iter([f"final answer with the probe value of round {len(captured)}"])

        orch.manager.stream_generate = MagicMock(side_effect=fake_stream_generate)
        engine = ToolLoopEngine(cast(Any, orch))
        return list(
            engine.run_loop([{"role": "user", "content": "context_probe.txt의 값을 읽어 답해"}], "CODER", "chat")
        )

    def test_round2_prompt_contains_bound_marker_only(self, workspace: dict[str, Path], registry: tuple) -> None:
        reg, proj_a, _proj_b = registry
        _ = resolve_project_execution_context(project_id=proj_a, registry=reg, bind=True)

        tr = _tool_registry(str(workspace["a"]))

        async def real_execute(name: str, args: dict[str, object], *a: object, **k: object) -> str:
            _permission, result = tr.execute_with_permission(name, dict(args), objective="probe read")
            return str(result)

        tool_xml = (
            "<action_call>\n<tool_call>\n"
            '{"name": "read_file", "arguments": {"file_path": "context_probe.txt"}}\n'
            "</tool_call>\n</action_call>\n"
        )
        captured: list[dict[str, Any]] = []
        orch = self._orchestrator(AsyncMock(side_effect=real_execute))
        _outputs = self._run(orch, tool_xml, captured)

        assert len(captured) >= 2, f"loop must call the provider at least twice, got {len(captured)}"
        second_prompt = json.dumps(captured[1], ensure_ascii=False, default=str)
        assert MARKER_A in second_prompt, "bound project marker must reach the provider payload"
        assert MARKER_B not in second_prompt, "sibling project marker must never leak into the payload"

    def test_round2_prompt_after_switch_contains_marker_b_only(
        self, workspace: dict[str, Path], registry: tuple
    ) -> None:
        reg, _proj_a, proj_b = registry
        _ = resolve_project_execution_context(project_id=proj_b, registry=reg, bind=True)

        tr = _tool_registry(str(workspace["b"]))

        async def real_execute(name: str, args: dict[str, object], *a: object, **k: object) -> str:
            _permission, result = tr.execute_with_permission(name, dict(args), objective="probe read")
            return str(result)

        tool_xml = (
            "<action_call>\n<tool_call>\n"
            '{"name": "read_file", "arguments": {"file_path": "context_probe.txt"}}\n'
            "</tool_call>\n</action_call>\n"
        )
        captured: list[dict[str, Any]] = []
        orch = self._orchestrator(AsyncMock(side_effect=real_execute))
        _outputs = self._run(orch, tool_xml, captured)

        assert len(captured) >= 2
        second_prompt = json.dumps(captured[1], ensure_ascii=False, default=str)
        assert MARKER_B in second_prompt
        assert MARKER_A not in second_prompt
