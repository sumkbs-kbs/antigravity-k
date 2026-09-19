from __future__ import annotations

from pathlib import Path

import pytest

from antigravity_k.engine.release_baseline import (
    ReleaseBaselineError,
    load_release_baseline,
    validate_held_out_manifests,
    validate_no_prohibited_source_text,
    validate_release_baseline,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_baseline_pins_both_upstream_commits_and_apache_licenses() -> None:
    baseline = load_release_baseline(PROJECT_ROOT)
    upstreams = {upstream.repository: upstream for upstream in baseline.upstreams}

    unsloth = upstreams["https://github.com/unslothai/unsloth"]
    freebuff = upstreams["https://github.com/CodebuffAI/freebuff"]

    assert unsloth.commit_sha == "20c015f292685c9dbf1e4cea92bf69a0792a6ca6"
    assert freebuff.commit_sha == "3dfaa35fae5ff4d0c6f894bafd0eb56d914f8807"
    assert unsloth.license_spdx == "Apache-2.0"
    assert freebuff.license_spdx == "Apache-2.0"
    assert unsloth.copied_files == ()
    assert freebuff.copied_files == ()


def test_baseline_inventory_covers_runtime_cli_api_and_dashboard_entrypoints() -> None:
    baseline = load_release_baseline(PROJECT_ROOT)

    validate_release_baseline(baseline, PROJECT_ROOT)

    names = {entrypoint.name for entrypoint in baseline.entrypoints}
    assert {"agk", "task-resume", "fastapi-server", "task-events", "react-dashboard"} <= names


def test_distribution_excludes_deprecated_vanilla_dashboard() -> None:
    baseline = load_release_baseline(PROJECT_ROOT)
    distribution_roots = {
        *baseline.distribution.source_roots,
        *baseline.distribution.manifest_roots,
    }

    assert "dashboard-vanilla" not in distribution_roots


def test_python_dependencies_do_not_request_agpl_pymupdf() -> None:
    configuration = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()

    assert "pymupdf" not in configuration
    assert "agpl" not in configuration


def test_locked_python_environment_contains_no_pymupdf_package() -> None:
    lock_text = (PROJECT_ROOT / "uv.lock").read_text(encoding="utf-8")

    assert 'name = "pymupdf"' not in lock_text.lower()


def test_validator_rejects_agpl_text_in_distribution_source(tmp_path: Path) -> None:
    baseline = load_release_baseline(PROJECT_ROOT)
    source_dir = tmp_path / "src"
    source_dir.mkdir(parents=True)
    agpl_file = source_dir / "vendor.py"
    _ = agpl_file.write_bytes(b"# GNU AFFERO GENERAL PUBLIC LICENSE\n")

    malicious = baseline.model_copy(
        update={
            "distribution": baseline.distribution.model_copy(
                update={"source_roots": ("src",)},
            ),
        },
    )
    with pytest.raises(ReleaseBaselineError, match="AGPL"):
        validate_no_prohibited_source_text(malicious, tmp_path)


@pytest.mark.parametrize(
    "spdx_text,expected_match",
    [
        (b"# SPDX-License-Identifier: AGPL-3.0-only\n", "AGPL-3.0-only"),
        (b"# SPDX-License-Identifier: AGPL-3.0-or-later\n", "AGPL-3.0-or-later"),
        (b"# spdx-license-identifier: agpl-3.0-only\n", "AGPL-3.0-only"),
        (b"agpl-3.0-only", "AGPL-3.0-only"),
        (b"/* GNU Affero General Public License */\n", "AGPL"),
        (b"# GNU.AFFERO.GENERAL.PUBLIC.LICENSE\n", "AGPL"),
    ],
)
def test_validator_rejects_spdx_agpl_variations_in_source(
    tmp_path: Path, spdx_text: bytes, expected_match: str
) -> None:
    baseline = load_release_baseline(PROJECT_ROOT)
    source_dir = tmp_path / "src"
    source_dir.mkdir(parents=True)
    _ = (source_dir / "component.py").write_bytes(spdx_text)

    malicious = baseline.model_copy(
        update={
            "distribution": baseline.distribution.model_copy(
                update={"source_roots": ("src",)},
            ),
        },
    )
    with pytest.raises(ReleaseBaselineError, match=expected_match):
        validate_no_prohibited_source_text(malicious, tmp_path)


@pytest.mark.parametrize(
    "spdx_text,expected_match",
    [
        (b"# SPDX-License-Identifier: GPL-2.0-only\n", "GPL-2.0-only"),
        (b"# SPDX-License-Identifier: GPL-3.0-or-later\n", "GPL-3.0-or-later"),
        (b"// GNU General Public License\n", "GPL"),
        (b"# GNU.GENERAL.PUBLIC.LICENSE\n", "GPL"),
    ],
)
def test_validator_rejects_spdx_gpl_variations_in_source(tmp_path: Path, spdx_text: bytes, expected_match: str) -> None:
    baseline = load_release_baseline(PROJECT_ROOT)
    source_dir = tmp_path / "src"
    source_dir.mkdir(parents=True)
    _ = (source_dir / "component.py").write_bytes(spdx_text)

    malicious = baseline.model_copy(
        update={
            "distribution": baseline.distribution.model_copy(
                update={"source_roots": ("src",)},
            ),
        },
    )
    with pytest.raises(ReleaseBaselineError, match=expected_match):
        validate_no_prohibited_source_text(malicious, tmp_path)


def test_validator_allows_permissive_and_benign_source_text(tmp_path: Path) -> None:
    baseline = load_release_baseline(PROJECT_ROOT)
    source_dir = tmp_path / "src"
    source_dir.mkdir(parents=True)
    benign_code = (
        b"# SPDX-License-Identifier: Apache-2.0\n"
        b"// Licensed under MIT License\n"
        b"const plugin = createTrackingPlugin('minimal');\n"
        b"def default_training_platform(platform: PlatformKind):\n"
        b"# This is non-gpl text with gplus mentions\n"
    )
    _ = (source_dir / "component.py").write_bytes(benign_code)

    benign_baseline = baseline.model_copy(
        update={
            "distribution": baseline.distribution.model_copy(
                update={"source_roots": ("src",)},
            ),
        },
    )
    # Should complete without error
    validate_no_prohibited_source_text(benign_baseline, tmp_path)


def test_validator_rejects_entrypoint_with_unimplemented_cli_subcommand() -> None:
    baseline = load_release_baseline(PROJECT_ROOT)
    mutated_entrypoints = tuple(
        ep.model_copy(update={"command": ("agk", "task", "nonexistent")}) if ep.name == "task-resume" else ep
        for ep in baseline.entrypoints
    )
    mutated_baseline = baseline.model_copy(update={"entrypoints": mutated_entrypoints})

    with pytest.raises(ReleaseBaselineError, match="CLI entrypoint 'task-resume' command"):
        validate_release_baseline(mutated_baseline, PROJECT_ROOT)


def test_validator_rejects_entrypoint_with_unimplemented_http_route() -> None:
    baseline = load_release_baseline(PROJECT_ROOT)
    mutated_entrypoints = tuple(
        ep.model_copy(update={"command": ("GET", "/api/tasks/nonexistent")}) if ep.name == "task-events" else ep
        for ep in baseline.entrypoints
    )
    mutated_baseline = baseline.model_copy(update={"entrypoints": mutated_entrypoints})

    with pytest.raises(ReleaseBaselineError, match="HTTP API entrypoint 'task-events' route"):
        validate_release_baseline(mutated_baseline, PROJECT_ROOT)


def test_validator_rejects_entrypoint_with_unimplemented_web_ui_script() -> None:
    baseline = load_release_baseline(PROJECT_ROOT)
    mutated_entrypoints = tuple(
        ep.model_copy(update={"command": ("npm", "run", "nonexistent")}) if ep.name == "react-dashboard" else ep
        for ep in baseline.entrypoints
    )
    mutated_baseline = baseline.model_copy(update={"entrypoints": mutated_entrypoints})

    with pytest.raises(ReleaseBaselineError, match="Web UI entrypoint 'react-dashboard' script"):
        validate_release_baseline(mutated_baseline, PROJECT_ROOT)


def test_validator_rejects_entrypoint_when_source_missing() -> None:
    baseline = load_release_baseline(PROJECT_ROOT)
    mutated_entrypoints = tuple(
        ep.model_copy(update={"source_path": "nonexistent/path.py"}) if ep.name == "agk" else ep
        for ep in baseline.entrypoints
    )
    mutated_baseline = baseline.model_copy(update={"entrypoints": mutated_entrypoints})

    with pytest.raises(ReleaseBaselineError, match="Entrypoint source is missing"):
        validate_release_baseline(mutated_baseline, PROJECT_ROOT)


def test_validator_rejects_held_out_dataset_digest_mutation(tmp_path: Path) -> None:
    benchmarks_dir = tmp_path / "data" / "benchmarks"
    benchmarks_dir.mkdir(parents=True)
    for f in (PROJECT_ROOT / "data" / "benchmarks").glob("*"):
        if f.is_file():
            _ = (benchmarks_dir / f.name).write_bytes(f.read_bytes())
    dataset_copy = benchmarks_dir / "held_out_v2.jsonl"
    original = dataset_copy.read_bytes()
    mutated = original.replace(b"heldout-ko-002", b"heldout-ko-mutated")
    _ = dataset_copy.write_bytes(mutated)

    with pytest.raises(ReleaseBaselineError, match="digest mismatch: held_out_v2.jsonl"):
        validate_held_out_manifests(tmp_path)


def test_validator_rejects_held_out_freeze_case_id_mutation(tmp_path: Path) -> None:
    benchmarks_dir = tmp_path / "data" / "benchmarks"
    benchmarks_dir.mkdir(parents=True)
    for f in (PROJECT_ROOT / "data" / "benchmarks").glob("*"):
        if f.is_file():
            _ = (benchmarks_dir / f.name).write_bytes(f.read_bytes())
    freeze_copy = benchmarks_dir / "held_out_v2.freeze.json"
    original = freeze_copy.read_bytes()
    mutated = original.replace(b"heldout-ko-002", b"heldout-ko-mutated")
    _ = freeze_copy.write_bytes(mutated)

    with pytest.raises(ReleaseBaselineError, match="case IDs mismatch: held_out_v2.jsonl"):
        validate_held_out_manifests(tmp_path)
