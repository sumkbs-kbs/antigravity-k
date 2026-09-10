# RP-04 implementation record

The baseline `RSISandbox.rollback_to` issued `git checkout <commit> -- .`. In a shared checkout this restores every tracked path, including another user's dirty B, even when the mutation only touched A.

The carried RP-04 implementation replaces the tree-level recovery with a mutation-owned transaction: `write_owned` records each target's preimage, whether it existed, original mode, and the bytes written by the mutation. `rollback_to` restores only entries whose current bytes still equal the mutation's last write. A changed owned path is retained as a conflict; an originally absent path is removed only when it still contains the mutation's bytes. Empty originals remain present and empty.

`MetaArchitect.execute_proposal` now writes proposed engine files through `RSISandbox.write_owned`, so the actual delegated code-mutation path participates in the transaction. This attempt adds a regression for that caller. It uses a deterministic validation failure and a real temporary Git repository; no rollback method or file system write is mocked.

The design is the plan's approved ownership/preimage transaction alternative to a dedicated worktree. Its safety boundary is explicit: writes that bypass `write_owned` are deliberately not claimed as rollback-owned and cannot be restored by this transaction.

The source tree must be forced ahead of the installed wheel with `PYTHONPATH=src` during verification. Without it, `uv run python` imports `.venv/site-packages`, which would not prove the dirty source implementation.
