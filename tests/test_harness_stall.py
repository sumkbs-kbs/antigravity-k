"""HarnessEnforcer 스톨 감지와 장기 실행 하네스 프롬프트 로더 테스트."""

from pathlib import Path

from antigravity_k.engine.harness_enforcer import (
    HarnessEnforcer,
    load_longrun_harness_prompt,
)


class TestStallDetection:
    def test_first_call_allowed(self):
        enforcer = HarnessEnforcer()
        res = enforcer.check_tool_boundary("read_file", {"path": "a.py"})
        assert res["allowed"] is True
        assert "stall" not in res

    def test_second_identical_call_blocked_with_stall_message(self):
        enforcer = HarnessEnforcer()
        args = {"command": "pytest -q tests/x.py"}
        assert enforcer.check_tool_boundary("run_command", args)["allowed"] is True
        second = enforcer.check_tool_boundary("run_command", args)
        assert second["allowed"] is False
        assert second.get("stall") is True
        assert "STALL DETECTED" in second["reason"]
        assert "폐기" in second["reason"]
        assert "대안 가설" in second["reason"]

    def test_different_args_not_stalled(self):
        enforcer = HarnessEnforcer()
        assert enforcer.check_tool_boundary("read_file", {"path": "a.py"})["allowed"] is True
        assert enforcer.check_tool_boundary("read_file", {"path": "b.py"})["allowed"] is True

    def test_reset_clears_counter(self):
        enforcer = HarnessEnforcer()
        args = {"path": "same.py"}
        enforcer.check_tool_boundary("grep_search", args)
        enforcer.check_tool_boundary("grep_search", args)
        enforcer.reset_stall_tracking()
        assert enforcer.check_tool_boundary("grep_search", args)["allowed"] is True

    def test_blocked_tools_do_not_count_toward_stall(self):
        enforcer = HarnessEnforcer()
        for _ in range(3):
            res = enforcer.check_tool_boundary("terminal_ws", {})
            assert res["allowed"] is False
            assert "stall" not in res


class TestLongrunPromptLoader:
    def test_loads_existing_file(self):
        prompt = load_longrun_harness_prompt(str(Path.cwd()))
        assert "Long-run Executor" in prompt or "[STATE]" in prompt

    def test_missing_file_returns_empty(self, tmp_path: Path):
        assert load_longrun_harness_prompt(str(tmp_path)) == ""


def test_goal_runner_contract_injects_harness_rules():
    from antigravity_k.engine.goal_runner import GoalRunner

    runner = GoalRunner(workspace_dir=str(Path.cwd()))
    report = runner.run("테스트 실패 원인을 분석하고 수정 계약을 세워라")
    markdown = runner.render_markdown(report)
    assert "# Long-run Harness Rules" in markdown
    assert "[STATE]" in markdown


class TestSimilarErrorCluster:
    def test_fingerprint_normalizes_surface_noise(self):
        a = HarnessEnforcer._error_fingerprint("FileNotFoundError: [Errno 2] no such file: /tmp/x1.py")
        b = HarnessEnforcer._error_fingerprint("FileNotFoundError: [Errno 2] no such file: /var/y999.py")
        assert a == b
        assert a != ""

    def test_three_similar_errors_trigger_one_shot_intervention(self):
        enforcer = HarnessEnforcer()
        for i in range(3):
            enforcer.record_outcome(failed=True, error_text=f"KeyError: 'config_{i}' missing")
        res = enforcer.check_tool_boundary("read_file", {"path": "other.py"})
        assert res["allowed"] is False
        assert res.get("stall") is True
        assert "유사한 오류" in res["reason"]
        # 원샷 — 소비 후에는 다시 허용
        assert enforcer.check_tool_boundary("read_file", {"path": "other.py"})["allowed"] is True

    def test_different_errors_do_not_cluster(self):
        enforcer = HarnessEnforcer()
        enforcer.record_outcome(failed=True, error_text="KeyError: alpha")
        enforcer.record_outcome(failed=True, error_text="TypeError: bad operand")
        enforcer.record_outcome(failed=True, error_text="PermissionError: denied")
        assert enforcer.check_tool_boundary("read_file", {"path": "z.py"})["allowed"] is True

    def test_success_does_not_block_progress(self):
        enforcer = HarnessEnforcer()
        enforcer.record_outcome(failed=True, error_text="KeyError: k")
        enforcer.record_outcome(failed=False)
        assert enforcer.check_tool_boundary("read_file", {"path": "z.py"})["allowed"] is True


class TestNoProgressWindow:
    def test_five_consecutive_failures_demand_subgoal_decomposition(self):
        enforcer = HarnessEnforcer()
        for i in range(5):
            enforcer.record_outcome(
                failed=True, error_text=f"distinct error {i}: {['alpha','beta','gamma','delta','epsilon'][i]}"
            )
        res = enforcer.check_tool_boundary("run_command", {"command": "make test"})
        assert res["allowed"] is False
        assert "진척 없는 행동" in res["reason"]

    def test_window_slides_on_success(self):
        enforcer = HarnessEnforcer()
        for word in ("alpha", "bravo", "charlie", "delta"):
            enforcer.record_outcome(failed=True, error_text=f"{word} exploded")
        enforcer.record_outcome(failed=False)
        enforcer.record_outcome(failed=True, error_text="echo exploded")
        assert enforcer.check_tool_boundary("read_file", {"path": "q.py"})["allowed"] is True

    def test_reset_clears_supervision_state(self):
        enforcer = HarnessEnforcer()
        for i in range(5):
            enforcer.record_outcome(failed=True, error_text=f"x{i} distinct-{i}")
        enforcer.reset_stall_tracking()
        assert enforcer.check_tool_boundary("read_file", {"path": "r.py"})["allowed"] is True
