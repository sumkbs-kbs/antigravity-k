# CTX-03 re-review request

Owner: `ctx_03_observability`
Reviewer requested: `ctx_03_verify` (Owner≠Reviewer)

Please independently re-run:
- `pytest tests/test_ctx03_compress_observability.py tests/test_ctx02_reject_fixes.py tests/test_final_prompt_budget.py tests/test_tool_loop.py::TestToolLoopEngineContextCompression`
- ruff on touched files
- adversarial probes: compress exception under/over limit; UI event mapping; no fail-open to provider

Do **not** mark APPROVE unless fail-open residual is gone and telemetry/UI/ops thresholds match docs/12.
