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
        assert second["stall"] is True
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
