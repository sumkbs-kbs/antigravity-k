from __future__ import annotations

import tarfile
import zipfile
from email.message import Message
from email.parser import BytesParser
from email.policy import compat32
from io import BytesIO
from pathlib import Path
from typing import NotRequired, TypedDict

import pytest
from pydantic import TypeAdapter
from typer.testing import CliRunner

from antigravity_k.engine.release_metadata import (
    ReleaseMetadataError,
    app,
    verify_release_metadata,
)


class _ProjectTable(TypedDict):
    version: NotRequired[str]
    dynamic: list[str]


class _PyProjectTable(TypedDict):
    project: _ProjectTable


def _write_metadata_message(name: str, version: str, metadata_version: str = "2.1") -> Message:
    message = Message()
    _ = message.add_header("Metadata-Version", metadata_version)
    _ = message.add_header("Name", name)
    _ = message.add_header("Version", version)
    return message


def _write_wheel(root: Path, version: str = "0.1.0", *, name: str = "Antigravity-K") -> Path:
    path = root / f"antigravity_k-{version}-py3-none-any.whl"
    metadata_dir = f"antigravity_k-{version}.dist-info"
    with zipfile.ZipFile(path, "w") as wheel:
        _ = wheel.writestr(
            f"{metadata_dir}/METADATA",
            _write_metadata_message(name, version).as_string(),
        )
    return path


def _write_sdist(root: Path, version: str = "0.1.0", *, name: str = "Antigravity-K") -> Path:
    path = root / f"antigravity-k-{version}.tar.gz"
    payload = _write_metadata_message(name, version).as_string().encode("utf-8")
    with tarfile.open(path, "w:gz") as sdist:
        info = tarfile.TarInfo(f"antigravity-k-{version}/PKG-INFO")
        info.size = len(payload)
        _ = sdist.addfile(info, BytesIO(payload))
    return path


def _metadata_text(path: Path) -> bytes:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as wheel:
            member = next(name for name in wheel.namelist() if name.endswith("/METADATA"))
            return wheel.read(member)
    with tarfile.open(path) as sdist:
        member = next(name for name in sdist.getnames() if name.endswith("/PKG-INFO"))
        extracted = sdist.extractfile(member)
        assert extracted is not None
        return extracted.read()


def test_release_workflow_reads_the_built_release_metadata() -> None:
    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/release.yml").read_text(encoding="utf-8")
    ci = (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "python -m antigravity_k.engine.release_metadata \\\n" in workflow
    assert "project']['version']" not in workflow
    assert "python -m antigravity_k.engine.release_metadata \\\n" in ci


def test_package_version_remains_the_single_toml_version_source() -> None:
    import tomllib

    raw = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
    parsed = TypeAdapter(_PyProjectTable).validate_python(raw)
    project = parsed["project"]

    assert "version" not in project
    assert "version" in project["dynamic"]


def test_matching_wheel_sdist_source_and_tag_pass(tmp_path: Path) -> None:
    wheel = _write_wheel(tmp_path)
    sdist = _write_sdist(tmp_path)

    release = verify_release_metadata(
        distribution_root=tmp_path,
        source_version="0.1.0",
        git_ref="refs/tags/v0.1.0",
    )

    assert (release.version, release.source_version, release.wheel, release.sdist) == (
        "0.1.0",
        "0.1.0",
        wheel,
        sdist,
    )


def test_version_mismatch_between_wheel_sdist_and_source_is_rejected(tmp_path: Path) -> None:
    _ = _write_wheel(tmp_path, "0.1.0")
    _ = _write_sdist(tmp_path, "0.2.0")

    with pytest.raises(ReleaseMetadataError, match="sdist version 0.2.0 does not match wheel version 0.1.0"):
        _ = verify_release_metadata(
            distribution_root=tmp_path,
            source_version="0.1.0",
            git_ref="refs/tags/v0.1.0",
        )


def test_source_version_mismatch_is_rejected_even_when_artifacts_agree(tmp_path: Path) -> None:
    _ = _write_wheel(tmp_path, "0.1.0")
    _ = _write_sdist(tmp_path, "0.1.0")

    with pytest.raises(ReleaseMetadataError, match="source package version 0.1.1"):
        _ = verify_release_metadata(
            distribution_root=tmp_path,
            source_version="0.1.1",
            git_ref="refs/tags/v0.1.0",
        )


def test_tag_version_mismatch_is_rejected(tmp_path: Path) -> None:
    _ = _write_wheel(tmp_path)
    _ = _write_sdist(tmp_path)

    with pytest.raises(ReleaseMetadataError, match="tag version 0.2.0"):
        _ = verify_release_metadata(
            distribution_root=tmp_path,
            source_version="0.1.0",
            git_ref="refs/tags/v0.2.0",
        )


@pytest.mark.parametrize("git_ref", ["refs/heads/main", "refs/tags/release-0.1.0"])
def test_non_release_refs_do_not_receive_a_tag_exception(tmp_path: Path, git_ref: str) -> None:
    _ = _write_wheel(tmp_path)
    _ = _write_sdist(tmp_path)

    release = verify_release_metadata(
        distribution_root=tmp_path,
        source_version="0.1.0",
        git_ref=git_ref,
    )

    assert release.version == "0.1.0"


def test_incomplete_or_unnamed_distribution_sets_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ReleaseMetadataError, match="exactly one wheel"):
        _ = verify_release_metadata(
            distribution_root=tmp_path,
            source_version="0.1.0",
            git_ref="refs/tags/v0.1.0",
        )

    _ = _write_wheel(tmp_path)
    _ = _write_wheel(tmp_path, "0.1.1")

    with pytest.raises(ReleaseMetadataError, match="exactly one wheel"):
        _ = verify_release_metadata(
            distribution_root=tmp_path,
            source_version="0.1.0",
            git_ref="refs/tags/v0.1.0",
        )


def test_cli_reports_the_verified_version_and_rejects_mismatch() -> None:
    runner = CliRunner()
    project_root = Path(__file__).resolve().parents[1]
    distribution_root = project_root / ".tmp-release-metadata-red"
    distribution_root.mkdir(exist_ok=True)
    wheel = _write_wheel(distribution_root)
    sdist = _write_sdist(distribution_root)

    try:
        passing = runner.invoke(app, ["--distribution-root", str(distribution_root), "--git-ref", "refs/tags/v0.1.0"])
        assert passing.exit_code == 0, passing.output
        assert '"version":"0.1.0"' in passing.output

        tampered = wheel.with_name("tampered.whl")
        with zipfile.ZipFile(wheel) as source, zipfile.ZipFile(tampered, "w") as target:
            for info in source.infolist():
                payload = source.read(info.filename)
                if info.filename.endswith("/METADATA"):
                    payload = _write_metadata_message("Antigravity-K", "9.9.9").as_string().encode("utf-8")
                _ = target.writestr(info, payload)
        _ = tampered.replace(wheel)

        failing = runner.invoke(app, ["--distribution-root", str(distribution_root), "--git-ref", "refs/tags/v0.1.0"])
        assert failing.exit_code == 2
        assert "wheel version 9.9.9 does not match wheel filename 0.1.0" in failing.output
    finally:
        wheel.unlink()
        sdist.unlink()
        distribution_root.rmdir()


def test_metadata_parser_reads_headers_from_both_distribution_formats(tmp_path: Path) -> None:
    wheel = _write_wheel(tmp_path, "1.2.3", name="Example-Project")
    sdist = _write_sdist(tmp_path, "1.2.3", name="Example-Project")

    for path in (wheel, sdist):
        message = BytesParser(policy=compat32).parsebytes(_metadata_text(path))

        assert message["Name"] == "Example-Project"
        assert message["Version"] == "1.2.3"
