# Manual filesystem QA

Scenario: run the normal `MetaArchitect.execute_proposal` callback against a newly initialized temporary Git repository. The repository begins with committed `src/antigravity_k/engine/owned.py` and `B.py`; B is then made user-dirty and C is created untracked. The proposal's generated content is syntactically invalid so the real AST validation fails after the delegated callback writes `owned.py`.

Invocation: `PYTHONPATH=src uv run --no-sync python .omo/evidence/final-review-remediation/RP-04/attempt-002/manual-qa-driver.py`.

PASS is binary: `execute_proposal` is `false`; `owned_restored`, `dirty_preserved`, `untracked_preserved`, `git_status_has_dirty_B`, `git_status_has_untracked_C`, and `temp_repo_removed` are all `true`.

Observed output is in [logs/manual-qa-source.txt](logs/manual-qa-source.txt). The traceback resolves to `src/antigravity_k/engine/meta_architect.py`, confirming source rather than the installed wheel ran.
