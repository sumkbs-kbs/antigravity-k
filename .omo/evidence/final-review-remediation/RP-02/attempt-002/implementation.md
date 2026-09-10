# RP-02 attempt-002 implementation

## Defect

`shlex.split` kept attached shell redirections and their target together. For
example, `echo PWNED >/tmp/sentinel` became `>/tmp/sentinel`, so the existing
absolute-path detector did not inspect `/tmp/sentinel` and `PermissionGate`
allowed the command.

## Change

`iter_shell_escape_path_candidates` now tokenizes shell punctuation and feeds
the target following `>`, `>>`, `<`, or `<>` into the pre-existing canonical
containment check. The change preserves in-root attached redirection.

## Scope

The OS sandbox remains the execution boundary. This change closes the fast,
explicit permission denial required for attached redirection syntax before
execution is authorized.
