# RP-07 implementation

The bundled package configuration now contains the same `agent` default block as root `config.yaml`: `default_entry=unified`, `headroom=true`, `max_repairs=2`, and `adaptive=true`. `pyproject.toml` already packages `config.yaml`, so no packaging refactor was needed.

The package resource was validated from a newly built wheel in an isolated environment outside the checkout. `ModelRegistry._default_config_path()` resolved to the installed package resource and `agk --help` completed without a provider connection.

Consumer trace: UnifiedAgent's code defaults are `headroom=True` and `max_repairs=2`, while the CLI/API expose the unified entry and adaptive mode. They do not currently parse the top-level YAML `agent` mapping directly. This attempt proves source/bundle/installed resource parity; adding new configuration wiring is outside the requested minimal packaging change.
