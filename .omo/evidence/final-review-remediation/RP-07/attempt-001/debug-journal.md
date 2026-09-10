# RP-07 debug and evidence journal

## Artifacts to revert or clean
- Temporary build output and isolated virtual environment created under `/tmp`; remove after evidence capture.
- Captured command logs under this attempt directory; retain as retrievable evidence.

## Scope
- Owned source files: `config.yaml`, `src/antigravity_k/config.yaml`, `pyproject.toml` only if required, `tests/test_model_registry.py` only if required.
- Do not edit checklist/progress documents or unrelated files.

## Hypotheses
1. The packaged source config is stale relative to the repository root, causing the equality test and installed defaults to diverge.
2. The root `agent` section may be unused or may be required by UnifiedAgent/CLI startup defaults; consumer traces will distinguish this.
3. Packaging metadata may omit `config.yaml`, causing a separate installed-resource failure even after content synchronization.
