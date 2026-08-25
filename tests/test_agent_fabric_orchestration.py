"""테스트: AgentFabric 오케스트레이션 (crew/debate/상태).
============================================
순차 파이프라인의 컨텍스트 누적·실패 중단, 토론 라운드 구조,
임시 에이전트 정리 계약을 검증한다.
"""

import pytest

from antigravity_k.engine.agent_fabric import AgentFabric


class FakeAgent:
    """스크립트된 응답을 반환하고 받은 프롬프트를 기록하는 가짜 에이전트."""

    def __init__(self, name="FAKE", outputs=("응답",)):
        self.name = name
        self.outputs = list(outputs)
        self.prompts = []
        self.inbox = []  # MessageBus 구독 시 호출되는 계약

    def add_message(self, role, content):
        self.inbox.append((role, content))

    def run(self, prompt, model_manager=None):
        self.prompts.append(prompt)
        return self.outputs.pop(0) if self.outputs else "기본 응답"


@pytest.fixture
def fabric():
    return AgentFabric()


# ─── execute_crew ────────────────────────────────────────────────


class TestExecuteCrew:
    def test_sequential_context_accumulates_across_steps(self, fabric):
        agents = {
            "ARCHITECT": FakeAgent("ARCHITECT", ["설계 완료"]),
            "WORKER": FakeAgent("WORKER", ["구현 완료"]),
        }
        fabric.get_or_create = lambda role: agents[role]
        steps = [
            {"agent": "ARCHITECT", "task": "설계해줘"},
            {"agent": "WORKER", "task": "구현해줘"},
        ]

        chunks = list(fabric.execute_crew(steps, [{"role": "user", "content": "과제"}]))

        joined = "".join(chunks)
        assert "Step 1/2" in joined and "Step 2/2" in joined
        assert "설계 완료" in joined and "구현 완료" in joined
        # 2단계 프롬프트에 1단계 결과가 주입된다 (CrewAI 전달 패턴)
        worker_prompt = agents["WORKER"].prompts[0]
        assert "이전 단계 결과" in worker_prompt
        assert "설계 완료" in worker_prompt
        assert "Crew Pipeline 완료" in joined

    def test_step_failure_breaks_pipeline(self, fabric):
        boom = FakeAgent("WORKER")
        boom.run = lambda prompt, model_manager=None: (_ for _ in ()).throw(RuntimeError("붐"))
        after = FakeAgent("QA", ["도달 불가"])
        fabric.get_or_create = lambda role: {"WORKER": boom, "QA": after}[role]

        chunks = list(
            fabric.execute_crew(
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

    def test_orchestrator_loop_takes_priority(self, fabric):
        sentinels = iter(["orch-chunk-1", "orch-chunk-2"])

        class Orch:
            def _run_single_agent(self, messages, role, task_type, max_steps):
                yield next(sentinels)

        steps = [
            {"agent": "WORKER", "task": "t1"},
            {"agent": "QA", "task": "t2"},
        ]
        joined = "".join(fabric.execute_crew(steps, [{"role": "user", "content": "과제"}], orchestrator=Orch()))

        assert "orch-chunk-1" in joined and "orch-chunk-2" in joined


# ─── execute_debate ──────────────────────────────────────────────


class TestExecuteDebate:
    def test_debate_round_structure_and_feedback_loop(self, fabric):
        def make_agent(kind):
            agent = FakeAgent(kind)

            def run(prompt, model_manager=None):
                agent.prompts.append(prompt)
                if kind == "PROPOSER":
                    return f"제안 v{len(agent.prompts)}"
                if kind.startswith("CRITIC"):
                    return f"비판 {prompt[-20:]}"
                return "최종 합의안"

            agent.run = run
            return agent

        fabric.create_temp_agent = lambda role, suffix="": make_agent(role)

        chunks = list(
            fabric.execute_debate(
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

    def test_second_round_prompt_includes_previous_proposal(self, fabric):
        captured = {}

        def make_proposer():
            agent = FakeAgent("PROPOSER")

            def run(prompt, model_manager=None):
                agent.prompts.append(prompt)
                if len(agent.prompts) == 1:
                    return "첫 제안 내용"
                captured["second"] = prompt
                return "개선 제안"

            agent.run = run
            return agent

        fabric.create_temp_agent = lambda role, suffix="": (make_proposer() if role == "PROPOSER" else FakeAgent(role))

        list(fabric.execute_debate("주제", [], rounds=2, num_critics=1))

        assert "첫 제안 내용" in captured["second"]
        assert "피드백을 반영" in captured["second"]

    def test_orchestrator_generate_for_role_used_when_available(self, fabric):
        calls = []

        class Orch:
            def _generate_for_role(self, role, prompt, messages):
                calls.append(role)
                yield f"[{role} 생성]"

        chunks = list(fabric.execute_debate("주제", [], orchestrator=Orch(), rounds=1, num_critics=2))

        joined = "".join(chunks)
        assert "[PROPOSER 생성]" in joined
        assert joined.count("[CRITIC 생성]") == 2
        assert set(calls) == {"PROPOSER", "CRITIC", "ARBITER"}


# ─── 상태 & 정리 ─────────────────────────────────────────────────


class TestStatusAndCleanup:
    def test_get_status_reports_registry_and_kanban(self, fabric):
        fabric.get_or_create("worker")

        status = fabric.get_status()

        assert "WORKER" in status["active_agents"]
        assert status["agent_count"] == 1
        assert "kanban" in status
        assert isinstance(status["message_channels"], list)

    def test_cleanup_removes_only_temp_agents(self, fabric):
        permanent = fabric.get_or_create("worker")  # 영구 등록
        fabric._agent_registry["TEMP_CRITIC_1"] = permanent
        fabric._agent_registry["TEMP_CRITIC_2"] = permanent

        fabric.cleanup_temp_agents()

        assert "WORKER" in fabric._agent_registry
        assert not any(k.startswith("TEMP_") for k in fabric._agent_registry)
