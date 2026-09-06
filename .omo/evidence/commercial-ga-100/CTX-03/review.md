# CTX-03 Independent Review — REJECT

| Field | Value |
|---|---|
| Reviewer | `ctx_03_verify` (Owner≠Reviewer; no implementation commits) |
| Owner | `ctx_03_observability` |
| Verdict | **REJECT** |
| Tip reviewed | `711be5926f1193153855ba71d05840fa65c5d65b` (HEAD confirmed) |
| Impl / Result SHA | `9f5678d890c2bec05a0c1a10b8e8b13d2331b1b0` |
| Branch / worktree | `codex/ctx-03-compress-observability` / `Ssak-Ai-ctx-03` |
| Reviewed at | 2026-09-06T12:55+09:00 |
| Confidence | 0.93 |

**DONE 금지.** Context lane **미완료**. **DAT-01 착수 금지** until `ctx_03_verify` re-review **APPROVE**.

## Scope checked

Must-verify from commercial GA CTX-03:

1. No catch-all fail-open sending over-limit after compress failure (incl. `_maybe_compress_context`)
2. Degrade vs halt policy correct; hard-limit → provider not called
3. Telemetry fields present (before/after, strategy, digest, elapsed, failure_code)
4. UI/status matches server for success/degrade/halt
5. Alert thresholds documented
6. Re-run CTX-03 + related CTX-02 suites; adversarial probes for silent swallow

## What passes (keep)

- `_maybe_compress_context` no longer returns a bare original-prompt tuple on exception. All exception / rebuild-unavailable paths return `ContextCompressAttempt(failed=True, failure_code=…)`. Adversarial probes: adaptive_compress / lookup / needs_compression / rebuild unavailable → `failed=True`, original prompt retained (P1–P4, P10).
- Tool-loop policy: compress fail + under hard-limit → degraded UI/telemetry and provider **may** run (`test_compress_failure_under_limit_is_degraded_not_halt`, `stream_generate.call_count >= 1`). Compress fail + `PromptBudgetExceededError` from final gate → halted; `stream_generate.call_count == 0` (`test_compress_failure_then_over_limit_halts_before_provider`). Outer enforce `except` always records halt + returns before provider.
- `CompressTelemetryRecord.as_payload()` includes `tokens_before` / `tokens_after`, `strategy`, `digest`, `elapsed_ms`, `failure_code`, and `alert_thresholds` (`ALERT_COMPRESS_FAILURE_RATE=0.05`, `ALERT_BUDGET_HEADROOM_PCT=15.0`). Events: `context.compress.succeeded|degraded|halted`.
- Stream-pre path no longer uses silent “non-critical” swallow; emits degraded telemetry + `ui_status_line`. State-graph agent steps still enter `ToolLoopEngine.run_loop` (hard-limit gate).
- Ops: `docs/09_OPERATION_GUIDE.md` documents 5% failure-rate and 15% headroom thresholds + degrade/halt policy.
- Stream/status lines distinguish success / degraded / halted via `ui_status_line`.
- Reviewer re-run: `pytest tests/test_ctx03_compress_observability.py tests/test_ctx02_reject_fixes.py tests/test_final_prompt_budget.py tests/test_tool_loop.py::TestToolLoopEngineContextCompression` → **27 passed**; ruff on touched Python → **All checks passed**.

## Blocking findings

### F1 — `statusFor` maps `context.compress.succeeded` → `unknown` (not `completed`) — BLOCKER (must-verify #4)

`dashboard/src/features/task-execution/taskExecutionProjection.ts` `statusFor`:

```ts
if (normalized.includes('complete') || normalized.includes('finish') || normalized.includes('success')) {
  return 'completed';
}
```

Server event type is `context.compress.succeeded` (`EVENT_COMPRESS_SUCCEEDED`).  
JavaScript/`String.includes('success')` is **false** for `"succeeded"` (`succee` ≠ `success`). Independent Node+Python probe:

| event_type | actual UI status | required |
|---|---|---|
| `context.compress.succeeded` | **`unknown`** | `completed` |
| `context.compress.degraded` | `degraded` | `degraded` |
| `context.compress.halted` | `failed` | `failed` |

Owner unit test `taskExecutionProjection.test.ts` (“maps compress success/degrade/halt to completed/degraded/failed”) **expects** `completed` for succeeded — but vitest deps are missing in this worktree and the assertion is **wrong relative to current `statusFor`**. Checklist claim “UI 상태가 server 결과와 일치” is therefore **false** for the success path. Degrade/halt map correctly; **success does not**.

Must-verify #4 requires UI to match server for **success / degrade / halt**. Success mismatch = REJECT.

## Must-verify scorecard

| # | Criterion | Result |
|---|---|---|
| 1 | No catch-all fail-open after compress failure (`_maybe_compress_context`) | **PASS** |
| 2 | Degrade vs halt; hard-limit → provider not called | **PASS** (tool_loop + tests) |
| 3 | Telemetry before/after, strategy, digest, elapsed, failure_code | **PASS** |
| 4 | UI/status matches server success/degrade/halt | **FAIL** — F1 succeeded→unknown |
| 5 | Alert thresholds documented | **PASS** (docs/09 + constants) |
| 6 | Re-run suites + adversarial silent-swallow probes | **PASS** suites; F1 found by adversarial UI probe |

## Precise fixes required (owner)

1. **Fix UI success mapping for compress**
   - Prefer exact / prefix-safe matching, e.g. check `succeed` **or** map exact event types:
     - `context.compress.succeeded` → `completed`
     - `context.compress.degraded` → `degraded`
     - `context.compress.halted` → `failed`
   - Do **not** rely on `includes('success')` alone for `succeeded`.
   - Alternative: rename event to `context.compress.success` **and** update server constants + tests + docs consistently (less preferred if telemetry already emitted).

2. **Prove the mapping**
   - Install/run dashboard vitest for `taskExecutionProjection.test.ts` (or equivalent node assert) and show green evidence under `.omo/evidence/commercial-ga-100/CTX-03/`.
   - Keep degrade/halt regressions; add an explicit assert that `succeeded` ≠ `unknown`.

3. **Evidence / checklist**
   - Uncheck CTX-03 UI checklist line until re-review.
   - Re-submit with new Result SHA; do **not** self-APPROVE; **do not start DAT-01**.

## Residual (non-blocking for this REJECT, track after F1)

- `decide_post_compress_policy` is unit-tested but **not wired** in `tool_loop` / `stream` production (inline equivalent exists). Wire or delete dead helper to avoid drift.
- Legacy 4-tuple compat shim in `run_loop` forces `failed=False` (test-only patch path).
- Stream-pre catch tuple is narrower than tool_loop (`AttributeError|RuntimeError|TypeError|ValueError`); other exceptions bubble (not fail-open) — acceptable, document if intentional.
- `vitest` package unresolved in this worktree at review time — owner must produce runnable UI proof on fix.

## Evidence

- `.omo/evidence/commercial-ga-100/CTX-03/adversarial-verify.txt` (F1 Node/Python reproduce + prior probes)
- `.omo/evidence/commercial-ga-100/CTX-03/tests-verify.txt` (27 passed)
- `.omo/evidence/commercial-ga-100/CTX-03/ruff-verify.txt`
- Owner test that would fail vs current mapper: `dashboard/src/features/task-execution/taskExecutionProjection.test.ts`

## Verdict

**REJECT.** Server compress fail-open removal, degrade/halt gate, telemetry, and alert docs look solid. **UI success status does not match server** (`succeeded` → `unknown`). Fix F1 and request re-review. **DAT-01 not started. Context lane not complete.**
