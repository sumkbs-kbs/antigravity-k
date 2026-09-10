"""FR-07 regression: VAL-01 Chroma verdicts must fail loudly.

Covers the staging-verifier contract:

- delete verdicts come from backend where-readback (target == 0, control kept),
  not from search-hit absence
- an intentionally broken (no-op) delete makes the scenario FAIL — the old
  false-green (bool detail ignored by ``_record``) is gone
- exceptions inside scenarios mark the scenario failed
- required-scenario gaps are reported as ``missing_required`` and force a
  non-zero CLI exit (no ``all([]) == True`` approval)
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import TypedDict

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "val01_staging.py"


class ScenarioPayload(TypedDict):
    scenario: str
    ok: bool
    detail: dict[str, object]
    failure_mode: str


def _load_val01() -> ModuleType:
    spec = importlib.util.spec_from_file_location("val01_staging_under_test", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def val01() -> ModuleType:
    return _load_val01()


def _by_name(records: list[ScenarioPayload], name: str) -> ScenarioPayload:
    return next(r for r in records if r["scenario"] == name)


class TestRealChromaVerdicts:
    """Run the chroma scenario block against a real persistent Chroma."""

    def test_delete_verdict_uses_backend_readback(self, val01: ModuleType, tmp_path: Path) -> None:
        records = [r.to_dict() for r in val01._chroma_scenarios(tmp_path)]
        delete = _by_name(records, "chroma_delete")
        assert delete["ok"] is True
        target_after = delete["detail"]["target_chunks_after"]
        control_after = delete["detail"]["control_chunks_after"]
        assert isinstance(target_after, int) and target_after == 0
        assert isinstance(control_after, int) and control_after >= 1

    def test_all_chroma_scenarios_pass_on_healthy_backend(self, val01: ModuleType, tmp_path: Path) -> None:
        records = [r.to_dict() for r in val01._chroma_scenarios(tmp_path)]
        names = {r["scenario"] for r in records}
        assert {
            "chroma_index",
            "chroma_restart_survives",
            "chroma_reindex",
            "chroma_delete",
            "chroma_citation",
        } <= names
        for record in records:
            assert record["ok"] is True, record

    def test_noop_delete_is_detected_as_failure(
        self, val01: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from antigravity_k.engine.vector_store import VectorStore

        # Negative control: pretend the backend delete is a silent no-op.
        monkeypatch.setattr(VectorStore, "delete_file_chunks", lambda self, file_path: None)
        records = [r.to_dict() for r in val01._chroma_scenarios(tmp_path)]
        reindex = _by_name(records, "chroma_reindex")
        delete = _by_name(records, "chroma_delete")
        assert reindex["ok"] is False
        assert "no-op" in reindex["failure_mode"] or "still present" in reindex["failure_mode"]
        assert delete["ok"] is False
        assert "still present" in delete["failure_mode"]


class TestRecordSemantics:
    def test_exception_marks_failure(self, val01: ModuleType) -> None:
        def boom() -> dict[str, object]:
            raise AssertionError("intended failure")

        record = val01._record("boom", boom)
        assert record.ok is False
        assert "intended failure" in record.failure_mode

    def test_false_detail_bool_marks_failure(self, val01: ModuleType) -> None:
        def sneaky() -> dict[str, bool]:
            return {"deleted_file_unsearchable": False}

        record = val01._record("sneaky", sneaky)
        assert record.ok is False
        assert "false boolean" in record.failure_mode


class TestRequiredScenarioGating:
    def test_missing_required_reported(self, val01: ModuleType) -> None:
        missing = val01._missing_required(["chroma_index"])
        assert "chroma_delete" in missing
        assert any("ollama" in m for m in missing)
        assert "fuse_and_promote" in missing

    def test_full_chroma_block_still_missing_training_and_ollama(self, val01: ModuleType) -> None:
        missing = val01._missing_required(
            [
                "ollama_streaming",
                "chroma_index",
                "chroma_restart_survives",
                "chroma_reindex",
                "chroma_delete",
                "chroma_citation",
            ]
        )
        assert "train_recipe_and_checkpoint" in missing
        assert missing != []

    def test_complete_list_has_no_missing(self, val01: ModuleType) -> None:
        names = [
            "ollama_streaming",
            "chroma_index",
            "chroma_restart_survives",
            "chroma_reindex",
            "chroma_delete",
            "chroma_citation",
            "train_recipe_and_checkpoint",
            "train_resume_from_checkpoint",
            "fuse_and_promote",
        ]
        assert val01._missing_required(names) == []


class TestCliExitCode:
    def test_main_returns_nonzero_on_failure_or_missing(
        self, val01: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        artifact = {
            "summary": {
                "total": 1,
                "passed": 1,
                "failed": 0,
                "missing_required": ["chroma_delete"],
                "failure_modes": [],
            }
        }
        monkeypatch.setattr(val01, "run_staging", lambda output: artifact)
        monkeypatch.setattr("sys.argv", ["val01_staging.py", "--output", str(tmp_path / "a.json")])
        assert val01.main() == 1

        artifact["summary"]["missing_required"] = []
        artifact["summary"]["failed"] = 1
        assert val01.main() == 1

        artifact["summary"]["failed"] = 0
        assert val01.main() == 0
