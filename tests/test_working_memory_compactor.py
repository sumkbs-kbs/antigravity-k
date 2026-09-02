"""Unit tests for WorkingMemoryCompactor."""

from antigravity_k.engine.working_memory_compactor import WorkingMemoryCompactor


def test_working_memory_compaction():
    # Simulate a long 15-message trajectory
    messages = [
        {"role": "user", "content": "Let's update src/auth/jwt.py and tests/test_jwt.py"},
        {"role": "assistant", "content": "I will read src/auth/jwt.py and configure RSA keys"},
        {"role": "user", "content": "Also check config.yaml and policy.yaml"},
    ]

    adrs = [
        "ADR-001: Use RS256 for all JWT tokens",
        "ADR-002: Disallow plain text tokens in logs",
    ]

    pending = ["Implement token refresh endpoint"]

    state = WorkingMemoryCompactor.compact(messages, adrs=adrs, pending_subgoals=pending)
    pinned_block = state.format_pinned_working_memory()

    assert "PINNED_WORKING_MEMORY_STATE" in pinned_block
    assert "ADR-001: Use RS256" in pinned_block
    assert "src/auth/jwt.py" in pinned_block
    assert "Implement token refresh endpoint" in pinned_block


def test_working_memory_preserves_failures_and_next_action():
    messages = [
        {"role": "assistant", "content": "Running tests for src/mod/plugin.py"},
        {"role": "tool", "content": "ERROR: syntax failure in src/mod/plugin.py"},
        {"role": "user", "content": "Fix the syntax error, then run the focused test again."},
    ]

    state = WorkingMemoryCompactor.compact(messages)

    assert state.recent_failures == ["ERROR: syntax failure in src/mod/plugin.py"]
    assert state.next_action == "Fix the syntax error, then run the focused test again."
    assert "Next Action" in state.format_pinned_working_memory()


class TestNextActionPurity:
    def test_tool_result_as_last_user_does_not_pollute_next_action(self):
        """도구 결과(role=user로 append됨)는 next_action을 오염시키지 않는다."""
        state = WorkingMemoryCompactor.compact(
            [
                {"role": "user", "content": "config.yaml에서 포트를 수정해줘"},
                {"role": "assistant", "content": "<tool_call>{}</tool_call>"},
                {"role": "user", "content": "<tool_response>[TOOL_EVIDENCE] {\"tool\": \"read_file\"} Successfully read 400 lines..."},
            ]
        )
        assert "config.yaml" in state.next_action
        assert "TOOL_EVIDENCE" not in state.next_action

    def test_system_feedback_marker_excluded(self):
        state = WorkingMemoryCompactor.compact(
            [
                {"role": "user", "content": "리팩터링해줘"},
                {"role": "user", "content": "[시스템 피드백] 이전 답변에서 오류가 발견되었습니다."},
            ]
        )
        assert state.next_action == "리팩터링해줘"
