# RP-06 implementation

`_record` now treats an explicit top-level `False` in a scenario detail mapping as an assertion failure. This closes the remaining false-green path after the target/control Chroma checks: a scenario cannot communicate a failed boolean condition while its outer record remains successful.

The pre-existing RP-06 work uses Chroma `source` metadata for target/control readback, validates restart/reindex/citation assertions, and makes missing required scenarios fail the CLI. This retry fixed the verifier's false-boolean aggregation gap and repaired three type errors exposed in the owned staging script without changing product behavior.

The validation is intentionally scoped to the staging verifier. Running the whole VAL-01 workload would require the unavailable Ollama/training hardware scenarios and is not represented as a pass.
