# RP-07 debugging journal

## Artifacts to retain

- Fresh wheel/sdist, isolated environment transcripts, and hashes are retained under this attempt directory.
- The isolated virtual environment and temporary directory will be removed after logs are captured.

## Hypotheses

1. The bundled `src/antigravity_k/config.yaml` could drift from root `config.yaml`.
2. `pyproject.toml` package-data could omit the bundled configuration despite source equality.
3. An installed wheel could import the checkout instead of its site-packages resource.

## Observations

- The existing equality regression passes only after the bundled config receives the root `agent` section.
- `pyproject.toml` declares `config.yaml` as `antigravity_k` package data.
- CLI and API UnifiedAgent construction select a registry default model and expose adaptive mode separately; the resource test records the documented `agent` defaults and verifies package-resource availability.
