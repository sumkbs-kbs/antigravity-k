# CTX-02 re-review request (`ctx_02_budget` → `ctx_02_verify`)

**Status:** ready for independent re-review (owner did **not** write APPROVE)
**Date:** 2026-09-06 (Asia/Seoul)

## Prior verdict

- `review.md` — **REJECT** by `ctx_02_verify` (left intact; do not erase)
- Blocking F1: `_enforce_final_prompt_budget` early-return on non-dict config / resolve/import/estimate failure → over-limit prompt unchanged → provider invoke
- Blocking F2: outer `except Exception` swallowed non-budget errors and continued to `stream_generate` with pre-enforce prompt
- Blocking F3: successful fit did not write system/tools/skills back to loop locals → multi-step rebuild could re-inflate aux

## Fix submitted

| Item | Value |
|---|---|
| Branch / worktree | `codex/ctx-02-prompt-budget` / `Ssak-Ai-ctx-02` |
| Fix SHA (result) | _(filled after commit; see metadata.json `result_sha`)_ |
| Prior impl SHA | `d04748cafe8879b9afaf310bdb6aab4f47ffb06a` |
| Prior REJECT tip | `15cccd7de34b75db6f7d44535706c8d5ca1d109d` (review.md tip was `8a0d845…`) |

### What changed

1. **F1 fail-closed gate:** `_enforce_final_prompt_budget` raises `PromptBudgetEnforcementError` on import/config/resolve/estimate failure — never returns unchecked over-limit prompt.
2. **F2 no swallow-and-continue:** unexpected `fit_final_prompt` errors wrapped as `PromptBudgetEnforcementError`; outer `except` always halts before `stream_generate` (typed exceed + enforcement + any other enforce failure).
3. **F3 aux write-back:** after fit, `system_prompt` / `tool_prompt` / `skill_prompts` (+ pinned memory cache) updated from `FinalPromptFit` so later `_rebuild_prompt` / compress cannot re-inflate fitted prefix.
4. Regressions: `tests/test_ctx02_reject_fixes.py` (F1 non-dict / resolve boom / run_loop halt; F2 RuntimeError; F3 rebuild + direct fit shrink).

### Owner re-runs (not a substitute for independent review)

- pytest F1–F3 + prior final budget: **14 passed** — `tests-fix-f1f3.txt`
- related budget/shaper/tool_loop (3 pre-existing unrelated deselected): **156 passed** — `tests-fix-related.txt`
- ruff touched files: All checks passed — `ruff-fix.txt`
- Owner adversarial: `adversarial-notes-fix.md` / `adversarial-verify-owner-fix.txt` — F1/F2/F3/F5 PASS (owner)

## Ask

Please re-run must-verify #1–#8 and adversarial F1/F2/F5/F3 probes independently. Write a new review artifact (e.g. `review-r2.md`) — do **not** erase prior REJECT in `review.md`. Do **not** start CTX-03 from this handoff. Owner will not self-APPROVE.
