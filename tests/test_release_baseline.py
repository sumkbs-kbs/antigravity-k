from __future__ import annotations

from pathlib import Path

import pytest

from antigravity_k.engine.release_baseline import (
    ReleaseBaselineError,
    load_release_baseline,
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


def test_python_dependencies_do_not_request_agpl_pymupdf() -> None:
    configuration = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()

    assert "pymupdf" not in configuration
    assert "agpl" not in configuration


def test_locked_python_environment_contains_no_pymupdf_package() -> None:
    lock_text = (PROJECT_ROOT / "uv.lock").read_text(encoding="utf-8")

    assert 'name = "pymupdf"' not in lock_text.lower()


def test_validator_rejects_agpl_text_in_distribution_source() -> None:
    baseline = load_release_baseline(PROJECT_ROOT)
    malicious = baseline.model_copy(
        update={
            "distribution": baseline.distribution.model_copy(
                update={"source_roots": ("tests/fixtures/release_baseline",)},
            ),
        },
    )
    fixture_root = PROJECT_ROOT / "tests" / "fixtures" / "release_baseline"
    _ = fixture_root.mkdir(parents=True, exist_ok=True)
    agpl_file = fixture_root / "vendor.py"
    original = agpl_file.read_bytes() if agpl_file.exists() else None
    _ = agpl_file.write_bytes(b"# GNU AFFERO GENERAL PUBLIC LICENSE\n")

    try:
        with pytest.raises(ReleaseBaselineError, match="AGPL"):
            validate_release_baseline(malicious, PROJECT_ROOT)
    finally:
        if original is None:
            agpl_file.unlink()
        else:
            _ = agpl_file.write_bytes(original)
