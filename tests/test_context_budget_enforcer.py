"""context_budget_enforcer 페어링 인식 드롭 테스트.

assistant의 <tool_call>과 그 결과는 함께 드롭되어야 한다 — 한쪽만 남으면
고아 호출/고아 결과가 히스토리로 재주입되어 모델과 파서를 오염시킨다.
"""

from antigravity_k.engine.context_budget_enforcer import enforce_context_budget
from antigravity_k.engine.tokenizer import TokenEstimator


def _est(text: str) -> int:
    return TokenEstimator.estimate_text(text)


def test_tool_call_and_result_dropped_together():
    messages = [
        {"role": "system", "content": "지침"},
        {"role": "user", "content": "작업"},
        {"role": "assistant", "content": '<tool_call>{"name": "read_file", "arguments": {}}</tool_call>'},
        {"role": "tool", "content": "[TOOL_EVIDENCE] 결과 " + "데이터 " * 200},
        {"role": "user", "content": "추가 요청 " * 50},
    ]
    fitted = enforce_context_budget(messages, token_budget=60, estimate_tokens=_est)

    contents = [m["content"] for m in fitted]
    has_call = any("<tool_call>" in c for c in contents)
    has_result = any("[TOOL_EVIDENCE]" in c for c in contents)
    # 호출과 결과 중 하나만 남는 고아 상태가 아니어야 한다
    assert has_call == has_result


def test_pairing_survives_when_budget_generous():
    messages = [
        {"role": "system", "content": "지침"},
        {"role": "user", "content": "작업"},
        {"role": "assistant", "content": "<tool_call>{}</tool_call>"},
        {"role": "tool", "content": "짧은 결과"},
    ]
    fitted = enforce_context_budget(messages, token_budget=10_000, estimate_tokens=_est)
    assert fitted == messages  # 예산 내 → 무결


def test_no_orphan_when_call_dropped_first():
    # assistant(호출)가 가장 낮은 보호 등급이라 먼저 드롭되는 시나리오
    messages = [
        {"role": "system", "content": "시스템 " * 30},
        {"role": "user", "content": "요청 " * 40},
        {"role": "assistant", "content": "<tool_call>{}</tool_call>"},
        {"role": "tool", "content": "결과 " * 300},
    ]
    fitted = enforce_context_budget(messages, token_budget=50, estimate_tokens=_est)
    contents = [m["content"] for m in fitted]
    has_call = any("<tool_call>" in c for c in contents)
    has_result = any(m.get("role") == "tool" for m in fitted)
    assert has_call == has_result
