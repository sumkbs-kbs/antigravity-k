from __future__ import annotations

import hashlib
import json
import tarfile
import zipfile
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Annotated, ClassVar, Never, override
from urllib.parse import quote

import typer
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from antigravity_k import __version__
from antigravity_k.engine.release_dependencies import (
    DashboardDependency,
    DashboardRuntimeDependencies,
    PythonDependency,
    PythonRuntimeDependencies,
    dashboard_runtime_dependencies,
    python_runtime_dependencies,
)


@dataclass(frozen=True, slots=True)
class ReleaseSbomError(ValueError):
    reason: str

    @override
    def __str__(self) -> str:
        return self.reason


@dataclass(frozen=True, slots=True)
class ReleaseDocuments:
    python_sbom: Path
    dashboard_sbom: Path
    notices: Path
    release_root: Path

    def __iter__(self) -> Iterator[Path]:
        return iter((self.python_sbom, self.dashboard_sbom, self.notices))


class _SbomComponent(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="allow")

    name: str


class _SbomDocument(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="allow")

    components: tuple[_SbomComponent, ...]


class _SupplyChainManifest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    artifacts: dict[str, str]
    documents: dict[str, str]


def generate_release_documents(project_root: Path) -> ReleaseDocuments:
    release_root = project_root / "src" / "antigravity_k" / "release"
    python = python_runtime_dependencies(project_root)
    dashboard = dashboard_runtime_dependencies(project_root)
    try:
        release_root.mkdir(parents=True, exist_ok=True)
        _write_json(release_root / "python.cdx.json", _python_sbom(python))
        _write_json(release_root / "dashboard.cdx.json", _dashboard_sbom(dashboard))
        _ = (release_root / "THIRD_PARTY_NOTICES.txt").write_text(
            _notices(python.dependencies, dashboard.dependencies),
            encoding="utf-8",
            newline="\n",
        )
    except OSError as error:
        raise ReleaseSbomError(f"Could not write release documents: {release_root}") from error
    return ReleaseDocuments(
        python_sbom=release_root / "python.cdx.json",
        dashboard_sbom=release_root / "dashboard.cdx.json",
        notices=release_root / "THIRD_PARTY_NOTICES.txt",
        release_root=release_root,
    )


def verify_release_bundle(*, distribution_root: Path, release_root: Path) -> Path:
    wheels = sorted(distribution_root.glob("*.whl"))
    sdists = sorted(distribution_root.glob("*.tar.gz"))
    if not wheels and not sdists:
        raise ReleaseSbomError(f"Distribution root has no wheel or sdist: {distribution_root}")
    documents = _release_documents(release_root)
    for document in documents:
        payload = document.read_bytes()
        for wheel in wheels:
            _verify_wheel_document(wheel, f"antigravity_k/release/{document.name}", payload, document.name)
        for sdist in sdists:
            prefix = sdist.name.removesuffix(".tar.gz")
            member = f"{prefix}/src/antigravity_k/release/{document.name}"
            _verify_sdist_document(sdist, member, payload, document.name)
    return _write_supply_chain_manifest(distribution_root, documents, (*wheels, *sdists))


def _python_sbom(python: PythonRuntimeDependencies) -> dict[str, object]:
    components: list[dict[str, object]] = [_application_component()]
    components.extend(_python_component(dependency) for dependency in python.dependencies)
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "component": _application_component(),
            "properties": [
                {"name": "agk:lockfile", "value": "uv.lock"},
                {"name": "agk:excluded-extras", "value": ",".join(python.excluded_extras)},
            ],
        },
        "components": components,
    }


def _dashboard_sbom(dashboard: DashboardRuntimeDependencies) -> dict[str, object]:
    root = {
        "bom-ref": "pkg:npm/antigravity-k-dashboard-react@0.1.0",
        "type": "application",
        "name": dashboard.root_name,
        "version": dashboard.root_version,
    }
    components = [root, *(_dashboard_component(dependency) for dependency in dashboard.dependencies)]
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {"component": root},
        "components": components,
    }


def _application_component() -> dict[str, object]:
    return {
        "bom-ref": f"pkg:pypi/antigravity-k@{quote(__version__)}",
        "type": "application",
        "name": "antigravity-k",
        "version": __version__,
        "licenses": [{"license": {"id": "MIT"}}],
    }


def _python_component(dependency: PythonDependency) -> dict[str, object]:
    component: dict[str, object] = {
        "bom-ref": f"pkg:pypi/{quote(dependency.name)}@{quote(dependency.version)}",
        "type": "library",
        "name": dependency.name,
        "version": dependency.version,
        "purl": f"pkg:pypi/{quote(dependency.name)}@{quote(dependency.version)}",
    }
    if dependency.source_url is not None:
        component["externalReferences"] = [{"type": "distribution", "url": dependency.source_url}]
    return component


def _dashboard_component(dependency: DashboardDependency) -> dict[str, object]:
    component: dict[str, object] = {
        "bom-ref": f"pkg:npm/{quote(dependency.name)}@{quote(dependency.version)}",
        "type": "library",
        "name": dependency.name,
        "version": dependency.version,
        "purl": f"pkg:npm/{quote(dependency.name)}@{quote(dependency.version)}",
    }
    if dependency.license_id is not None:
        component["licenses"] = [{"license": {"id": dependency.license_id}}]
    if dependency.source_url is not None:
        component["externalReferences"] = [{"type": "distribution", "url": dependency.source_url}]
    return component


def _notices(
    python_dependencies: Iterable[PythonDependency],
    dashboard_dependencies: Iterable[DashboardDependency],
) -> str:
    lines = [
        "Ssak-Ai third-party notices",
        "",
        "Project license: MIT",
        "Dependency scope: runtime dependency closure; dev dependencies excluded",
        "",
        "Python dependencies (uv.lock):",
    ]
    for python_dep in python_dependencies:
        lines.append(f"- {python_dep.name} {python_dep.version} — {_python_license(python_dep.name)}")
    lines.extend(("", "Dashboard dependencies (dashboard/package-lock.json):"))
    for dashboard_dep in dashboard_dependencies:
        license_id = dashboard_dep.license_id or "license metadata unavailable"
        lines.append(f"- {dashboard_dep.name} {dashboard_dep.version} — {license_id}")
    lines.extend(("", "Missing license or notice metadata is reported explicitly and never synthesized."))
    return "\n".join(lines) + "\n"


def _sbom_component_count(sbom_path: Path) -> int:
    try:
        document = TypeAdapter(_SbomDocument).validate_json(sbom_path.read_bytes())
    except (OSError, ValidationError) as error:
        raise ReleaseSbomError(f"Could not count release SBOM components: {sbom_path}") from error
    return len(document.components)


def _python_license(name: str) -> str:
    try:
        value = metadata.metadata(name).get("License", "")
    except metadata.PackageNotFoundError:
        return "license metadata unavailable"
    return value or "license metadata unavailable"


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    content = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    _ = path.write_text(content, encoding="utf-8", newline="\n")


def _release_documents(release_root: Path) -> tuple[Path, ...]:
    names = ("python.cdx.json", "dashboard.cdx.json", "THIRD_PARTY_NOTICES.txt")
    documents = tuple(release_root / name for name in names)
    for document in documents:
        if not document.is_file():
            raise ReleaseSbomError(f"missing release document: {document}")
    return documents


def _verify_wheel_document(wheel: Path, member: str, expected: bytes, name: str) -> None:
    try:
        with zipfile.ZipFile(wheel) as archive:
            if member not in archive.namelist():
                raise ReleaseSbomError(f"wheel is missing release document: {name}")
            if archive.read(member) != expected:
                raise ReleaseSbomError(f"{name} does not match wheel release document")
    except (OSError, zipfile.BadZipFile) as error:
        raise ReleaseSbomError(f"Could not verify wheel: {wheel}") from error


def _verify_sdist_document(sdist: Path, member: str, expected: bytes, name: str) -> None:
    try:
        with tarfile.open(sdist, "r:gz") as archive:
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ReleaseSbomError(f"sdist is missing release document: {name}")
            if extracted.read() != expected:
                raise ReleaseSbomError(f"{name} does not match sdist release document")
    except (OSError, tarfile.TarError) as error:
        raise ReleaseSbomError(f"Could not verify sdist: {sdist}") from error


def _write_supply_chain_manifest(
    distribution_root: Path,
    documents: tuple[Path, ...],
    archives: tuple[Path, ...],
) -> Path:
    payload = {
        "artifacts": {archive.name: _sha256_hex(archive) for archive in archives},
        "documents": {document.name: f"sha256-{_sha256_hex(document)}" for document in documents},
    }
    manifest = distribution_root / "release-supply-chain.json"
    _write_json(manifest, payload)
    return manifest


def _sha256_hex(path: Path) -> str:
    try:
        with path.open("rb") as handle:
            return hashlib.file_digest(handle, "sha256").hexdigest()
    except OSError as error:
        raise ReleaseSbomError(f"Could not hash release file: {path}") from error


app = typer.Typer(help="Generate and verify Ssak-Ai release SBOMs and notices.")


@app.command()
def generate(
    project_root: Annotated[Path, typer.Option("--project-root")],
    release_root: Annotated[Path, typer.Option("--release-root")],
) -> None:
    try:
        documents = generate_release_documents(project_root)
        if documents.release_root != release_root:
            raise ReleaseSbomError("The requested release root does not match the project src layout")
        python_count = _sbom_component_count(documents.python_sbom)
        dashboard_count = _sbom_component_count(documents.dashboard_sbom)
    except ReleaseSbomError as error:
        _exit_with_error(error)
    typer.echo(
        json.dumps(
            {
                "dashboard_components": dashboard_count,
                "python_components": python_count,
                "release_root": str(release_root),
                "status": "generated",
            }
        )
    )


@app.command()
def verify(
    distribution_root: Annotated[Path, typer.Option("--distribution-root")],
    release_root: Annotated[Path, typer.Option("--release-root")],
    output: Annotated[Path | None, typer.Option("--output")] = None,
) -> None:
    try:
        manifest = verify_release_bundle(distribution_root=distribution_root, release_root=release_root)
        if output is not None:
            supply_chain = TypeAdapter(_SupplyChainManifest).validate_json(manifest.read_bytes())
            _write_json(output, supply_chain.model_dump(mode="json"))
        python_count = _sbom_component_count(release_root / "python.cdx.json")
    except ReleaseSbomError as error:
        _exit_with_error(error)
    typer.echo(
        json.dumps({"manifest": str(output or manifest), "python_components": python_count, "status": "verified"})
    )


def _exit_with_error(error: ReleaseSbomError) -> Never:
    typer.echo(json.dumps({"error": str(error), "status": "error"}), err=True)
    raise typer.Exit(code=2)


if __name__ == "__main__":
    app()
