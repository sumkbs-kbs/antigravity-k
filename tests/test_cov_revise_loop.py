"""테스트: Chain-of-Verification revise→verify 폐루프.

검증 실패 응답이 revise→재검증 루프로 개선되는지 검증한다.
verify()는 항상 rule 기반(ast.parse) 검증을 수행하므로, generate_fn이
verify 호출에는 결과를 기여하지 않게 해 순수 rule 기반 동작을 유지한다.
GOOD 코드는 ast.parse 통과(issues 0), BAD/STILL 코드는 구문 오류로 failed.
"""

from collections.abc import Callable

from antigravity_k.engine.chain_of_verification import ChainOfVerification

COMPLEX_TASK = "복잡한 알고리즘 아키텍처 리팩토링 마이그레이션 설계 최적화 시간복잡도 분석"
BAD_CODE = "```python\ndef broken_function_name(\n    return\n    value\n```"
GOOD_CODE = "```python\ndef fixed_function():\n    return 1\n    # O(1) 시간복잡도 정답\n```"
STILL_BAD = "```python\ndef still_broken_name(\n    return\n    value\n```"


def _make_cov(
    gen_fn: Callable[[str], str] | None,
    max_revise: int = 1,
    min_len: int = 20,
    complexity: float = 0.0,
) -> ChainOfVerification:
    return ChainOfVerification(
        generate_fn=gen_fn,
        min_response_length=min_len,
        complexity_threshold=complexity,
        max_revise_iterations=max_revise,
    )


VERIFY_ISSUES = (
    "1. 함수 정의에 심각한 구문 오류가 발견되었습니다\n"
    "2. 괄호가 올바르게 종료되지 않았습니다\n"
    "3. 반환문이 누락되어 있습니다\n"
    "4. 들여쓰기가 잘못되었습니다\n"
    "5. 함수 본문이 완전하지 않습니다"
)


def _gen_factory(revise_responses: list[str]) -> tuple[Callable[[str], str], dict[str, int]]:
    """revise 호출 시 순차 응답, verify 호출 시 검증 대상 코드의 실제 파싱 결과 반환.

    verify 프롬프트에는 검증 대상 응답이 포함된다. 그 코드를 ast.parse 해서
    통과하면 '문제 없음', 실패하면 5개 이슈를 반환해 rule 검증과 일치시킨다.
    이렇게 해야 revise 루프가 GOOD 코드에서는 통과하고 BAD/STILL에서는 실패한다.
    """
    import ast as _ast
    import re as _re

    state = {"revise_idx": 0}

    def gen(prompt: str) -> str:
        if "검증해주세요" in prompt:
            m = _re.search(r"```python\n(.*?)```", prompt, _re.DOTALL)
            if m:
                try:
                    _ = _ast.parse(m.group(1))
                    return "문제 없음"
                except SyntaxError:
                    return VERIFY_ISSUES
            return VERIFY_ISSUES
        idx = state["revise_idx"]
        state["revise_idx"] += 1
        return revise_responses[min(idx, len(revise_responses) - 1)]

    return gen, state


def test_default_max_revise_is_one():
    assert ChainOfVerification().max_revise_iterations == 1


def test_single_revise_applies_fix():
    gen, state = _gen_factory([GOOD_CODE])
    cov = _make_cov(gen, max_revise=1)
    trace = cov.run(COMPLEX_TASK, BAD_CODE)
    assert trace.revised_response == GOOD_CODE
    assert state["revise_idx"] == 1


def test_loop_re_verifies_until_pass():
    gen, state = _gen_factory([STILL_BAD, GOOD_CODE])
    cov = _make_cov(gen, max_revise=3)
    trace = cov.run(COMPLEX_TASK, BAD_CODE)
    assert trace.revised_response == GOOD_CODE
    assert state["revise_idx"] == 2


def test_loop_stops_at_max_iterations():
    gen, state = _gen_factory([STILL_BAD, STILL_BAD, STILL_BAD])
    cov = _make_cov(gen, max_revise=2)
    trace = cov.run(COMPLEX_TASK, BAD_CODE)
    assert state["revise_idx"] == 2
    assert trace.revised_response == STILL_BAD


def test_loop_early_terminates_when_no_improvement():
    # revise가 원본(BAD) 그대로 반환 → revised == current → 즉시 종료
    gen, state = _gen_factory([BAD_CODE])
    cov = _make_cov(gen, max_revise=5)
    trace = cov.run(COMPLEX_TASK, BAD_CODE)
    assert state["revise_idx"] == 1
    assert trace.revised_response == BAD_CODE


def test_no_generate_fn_keeps_original_behavior():
    cov = _make_cov(None, max_revise=3)
    trace = cov.run(COMPLEX_TASK, BAD_CODE)
    assert trace.revised_response == BAD_CODE


def test_skipped_short_response():
    gen, _ = _gen_factory(["x"])
    cov = _make_cov(gen, max_revise=3, min_len=200)
    trace = cov.run(COMPLEX_TASK, "짧은 답변")
    assert trace.skipped is True
