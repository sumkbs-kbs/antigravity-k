# RP-06 manual QA

| Scenario | Invocation | Binary observable | Raw artifact |
|---|---|---|---|
| Healthy persistent Chroma | `uv run --no-sync python -` loading `_chroma_scenarios` on a temporary persistent directory | `all_ok=true`; delete target count is `0`; control count is `1` | `logs/manual-chroma-healthy.json` |
| No-op delete negative control | Same real Chroma invocation with `VectorStore.delete_file_chunks` replaced only for the run | `negative_control_detected=true`; reindex and delete records fail | `logs/manual-chroma-noop-negative.json` |
| Missing-required CLI verdict | `val01.main()` with a staging artifact containing `missing_required=[chroma_delete]` | Printed JSON retains the missing scenario and `CLI_EXIT_CODE=1` | `logs/manual-cli-fail-closed.log` |

Temporary Chroma directories are pytest/tempfile fixtures and have no persistent service or port to tear down.
