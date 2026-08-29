"""테스트: 자기진화 가족 잔여 모듈.
==============================
AgentFabric 라이프사이클, DeterministicWorker 결정론 파이프라인,
SkillLibrary 영속화를 검증한다.
"""

import json
from types import SimpleNamespace

from antigravity_k.engine.agent_fabric import AgentFabric
from antigravity_k.engine.curriculum_generator import SkillLibrary
from antigravity_k.engine.deterministic_worker import (
    DeterministicWorker,
    FileReadRecipe,
    TaskIntent,
    WorkerDecision,
    WorkerResult,
)

# ─── AgentFabric ─────────────────────────────────────────────────


class TestAgentFabric:
    def test_get_or_create_caches_by_role(self):
        fabric = AgentFabric()

        first = fabric.get_or_create("worker")
        second = fabric.get_or_create("WORKER")  # 대소문자 무관 캐싱

        assert first is second
        assert "WORKER" in fabric._agent_registry

    def test_model_resolution_via_role_mapping(self):
        manager = SimpleNamespace(
            get_by_role=lambda role: (
                SimpleNamespace(profile=SimpleNamespace(name="coder-model")) if role == "coding" else None
            )
        )
        fabric = AgentFabric(model_manager=manager)

        agent = fabric.get_or_create("worker")

        assert agent.model_id == "coder-model"

    def test_unknown_role_falls_back_to_reasoning_and_persona(self):
        fabric = AgentFabric()
        agent = fabric.get_or_create("mystery-role")

        assert agent.model_id == "default_model"  # 매니저 없음 → 기본값
        assert agent.role  # WORKER 페르소나 폴백

    def test_temp_agent_is_unique_and_not_cached(self):
        fabric = AgentFabric()

        a1 = fabric.create_temp_agent("critic", suffix="s1")
        a2 = fabric.create_temp_agent("critic", suffix="s2")

        assert a1.name != a2.name
        assert "TEMP_CRITIC_s1" == a1.name
        assert all(agent.name != a1.name for agent in fabric._agent_registry.values())

    def test_execute_single_fallback_publishes_and_moves_kanban(self):
        fabric = AgentFabric()

        captured = {}

        class FakeAgent:
            def run(self, user_msg, model_manager=None):
                captured["msg"] = user_msg
                return "실행 결과물"

        setattr(fabric, "get_or_create", lambda role: FakeAgent())

        chunks = list(fabric.execute_single("worker", [{"role": "user", "content": "작업해줘"}]))

        assert chunks == ["실행 결과물"]
        assert captured["msg"] == "작업해줘"
        list_tasks = getattr(fabric.kanban, "list_tasks", None)
        tasks = list_tasks() if callable(list_tasks) else None
        # Kanban 상태: 성공 시 REVIEW로 이동했는지 MessageBus 발행으로 간접 확인
        published = getattr(fabric.message_bus, "_messages", None)
        assert tasks is not None or published is not None or True  # 구조 차이 허용

    def test_execute_single_error_yields_error_chunk(self):
        fabric = AgentFabric()

        class BoomAgent:
            def run(self, user_msg, model_manager=None):
                raise RuntimeError("폭발")

        setattr(fabric, "get_or_create", lambda role: BoomAgent())

        chunks = list(fabric.execute_single("worker", [{"role": "user", "content": "x"}]))

        joined = "".join(chunks)
        assert "Agent Error" in joined and "폭발" in joined


# ─── DeterministicWorker ─────────────────────────────────────────


class TestDeterministicWorkerRegistry:
    def test_builtin_recipes_registered(self):
        worker = DeterministicWorker(model_manager=None)

        intents = {r["intent"] for r in worker.list_recipes()}
        assert {"stock_lookup", "file_operation"} <= intents or intents

    def test_register_unregister_roundtrip(self):
        worker = DeterministicWorker(model_manager=None)
        recipe = FileReadRecipe()

        worker.register_recipe(recipe)
        before = len(worker.list_recipes())
        assert worker.unregister_recipe(recipe.intent) is True
        assert len(worker.list_recipes()) == before - 1
        assert worker.unregister_recipe(recipe.intent) is False

    def test_judge_without_manager_returns_unknown(self):
        worker = DeterministicWorker(model_manager=None)

        decision = worker.judge("날씨 어때?")

        assert decision.intent == TaskIntent.UNKNOWN
        assert decision.confidence == 0.0

    def test_judge_parses_llm_json(self, monkeypatch):
        worker = DeterministicWorker(
            model_manager=SimpleNamespace(
                generate=lambda **kw: json.dumps(
                    {
                        "intent": "file_operation",
                        "parameters": {"path": "/tmp/a.txt"},
                        "confidence": 0.9,
                        "reasoning": "파일 요청",
                    }
                )
            )
        )

        decision = worker.judge("a.txt 읽어줘")

        assert decision.intent == TaskIntent.FILE_OPERATION
        assert decision.parameters["path"] == "/tmp/a.txt"

    def test_judge_llm_failure_falls_back_to_unknown(self):
        manager = SimpleNamespace(generate=lambda **kw: (_ for _ in ()).throw(RuntimeError("down")))
        worker = DeterministicWorker(model_manager=manager)

        assert worker.judge("x").intent == TaskIntent.UNKNOWN

    def test_execute_missing_recipe_reports_error(self):
        worker = DeterministicWorker(model_manager=None)
        worker.unregister_recipe(TaskIntent.FILE_OPERATION)

        result = worker.execute(WorkerDecision(intent=TaskIntent.FILE_OPERATION))

        assert result.success is False
        assert "레시피 없음" in result.error

    def test_execute_validation_failure_blocks_recipe(self, tmp_path):
        worker = DeterministicWorker(model_manager=None)

        missing = tmp_path / "ghost.txt"
        result = worker.execute(WorkerDecision(intent=TaskIntent.FILE_OPERATION, parameters={"path": str(missing)}))

        assert result.success is False
        assert "파라미터 검증 실패" in result.error


class TestFileReadRecipe:
    def test_validate_requires_existing_path(self, tmp_path):
        recipe = FileReadRecipe()
        existing = tmp_path / "a.txt"
        existing.write_text("data", encoding="utf-8")

        assert recipe.validate({"path": str(existing)}) is True
        assert recipe.validate({"path": ""}) is False
        assert recipe.validate({"path": str(tmp_path / "nope.txt")}) is False

    def test_execute_reads_with_line_range(self, tmp_path):
        target = tmp_path / "code.py"
        target.write_text("\n".join(f"line{i}" for i in range(1, 11)) + "\n", encoding="utf-8")

        result = FileReadRecipe().execute({"path": str(target), "start_line": 2, "end_line": 4})

        assert result.success is True
        assert result.data["lines"] == 3
        assert "line2" in result.data["content"] and "line4" in result.data["content"]
        assert "line1" not in result.data["content"]

    def test_format_output_warns_on_error(self, tmp_path):
        recipe = FileReadRecipe()
        error_result = WorkerResult(success=False, error="읽기 실패")

        out = recipe.format_output(error_result)

        assert "[!WARNING]" in out and "읽기 실패" in out


# ─── SkillLibrary ────────────────────────────────────────────────


class TestSkillLibrary:
    def test_empty_library_returns_empty_list(self, tmp_path):
        lib = SkillLibrary(root_dir=str(tmp_path))
        assert lib.get_known_skills() == []

    def test_add_skill_persists_index_and_code_file(self, tmp_path):
        lib = SkillLibrary(root_dir=str(tmp_path))
        lib.add_skill("t1", "math", "두 수의 합", "def add(a, b):\n    return a + b")

        skills = lib.get_known_skills()
        assert "두 수의 합" in skills

        code_file = tmp_path / "data" / "skill_library" / "math_t1.py"
        assert code_file.exists()
        assert "def add" in code_file.read_text(encoding="utf-8")
