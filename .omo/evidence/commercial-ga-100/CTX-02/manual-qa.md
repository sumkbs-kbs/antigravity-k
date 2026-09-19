# CTX-02 manual QA (owner)

Surface: final prompt budget unit + tool_loop enforce gate (no live provider required for gate).

1. `uv run pytest tests/test_final_prompt_budget.py tests/test_ctx02_reject_fixes.py` → **14 passed** (prior 8 + F1–F3 regressions).
2. Related: context_budget / enforcer / shaper / tool_loop (deselect 3 pre-existing unrelated) → **156 passed**.
3. Confirmed fail-closed: non-dict config / resolve boom / fit RuntimeError → no `stream_generate`.
4. Confirmed F3: fitted system written back; rebuild path does not restore pre-fit aux blob.
5. ruff clean on `tool_loop.py` / `context_budget.py` / new tests.

Secrets: none. No user data in evidence. **Not APPROVE.**
