"""Workspace change review handler for the orchestrator state graph."""

import logging
from collections.abc import Generator

from antigravity_k.engine.state_graph import StateContext
from antigravity_k.engine.tool_guardrails import MUTATING_TOOL_NAMES

logger = logging.getLogger("antigravity_k.engine.orchestrator_handlers")


def _agent_used_mutating_tool(orch, started_at: float) -> bool:
    tool_executor = getattr(getattr(orch, "ctx", None), "tool_executor", None)
    history = getattr(tool_executor, "tool_call_history", [])
    return any(
        isinstance(entry, dict)
        and entry.get("name") in MUTATING_TOOL_NAMES
        and isinstance(entry.get("timestamp"), (int, float))
        and entry["timestamp"] >= started_at
        for entry in history
    )


def code_review_handler(ctx: StateContext, orch) -> Generator[str, None, None]:
    """코드 변경 사항을 자동 리뷰합니다. (After CoV)

    COV_VERIFY 완료 후 호출되어:
    1. Git diff 확인
    2. LLM 리뷰 요청 (버그/타입/품질)
    3. 심각한 문제 발견 시 retry 루프백 (validation_passed=False)
    """
    if not ctx.agent_output or len(ctx.agent_output.strip()) < 100:
        return

    # coding/debug 태스크만 리뷰
    if ctx.task_type not in ("coding", "complex"):
        return
    if not _agent_used_mutating_tool(orch, ctx.started_at):
        return

    try:
        # Git diff 확인
        import subprocess

        diff_result = subprocess.run(
            ["git", "diff", "--stat"],
            cwd=orch.project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        diff_stat = diff_result.stdout.strip()

        if not diff_stat:
            return  # 변경 사항 없으면 스킵

        # 변경된 파일이 적을 때만 상세 diff 확인
        changed_lines = diff_stat.count("\n")
        if changed_lines > 15:
            yield f"\n\n📋 **변경된 파일**: {diff_stat[:300]}\n"
            return  # 너무 많은 변경은 스킵

        # 상세 diff 가져오기
        diff_detail = subprocess.run(
            ["git", "diff"],
            cwd=orch.project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        diff_content = diff_detail.stdout

        if len(diff_content) > 8000:
            diff_content = diff_content[:8000] + "\n... (diff truncated)"

        # LLM 리뷰 요청
        if hasattr(orch, "manager") and orch.manager:
            review_prompt = f"""Review the following code changes for bugs or issues.

Original user request: {ctx.user_message[:200]}

```diff
{diff_content}
```

Respond in EXACTLY this format (one line per category, 'None' if none):
BUGS: <brief description or None>
TYPES: <type error description or None>
QUALITY: <quality concern or None>
"""
            try:
                review_response = orch.manager.generate(
                    prompt=review_prompt,
                    target=orch._get_model_for_role("QA"),
                    max_tokens=256,
                )
                review_response = review_response.strip()

                # 결과 파싱
                has_bugs = "BUGS:" in review_response and "None" not in review_response.split("BUGS:")[1][:20]
                has_types = "TYPES:" in review_response and "None" not in review_response.split("TYPES:")[1][:20]

                if has_bugs or has_types:
                    yield "\n\n🔍 **[Auto Review]** 잠재적 이슈 발견:\n"
                    for line in review_response.split("\n"):
                        line = line.strip()
                        if line and not line.startswith("Respond"):
                            yield f"> {line}\n"

                    # 심각한 버그 감지 시 루프백 플래그 (quality_check_handler와 충돌 방지)
                    if has_bugs and ctx.retry_count < ctx.max_retries:
                        yield "> ⚠️ 버그가 감지되어 자가 수정을 시도합니다...\n"
                        ctx.validation_passed = False
                        ctx.retry_count += 1
                else:
                    logger.debug("[AutoReview] Code review passed — no issues")
            except Exception as e:  # noqa: BLE001  # noqa: BROAD_EXCEPT_OK - provider boundary
                logger.warning("[AutoReview] 코드 리뷰 LLM 호출 실패 (non-critical): %s", e, exc_info=True)
    except OSError:
        logger.warning("[AutoReview] git diff 조회 실패 (non-critical)", exc_info=True)
