"""테스트: AgentFabric 오케스트레이션 (crew/debate/상태).
============================================
순차 파이프라인의 컨텍스트 누적·실패 중단, 토론 라운드 구조,
임시 에이전트 정리 계약을 검증한다.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Callable, Protocol, cast

import pytest

from antigravity_k.agents.base_agent import BaseAgent
from antigravity_k.engine.agent_fabric import AgentFabric
from antigravity_k.engine.model_manager import ModelManager


class CrewOrchestrator(Protocol):
    def _run_single_agent(
        self,
        messages: list[dict[str, str]],
        role: str,
        task_type: str,
        max_steps: int,
    ) -> Iterator[str]: ...


class DebateOrchestrator(Protocol):
    def _generate_for_role(
        self,
        role: str,
        prompt: str,
        messages: list[dict[str, str]],
    ) -> Iterator[str]: ...


def _execute_crew(
    fabric: AgentFabric,
    steps: list[dict[str, str]],
    messages: list[dict[str, str]],
    orchestrator: CrewOrchestrator | None = None,
) -> Iterator[str]:
    method = cast(Callable[..., Iterator[str]], getattr(fabric, "execute_crew"))
    return method(steps, messages, orchestrator=orchestrator)


def _execute_debate(
    fabric: AgentFabric,
    topic: str,
    messages: list[dict[str, str]],
    *,
    orchestrator: DebateOrchestrator | None = None,
    rounds: int = 2,
    num_critics: int = 2,
) -> Iterator[str]:
    method = cast(Callable[..., Iterator[str]], getattr(fabric, "execute_debate"))
    return method(topic, messages, orchestrator=orchestrator, rounds=rounds, num_critics=num_critics)


class FakeAgent:
    """스크립트된 응답을 반환하고 받은 프롬프트를 기록하는 가짜 에이전트."""

    def __init__(self, name: str = "FAKE", outputs: Iterable[str] = ("응답",)) -> None:
        self.name: str = name
        self.outputs: list[str] = list(outputs)
        self.prompts: list[str] = []
        self.inbox: list[tuple[str, str]] = []  # MessageBus 구독 시 호출되는 계약

    def add_message(self, role: str, content: str) -> None:
        self.inbox.append((role, content))

    def run(self, prompt: str, model_manager: ModelManager | None = None) -> str:
        _ = model_manager
        self.prompts.append(prompt)
        return self.outputs.pop(0) if self.outputs else "기본 응답"


@pytest.fixture
def fabric() -> AgentFabric:
    return AgentFabric()


# ─── execute_crew ────────────────────────────────────────────────


class TestExecuteCrew:
    def test_sequential_context_accumulates_across_steps(self, fabric: AgentFabric) -> None:
        agents: dict[str, FakeAgent] = {
            "ARCHITECT": FakeAgent("ARCHITECT", ["설계 완료"]),
            "WORKER": FakeAgent("WORKER", ["구현 완료"]),
        }

        def get_agent(role: str) -> FakeAgent:
            return agents[role]

        setattr(fabric, "get_or_create", get_agent)
        steps: list[dict[str, str]] = [
            {"agent": "ARCHITECT", "task": "설계해줘"},
            {"agent": "WORKER", "task": "구현해줘"},
        ]

        chunks = list(_execute_crew(fabric, steps, [{"role": "user", "content": "과제"}]))

        joined = "".join(chunks)
        assert "Step 1/2" in joined and "Step 2/2" in joined
        assert "설계 완료" in joined and "구현 완료" in joined
        # 2단계 프롬프트에 1단계 결과가 주입된다 (CrewAI 전달 패턴)
        worker_prompt: str = agents["WORKER"].prompts[0]
        assert "이전 단계 결과" in worker_prompt
        assert "설계 완료" in worker_prompt
        assert "Crew Pipeline 완료" in joined

    def test_step_failure_breaks_pipeline(self, fabric: AgentFabric) -> None:
        boom = FakeAgent("WORKER")

        def fail_run(prompt: str, model_manager: ModelManager | None = None) -> str:
            _ = prompt, model_manager
            raise RuntimeError("붐")

        setattr(boom, "run", fail_run)
        after = FakeAgent("QA", ["도달 불가"])

        def get_agent(role: str) -> FakeAgent:
            return {"WORKER": boom, "QA": after}[role]

        setattr(fabric, "get_or_create", get_agent)

        chunks = list(
            _execute_crew(
                fabric,
                [
                    {"agent": "WORKER", "task": "폭발 단계"},
                    {"agent": "QA", "task": "미도달 단계"},
                ],
                [{"role": "user", "content": "x"}],
            )
        )

        joined = "".join(chunks)
        assert "실행 실패" in joined and "붐" in joined
        assert "미도달 단계" not in joined  # break로 이후 단계 스킵

    def test_orchestrator_loop_takes_priority(self, fabric: AgentFabric) -> None:
        sentinels = iter(["orch-chunk-1", "orch-chunk-2"])

        class Orch:
            def _run_single_agent(
                self,
                messages: list[dict[str, str]],
                role: str,
                task_type: str,
                max_steps: int,
            ) -> Iterator[str]:
                _ = messages, role, task_type, max_steps
                yield next(sentinels)

        steps: list[dict[str, str]] = [
            {"agent": "WORKER", "task": "t1"},
            {"agent": "QA", "task": "t2"},
        ]
        joined = "".join(_execute_crew(fabric, steps, [{"role": "user", "content": "과제"}], orchestrator=Orch()))

        assert "orch-chunk-1" in joined and "orch-chunk-2" in joined


# ─── execute_debate ──────────────────────────────────────────────


class TestExecuteDebate:
    def test_debate_rounds_are_bounded(self, fabric: AgentFabric) -> None:
        def create_temp(role: str, suffix: str = "") -> FakeAgent:
            _ = suffix
            return FakeAgent(role)

        setattr(fabric, "create_temp_agent", create_temp)

        joined = "".join(
            _execute_debate(
                fabric,
                "상한 점검",
                [],
                rounds=100,
                num_critics=0,
            )
        )

        assert "📌 라운드: 10" in joined
        assert joined.count("## 🔄 Round") == 10

    @pytest.mark.parametrize("requested_rounds", [0, -3])
    def test_non_positive_rounds_run_one_round(self, fabric: AgentFabric, requested_rounds: int) -> None:
        def create_temp(role: str, suffix: str = "") -> FakeAgent:
            _ = suffix
            return FakeAgent(role)

        setattr(fabric, "create_temp_agent", create_temp)

        joined = "".join(
            _execute_debate(
                fabric,
                "최소 라운드 점검",
                [],
                rounds=requested_rounds,
                num_critics=0,
            )
        )

        assert "📌 라운드: 1" in joined
        assert joined.count("## 🔄 Round") == 1

    def test_debate_round_structure_and_feedback_loop(self, fabric: AgentFabric) -> None:
        def make_agent(kind: str) -> FakeAgent:
            agent = FakeAgent(kind)

            def run(prompt: str, model_manager: ModelManager | None = None) -> str:
                _ = model_manager
                agent.prompts.append(prompt)
                if kind == "PROPOSER":
                    return f"제안 v{len(agent.prompts)}"
                if kind.startswith("CRITIC"):
                    return f"비판 {prompt[-20:]}"
                return "최종 합의안"

            setattr(agent, "run", run)
            return agent

        def create_temp(role: str, suffix: str = "") -> FakeAgent:
            _ = suffix
            return make_agent(role)

        setattr(fabric, "create_temp_agent", create_temp)

        chunks = list(
            _execute_debate(
                fabric,
                "캐시 전략",
                [{"role": "user", "content": "질문"}],
                rounds=2,
                num_critics=2,
            )
        )

        joined = "".join(chunks)
        assert "Round 1" in joined and "Round 2" in joined
        assert joined.count("### 🔍 CRITIC") == 4  # 2 critics × 2 rounds
        assert "ARBITER" in joined and "Debate 완료" in joined

    def test_second_round_prompt_includes_previous_proposal(self, fabric: AgentFabric) -> None:
        captured: dict[str, str] = {}

        def make_proposer():
            agent = FakeAgent("PROPOSER")

            def run(prompt: str, model_manager: ModelManager | None = None) -> str:
                _ = model_manager
                agent.prompts.append(prompt)
                if len(agent.prompts) == 1:
                    return "첫 제안 내용"
                captured["second"] = prompt
                return "개선 제안"

            setattr(agent, "run", run)
            return agent

        def create_temp(role: str, suffix: str = "") -> FakeAgent:
            _ = suffix
            return make_proposer() if role == "PROPOSER" else FakeAgent(role)

        setattr(fabric, "create_temp_agent", create_temp)

        _ = list(_execute_debate(fabric, "주제", [], rounds=2, num_critics=1))

        assert "첫 제안 내용" in captured["second"]
        assert "피드백을 반영" in captured["second"]

    def test_orchestrator_generate_for_role_used_when_available(self, fabric: AgentFabric) -> None:
        calls: list[str] = []

        class Orch:
            def _generate_for_role(
                self,
                role: str,
                prompt: str,
                messages: list[dict[str, str]],
            ) -> Iterator[str]:
                _ = prompt, messages
                calls.append(role)
                yield f"[{role} 생성]"

        chunks = list(_execute_debate(fabric, "주제", [], orchestrator=Orch(), rounds=1, num_critics=2))

        joined = "".join(chunks)
        assert "[PROPOSER 생성]" in joined
        assert joined.count("[CRITIC 생성]") == 2
        assert set(calls) == {"PROPOSER", "CRITIC", "ARBITER"}


# ─── 상태 & 정리 ─────────────────────────────────────────────────


class TestStatusAndCleanup:
    def test_get_status_reports_registry_and_kanban(self, fabric: AgentFabric) -> None:
        _ = fabric.get_or_create("worker")

        status = fabric.get_status()

        assert "WORKER" in status["active_agents"]
        assert status["agent_count"] == 1
        assert "kanban" in status
        assert isinstance(status["message_channels"], list)

    def test_cleanup_removes_only_temp_agents(self, fabric: AgentFabric) -> None:
        permanent = fabric.get_or_create("worker")  # 영구 등록
        agent_registry = cast(dict[str, BaseAgent], getattr(fabric, "_agent_registry"))
        agent_registry["TEMP_CRITIC_1"] = permanent
        agent_registry["TEMP_CRITIC_2"] = permanent

        fabric.cleanup_temp_agents()

        assert "WORKER" in agent_registry
        assert not any(k.startswith("TEMP_") for k in agent_registry)
