#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pydantic>=2.10.0,<3.0", "typer>=0.13.0,<1.0"]
# ///
# ─── How to run ───
# uv run scripts/ga_gate.py --manifest scripts/commercial_ga_gates.json --output .artifacts/commercial-ga.json

from __future__ import annotations

import hashlib
import json
import os
import platform
import signal
import subprocess
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Annotated, ClassVar, Literal

import typer
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from pydantic_core import PydanticCustomError

type JsonValue = None | bool | int | float | str | Sequence[JsonValue] | Mapping[str, JsonValue]


class Gate(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    category: Literal[
        "accessibility", "dashboard", "docker", "package", "python_backend", "runtime", "security", "supply_chain"
    ]
    command: tuple[str, ...] = Field(min_length=1)
    cwd: Path
    timeout_seconds: int = Field(gt=0, le=28_800)
    required: bool
    finding_ids: tuple[str, ...] = Field(min_length=1)
    task_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("cwd")
    @classmethod
    def cwd_must_be_relative(cls, value: Path) -> Path:
        if value.is_absolute() or ".." in value.parts:
            raise PydanticCustomError("cwd_escape", "cwd must remain inside the repository")
        return value


class Manifest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    schema_version: Literal[1]
    dependency_locks: tuple[Path, ...] = Field(min_length=1)
    gates: tuple[Gate, ...] = Field(min_length=1)

    @field_validator("dependency_locks")
    @classmethod
    def locks_must_be_relative(cls, values: tuple[Path, ...]) -> tuple[Path, ...]:
        if any(value.is_absolute() or ".." in value.parts for value in values):
            raise PydanticCustomError("lock_escape", "dependency locks must remain inside the repository")
        return values


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


def _load_manifest(path: Path) -> Manifest:
    return Manifest.model_validate_json(path.read_bytes())


def _terminate(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "posix":
        os.killpg(process.pid, signal.SIGTERM)
    else:
        process.terminate()
    try:
        _ = process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()


def _run_gate(gate: Gate, root: Path) -> tuple[dict[str, bool | float | int | list[str] | str], bool]:
    started_at = _utc_now()
    started = monotonic()
    try:
        process = subprocess.Popen(
            gate.command,
            cwd=root / gate.cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
    except OSError as error:
        return (
            {
                "id": gate.id,
                "category": gate.category,
                "command": list(gate.command),
                "cwd": gate.cwd.as_posix(),
                "required": gate.required,
                "finding_ids": list(gate.finding_ids),
                "task_ids": list(gate.task_ids),
                "started_at": started_at,
                "finished_at": _utc_now(),
                "duration_seconds": round(monotonic() - started, 6),
                "exit_code": 127,
                "status": "failed",
                "stdout": "",
                "stderr": str(error),
            },
            False,
        )
    interrupted = False
    try:
        stdout, stderr = process.communicate(timeout=gate.timeout_seconds)
        exit_code = process.wait()
        status = "passed" if exit_code == 0 else "failed"
    except subprocess.TimeoutExpired:
        _terminate(process)
        stdout, stderr = process.communicate()
        exit_code = 124
        status = "timed_out"
    except KeyboardInterrupt:
        _terminate(process)
        stdout, stderr = process.communicate()
        exit_code = 130
        status = "interrupted"
        interrupted = True
    result: dict[str, bool | float | int | list[str] | str] = {
        "id": gate.id,
        "category": gate.category,
        "command": list(gate.command),
        "cwd": gate.cwd.as_posix(),
        "required": gate.required,
        "finding_ids": list(gate.finding_ids),
        "task_ids": list(gate.task_ids),
        "started_at": started_at,
        "finished_at": _utc_now(),
        "duration_seconds": round(monotonic() - started, 6),
        "exit_code": exit_code,
        "status": status,
        "stdout": stdout,
        "stderr": stderr,
    }
    return result, interrupted


def _summary(results: list[dict[str, bool | float | int | list[str] | str]]) -> dict[str, int]:
    passed = sum(result["status"] == "passed" for result in results)
    required_failed = sum(result["required"] is True and result["status"] != "passed" for result in results)
    return {
        "failed": len(results) - passed,
        "passed": passed,
        "required_failed": required_failed,
        "total": len(results),
    }


def _atomic_write(path: Path, report: dict[str, JsonValue]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        _ = stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def main(
    manifest_path: Annotated[Path, typer.Option("--manifest", exists=True, dir_okay=False)],
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
    list_only: Annotated[bool, typer.Option("--list", help="Validate and list gates without executing them.")] = False,
    only: Annotated[list[str] | None, typer.Option("--only", help="Run only the named gate; repeat for more.")] = None,
) -> None:
    root = Path(__file__).resolve().parents[1]
    try:
        manifest = _load_manifest(manifest_path)
        locks = [{"path": path.as_posix(), "sha256": _sha256(root / path)} for path in manifest.dependency_locks]
        for gate in manifest.gates:
            if not (root / gate.cwd).is_dir():
                raise FileNotFoundError(root / gate.cwd)
    except (FileNotFoundError, json.JSONDecodeError, ValidationError) as error:
        typer.echo(f"invalid manifest: {error}", err=True)
        raise typer.Exit(code=2) from error
    selected = [gate for gate in manifest.gates if only is None or gate.id in only]
    if only is not None and len(selected) != len(set(only)):
        typer.echo("invalid manifest selection: every --only gate must exist", err=True)
        raise typer.Exit(code=2)
    if list_only:
        typer.echo(json.dumps([gate.model_dump(mode="json") for gate in selected], indent=2))
        return
    if output is None:
        typer.echo("--output is required unless --list is used", err=True)
        raise typer.Exit(code=2)
    report: dict[str, JsonValue] = {
        "schema_version": 1,
        "generated_at": _utc_now(),
        "git": {"sha": _git(root, "rev-parse", "HEAD"), "dirty": bool(_git(root, "status", "--porcelain"))},
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
        },
        "manifest": {"path": str(manifest_path), "sha256": _sha256(manifest_path)},
        "dependency_locks": locks,
        "gates": [],
        "summary": {"failed": 0, "passed": 0, "required_failed": 0, "total": 0},
    }
    results: list[dict[str, bool | float | int | list[str] | str]] = []
    interrupted = False
    for gate in selected:
        typer.echo(f"[{gate.id}] {' '.join(gate.command)}")
        result, interrupted = _run_gate(gate, root)
        results.append(result)
        report["gates"] = results
        report["summary"] = _summary(results)
        _atomic_write(output, report)
        if interrupted:
            break
    if interrupted:
        raise typer.Exit(code=130)
    if _summary(results)["required_failed"] > 0:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    typer.run(main)
