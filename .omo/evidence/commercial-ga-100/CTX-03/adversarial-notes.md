# CTX-03 adversarial notes (owner self-check; not APPROVE)

1. adaptive_compress raises → ContextCompressAttempt.failed=True (not silent success).
2. compress fail + under hard limit → degraded UI/event; stream_generate may still run.
3. compress fail + fit_final_prompt PromptBudgetExceededError → halted; stream_generate call_count 0.
4. Telemetry payload always includes tokens_before/after, strategy, digest, elapsed_ms, failure_code, alert_thresholds.
5. UI maps context.compress.succeeded→completed, .degraded→degraded, .halted→failed.
6. No catch-all Exception path returns original prompt without failed=True marking.
