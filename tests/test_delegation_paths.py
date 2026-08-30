"""테스트: DelegationEngine 위임 경로 보완.
====================================
기존 test_delegation_engine.py에서 미커버인 실제 위임 실행 경로
(single/parallel/pipeline/debate/subagent)와 실패 폴백을 검증한다.
"""

from collections.abc import Callable, Iterator
from types import SimpleNamespace
from typing import cast, override
from unittest.mock import MagicMock

import pytest

from antigravity_k.engine.delegation_engine import DelegationEngine


class FakeToolLoop:
    """ToolLoopEngine 대체 — 역할별 스크립트된 청크를 yield."""

    outputs_by_role: dict[str, list[str]] = {}

    def __init__(self, orch: object) -> None:
        pass

    def run_loop(
        self,
        messages: list[dict[str, str]],
        delegate_to: str,
        task_type: str,
        max_steps: int,
        target_model: str | None = None,
    ) -> Iterator[str]:
        _ = (messages, task_type, max_steps, target_model)
        for chunk in FakeToolLoop.outputs_by_role.get(delegate_to, ["기본"]):
            yield chunk


@pytest.fixture
def orchestrator() -> SimpleNamespace:
    return SimpleNamespace(
        manager=None,
        _last_agent_output="",
        max_engine=None,
        agent_runtime=None,
        config={},
    )


@pytest.fixture
def fake_loop(monkeypatch: pytest.MonkeyPatch) -> Callable[[dict[str, list[str]]], None]:
    def _setup(mapping_: dict[str, list[str]]) -> None:
        FakeToolLoop.outputs_by_role = mapping_
        monkeypatch.setattr("antigravity_k.engine.tool_loop.ToolLoopEngine", FakeToolLoop)

    return _setup


def _run_delegate(
    engine: DelegationEngine,
    strategy: str,
    messages: list[dict[str, str]],
    *,
    task_type: str | None = None,
) -> list[str]:
    delegate = cast(Callable[..., Iterator[str]], DelegationEngine.delegate)
    if task_type is None:
        return list(delegate(engine, strategy, messages))
    return list(delegate(engine, strategy, messages, task_type=task_type))


def _run_private_delegate(
    engine: DelegationEngine,
    method_name: str,
    messages: list[dict[str, str]],
    delegate_to: str,
    task_type: str,
    max_steps: int,
    target_model: str | None = None,
    **kwargs: object,
) -> Iterator[str]:
    method = cast(
        Callable[..., Iterator[str]],
        getattr(engine, method_name),
    )
    return method(messages, delegate_to, task_type, max_steps, target_model, **kwargs)


# ─── SINGLE ──────────────────────────────────────────────────────


class TestSinglePath:
    def test_single_yields_tool_loop_chunks(
        self, orchestrator: SimpleNamespace, fake_loop: Callable[[dict[str, list[str]]], None]
    ) -> None:
        fake_loop({"WORKER": ["청크1", "청크2"]})
        engine = DelegationEngine(orchestrator)

        chunks = _run_delegate(engine, "single", [{"role": "user", "content": "작업"}])

        assert "청크1" in chunks and "청크2" in chunks

    def test_single_yields_all_chunks_in_order(
        self, orchestrator: SimpleNamespace, fake_loop: Callable[[dict[str, list[str]]], None]
    ) -> None:
        fake_loop({"WORKER": ["첫", "둘", "셋"]})
        engine = DelegationEngine(orchestrator)

        chunks = _run_delegate(engine, "single", [{"role": "user", "content": "x"}])

        assert chunks == ["첫", "둘", "셋"]


# ─── PARALLEL ────────────────────────────────────────────────────


class TestParallelPath:
    def test_parallel_without_max_engine_falls_back_to_single(
        self, orchestrator: SimpleNamespace, fake_loop: Callable[[dict[str, list[str]]], None]
    ) -> None:
        fake_loop({"WORKER": ["폴백 응답"]})
        engine = DelegationEngine(orchestrator)

        chunks = _run_delegate(engine, "parallel", [{"role": "user", "content": "x"}])

        joined = "".join(chunks)
        assert "MAX Engine 미가용" in joined
        assert "폴백 응답" in joined

    def test_parallel_selector_result_yields_winner_info(self, orchestrator: SimpleNamespace) -> None:
        max_engine = MagicMock()
        setattr(
            max_engine,
            "run",
            MagicMock(
                return_value=SimpleNamespace(
                    final_output="통합 결과물",
                    selected_idx=0,
                    results=[SimpleNamespace(model="qwen3-test")],
                )
            ),
        )
        orchestrator.max_engine = max_engine
        engine = DelegationEngine(orchestrator)

        chunks = _run_delegate(engine, "parallel", [{"role": "user", "content": "x"}], task_type="coding")

        joined = "".join(chunks)
        assert "Selector 선정" in joined
        assert "통합 결과물" in joined

    def test_parallel_all_workers_fail_reports_error(self, orchestrator: SimpleNamespace) -> None:
        max_engine = MagicMock()
        setattr(
            max_engine,
            "run",
            MagicMock(return_value=SimpleNamespace(final_output="", selected_idx=-1, results=[], error="모두 실패")),
        )
        orchestrator.max_engine = max_engine
        engine = DelegationEngine(orchestrator)

        joined = "".join(_run_delegate(engine, "parallel", [{"role": "user", "content": "x"}], task_type="coding"))

        assert "병렬 위임 실패" in joined and "모두 실패" in joined

    def test_parallel_max_engine_exception_propagates_to_delegate_fallback(self, orchestrator: SimpleNamespace) -> None:
        max_engine = MagicMock()
        setattr(max_engine, "run", MagicMock(side_effect=RuntimeError("병렬 붕괴")))
        orchestrator.max_engine = max_engine
        engine = DelegationEngine(orchestrator)
        setattr(engine, "_delegate_single", MagicMock(return_value=iter(["단일 폴백"])))

        joined = "".join(_run_delegate(engine, "parallel", [{"role": "user", "content": "x"}], task_type="coding"))

        assert "위임 실패" in joined and "단일 폴백" in joined


# ─── PIPELINE ────────────────────────────────────────────────────


class TestPipelinePath:
    def test_pipeline_without_steps_falls_back_to_single(
        self, orchestrator: SimpleNamespace, fake_loop: Callable[[dict[str, list[str]]], None]
    ) -> None:
        fake_loop({"WORKER": ["단일 응답"]})
        engine = DelegationEngine(orchestrator)

        chunks = list(_run_private_delegate(engine, "_delegate_pipeline", [], "WORKER", "coding", 5, None))

        assert "단일 응답" in chunks

    def test_pipeline_sequential_context_passing(
        self, orchestrator: SimpleNamespace, fake_loop: Callable[[dict[str, list[str]]], None]
    ) -> None:
        fake_loop({"ARCHITECT": ["설계 결과"], "WORKER": ["구현 완료"]})
        engine = DelegationEngine(orchestrator)
        messages = [{"role": "user", "content": "시작"}]

        single_calls: list[tuple[str, list[str]]] = []
        orig_single = cast(
            Callable[[list[dict[str, str]], str, str, int, str | None], Iterator[str]],
            getattr(engine, "_delegate_single"),
        )

        def spy_single(
            msgs: list[dict[str, str]],
            role: str,
            task_type: str,
            max_steps: int,
            target_model: str | None = None,
        ) -> Iterator[str]:
            single_calls.append((role, [m.get("content", "") for m in msgs]))
            yield from orig_single(msgs, role, task_type, max_steps, target_model)

        setattr(engine, "_delegate_single", spy_single)

        gen = _run_private_delegate(
            engine,
            "_delegate_pipeline",
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
    def test_debate_three_phase_flow(
        self, orchestrator: SimpleNamespace, fake_loop: Callable[[dict[str, list[str]]], None]
    ) -> None:
        fake_loop(
            {
                "WORKER": ["제안: 캐시 사용"],
                "QA": ["비판: 무효화 정책 없음"],
                "ENG_MANAGER": ["최종: TTL 캐시 도입"],
            }
        )
        engine = DelegationEngine(orchestrator)
        messages = [{"role": "user", "content": "캐시 전략"}]

        chunks = _run_delegate(engine, "debate", messages, task_type="reasoning")

        joined = "".join(chunks)
        assert "토론 위임" in joined
        assert "제안 단계" in joined and "비판 단계" in joined and "합성 단계" in joined
        assert "TTL 캐시 도입" in joined

    def test_debate_synth_stage_uses_eng_manager_role(
        self, orchestrator: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        roles_used: list[str] = []

        class TrackingLoop(FakeToolLoop):
            @override
            def run_loop(
                self,
                messages: list[dict[str, str]],
                delegate_to: str,
                task_type: str,
                max_steps: int,
                target_model: str | None = None,
            ) -> Iterator[str]:
                _ = (messages, task_type, max_steps, target_model)
                roles_used.append(delegate_to)
                yield from super().run_loop(messages, delegate_to, task_type, max_steps, target_model)

        FakeToolLoop.outputs_by_role = {
            "WORKER": ["제안"],
            "QA": ["비판"],
            "ENG_MANAGER": ["최종 합성"],
        }
        monkeypatch.setattr("antigravity_k.engine.tool_loop.ToolLoopEngine", TrackingLoop)
        engine = DelegationEngine(orchestrator)

        _ = _run_delegate(engine, "debate", [{"role": "user", "content": "x"}], task_type="r")

        assert roles_used == ["WORKER", "QA", "ENG_MANAGER"]


# ─── SUBAGENT ────────────────────────────────────────────────────


class TestSubagentPath:
    def test_subagent_success_yields_result(
        self, orchestrator: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        spawner = MagicMock()
        setattr(spawner, "spawn", MagicMock(return_value="서브에이전트 결과"))

        def make_spawner(*args: object) -> MagicMock:
            _ = args
            return spawner

        monkeypatch.setattr(
            "antigravity_k.engine.subagent_spawner.SubagentSpawner",
            make_spawner,
        )
        orchestrator.tool_registry = MagicMock()
        engine = DelegationEngine(orchestrator)

        chunks = list(
            _run_private_delegate(
                engine, "_delegate_subagent", [{"role": "user", "content": "t"}], "WORKER", "c", 3, None
            )
        )

        assert "서브에이전트 결과" in chunks

    def test_subagent_failure_falls_back_to_single(
        self, orchestrator: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def broken_spawner(*args: object) -> None:
            _ = args
            raise RuntimeError("spawn 불가")

        monkeypatch.setattr(
            "antigravity_k.engine.subagent_spawner.SubagentSpawner",
            broken_spawner,
        )
        engine = DelegationEngine(orchestrator)
        setattr(engine, "_delegate_single", MagicMock(return_value=iter(["싱글 폴백"])))

        chunks = list(
            _run_private_delegate(engine, "_delegate_subagent", [{"role": "user", "content": "t"}], "W", "c", 3, None)
        )

        assert "싱글 폴백" in chunks
