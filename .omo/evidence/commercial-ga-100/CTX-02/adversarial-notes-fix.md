# CTX-02 adversarial notes — F1–F3 REJECT fix (owner; not APPROVE)

Date: 2026-09-06 (Asia/Seoul)
Owner: `ctx_02_budget`

## Prior REJECT probes (from `adversarial-verify.txt`)

- F1 `config="not-a-dict"` → returned over-limit 2008 unchanged
- F5 resolve boom → same fail-open
- F2 `fit_final_prompt` RuntimeError → outer except continued to `stream_generate`

## Owner re-probe after fix (`adversarial-verify-owner-fix.txt`)

1. **F1** non-dict config → `PromptBudgetEnforcementError`; over-limit prompt **not** returned; run_loop does **not** call `stream_generate`.
2. **F5** `resolve_hard_token_limit` boom → `PromptBudgetEnforcementError`; no over-limit return.
3. **F2** unexpected `fit_final_prompt` RuntimeError wrapped as enforcement error → run_loop halt; `stream_generate` call_count **0**.
4. **F3** successful fit under operator 1000 shrinks system; loop locals / rebuild path use fitted aux (regression `test_f3_*`).

## Residual (non-blocking / CTX-03)

- Legacy `_maybe_compress_context` catch-all fail-open remains; acceptable only after this final gate is fail-closed (now).
- Pre-existing unrelated tool_loop failures (`guardrail_prechecked` assert / scratchpad recover) deselected; not introduced by this fix.

**Owner does not APPROVE.** Awaiting `ctx_02_verify` re-review. CTX-03 not started.
