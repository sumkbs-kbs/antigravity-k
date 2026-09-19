"""Tests for state graph handler output boundaries."""

import time
from unittest.mock import MagicMock, patch

from antigravity_k.engine import orchestrator_handlers
from antigravity_k.engine.orchestrator_handlers import code_review_handler
from antigravity_k.engine.state_graph import AgentState, StateContext


def _review_context() -> StateContext:
    return StateContext(
        task_type="coding",
        user_message="코드를 설명해줘",
        agent_output="x" * 120,
    )


def _orchestrator(tool_names: tuple[str, ...]) -> MagicMock:
    orch = MagicMock()
    orch.project_root = "/tmp/project"
    orch.ctx.tool_executor.tool_call_history = [
        {"name": tool_name, "arguments": {}, "success": True, "timestamp": time.time()} for tool_name in tool_names
    ]
    return orch


def test_code_review_skips_workspace_diff_when_agent_only_read_files():
    # Given: the workspace is dirty but this agent turn used no mutating tool.
    ctx = _review_context()
    orch = _orchestrator(("read_file", "glob_search"))

    with patch("subprocess.run") as run:
        chunks = list(code_review_handler(ctx, orch))

    # Then: unrelated pre-existing changes stay out of the user's answer.
    assert chunks == []
    run.assert_not_called()
    orch.manager.generate.assert_not_called()


def test_code_review_reviews_diff_after_mutating_tool_use():
    # Given: this agent turn actually edited a file.
    ctx = _review_context()
    orch = _orchestrator(("read_file", "edit_file"))
    orch.manager.generate.return_value = "BUGS: None\nTYPES: None\nQUALITY: None"

    with patch("subprocess.run") as run:
        run.side_effect = [
            MagicMock(stdout="src/file.py | 5 +++--"),
            MagicMock(stdout="diff --git a/src/file.py b/src/file.py"),
        ]
        chunks = list(code_review_handler(ctx, orch))

    # Then: the review path runs for the agent-owned change.
    assert chunks == []
    assert run.call_count == 2
    orch.manager.generate.assert_called_once()


def test_code_review_ignores_mutating_tools_from_previous_turns():
    # Given: an earlier turn edited a file, but this turn only explains code.
    ctx = _review_context()
    orch = _orchestrator(("read_file",))
    orch.ctx.tool_executor.tool_call_history = [
        {"name": "edit_file", "arguments": {}, "success": True, "timestamp": 0.0},
        {"name": "read_file", "arguments": {}, "success": True, "timestamp": time.time()},
    ]

    with patch("subprocess.run") as run:
        chunks = list(code_review_handler(ctx, orch))

    # Then: stale history cannot make this answer review an unrelated diff.
    assert chunks == []
    run.assert_not_called()


def test_graph_registers_public_handler_exports() -> None:
    # Given: the public compatibility module and its production graph builder.
    graph = orchestrator_handlers.build_orchestrator_graph()
    expected_handlers = {
        AgentState.INIT: orchestrator_handlers.init_handler,
        AgentState.CONTEXT_ENRICH: orchestrator_handlers.context_enrich_handler,
        AgentState.AUTO_LEARN: orchestrator_handlers.auto_learn_handler,
        AgentState.SKILL_MATCH: orchestrator_handlers.skill_match_handler,
        AgentState.CEO_ANALYZE: orchestrator_handlers.ceo_analyze_handler,
        AgentState.PRE_ROUTE: orchestrator_handlers.pre_route_handler,
        AgentState.ROUTE: orchestrator_handlers.route_handler,
        AgentState.AGENT_EXECUTE: orchestrator_handlers.agent_execute_handler,
        AgentState.CODE_REVIEW: orchestrator_handlers.code_review_handler,
        AgentState.MAX_EXECUTE: orchestrator_handlers.max_execute_handler,
        AgentState.PIPELINE_EXECUTE: orchestrator_handlers.pipeline_execute_handler,
        AgentState.DEBATE_EXECUTE: orchestrator_handlers.debate_execute_handler,
        AgentState.AGI_CORE: orchestrator_handlers.agi_core_handler,
        AgentState.COV_VERIFY: orchestrator_handlers.cov_verify_handler,
        AgentState.QUALITY_CHECK: orchestrator_handlers.quality_check_handler,
        AgentState.MEMORY_SAVE: orchestrator_handlers.memory_save_handler,
    }

    # When/Then: every state resolves to the same object exported by the facade.
    assert graph._nodes == expected_handlers
    assert graph._conditional_edges[AgentState.ROUTE] is orchestrator_handlers.route_decision
    assert graph._conditional_edges[AgentState.QUALITY_CHECK] is orchestrator_handlers.quality_check_decision


def test_quality_check_loopback_returns_to_execution_origin() -> None:
    """품질 재시도 루프백은 원 실행 노드로 되돌아간다 (전략 강등 방지)."""
    from antigravity_k.engine.orchestrator_verification_handlers import quality_check_decision

    # Given: MAX 모드로 실행됐고 품질 검증이 실패해 루프백이 걸린 상태.
    ctx = StateContext(user_message="task", execution_origin=AgentState.MAX_EXECUTE)
    ctx._loop_back = True

    # Then: 단일 에이전트가 아니라 MAX_EXECUTE로 되돌아간다.
    assert quality_check_decision(ctx) == AgentState.MAX_EXECUTE

    # PIPELINE/DEBATE 원 노드도 각각 보존된다.
    ctx_pipeline = StateContext(user_message="task", execution_origin=AgentState.PIPELINE_EXECUTE)
    ctx_pipeline._loop_back = True
    assert quality_check_decision(ctx_pipeline) == AgentState.PIPELINE_EXECUTE

    ctx_debate = StateContext(user_message="task", execution_origin=AgentState.DEBATE_EXECUTE)
    ctx_debate._loop_back = True
    assert quality_check_decision(ctx_debate) == AgentState.DEBATE_EXECUTE

    # 루프백이 없으면 MEMORY_SAVE.
    ctx_ok = StateContext(user_message="task", execution_origin=AgentState.MAX_EXECUTE)
    ctx_ok._loop_back = False
    assert quality_check_decision(ctx_ok) == AgentState.MEMORY_SAVE


def test_ceo_gate_decision_bypasses_enrichment_for_simple_chat() -> None:
    """simple_chat은 컨텍스트 풍부화 프리룰을 건너뛰고 ROUTE로 조기 차단한다."""
    from antigravity_k.engine.orchestrator_analysis_handlers import ceo_gate_decision

    simple = StateContext(user_message="안녕하세요", task_type="simple_chat")
    assert ceo_gate_decision(simple) == AgentState.ROUTE

    work = StateContext(user_message="config.yaml 수정해줘", task_type="coding")
    assert ceo_gate_decision(work) == AgentState.CONTEXT_ENRICH
