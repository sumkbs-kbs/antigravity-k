# CTX-02 adversarial notes (owner self-check; not APPROVE)

1. 5-token message + 1005-token aux under operator limit 1000 → compressed ≤1000; latest user stub retained.
2. Identical inputs → identical selection digest (sha256) and serialized bytes.
3. Mutable-only compression keeps System+skills+tools cache prefix byte-identical.
4. Structured `[TOOL_EVIDENCE]` / `VERIFIED_RESULT` survives final fit under tight budget.
5. Single oversized component → bounded result or OversizedPromptComponentError / PromptBudgetExceededError; provider not called on typed exceed in tool_loop.
6. Residual (CTX-03): fail-open compress catch-all still exists elsewhere; telemetry/UI for ledger not yet wired as product events.
