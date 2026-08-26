"""테스트: DelegationEngine 위임 경로 보완.
====================================
기존 test_delegation_engine.py에서 미커버인 실제 위임 실행 경로
(single/parallel/pipeline/debate/subagent)와 실패 폴백을 검증한다.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from antigravity_k.engine.delegation_engine import DelegationEngine


class FakeToolLoop:
    """ToolLoopEngine 대체 — 역할별 스크립트된 청크를 yield."""

    outputs_by_role: dict[str, list[str]] = {}

    def __init__(self, orch):
        pass

    def run_loop(self, messages, delegate_to, task_type, max_steps, target_model=None):
        for chunk in FakeToolLoop.outputs_by_role.get(delegate_to, ["기본"]):
            yield chunk


@pytest.fixture
def orchestrator():
    return SimpleNamespace(
        manager=None,
        _last_agent_output="",
        max_engine=None,
        agent_runtime=None,
        config={},
    )


@pytest.fixture
def fake_loop(monkeypatch):
    def _setup(mapping_):
        FakeToolLoop.outputs_by_role = mapping_
        monkeypatch.setattr("antigravity_k.engine.tool_loop.ToolLoopEngine", FakeToolLoop)
        return mapping_

    return _setup


# ─── SINGLE ──────────────────────────────────────────────────────


class TestSinglePath:
    def test_single_yields_tool_loop_chunks(self, orchestrator, fake_loop):
        fake_loop({"WORKER": ["청크1", "청크2"]})
        engine = DelegationEngine(orchestrator)

        chunks = list(engine.delegate("single", [{"role": "user", "content": "작업"}]))

        assert "청크1" in chunks and "청크2" in chunks

    def test_single_yields_all_chunks_in_order(self, orchestrator, fake_loop):
        fake_loop({"WORKER": ["첫", "둘", "셋"]})
        engine = DelegationEngine(orchestrator)

        chunks = list(engine.delegate("single", [{"role": "user", "content": "x"}]))

        assert chunks == ["첫", "둘", "셋"]


# ─── PARALLEL ────────────────────────────────────────────────────


class TestParallelPath:
    def test_parallel_without_max_engine_falls_back_to_single(self, orchestrator, fake_loop):
        fake_loop({"WORKER": ["폴백 응답"]})
        engine = DelegationEngine(orchestrator)

        chunks = list(engine.delegate("parallel", [{"role": "user", "content": "x"}]))

        joined = "".join(chunks)
        assert "MAX Engine 미가용" in joined
        assert "폴백 응답" in joined

    def test_parallel_selector_result_yields_winner_info(self, orchestrator):
        max_engine = MagicMock()
        max_engine.run.return_value = SimpleNamespace(
            final_output="통합 결과물",
            selected_idx=0,
            results=[SimpleNamespace(model="qwen3-test")],
        )
        orchestrator.max_engine = max_engine
        engine = DelegationEngine(orchestrator)

        chunks = list(engine.delegate("parallel", [{"role": "user", "content": "x"}], task_type="coding"))

        joined = "".join(chunks)
        assert "Selector 선정" in joined
        assert "통합 결과물" in joined

    def test_parallel_all_workers_fail_reports_error(self, orchestrator):
        max_engine = MagicMock()
        max_engine.run.return_value = SimpleNamespace(final_output="", selected_idx=-1, results=[], error="모두 실패")
        orchestrator.max_engine = max_engine
        engine = DelegationEngine(orchestrator)

        joined = "".join(engine.delegate("parallel", [{"role": "user", "content": "x"}], task_type="coding"))

        assert "병렬 위임 실패" in joined and "모두 실패" in joined

    def test_parallel_max_engine_exception_propagates_to_delegate_fallback(self, orchestrator):
        max_engine = MagicMock()
        max_engine.run.side_effect = RuntimeError("병렬 붕괴")
        orchestrator.max_engine = max_engine
        engine = DelegationEngine(orchestrator)
        engine._delegate_single = MagicMock(return_value=iter(["단일 폴백"]))

        joined = "".join(engine.delegate("parallel", [{"role": "user", "content": "x"}], task_type="coding"))

        assert "위임 실패" in joined and "단일 폴백" in joined


# ─── PIPELINE ────────────────────────────────────────────────────


class TestPipelinePath:
    def test_pipeline_without_steps_falls_back_to_single(self, orchestrator, fake_loop):
        fake_loop({"WORKER": ["단일 응답"]})
        engine = DelegationEngine(orchestrator)

        chunks = list(engine._delegate_pipeline([], "WORKER", "coding", 5, None))

        assert "단일 응답" in chunks

    def test_pipeline_sequential_context_passing(self, orchestrator, fake_loop):
        fake_loop({"ARCHITECT": ["설계 결과"], "WORKER": ["구현 완료"]})
        engine = DelegationEngine(orchestrator)
        messages = [{"role": "user", "content": "시작"}]

        single_calls = []
        orig_single = engine._delegate_single

        def spy_single(msgs, role, task_type, max_steps, target_model=None):
            single_calls.append((role, [m.get("content", "") for m in msgs]))
            yield from orig_single(msgs, role, task_type, max_steps, target_model)

        engine._delegate_single = spy_single

        gen = engine._delegate_pipeline(
            messages,
            "WORKER",
            "coding",
            5,
            None,
            steps=[
                {"delegate_to": "ARCHITECT", "prompt": "설계해줘"},
                {"delegate_to": "WORKER", "prompt": "구현해줘"},
            ],
        )
        chunks = list(gen)

        joined = "".join(chunks)
        assert "파이프라인 위임" in joined and "1/2" in joined
        # Step 2 메시지에 Step 1 결과가 assistant로 누적됨
        second_call_msgs = single_calls[1][1]
        assert any("설계 결과" in m for m in second_call_msgs)


# ─── DEBATE ──────────────────────────────────────────────────────


class TestDebatePath:
    def test_debate_three_phase_flow(self, orchestrator, fake_loop):
        fake_loop(
            {
                "WORKER": ["제안: 캐시 사용"],
                "QA": ["비판: 무효화 정책 없음"],
                "ENG_MANAGER": ["최종: TTL 캐시 도입"],
            }
        )
        engine = DelegationEngine(orchestrator)
        messages = [{"role": "user", "content": "캐시 전략"}]

        chunks = list(engine.delegate("debate", messages, task_type="reasoning"))

        joined = "".join(chunks)
        assert "토론 위임" in joined
        assert "제안 단계" in joined and "비판 단계" in joined and "합성 단계" in joined
        assert "TTL 캐시 도입" in joined

    def test_debate_synth_stage_uses_eng_manager_role(self, orchestrator, monkeypatch):
        roles_used = []

        class TrackingLoop(FakeToolLoop):
            def run_loop(self, messages, delegate_to, task_type, max_steps, target_model=None):
                roles_used.append(delegate_to)
                yield from super().run_loop(messages, delegate_to, task_type, max_steps, target_model)

        FakeToolLoop.outputs_by_role = {
            "WORKER": ["제안"],
            "QA": ["비판"],
            "ENG_MANAGER": ["최종 합성"],
        }
        monkeypatch.setattr("antigravity_k.engine.tool_loop.ToolLoopEngine", TrackingLoop)
        engine = DelegationEngine(orchestrator)

        list(engine.delegate("debate", [{"role": "user", "content": "x"}], task_type="r"))

        assert roles_used == ["WORKER", "QA", "ENG_MANAGER"]


# ─── SUBAGENT ────────────────────────────────────────────────────


class TestSubagentPath:
    def test_subagent_success_yields_result(self, orchestrator, monkeypatch):
        spawner = MagicMock()
        spawner.spawn.return_value = "서브에이전트 결과"
        monkeypatch.setattr(
            "antigravity_k.engine.subagent_spawner.SubagentSpawner",
            lambda *a: spawner,
        )
        orchestrator.tool_registry = MagicMock()
        engine = DelegationEngine(orchestrator)

        chunks = list(engine._delegate_subagent([{"role": "user", "content": "t"}], "WORKER", "c", 3, None))

        assert "서브에이전트 결과" in chunks

    def test_subagent_failure_falls_back_to_single(self, orchestrator, monkeypatch):
        def broken_spawner(*a):
            raise RuntimeError("spawn 불가")

        monkeypatch.setattr(
            "antigravity_k.engine.subagent_spawner.SubagentSpawner",
            broken_spawner,
        )
        engine = DelegationEngine(orchestrator)
        engine._delegate_single = MagicMock(return_value=iter(["싱글 폴백"]))

        chunks = list(engine._delegate_subagent([{"role": "user", "content": "t"}], "W", "c", 3, None))

        assert "싱글 폴백" in chunks
