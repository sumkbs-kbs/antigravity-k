from __future__ import annotations

import hashlib
import json
import tarfile
import zipfile
from io import BytesIO
from pathlib import Path
from typing import NotRequired, TypedDict

import pytest
from pydantic import TypeAdapter
from typer.testing import CliRunner

from antigravity_k.engine.release_dependencies import (
    ReleaseDependencyError,
    dashboard_runtime_dependencies,
)
from antigravity_k.engine.release_sbom import (
    ReleaseSbomError,
    app,
    generate_release_documents,
    verify_release_bundle,
)


class _Component(TypedDict):
    name: str
    version: str


class _Sbom(TypedDict):
    components: list[_Component]
    specVersion: str
    metadata: NotRequired[_Metadata]


class _Metadata(TypedDict):
    properties: NotRequired[list[_Property]]


class _Property(TypedDict):
    name: str
    value: str


class _LockPackagePatch(TypedDict):
    dependencies: NotRequired[dict[str, str]]
    name: NotRequired[str]
    version: NotRequired[str]
    devDependencies: NotRequired[dict[str, str]]


class _LockPatch(TypedDict):
    packages: dict[str, _LockPackagePatch]
    name: str
    version: str
    lockfileVersion: int
    requires: bool


def _properties(sbom: _Sbom) -> list[_Property]:
    return sbom.get("metadata", {}).get("properties", [])


class _Manifest(TypedDict):
    artifacts: dict[str, str]
    documents: dict[str, str]


def _sbom(path: Path) -> _Sbom:
    return TypeAdapter(_Sbom).validate_json(path.read_bytes())


def _manifest(path: Path) -> _Manifest:
    return TypeAdapter(_Manifest).validate_json(path.read_bytes())


def _write_python_lock(project: Path) -> None:
    payload = "\n".join(
        (
            "version = 1",
            "",
            "[[package]]",
            'name = "antigravity-k"',
            'source = { editable = "." }',
            'dependencies = [{ name = "example-runtime" }]',
            "",
            "[package.optional-dependencies]",
            'dev = [{ name = "example-dev" }]',
            'rag = [{ name = "example-rag" }]',
            "",
            "[package.metadata]",
            'provides-extras = ["dev", "rag"]',
            "",
            "[[package]]",
            'name = "example-runtime"',
            'version = "1.2.3"',
            'source = { registry = "https://pypi.org/simple" }',
            'dependencies = [{ name = "example-transitive" }]',
            "",
            "[[package]]",
            'name = "example-transitive"',
            'version = "4.5.6"',
            'source = { registry = "https://pypi.org/simple" }',
            "",
            "[[package]]",
            'name = "example-dev"',
            'version = "0.0.1"',
            'source = { registry = "https://pypi.org/simple" }',
            "",
            "[[package]]",
            'name = "example-rag"',
            'version = "0.0.2"',
            'source = { registry = "https://pypi.org/simple" }',
            "",
        )
    )
    _ = (project / "uv.lock").write_text(payload, encoding="utf-8")


def _write_dashboard_lock(project: Path) -> None:
    packages = {
        "": {
            "name": "antigravity-k-dashboard-react",
            "version": "0.1.0",
            "dependencies": {"runtime-lib": "^1.0.0"},
            "devDependencies": {"dev-lib": "^2.0.0"},
        },
        "node_modules/runtime-lib": {
            "version": "1.4.0",
            "resolved": "https://registry.npmjs.org/runtime-lib/-/runtime-lib-1.4.0.tgz",
            "integrity": "sha512-runtime",
            "license": "Apache-2.0",
            "dependencies": {"nested-lib": "^3.0.0"},
        },
        "node_modules/runtime-lib/node_modules/intermediate-lib": {
            "version": "4.0.0",
            "resolved": "https://registry.npmjs.org/intermediate-lib/-/intermediate-lib-4.0.0.tgz",
            "integrity": "sha512-intermediate",
            "license": "MIT",
            "dependencies": {"hoisted-lib": "^5.0.0"},
        },
        "node_modules/runtime-lib/node_modules/nested-lib": {
            "version": "3.1.0",
            "resolved": "https://registry.npmjs.org/nested-lib/-/nested-lib-3.1.0.tgz",
            "integrity": "sha512-nested",
            "license": "MIT",
            "dependencies": {"intermediate-lib": "^4.0.0"},
        },
        "node_modules/hoisted-lib": {
            "version": "5.6.7",
            "resolved": "https://registry.npmjs.org/hoisted-lib/-/hoisted-lib-5.6.7.tgz",
            "integrity": "sha512-hoisted",
            "license": "MIT",
        },
        "node_modules/dev-lib": {
            "version": "2.2.0",
            "resolved": "https://registry.npmjs.org/dev-lib/-/dev-lib-2.2.0.tgz",
            "integrity": "sha512-dev",
            "dev": True,
            "license": "MIT",
        },
    }
    payload = {
        "name": "antigravity-k-dashboard-react",
        "version": "0.1.0",
        "lockfileVersion": 3,
        "requires": True,
        "packages": packages,
    }
    _ = (project / "dashboard").mkdir()
    _ = (project / "dashboard" / "package-lock.json").write_text(json.dumps(payload), encoding="utf-8")


def _project(tmp_path: Path) -> Path:
    _write_python_lock(tmp_path)
    _write_dashboard_lock(tmp_path)
    return tmp_path


def _component(sbom: _Sbom, name: str) -> _Component:
    matches = [component for component in sbom["components"] if component["name"] == name]
    assert len(matches) == 1
    return matches[0]


def test_generation_uses_runtime_lock_closures_and_documents_scopes(tmp_path: Path) -> None:
    project = _project(tmp_path)

    documents = generate_release_documents(project)

    python_sbom = _sbom(documents.python_sbom)
    dashboard_sbom = _sbom(documents.dashboard_sbom)
    notices = documents.notices.read_text(encoding="utf-8")

    assert python_sbom["specVersion"] == "1.5"
    assert _component(python_sbom, "example-runtime")["version"] == "1.2.3"
    assert _component(python_sbom, "example-transitive")["version"] == "4.5.6"
    assert "example-dev" not in {component["name"] for component in python_sbom["components"]}
    assert "example-rag" not in {component["name"] for component in python_sbom["components"]}
    assert {property["name"]: property["value"] for property in _properties(python_sbom)}[
        "agk:excluded-extras"
    ] == "dev,rag"

    assert _component(dashboard_sbom, "runtime-lib")["version"] == "1.4.0"
    assert _component(dashboard_sbom, "nested-lib")["version"] == "3.1.0"
    assert _component(dashboard_sbom, "hoisted-lib")["version"] == "5.6.7"
    assert "dev-lib" not in {component["name"] for component in dashboard_sbom["components"]}
    assert "runtime dependency closure; dev dependencies excluded" in notices
    assert "runtime-lib 1.4.0" in notices
    assert "Apache-2.0" in notices


def test_real_dashboard_lock_includes_transitive_runtime_packages() -> None:
    root = Path(__file__).resolve().parents[1]

    dependencies = dashboard_runtime_dependencies(root)

    names = {dependency.name for dependency in dependencies.dependencies}
    assert "scheduler" in names
    assert len(dependencies.dependencies) > 20


def test_dashboard_lock_rejects_an_unresolved_runtime_dependency(tmp_path: Path) -> None:
    project = _project(tmp_path)
    lock_path = project / "dashboard" / "package-lock.json"
    payload = TypeAdapter(_LockPatch).validate_json(lock_path.read_text(encoding="utf-8"))
    runtime_packages = payload["packages"]
    runtime_lib = runtime_packages["node_modules/runtime-lib"]
    dependencies = runtime_lib.get("dependencies", {})
    dependencies["missing-lib"] = "^1.0.0"
    _ = lock_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ReleaseDependencyError, match="missing-lib"):
        _ = dashboard_runtime_dependencies(project)


def test_verification_rejects_missing_or_modified_release_documents(tmp_path: Path) -> None:
    project = _project(tmp_path)
    documents = generate_release_documents(project)
    distribution = tmp_path / "dist"
    _ = distribution.mkdir()
    wheel = distribution / "antigravity_k-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for source in documents:
            _ = archive.writestr(f"antigravity_k/release/{source.name}", source.read_bytes())

    manifest = verify_release_bundle(distribution_root=distribution, release_root=documents.release_root)
    payload = _manifest(manifest)
    expected_wheel_hash = hashlib.sha256(wheel.read_bytes()).hexdigest()
    assert payload["artifacts"]["antigravity_k-0.1.0-py3-none-any.whl"] == expected_wheel_hash
    assert payload["documents"]["python.cdx.json"].startswith("sha256-")

    _ = documents.python_sbom.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ReleaseSbomError, match="does not match wheel release document"):
        _ = verify_release_bundle(
            distribution_root=distribution,
            release_root=documents.release_root,
        )


def _distribution(tmp_path: Path, *, include_documents: bool) -> Path:
    project = _project(tmp_path)
    documents = generate_release_documents(project) if include_documents else None
    distribution = tmp_path / "dist"
    _ = distribution.mkdir()
    wheel = distribution / "antigravity_k-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        if documents is not None:
            for source in documents:
                _ = archive.writestr(f"antigravity_k/release/{source.name}", source.read_bytes())
    return distribution


def test_verification_rejects_a_bundle_without_release_documents(tmp_path: Path) -> None:
    distribution = _distribution(tmp_path, include_documents=False)
    project = tmp_path
    documents = generate_release_documents(project)

    with pytest.raises(ReleaseSbomError, match="missing release document"):
        _ = verify_release_bundle(distribution_root=distribution, release_root=documents.release_root)


def test_sdist_members_are_verified_when_present(tmp_path: Path) -> None:
    project = _project(tmp_path)
    documents = generate_release_documents(project)
    distribution = tmp_path / "dist"
    _ = distribution.mkdir()
    sdist = distribution / "antigravity_k-0.1.0.tar.gz"
    with tarfile.open(sdist, "w:gz") as archive:
        for source in documents:
            source_payload = source.read_bytes()
            info = tarfile.TarInfo(f"antigravity_k-0.1.0/src/antigravity_k/release/{source.name}")
            info.size = len(source_payload)
            _ = archive.addfile(info, BytesIO(source_payload))

    manifest = verify_release_bundle(distribution_root=distribution, release_root=documents.release_root)
    payload = _manifest(manifest)

    assert payload["artifacts"]["antigravity_k-0.1.0.tar.gz"] == hashlib.sha256(sdist.read_bytes()).hexdigest()


def test_workflows_generate_verify_and_provide_supply_chain_manifest() -> None:
    root = Path(__file__).resolve().parents[1]
    release_workflow = (root / ".github/workflows/release.yml").read_text(encoding="utf-8")
    ci_workflow = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")

    for workflow in (release_workflow, ci_workflow):
        assert "python -m antigravity_k.engine.release_sbom generate" in workflow
        assert "python -m antigravity_k.engine.release_sbom verify" in workflow
        assert "release-supply-chain.json" in workflow
    assert '"release/python.cdx.json"' in pyproject
    assert '"release/dashboard.cdx.json"' in pyproject
    assert '"release/THIRD_PARTY_NOTICES.txt"' in pyproject


def test_cli_generates_and_verifies(tmp_path: Path) -> None:
    project = _project(tmp_path)
    distribution = tmp_path / "dist"
    _ = distribution.mkdir()
    runner = CliRunner()

    generated = runner.invoke(
        app,
        ["generate", "--project-root", str(project), "--release-root", str(project / "src/antigravity_k/release")],
    )
    assert generated.exit_code == 0, generated.output

    release_root = project / "src/antigravity_k/release"
    wheel = distribution / "antigravity_k-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for source in release_root.iterdir():
            _ = archive.writestr(f"antigravity_k/release/{source.name}", source.read_bytes())
    verified = runner.invoke(
        app,
        [
            "verify",
            "--distribution-root",
            str(distribution),
            "--release-root",
            str(release_root),
            "--output",
            str(project / "release-supply-chain.json"),
        ],
    )
    assert verified.exit_code == 0, verified.output
    assert "python_components" in verified.output
