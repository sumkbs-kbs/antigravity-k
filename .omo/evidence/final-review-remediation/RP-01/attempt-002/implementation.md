# RP-01 attempt-002 implementation

`UnifiedAgent._run_test_suite` is the sole test-code execution seam. It calls `run_sandboxed_argv` with an explicit pytest argv and a minimal child environment. `_run_code` and `_run_code_consistent` now both call that seam; sandbox refusal, timeout, and unsandboxed execution return failure feedback instead of host fallback.

`run_sandboxed_argv` constructs an enabled, network-disabled, read-restricted `SandboxRunner`, canonicalizes its workspace and explicit read paths, and never inherits `os.environ` when no environment is supplied. The seatbelt restricted profile permits the workspace and necessary interpreter prefixes, denies the user tree and shared temporary roots, and permits writes only inside the workspace plus `/dev/null`.

The regression suite uses a real `sandbox-exec` backend on this macOS host. It verifies normal and failing model tests, both UnifiedAgent code routes, no-execution backend failure, synthetic-secret noninheritance, external read/write rejection, loopback rejection, timeout process-group cleanup, and bounded output. The test-only graphify stub prevents graph embeddings/MPS work from masking the sandbox scenario.

During source-import validation, Docker cwd containment misclassified `/tmp/proj/sub`: the root was canonicalized to `/private/tmp/proj`, while cwd was not. `_execute_docker` now canonicalizes cwd before `relpath`, retaining both internal acceptance and external rejection. The red and green proof is in `logs/rp02-reported-source-import-red.txt` and `logs/rp02-source-import-docker-cwd-green.txt`.

The clean-HEAD red proof preserves the original host-secret leak in `logs/red-clean-head-host-secret.txt`; the current boundary turns the same scenario green in `logs/green-current-host-secret.txt`.
