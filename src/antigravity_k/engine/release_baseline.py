from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path
from typing import ClassVar, Final, cast

from pydantic import BaseModel, ConfigDict, Field


class UpstreamProvenance(BaseModel):
    repository: str
    commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    license_spdx: str
    copied_files: tuple[str, ...]
    integration: str


class EntrypointInventory(BaseModel):
    name: str
    kind: str
    command: tuple[str, ...] = Field(min_length=1)
    source_path: str


class DistributionInventory(BaseModel):
    source_roots: tuple[str, ...] = Field(min_length=1)
    manifest_roots: tuple[str, ...] = Field(min_length=1)
    prohibited_spdx: tuple[str, ...] = Field(min_length=1)
    prohibited_python_packages: tuple[str, ...] = Field(min_length=1)


class ReleaseBaseline(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    schema_version: int
    pinned_at: str
    upstreams: tuple[UpstreamProvenance, ...] = Field(min_length=1)
    entrypoints: tuple[EntrypointInventory, ...] = Field(min_length=1)
    distribution: DistributionInventory


class ReleaseBaselineError(ValueError):
    """A release-baseline file or distribution violates release policy."""


_REQUIRED_FILES: Final[tuple[str, ...]] = (
    "THIRD_PARTY_PROVENANCE.toml",
    "NOTICE",
    "docs/RELEASE_POLICY.md",
    "docs/adr/0001-single-task-runtime-and-event-store.md",
    "data/benchmarks/held_out_v1.jsonl",
    "data/benchmarks/held_out_v1.freeze.json",
    "data/benchmarks/held_out_v2.jsonl",
    "data/benchmarks/held_out_v2.freeze.json",
)

_HELD_OUT_DATASETS: Final[tuple[str, ...]] = ("held_out_v1.jsonl", "held_out_v2.jsonl")
_JsonObject = dict[str, object]


def load_release_baseline(project_root: Path) -> ReleaseBaseline:
    path = project_root / "THIRD_PARTY_PROVENANCE.toml"
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        message = f"Could not read release baseline at {path}: {error}"
        raise ReleaseBaselineError(message) from error
    try:
        return ReleaseBaseline.model_validate(raw)
    except ValueError as error:
        message = f"Invalid release baseline at {path}: {error}"
        raise ReleaseBaselineError(message) from error


def validate_release_baseline(baseline: ReleaseBaseline, project_root: Path) -> None:
    if baseline.schema_version != 1:
        raise ReleaseBaselineError(f"Unsupported release baseline schema: {baseline.schema_version}")

    for relative_path in _REQUIRED_FILES:
        path = project_root / relative_path
        if not path.is_file():
            raise ReleaseBaselineError(f"Required release artifact is missing: {relative_path}")

    for entrypoint in baseline.entrypoints:
        path = project_root / entrypoint.source_path
        if not path.is_file():
            raise ReleaseBaselineError(f"Entrypoint source is missing: {entrypoint.source_path}")

    for root_name in (*baseline.distribution.manifest_roots, *baseline.distribution.source_roots):
        root = project_root / root_name
        if not root.is_dir():
            raise ReleaseBaselineError(f"Distribution root is missing: {root_name}")

    _validate_no_prohibited_source_text(baseline, project_root)
    _validate_python_lock(baseline, project_root)
    _validate_held_out_manifests(project_root)


def _validate_no_prohibited_source_text(baseline: ReleaseBaseline, project_root: Path) -> None:
    prohibited = frozenset(baseline.distribution.prohibited_spdx)
    agpl_ids = tuple(spdx for spdx in prohibited if spdx.upper().startswith("AGPL"))
    readable_agpl_marker = ".".join(("GNU", "AFFERO", "GENERAL", "PUBLIC", "LICENSE"))
    marker_pairs: tuple[tuple[str, str], ...] = ()
    if agpl_ids:
        marker_pairs += (
            (agpl_ids[0], readable_agpl_marker),
            (agpl_ids[0], readable_agpl_marker.replace(".", " ")),
        )
    validator_path = Path(__file__).resolve()
    marker_pairs += tuple((spdx, spdx.upper()) for spdx in prohibited if not spdx.upper().startswith("AGPL"))

    for root_name in baseline.distribution.source_roots:
        root = project_root / root_name
        for path in root.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            if path.resolve() == validator_path:
                continue
            content = path.read_bytes()
            for spdx, marker in marker_pairs:
                if marker.encode("utf-8") in content:
                    relative = path.relative_to(project_root).as_posix()
                    message = f"Prohibited license marker {spdx} found in {relative}"
                    raise ReleaseBaselineError(message)


def _validate_python_lock(baseline: ReleaseBaseline, project_root: Path) -> None:
    lock_path = project_root / "uv.lock"
    if not lock_path.is_file():
        raise ReleaseBaselineError("Python lockfile is missing: uv.lock")
    lock_text = lock_path.read_text(encoding="utf-8").lower()
    for package_name in baseline.distribution.prohibited_python_packages:
        if f'name = "{package_name}"' in lock_text:
            message = f"Prohibited Python package is locked: {package_name}"
            raise ReleaseBaselineError(message)


def _validate_held_out_manifests(project_root: Path) -> None:
    benchmark_root = project_root / "data" / "benchmarks"
    for dataset_name in _HELD_OUT_DATASETS:
        dataset_path = benchmark_root / dataset_name
        freeze_path = dataset_path.with_suffix(".freeze.json")
        try:
            manifest_value = cast(object, json.loads(freeze_path.read_text(encoding="utf-8")))
            lines = tuple(line for line in dataset_path.read_text(encoding="utf-8").splitlines() if line)
            row_values = tuple(cast(object, json.loads(line)) for line in lines)
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ReleaseBaselineError(f"Held-out evaluation asset is invalid: {dataset_name}") from error

        if not isinstance(manifest_value, dict) or any(not isinstance(row_value, dict) for row_value in row_values):
            raise ReleaseBaselineError(f"Held-out evaluation asset is invalid: {dataset_name}")
        manifest = cast(_JsonObject, manifest_value)
        rows = tuple(cast(_JsonObject, row_value) for row_value in row_values)
        if Path(str(manifest.get("dataset_path", ""))).name != dataset_name:
            raise ReleaseBaselineError(f"Held-out freeze manifest names a different dataset: {dataset_name}")
        digest = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
        if manifest.get("sha256") != digest:
            raise ReleaseBaselineError(f"Held-out dataset digest mismatch: {dataset_name}")
        if manifest.get("row_count") != len(rows):
            raise ReleaseBaselineError(f"Held-out dataset row count mismatch: {dataset_name}")

        case_ids = tuple(row.get("id") for row in rows)
        if any(not isinstance(case_id, str) or not case_id for case_id in case_ids):
            raise ReleaseBaselineError(f"Held-out dataset contains an invalid case ID: {dataset_name}")
        if len(set(case_ids)) != len(case_ids):
            raise ReleaseBaselineError(f"Held-out dataset contains duplicate case IDs: {dataset_name}")
        if any(row.get("forbidden_for_training") is not True for row in rows):
            raise ReleaseBaselineError(f"Held-out dataset permits training: {dataset_name}")
        manifest_case_ids_value = manifest.get("case_ids")
        if not isinstance(manifest_case_ids_value, list):
            raise ReleaseBaselineError(f"Held-out freeze case IDs mismatch: {dataset_name}")
        manifest_case_ids_items = cast(list[object], manifest_case_ids_value)
        if any(not isinstance(case_id, str) for case_id in manifest_case_ids_items):
            raise ReleaseBaselineError(f"Held-out freeze case IDs mismatch: {dataset_name}")
        manifest_case_ids = tuple(case_id for case_id in manifest_case_ids_items if isinstance(case_id, str))
        if manifest_case_ids != case_ids:
            raise ReleaseBaselineError(f"Held-out freeze case IDs mismatch: {dataset_name}")
