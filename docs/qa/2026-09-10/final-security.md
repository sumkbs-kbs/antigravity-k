# Final security review

Reviewed SHA: `8794aaecabf5664a7ee560b104e0115d915aabb7` (`codex/m1-task-events` at review start)

Scope: current implementation of HTTP/SSE/WS authentication, project and shell path containment, mutation fail-closed behavior, shared-vault rollback, and the post-RC unified-agent API. The SHA's own diff only reformats two generated dashboard bundle assets; this review therefore inspected the live security-critical implementation rather than treating that small diff as evidence of system safety.

## Result

**BLOCK — REQUEST CHANGES.** Four HIGH findings remain. No CRITICAL findings were identified.

## Findings

### CRITICAL

None.

### HIGH

1. **Authenticated `/api/agent/ask` executes caller-provided Python outside the sandbox.**

   - [agent_ask.py](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/api/routes/agent_ask.py:35) accepts `test_code` from an HTTP request and passes it directly to `UnifiedAgent.run` ([line 48](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/api/routes/agent_ask.py:48)). The HTTP middleware authenticates this endpoint, but does not grant a separate code-execution capability or sandbox it.
   - [unified_agent.py](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/unified_agent.py:209) writes that untrusted value to `test_solution.py`, then [runs pytest with the host interpreter](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/unified_agent.py:210). The same direct-host execution is duplicated in the adaptive path at [line 276](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/unified_agent.py:276). It passes the inherited environment at [line 227](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/unified_agent.py:227), including any credentials available to the server process.
   - An authenticated caller can supply test module import-time code. A temporary `cwd` does not isolate host filesystem access, subprocess creation, environment secrets, or network access. Route all supplied/generated test execution through the existing fail-closed sandbox boundary with a minimal environment and resource limits, or remove the HTTP-supplied execution feature.
   - Existing [agent ask tests](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/tests/test_agent_ask_api.py:31) mock `UnifiedAgent.run`; they never prove that supplied `test_code` cannot escape its workspace.

2. **Shell project-root containment is bypassable with environment-variable expansion.**

   - [tool_path.py](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/tools/tool_path.py:284) only considers lexical absolute paths, `~`, and `..` components. Shell variables such as `$HOME/outside` and `${HOME}/outside` do not meet any of those tests.
   - [permission_gate.py](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/tools/permission_gate.py:151) relies on that incomplete parser before allowing commands. [terminal_tools.py](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/tools/terminal_tools.py:118) retains a `shell=True` fallback, so the shell expands the unchecked variable when the command executes.
   - Isolated policy probe (no command executed) confirmed both `printf x > "$HOME/ssak_review_probe"` and `printf x > "${HOME}/ssak_review_probe"` receive `allow` from an auto-pilot `PermissionGate` whose root is `/tmp/ssak-security-contained-root`.
   - Do not use token inspection as a containment boundary for a shell language. Make the sandbox enforce the filesystem boundary, reject shell expansion constructs entirely, or replace arbitrary shell strings with a structured argv API whose path operands are resolved before execution. Add adversarial tests for variable, command-substitution, glob, and redirection expansion.

3. **`AtomicTransactionEngine` permits transaction paths to write outside its project root.**

   - [atomic_transaction_engine.py](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/atomic_transaction_engine.py:50) joins the supplied `rel_path` without resolving it or checking containment, and [line 80](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/atomic_transaction_engine.py:80) writes to the same unchecked result. `../` traversal and symlink parents therefore escape `project_root`.
   - Isolated reproduction: with a temporary directory containing `project/`, staging `../outside.py` and committing returned `committed=True` and created the sibling `outside.py`. No user files were touched.
   - Resolve every target using the canonical containment helper before reading, creating parents, writing, or rollback. Preserve whether a target existed as explicit metadata so rollback does not treat an existing empty file as a newly created one. Add traversal and symlink tests; current [tests](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/tests/test_atomic_transaction_engine.py:9) cover only in-root happy and syntax-error paths.

4. **RSI rollback discards the entire shared working tree, including unrelated work.**

   - `safe_mutation` unconditionally invokes rollback after a mutation exception at [rsi_sandbox.py](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/rsi_sandbox.py:418). `rollback_to` runs `git checkout <snapshot> -- .` at [line 239](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/rsi_sandbox.py:239), not a rollback limited to files actually staged by that mutation.
   - This overwrites all tracked changes made after the snapshot: concurrent agent work, a user's local edits, and unrelated subsystem changes. The snapshot stores a file list at [lines 213-224](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/rsi_sandbox.py:213), but rollback ignores it and the list is not a mutation-owned scope.
   - Capture the exact mutation-owned paths and their preimages in an isolated worktree or transaction, then restore only that scope while holding an appropriate cross-process lock. Treat inability to establish that isolation as fail-closed before mutation. The current [rollback test](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/tests/test_rsi_family.py:349) replaces `rollback_to` with a mock, so it cannot detect destructive rollback behavior.

### MEDIUM

None.

### LOW

None.

## Checks and evidence

- Skill-perspective check: **ran**. I loaded `omo:programming` and `omo:remove-ai-slops` before maintainability/test assessment. The diff does not introduce deletion-only, prose, tautological, or implementation-constant tests. It does violate both perspectives where the unified-agent endpoint adds direct validation/execution complexity at the wrong boundary and its tests mock the safety-critical behavior instead of testing the observable sandbox boundary.
- Graph-first check: the mandated codebase-memory MCP graph tools were not available in this session. Discovery therefore used bounded literal searches and direct call-site inspection.
- HTTP/SSE/WS auth: verified the HTTP middleware protects `/api/`, `/v1/`, `/ws/`, and `/ide/` paths ([server.py](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/api/server.py:421)); WebSocket routes invoke the shared gate and enforce origin before ticket/bearer credential checks ([session_state.py](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/api/routes/session_state.py:55)). No separate auth bypass was confirmed in the reviewed routes.
- Vault privacy mutations use path-scoped Git restore and a cross-process lock ([vault_privacy.py](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/vault_privacy.py:35), [vault.py](/Users/mr.k/program/coding/ssak_comp/Ssak-Ai/src/antigravity_k/engine/vault.py:116)); no independent shared-vault privacy rollback defect was confirmed there.
- Focused regression command `PYTHONPATH=src pytest -q tests/test_atomic_transaction_engine.py tests/test_agent_ask_api.py tests/test_unified_agent.py` passed: **15 passed** in 1.89s. The passing tests do not exercise the four adversarial cases above. The two containment probes are self-contained and confirmed.

## Recommendation

`codeQualityStatus: BLOCK`

`recommendation: REQUEST_CHANGES`

Blockers: sandbox or remove HTTP-supplied test execution; close shell-expansion containment bypass; enforce canonical project-root containment in `AtomicTransactionEngine`; replace whole-tree RSI rollback with mutation-scoped isolation and restoration.
