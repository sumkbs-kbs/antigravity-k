# Final Quality Review — conversation and prompt pipeline

- Reviewed commit: `8794aaecabf5664a7ee560b104e0115d915aabb7`
- Scope: authoritative conversation storage, revision protocol, context compression, and final serialized-prompt budget enforcement.
- Verdict: **REQUEST CHANGES** (`BLOCK`)

## Evidence reviewed

- Code graph discovery and call-path inspection for `ConversationStore`, `ToolLoopEngine._enforce_final_prompt_budget`, `fit_final_prompt`, and the chat/conversation routes.
- `uv run pytest -q tests/test_final_prompt_budget.py tests/test_ctx02_reject_fixes.py tests/test_ctx03_compress_observability.py tests/test_conversation_store_ctx01.py tests/test_conversation_api_ctx01.py tests/test_val02_conversation_multiprocess.py` — **34 passed**.
- `uv run ruff check` on the reviewed production and test files — **passed**.

The plain `pytest` invocation cannot collect this package because it does not put `src/` on `sys.path`; the project-supported `uv run pytest` command above was used instead.

## Findings

### HIGH — cached cross-process reads and revision checks are not authoritative

[conversation_store.py:182](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/conversation_store.py:182), [conversation_store.py:220](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/conversation_store.py:220), and [conversation_store.py:224](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/conversation_store.py:224) read the process-local cache without the cross-process lock or a disk refresh. By contrast, `append` refreshes inside the flock at [conversation_store.py:304](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/conversation_store.py:304). Therefore a long-lived worker returns stale history/revision after another worker writes it, and `get_or_create` accepts an old expected revision.

Reproduction on this commit: [`reproduce_conversation_store_stale_cache.py`](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/docs/qa/2026-09-10/reproduce_conversation_store_stale_cache.py) runs with `uv run python docs/qa/2026-09-10/reproduce_conversation_store_stale_cache.py`; its captured output is [`reproduce_conversation_store_stale_cache.output.txt`](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/docs/qa/2026-09-10/reproduce_conversation_store_stale_cache.output.txt). It creates two stores over one temporary directory, populates the reader cache at revision 1, and appends revision 2 through the writer. The reader still returns revision 1 and one message; `get_or_create(..., expected_revision=1)` returns normally; a fresh reader sees revision 2 and two messages.

This breaks the stated authoritative-history/revision-CAS contract for multi-worker server deployments. The existing multi-process test covers append only, so it cannot detect stale reads or stale no-new-turn requests.

### MEDIUM — final-prompt fitting is an oversized, high-complexity policy function

[context_budget_enforcer.py:268](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/context_budget_enforcer.py:268) is 342 lines according to the graph, with cognitive complexity 62; the module is 513 pure LOC. It combines serialization, dual accounting, mutable-suffix fitting, prefix fitting, single-component fallback, error policy, and result assembly. The nested helpers also close over mutable state. This makes the hard-limit policy hard to safely extend or audit, especially because [tool_loop.py:933](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/tool_loop.py:933) has a second 189-line implementation-facing wrapper around it.

This is a maintainability finding; focused behavioral tests passed and I did not identify a direct budget bypass from it.

### MEDIUM — a test pins implementation constants instead of an observable contract

[test_ctx03_compress_observability.py:102](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/tests/test_ctx03_compress_observability.py:102) asserts the literal implementation values `0.05` and `15.0`, then re-computes their simple helper outcome. It will fail on a legitimate operations-policy adjustment while providing no protection that telemetry is emitted, routed, or alerted on. Test an externally consumed configuration/alerting behavior, or remove this constant-pin test.

### LOW — multiprocess append test does not fully assert its declared invariant

[test_val02_conversation_multiprocess.py:68](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/tests/test_val02_conversation_multiprocess.py:68) permits `final_count > appended` even though this clean-store test has no initial messages. The documented invariant at line 9 says successful appends equal final messages. Equality would catch unexpected duplicate/phantom writes and make the evidence match the contract.

### CRITICAL

None found.

## Skill-perspective check

Ran the required `omo:remove-ai-slops` and `omo:programming` skill review perspectives before evaluating test relevance and maintainability.

- `remove-ai-slops`: violated by the oversized final-prompt module and by the implementation-constant test. I found no deletion-only test and no prose/prompt-text assertion in the focused test set.
- `programming`: violated by the same brittle constant-pin test and by the policy concentration described above. The production code uses a narrow `# type: ignore[arg-type]` in [conversation_store.py:518](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/conversation_store.py:518); it is not the basis for this verdict because runtime role validation precedes it, but it remains an avoidable typed escape hatch.

## Limits

This was a static and focused-test review of the current HEAD. It did not run the entire repository suite, live provider calls, or a multi-worker HTTP deployment. The reproduced stale-cache failure uses two store instances over the same persisted directory, which is the storage pattern used by the stated multi-process contract.
