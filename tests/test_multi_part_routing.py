from typing import Any

from antigravity_k.engine.orchestrator_handlers import route_decision
from antigravity_k.engine.state_graph import AgentState, StateContext


def _ctx(user_message: str, task_type: str = "simple_chat", analysis: dict[str, Any] | None = None) -> StateContext:
    ctx = StateContext()
    ctx.user_message = user_message
    ctx.task_type = task_type
    ctx.analysis = analysis or {}
    return ctx


class TestMultiPartRouting:
    def test_numbered_multi_part_prompt_routes_to_pipeline(self):
        ctx = _ctx(
            "다음을 해줘.\n1. README 읽기\n2. config 확인\n3. 테스트 실행",
            task_type="simple_chat",
        )

        decision = route_decision(ctx)

        assert decision == AgentState.PIPELINE_EXECUTE

    def test_bullet_multi_part_prompt_routes_to_pipeline(self):
        ctx = _ctx(
            "작업:\n- 파일 정리\n- 린트 실행\n- 커밋",
            task_type="coding",
        )

        decision = route_decision(ctx)

        assert decision == AgentState.PIPELINE_EXECUTE

    def test_single_part_prompt_stays_on_agent_path(self):
        ctx = _ctx("피보나치 함수를 작성해줘.", task_type="coding")

        decision = route_decision(ctx)

        assert decision == AgentState.AGENT_EXECUTE

    def test_pipeline_strips_step_prefix_for_task_description(self):
        ctx = _ctx(
            "1. 첫 번째\n2. 두 번째\n3. 세 번째",
            task_type="simple_chat",
        )
        route_decision(ctx)

        pipeline = ctx.analysis.get("pipeline", [])
        assert len(pipeline) == 3
        assert all("첫 번째" not in s.get("task", "") or "번째" in s.get("task", "") for s in pipeline)
        descriptions = [s["task"] for s in pipeline]
        assert descriptions == ["첫 번째", "두 번째", "세 번째"]
