# RP-03 Attempt 002 Verification

Start SHA: `8794aaecabf5664a7ee560b104e0115d915aabb7`

Changed source is loaded with `PYTHONPATH=src`; plain `uv run` selected the installed baseline package during this attempt and is not used for the green result.

| Success criterion | Scenario and invocation | Binary observable | Captured artifact |
| --- | --- | --- | --- |
| Red proof | `uv run --no-sync pytest -q tests/test_fr03_transaction_containment.py::TestCommitReverification::test_symlink_swap_after_preflight_cannot_redirect_write` before the no-follow implementation | FAIL: `TransactionResult(... committed=True ...)` | `red-symlink-toctou.txt` |
| Traversal, outside absolute path, outside symlink, and symlink-parent new leaf rejection | `PYTHONPATH=src uv run --no-sync pytest -q tests/test_atomic_transaction_engine.py tests/test_fr03_transaction_containment.py` | PASS: `13 passed`; the suite includes each rejection case | `targeted-tests.txt` |
| Resolve-to-write symlink swap | Same source-loaded command, node `TestCommitReverification::test_symlink_swap_after_preflight_cannot_redirect_write` | PASS: `1 passed` in each of five runs; the test swaps a real temporary leaf into an outside symlink immediately before the safe open | `toctou-repeat.txt` |
| Failure rollback, original empty-file preservation, new-file removal, unrelated-file preservation, and foreign-edit conflict | `PYTHONPATH=src uv run --no-sync pytest -q` with the three FR-03 adversarial node IDs | PASS: `3 passed` | `adversarial-scenarios.txt` |
| Public API temporary-directory end-to-end path | Source-loaded Python driver stages traversal, swaps a staged target to an external sentinel symlink before commit, then commits two in-root files | JSON has `traversal_rejected: true`, `swap_committed: false`, `sentinel_sha256_unchanged: true`, `two_file_commit: true`, and `tempdir_cleanup: true` | `tempdir-e2e.txt` |
| Static and formatting checks | `uv run --no-sync ruff check src/antigravity_k/engine/atomic_transaction_engine.py tests/test_fr03_transaction_containment.py` | PASS: `All checks passed!` | `ruff.txt` |
| Type diagnostics | `uv run --no-sync basedpyright src/antigravity_k/engine/atomic_transaction_engine.py tests/test_fr03_transaction_containment.py` | PASS: `0 errors`; 21 test-fixture warnings remain, including three test-only protected-helper seam warnings | `basedpyright.txt` |
| Diff integrity | `git diff --check` | PASS: empty output and exit 0 | `diff-check.txt` |

Adversarial coverage: malformed path inputs and symlink replacement are rejected; the deterministic race test ran five times without a timing wait; the E2E sentinel hash prevents an exit-code-only false green; the inherited dirty worktree was observed without reset, and the foreign-edit regression preserves a concurrent change. Prompt injection, cancellation/resume, generated-cache stale state, and hung external commands do not apply to this local synchronous filesystem transaction.

Cleanup receipt: the end-to-end driver uses `TemporaryDirectory` and reports `tempdir_cleanup: true`; no server, process, port, browser, or persistent temporary resource was created.
