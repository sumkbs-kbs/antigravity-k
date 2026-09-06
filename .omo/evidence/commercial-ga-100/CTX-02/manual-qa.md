# CTX-02 manual QA (owner)

Surface: final prompt budget unit path (no live provider required for gate).

1. `uv run pytest tests/test_final_prompt_budget.py` → 8 passed (5+1005, digest, prefix, evidence, oversized).
2. Related: context_budget / enforcer / shaper / tool_loop compress subset → green.
3. Confirmed tool_loop raises/stops on PromptBudgetExceededError / OversizedPromptComponentError before stream_generate.
4. Confirmed shape_for_model accepts aux_token_overhead so prepare_agent_prompt leaves room for system/tools/skills/pinned.

Secrets: none. No user data in evidence.
