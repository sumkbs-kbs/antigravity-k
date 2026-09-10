# RP-02 / attempt-002 handoff

Status: INCOMPLETE

The RP-02-owned attached-redirection bypass is fixed and its source-imported
targeted suite passes. `shlex.split` had retained `>/tmp/file` as one token,
so the lexical candidate detector never examined the target. The replacement
tokenizes shell punctuation and passes targets following `>`, `>>`, `<`, and
`<>` to the existing canonical containment check.

The live macOS seatbelt manual QA is captured in
`logs/manual-qa-seatbelt.txt`: an external sentinel write failed with
`Operation not permitted`, its digest remained unchanged, and a command started
under project-a wrote there even after the parent cwd switched to project-b.
Both terminal and temporary-profile registries were empty after collection.

The RP-02 targeted source suite is `40 passed` in
`logs/regression-rp02-source-pytest.txt`. `basedpyright` found `0 errors` in
`logs/basedpyright-rp02.txt`.

Completion is blocked by a source-imported shared-sandbox regression outside
this assignment: `tests/test_sandbox_isolation.py::TestDockerCwdConfinement::test_cwd_inside_project_root_is_accepted`
fails in RP-01-owned `src/antigravity_k/engine/sandbox.py` because `/tmp/proj`
and `/tmp/proj/sub` are compared after only one side canonicalizes the macOS
`/tmp` symlink. The full command and raw failure are in
`logs/regression-source-pytest.txt`; the coordinator was notified.

No docs status file was modified. No persistent QA process, temporary QA root,
or temporary terminal profile remains; receipt: `logs/cleanup-receipt.txt`.

## Coordinator addendum (2026-09-10, attempt-002 follow-up)

Blocker resolved. The failing `TestDockerCwdConfinement` was NOT a source-tree
regression in `sandbox.py`: the repository `.venv` held a stale site-packages
copy of `antigravity_k` (snapshot 19:56, installed from the sibling checkout
`../antigravity-k`) which shadowed the source tree for plain `uv run` imports.
The project has been reinstalled editable into `.venv` (`uv pip install
--python .venv/bin/python -e . --no-deps` after removing the stale copy), so
imports now resolve to `Ssak-Ai/src`.

Verification after the fix:
- `uv run --no-sync pytest -q tests/test_sandbox_isolation.py tests/test_sandbox.py`
  → 35 passed (the previously failing node now passes).
- Full FR-01..07 regression rerun → 84 passed.

Status raised INCOMPLETE → REVIEW accordingly (independent review still RP-14).
