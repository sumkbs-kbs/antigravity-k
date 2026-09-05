# Release Baseline Policy

## Scope

Every release candidate starts from `THIRD_PARTY_PROVENANCE.toml`. The file is
the source of truth for pinned analysis baselines, entrypoints, distribution
roots, prohibited licenses, and prohibited packages.

## Upstream provenance

An upstream may be consulted for design or interoperation, but files are copied
into Ssak-Ai only after being listed in `copied_files` with their upstream
path, destination path, and applicable license. An empty `copied_files` list is
the required default. Updates to the upstream pin require a new pinned commit
SHA and a fresh review of the copied-file list.

## SBOM

The Python SBOM is generated from the exact content of `uv.lock`; the dashboard
SBOM is generated from the exact content of `dashboard/package-lock.json`.
Generation happens at release packaging time, not at development time, so the
SBOM cannot drift from the checked-in lockfiles. Package names and versions come
from the lockfiles; licenses and notice text come from package metadata supplied
by the resolver, never from a manually edited table.

The release validator rejects a lockfile containing a package named by
`distribution.prohibited_python_packages`. It also scans all distribution source
roots for the license markers listed by `distribution.prohibited_spdx`.

## NOTICE

`NOTICE` identifies the project license and the pinned, non-copied upstream
baselines. Dependency-specific notices are generated into the release package
from the SBOM. A release is invalid if its generated notices omit a package
that declares a notice file or a non-identical license text.

## Entrypoints

The runtime, CLI, HTTP API, and web entrypoints listed in the provenance file
must resolve to real files. A release candidate is rejected when an entrypoint
name, command, or source path is removed without updating the inventory. The
inventory is intentionally not exhaustive at the route level; it pins the
surfaces used by the release baseline gate.

## Blind held-out evaluation

Every versioned file under `data/benchmarks/held_out_*.jsonl` and its matching
`.freeze.json` record is frozen before model training. The release baseline
requires both shipped v1 and v2 assets and validates each dataset's SHA-256,
row count, ordered case IDs, and `forbidden_for_training` flags against its
freeze record. The training dataset builder must reject a frozen path and any
file whose SHA-256 digest appears in a held-out record. Results from these sets
are never used for prompt, recipe, router, or checkpoint selection; they are
reported only as final held-out evaluation. Any change requires a new versioned
held-out file and leaves the old freeze immutable.
