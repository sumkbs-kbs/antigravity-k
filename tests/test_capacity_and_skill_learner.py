"""테스트: SkillAutoLearner + CapacityCheckpoint.
====================================
스킬 자동 학습 루프(관찰→패턴 감지→스킬 생성)와
용량 가드레일 3축(컨텍스트/스텝/비용), 체크포인트 복구를 검증한다.
"""

import pytest

from antigravity_k.engine.capacity_flow import (
    CapacityAction,
    CapacityCheckpoint,
    CrashRecovery,
)
from antigravity_k.engine.skill_auto_learner import SkillAutoLearner

# ─── CapacityCheckpoint: 컨텍스트 예산 ───────────────────────────


class TestContextBudget:
    @pytest.fixture
    def cp(self):
        return CapacityCheckpoint(warn_pct=70, compress_pct=85, halt_pct=95)

    def test_ok_below_warn(self, cp):
        d = cp.check_context_budget(500, 1000)
        assert d.action == CapacityAction.OK

    def test_warn_at_70pct(self, cp):
        d = cp.check_context_budget(750, 1000)
        assert d.action == CapacityAction.WARN
        assert "경고" in d.message

    def test_compress_at_85pct(self, cp):
        d = cp.check_context_budget(900, 1000)
        assert d.action == CapacityAction.COMPRESS

    def test_halt_at_95pct(self, cp):
        d = cp.check_context_budget(960, 1000)
        assert d.action == CapacityAction.HALT

    def test_zero_max_tokens_returns_ok(self, cp):
        assert cp.check_context_budget(100, 0).action == CapacityAction.OK


# ─── CapacityCheckpoint: 스텝·비용 예산 ──────────────────────────


class TestStepAndCostBudget:
    @pytest.fixture
    def cp(self):
        return CapacityCheckpoint()

    def test_step_ok_within_limit(self, cp):
        assert cp.check_step_budget(5, 15).action == CapacityAction.OK

    def test_step_warn_near_limit(self, cp):
        d = cp.check_step_budget(13, 15)
        assert d.action in (CapacityAction.WARN, CapacityAction.COMPRESS)

    def test_step_halt_exceeded(self, cp):
        assert cp.check_step_budget(20, 15).action == CapacityAction.HALT

    def test_cost_over_budget_switches_model(self, cp):
        d = cp.check_cost_budget(estimated_cost=1.5, max_cost=1.0)
        assert d.action == CapacityAction.SWITCH_MODEL

    def test_cost_within_budget_is_ok(self, cp):
        d = cp.check_cost_budget(estimated_cost=0.3, max_cost=1.0)
        assert d.action in (CapacityAction.OK, CapacityAction.WARN)


# ─── CrashRecovery ───────────────────────────────────────────────


class TestCrashRecovery:
    @pytest.fixture
    def recovery(self, tmp_path):
        return CrashRecovery(checkpoint_dir=str(tmp_path / "cp"))

    def test_save_and_restore_checkpoint(self, recovery):
        state = {"task_id": "t-1", "step": 3, "messages": ["a"]}
        recovery.save_checkpoint(state, label="auto")

        restored = recovery.restore_from_checkpoint("auto")
        assert restored is not None
        assert "task_id" in str(restored) or restored.get("task_id") == "t-1" or restored["task_id"] == "t-1"

    def test_restore_missing_checkpoint_returns_none(self, recovery):
        assert recovery.restore_from_checkpoint("nonexistent") is None

    def test_offline_queue_roundtrip(self, recovery, tmp_path):
        recovery.queue_offline("오프라인 작업", context={"model": "test"})

        queued = recovery.list_offline_queue()
        assert len(queued) >= 1


# ─── SkillAutoLearner: 관찰·패턴·영속화 ──────────────────────────


@pytest.fixture
def learner(tmp_path):
    return SkillAutoLearner(project_root=str(tmp_path))


class TestSkillAutoLearnerObservation:
    def test_record_tool_call_appends_to_current_task(self, learner):
        learner.record_tool_call("read_file", {"path": "a.py"}, result="ok")
        assert len(learner._current_task_calls) == 1

    def test_flush_task_moves_to_history_and_resets(self, learner):
        learner.record_tool_call("read_file", {"path": "a.py"})
        learner.flush_task()

        assert len(learner._history) == 1
        assert learner._current_task_calls == []


class TestSkillAutoLearnerPersistence:
    def test_registry_survives_restart(self, tmp_path):
        learner1 = SkillAutoLearner(project_root=str(tmp_path))
        from antigravity_k.engine.skill_auto_learner import SkillRecord

        learner1._registry["test-skill"] = SkillRecord(
            name="test-skill",
            description="desc",
            source_pattern="seq",
            created_at="2026-01-01",
            use_count=1,
            success_count=1,
            last_used="2026-01-01",
            file_path="",
        )
        learner1._save_registry()

        learner2 = SkillAutoLearner(project_root=str(tmp_path))

        assert "test-skill" in learner2._registry
