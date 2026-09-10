# RP-06 debugging journal

## Artifacts to retain

- Raw test and manual-CLI output in `logs/` is retained as evidence.
- Temporary Chroma persistence directories are created by pytest's `tmp_path` and removed by pytest.

## Hypotheses

1. `_record` treats every non-exception detail mapping as success, so a scenario can return an explicit `False` and still pass.
2. Chroma's `delete_file_chunks` could ignore a delete request; the new target/control readback checks must make that observable as a failed scenario.
3. Required scenario accounting could allow a partial suite to return exit code zero; the required-scenario list must prevent that.

## Observations

- `tests/test_fr07_staging_verdicts.py::TestRecordSemantics::test_false_detail_bool_marks_failure` fails before this fix: `ScenarioRecord(... ok=True, detail={'deleted_file_unsearchable': False})`.
- The source delete path is invoked by the staging scenario and uses `where={\"source\": file_path}` in the strict VectorStore path; target/control readback therefore uses the same source identity.

## Root cause

`_record` converts a normal return value to a successful `ScenarioRecord` without checking boolean verdict fields. A no-op delete can therefore be represented by a false detail value while the top-level staging summary still counts it as passed.
