# RP-07 manual QA

| Scenario | Invocation | Binary observable | Raw artifact |
|---|---|---|---|
| Source contract | `uv run --no-sync python -` compares config bytes and parses `agent` | `source_bytes_equal=True` and four expected defaults | `logs/source-config-contract.log` |
| Fresh distributables | `uv build --out-dir .../artifacts`, then `tar`/`unzip` listings | Wheel and sdist both list `antigravity_k/config.yaml` | `logs/uv-build.log`, `logs/wheel-config-listing.log`, `logs/sdist-config-listing.log` |
| Installed CLI/resource | Isolated `uv venv`, wheel install, outside-checkout Python resource/registry driver, then `agk --help` | All import/resource paths are under `site-packages`; defaults match; help exits 0 | `logs/isolated-install-smoke.log` |

The temporary isolated environment was deleted in the smoke invocation; its receipt is `CLEANUP=isolated virtual environment removed`.
