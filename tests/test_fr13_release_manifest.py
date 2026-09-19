"""FR-09/RP-13 regression: release manifest verification must catch tampering.

Covers R13-09/R13-10:

- a healthy manifest verifies PASS
- a missing artifact file fails
- a tampered artifact (sha mismatch) fails
- a duplicate artifact id fails
- a malformed source SHA fails
- an empty artifact list fails
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "release_manifest_verify.py"


@pytest.fixture()
def verifier() -> ModuleType:
    spec = importlib.util.spec_from_file_location("release_manifest_verify_under_test", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def healthy(tmp_path: Path) -> dict:
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"release artifact payload")
    import hashlib

    return {
        "schema_version": 1,
        "source_sha": "a" * 40,
        "artifacts": [
            {
                "id": "wheel",
                "path": str(artifact),
                "size_bytes": artifact.stat().st_size,
                "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            }
        ],
    }


class TestManifestVerification:
    def test_healthy_manifest_passes(self, verifier: ModuleType, healthy: dict) -> None:
        assert verifier.verify_manifest(healthy, None) == []

    def test_missing_artifact_fails(self, verifier: ModuleType, healthy: dict, tmp_path: Path) -> None:
        Path(healthy["artifacts"][0]["path"]).unlink()
        problems = verifier.verify_manifest(healthy, None)
        assert any("artifact missing" in p for p in problems)

    def test_tampered_artifact_fails(self, verifier: ModuleType, healthy: dict) -> None:
        Path(healthy["artifacts"][0]["path"]).write_bytes(b"tampered payload")
        problems = verifier.verify_manifest(healthy, None)
        assert any("sha256 mismatch" in p for p in problems)

    def test_declared_size_mismatch_fails(self, verifier: ModuleType, healthy: dict) -> None:
        healthy["artifacts"][0]["size_bytes"] = healthy["artifacts"][0]["size_bytes"] + 7
        problems = verifier.verify_manifest(healthy, None)
        assert any("size mismatch" in p for p in problems)

    def test_duplicate_id_fails(self, verifier: ModuleType, healthy: dict) -> None:
        healthy["artifacts"].append(dict(healthy["artifacts"][0]))
        problems = verifier.verify_manifest(healthy, None)
        assert any("duplicate artifact id" in p for p in problems)

    def test_short_source_sha_fails(self, verifier: ModuleType, healthy: dict) -> None:
        healthy["source_sha"] = "abc123"
        problems = verifier.verify_manifest(healthy, None)
        assert any("not a full 40-hex sha" in p for p in problems)

    def test_empty_artifact_list_fails(self, verifier: ModuleType) -> None:
        problems = verifier.verify_manifest({"source_sha": "b" * 40, "artifacts": []}, None)
        assert any("empty or missing artifact list" in p for p in problems)

    def test_relative_path_resolves_against_source_root(
        self, verifier: ModuleType, healthy: dict, tmp_path: Path
    ) -> None:
        import hashlib

        rel_dir = tmp_path / "rel"
        rel_dir.mkdir()
        artifact = rel_dir / "rel.bin"
        artifact.write_bytes(b"relative artifact")
        healthy["artifacts"][0] = {
            "id": "rel",
            "path": "rel/rel.bin",
            "size_bytes": artifact.stat().st_size,
            "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        }
        assert verifier.verify_manifest(healthy, tmp_path) == []
        assert any("artifact missing" in p for p in verifier.verify_manifest(healthy, tmp_path / "nowhere"))
