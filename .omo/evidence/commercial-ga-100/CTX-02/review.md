# CTX-02 Independent Review — REJECT

| Field | Value |
|---|---|
| Reviewer | `ctx_02_verify` |
| Owner | `ctx_02_budget` |
| Verdict | **REJECT** |
| Tip reviewed | `8a0d8451d9b91fe06a29eb070eb466e2ae2fdd4d` (HEAD confirmed) |
| Impl / Result SHA | `d04748cafe8879b9afaf310bdb6aab4f47ffb06a` |
| Branch / worktree | `codex/ctx-02-prompt-budget` / `Ssak-Ai-ctx-02` |
| Reviewed at | 2026-09-06T12:20+09:00 |
| Confidence | 0.94 |

**DONE 금지.** CTX-03 착수 금지 until `ctx_02_verify` re-review **APPROVE**.

## Scope checked

Must-verify from commercial GA CTX-02:

1. Final serialized prompt counts all components + output reserve
2. Hard limit re-check immediately before provider invoke
3. 5-token message + ~1005 aux prompt fits under limit (repro test)
4. Tool evidence + latest user constraints preserved; cache prefix stability if claimed
5. Deterministic digest for same input
6. Oversized component → bounded/typed error
7. Re-run CTX-02 tests + related budget suites (reviewer)
8. Fail-open paths that still send over-limit prompts = REJECT

## What passes (keep)

- `PromptComponentLedger` / `build_prompt_component_ledger` counts system/tools/skills/memory/artifacts/messages + `output_reserve`; `resolve_hard_token_limit` = min(declared_input, empirical, operator, MAX).
- Happy-path `fit_final_prompt` + `serialize_final_prompt` pipeline: deterministic priority compress; `prompt_selection_digest` sha256 stable for identical inputs; serialized bytes identical across two fits.
- Unit repro: 5-token message + ~1005 aux under operator 1000 → `fit.ledger.input_total` and `estimate(serialized)` ≤ 1000; latest user edges retained when possible.
- Cache-prefix claim holds for mutable-suffix-only shrink: `fit.cache_prefix == original_prefix` and `serialized.startswith(original_prefix)`.
- `[TOOL_EVIDENCE]` protection rank 5 + latest-user rank 4; structured evidence / `VERIFIED_RESULT` survive tight fit in unit test.
- Oversized single / multi component: bound under budget or `OversizedPromptComponentError` / `PromptBudgetExceededError` (with `allow_typed_error=True`).
- Typed budget errors in `run_loop` stop before `stream_generate` / manager generate (`prompt_budget_exceeded` outcome).
- `ContextShaper.shape_for_model(aux_token_overhead=…)` + `_prepare_agent_prompt` aux pre-deduction — good defense-in-depth for message shaping.
- Reviewer re-run: `tests/test_final_prompt_budget.py` **8 passed**; related budget/shaper/tool_loop subset **67 passed**; ruff clean on touched engine files.

## Blocking findings

### F1 — `_enforce_final_prompt_budget` early-returns over-limit prompt unchanged — BLOCKER (must-verify #2, #8)

Several branches return `(prompt_str, shaped_messages, None)` **without** fitting or raising when enforcement cannot run:

- import failure (`tool_loop.py` ~787–789)
- `config` not a `dict` (~791–793)
- `resolve_hard_token_limit` exception (~799–803)
- `estimate(prompt_str)` `TypeError` (~805–808)

Adversarial probe (`adversarial-verify.txt`):

- **F1** `config="not-a-dict"` → returned prompt still **2008** tokens (over operator 1000), `fit=None`, bytes unchanged.
- **F5** `resolve_hard_token_limit` raises → same **2008** over-limit return, `fit=None`.

Caller then builds `stream_kwargs["prompt"]=prompt_str` and invokes the provider. This is a hard-limit **fail-open**.

### F2 — outer `except Exception` swallows non-budget errors then still invokes — BLOCKER (must-verify #2, #8)

`run_loop` (~1187–1208): only `OversizedPromptComponentError` / `PromptBudgetExceededError` halt. Any other exception from `_enforce_final_prompt_budget` (e.g. unexpected `RuntimeError` from `fit_final_prompt`) is logged at debug and **execution continues** to `stream_generate` with the **pre-enforce** `prompt_str`.

Probe: patched `fit_final_prompt` → `RuntimeError` propagates out of enforce; outer policy is fail-open continue. Over-limit prompt reaches the provider.

Owner residual note that compress fail-open is “CTX-03” does **not** excuse a final hard-limit gate that itself fail-opens. Criterion #8 is explicit for CTX-02.

### F3 — successful fit does not update `system_prompt` / `tool_prompt` / `skill_prompts` locals — RELATED BLOCKER for multi-step stability (#2, #4)

After `prompt_str, shaped_messages, _final_fit = _enforce_final_prompt_budget(...)`, only `prompt_str` and `shaped_messages` are assigned. If fit shrunk system/tools/skills, the loop locals still hold the **original** aux. Next iteration `_maybe_compress_context` → `_rebuild_prompt(system_prompt, …)` can **re-inflate** aux, relying again on enforce. Combined with F1/F2, re-inflate + fail-open = over-limit send. Even without fail-open, cache-prefix stability across tool steps is not held when prefix components were mutated then rebuilt from stale locals.

## Must-verify scorecard

| # | Criterion | Result |
|---|---|---|
| 1 | Ledger counts all components + output reserve | **PASS** |
| 2 | Hard limit re-check immediately before invoke | **FAIL** — happy path OK; F1/F2 skip/bypass |
| 3 | 5-token + ~1005 aux under limit | **PASS** (unit) |
| 4 | Tool evidence + latest user; cache prefix if claimed | **PARTIAL** — unit PASS; F3 multi-step re-inflate risk |
| 5 | Deterministic digest same input | **PASS** |
| 6 | Oversized → bounded/typed error | **PASS** (happy `allow_typed_error=True`) |
| 7 | Reviewer re-run suites | **PASS** — 8 + 67; ruff clean |
| 8 | No fail-open sending over-limit prompts | **FAIL** — F1/F2 confirmed |

## Precise fixes required (owner)

1. **Final budget gate must be fail-closed**
   - If enforce cannot complete (bad config, resolve/import/estimate failure, unexpected exception): **do not** return/send the original prompt when `estimate(prompt) > input_budget`.
   - Prefer: raise `PromptBudgetExceededError` (or a dedicated `PromptBudgetEnforcementError`) and halt the loop with the same user-facing stop as typed exceed — **never** fall through to `stream_generate` / manager generate.
   - Remove or narrow the outer `except Exception` continue path (~1206–1208): non-budget errors during enforce are hard stops when the current prompt is over budget (at minimum: re-check `estimate(prompt_str) <= hard_limit.input_budget` before invoke; if unknown limit, halt).

2. **Eliminate silent early-return of unchecked prompts**
   - Replace `return prompt_str, shaped_messages, None` fail-opens with halt/raise when over budget (or when budget cannot be resolved while a serialized prompt exists).
   - Add regression tests that patch: (a) non-dict config, (b) resolve boom, (c) `fit_final_prompt` unexpected `RuntimeError` — assert provider/`stream_generate` is **not** called and loop stops with budget/enforcement failure.

3. **Propagate fitted components into loop locals**
   - When `_final_fit` is not None and compressed (or whenever fit mutates components): assign `system_prompt`/`tool_prompt`/`skill_prompts` (and pinned/memory if applicable) from the fit so subsequent rebuilds cannot re-inflate past the fitted prefix.
   - Add a multi-step regression: after a shrink of system on step 1, step 2 rebuild must not restore the pre-fit system blob.

4. **Evidence / checklist**
   - Uncheck failed CTX-02 checklist lines (#2 hard re-check / fail-open) until re-review.
   - Re-submit with new Result SHA; do not self-APPROVE; **do not start CTX-03**.

## Residual (non-blocking for this REJECT, track)

- Legacy `_maybe_compress_context` catch-all fail-open remains; acceptable as CTX-03 **only after** final gate is fail-closed.
- Plan “citation provenance” has no dedicated protection rank (TOOL_EVIDENCE-focused); consider explicit citation marker protection or document residual.
- `metadata.json` tip_sha lagged HEAD during review (owner docs tip vs `8a0d845`); refresh on resubmit.

## Evidence

- `.omo/evidence/commercial-ga-100/CTX-02/adversarial-verify.txt`
- `.omo/evidence/commercial-ga-100/CTX-02/tests-verify-rerun.txt` (8 passed)
- `.omo/evidence/commercial-ga-100/CTX-02/tests-verify-related.txt` (67 passed)
- `.omo/evidence/commercial-ga-100/CTX-02/ruff-verify.txt`
