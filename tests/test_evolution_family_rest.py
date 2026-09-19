"""테스트: 자기진화 가족 잔여 모듈.
==============================
DeterministicWorker 결정론 파이프라인과 SkillLibrary 영속화를 검증한다.
"""

import json
from pathlib import Path
from typing import cast

import pytest

from antigravity_k.engine.curriculum_generator import SkillLibrary
from antigravity_k.engine.deterministic_worker import (
    DeterministicWorker,
    FileReadRecipe,
    TaskIntent,
    WorkerDecision,
    WorkerResult,
)

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

    def test_judge_parses_llm_json(self, monkeypatch: pytest.MonkeyPatch):
        del monkeypatch

        class JsonManager:
            def generate(self, **kwargs: object) -> object:
                del kwargs
                return json.dumps(
                    {
                        "intent": "file_operation",
                        "parameters": {"path": "/tmp/a.txt"},
                        "confidence": 0.9,
                        "reasoning": "파일 요청",
                    }
                )

        worker = DeterministicWorker(
            model_manager=JsonManager(),
        )

        decision = worker.judge("a.txt 읽어줘")

        assert decision.intent == TaskIntent.FILE_OPERATION
        assert decision.parameters["path"] == "/tmp/a.txt"

    def test_judge_llm_failure_falls_back_to_unknown(self):
        class FailingManager:
            def generate(self, **kwargs: object) -> object:
                del kwargs
                raise RuntimeError("down")

        manager = FailingManager()
        worker = DeterministicWorker(model_manager=manager)

        assert worker.judge("x").intent == TaskIntent.UNKNOWN

    def test_execute_missing_recipe_reports_error(self):
        worker = DeterministicWorker(model_manager=None)
        _ = worker.unregister_recipe(TaskIntent.FILE_OPERATION)

        result = worker.execute(WorkerDecision(intent=TaskIntent.FILE_OPERATION))

        assert result.success is False
        assert "레시피 없음" in result.error

    def test_execute_validation_failure_blocks_recipe(self, tmp_path: Path):
        worker = DeterministicWorker(model_manager=None)

        missing = tmp_path / "ghost.txt"
        result = worker.execute(WorkerDecision(intent=TaskIntent.FILE_OPERATION, parameters={"path": str(missing)}))

        assert result.success is False
        assert "파라미터 검증 실패" in result.error


class TestFileReadRecipe:
    def test_validate_requires_existing_path(self, tmp_path: Path):
        recipe = FileReadRecipe()
        existing = tmp_path / "a.txt"
        _ = existing.write_text("data", encoding="utf-8")

        assert recipe.validate({"path": str(existing)}) is True
        assert recipe.validate({"path": ""}) is False
        assert recipe.validate({"path": str(tmp_path / "nope.txt")}) is False

    def test_execute_reads_with_line_range(self, tmp_path: Path):
        target = tmp_path / "code.py"
        _ = target.write_text("\n".join(f"line{i}" for i in range(1, 11)) + "\n", encoding="utf-8")

        result = FileReadRecipe().execute({"path": str(target), "start_line": 2, "end_line": 4})

        assert result.success is True
        data = cast(dict[str, object], result.data)
        content = cast(str, data["content"])
        assert data["lines"] == 3
        assert "line2" in content and "line4" in content
        assert "line1" not in content

    def test_format_output_warns_on_error(self, tmp_path: Path):
        del tmp_path
        recipe = FileReadRecipe()
        error_result = WorkerResult(success=False, error="읽기 실패")

        out = recipe.format_output(error_result)

        assert "[!WARNING]" in out and "읽기 실패" in out


# ─── SkillLibrary ────────────────────────────────────────────────


class TestSkillLibrary:
    def test_empty_library_returns_empty_list(self, tmp_path: Path):
        lib = SkillLibrary(root_dir=str(tmp_path))
        assert lib.get_known_skills() == []

    def test_add_skill_persists_index_and_code_file(self, tmp_path: Path):
        lib = SkillLibrary(root_dir=str(tmp_path))
        lib.add_skill("t1", "math", "두 수의 합", "def add(a, b):\n    return a + b")

        skills = lib.get_known_skills()
        assert "두 수의 합" in skills

        code_file = tmp_path / "data" / "skill_library" / "math_t1.py"
        assert code_file.exists()
        assert "def add" in code_file.read_text(encoding="utf-8")
