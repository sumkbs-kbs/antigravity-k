#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pydantic>=2.10.0,<3.0", "typer>=0.13.0,<1.0"]
# ///
# ─── How to run ───
# uv run scripts/ga_gate.py --manifest scripts/commercial_ga_gates.json --output .artifacts/commercial-ga.json
#
# 20개 gate는 한 프로세스 창에 다 들어가지 않을 수 있다. 이때는 단계별로 실행한다:
#   uv run scripts/ga_gate.py --manifest scripts/commercial_ga_gates.json \
#     --output .artifacts/commercial-ga.json --only python-ruff --only python-format
#   uv run scripts/ga_gate.py --manifest scripts/commercial_ga_gates.json \
#     --output .artifacts/commercial-ga.json --only python-tests --merge-into
# --merge-into는 **같은 후보 SHA·같은 manifest**의 결과만 이어받고, 같은 gate id는
# 이번 실행 결과로 교체한다. 다른 후보의 초록을 섞으려 하면 exit 2로 거부한다.

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
from typing import Annotated, ClassVar, Final, Literal

import typer
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from pydantic_core import PydanticCustomError

type JsonValue = None | bool | int | float | str | Sequence[JsonValue] | Mapping[str, JsonValue]

# gate 하나의 결과 레코드. `JsonValue` 와 같은 별칭을 쓰지 않으면 dict 값 타입이
# 불변(invariant)이라 단계별 병합 결과를 주고받을 때 basedpyright 가 막는다.
GateResult = dict[str, JsonValue]

OUTPUT_ENCODING: Final = "utf-8"
OUTPUT_ERRORS: Final = "backslashreplace"
PYTHON_ENVIRONMENT_VARIABLES: Final = (
    "CONDA_DEFAULT_ENV",
    "CONDA_PREFIX",
    "PIPAPI_PYTHON_LOCATION",
    "PYTHONHOME",
    "PYTHONPATH",
    "VIRTUAL_ENV",
)


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


# gate 결과를 무효화하는 것은 **코드·lock·workflow·설정** 변경이다. 계획서가 요구하는
# "결과 문서 커밋은 코드 후보와 별도"를 지키려면, 증거·계획 문서를 쓰는 것만으로 gate
# 결과가 낡아서는 안 된다. 그래서 지문에서 문서·증거 트리를 제외한다.
FINGERPRINT_EXCLUDED_PREFIXES: Final = ("docs/", ".omo/")


# 내용을 읽을 수 없는 항목(gitlink)을 표시하는 값. 작업 트리에서 gitlink(`vault_data`)는
# 디렉터리라 `_sha256` 이 `OSError` 로 떨어지고, 커밋 트리에서는 blob 이 아니다 — 두 경로가
# **같은 값**에 도달해야 커밋 지문과 작업 트리 지문을 비교할 수 있다(C14-F23 의 전제).
MISSING_CONTENT: Final = "missing"


def _tree_fingerprint(root: Path) -> str:
    """**코드** 작업 트리 내용의 지문.

    커밋 SHA 만으로는 미커밋 후보를 구분할 수 없고, `git status --porcelain` 만으로는
    내용 변화를 구분할 수 없다. 단계별 `--merge-into` 가 **다른 코드 상태의 초록**을
    이어 붙이지 못하도록 추적+미추적 코드 파일의 내용 hash 를 모아 지문을 만든다.
    `docs/`·`.omo/` 는 증거·문서 산출물이라 제외한다(C14-01 주석 참조).
    """
    listing = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--deduplicate"],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout.split(b"\0")
    digest = hashlib.sha256()
    for raw in sorted(entry for entry in listing if entry):
        relative = raw.decode("utf-8", "surrogateescape")
        if relative.startswith(FINGERPRINT_EXCLUDED_PREFIXES):
            continue
        digest.update(raw)
        digest.update(b"\0")
        path = root / relative
        try:
            digest.update(_sha256(path).encode())
        except OSError:
            digest.update(MISSING_CONTENT.encode())
        digest.update(b"\n")
    return digest.hexdigest()


def worktree_fingerprint(root: Path) -> str:
    """작업 트리 **코드** 지문 — 보고서에 적히는 값과 **같은 함수**다.

    마감 절차(`scripts/run_attempt_close.py`)가 이어받기 판단에 이 값을 넘긴다(F-27).
    절차가 지문을 따로 계산하면 규칙이 갈라진다 — 지문은 여기서만 만든다.
    """
    return _tree_fingerprint(root)


def _blob_content_hashes(root: Path, object_ids: Sequence[str]) -> dict[str, str]:
    """여러 blob 의 내용 sha256 을 **한 프로세스**로 읽는다.

    파일 3000개에 `git cat-file` 을 3000번 띄우면 지문 계산이 게이트만큼 느려진다 —
    `--batch` 는 요청을 한 번에 넣고 헤더(`<oid> <type> <size>` + LF + 내용 + LF)를 순서대로 돌려준다.
    """
    if not object_ids:
        return {}
    stream = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=root,
        input=("\n".join(object_ids) + "\n").encode(),
        check=True,
        capture_output=True,
    ).stdout
    hashes: dict[str, str] = {}
    offset = 0
    for _ in object_ids:
        newline = stream.index(b"\n", offset)
        header = stream[offset:newline].decode("utf-8", "replace").split()
        offset = newline + 1
        if len(header) < 3:  # `<oid> missing`
            if header:
                hashes[header[0]] = MISSING_CONTENT
            continue
        size = int(header[2])
        hashes[header[0]] = hashlib.sha256(stream[offset : offset + size]).hexdigest()
        offset += size + 1  # blob 내용 ë¤의 LF
    return hashes


def tree_fingerprint_of_commit(root: Path, rev: str, prefixes: Sequence[str] | None = None) -> str:
    """커밋 **트리**의 코드 지문 — 작업 트리를 쓰지 않고 git 객체만으로 계산한다.

    `_tree_fingerprint` 와 **같은 규칙**(경로 bytes · NUL · 내용 sha256 · LF)을 쓴다. 작업 트리를
    읽지 않으므로 체크아웃/미커밋 상태와 무관하게 과거 후보를 잴 수 있고, 그 성질 덕분에
    "선언된 증거가 지금도 그 후보의 것인가"를 물을 수 있다(C14-F23, `scripts/verify_attempt_close.py`).
    gitlink(모드 160000)는 blob 이 아니므로 `MISSING_CONTENT` 로 본다 — 작업 트리 경로도 같은 값에
    도달한다(위 주석 참조).
    """
    excluded = FINGERPRINT_EXCLUDED_PREFIXES if prefixes is None else tuple(prefixes)
    entries = subprocess.run(
        ["git", "ls-tree", "-r", "-z", "--full-tree", rev],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout.split(b"\0")
    scoped: list[tuple[bytes, str]] = []  # (경로 bytes, blob oid) — blob 이 아니면 oid 자리에 MISSING_CONTENT
    for entry in entries:
        if not entry:
            continue
        meta, _, raw_path = entry.partition(b"\t")
        _mode, kind, object_id = meta.split(b" ")
        relative = raw_path.decode("utf-8", "surrogateescape")
        if relative.startswith(excluded):
            continue
        scoped.append((raw_path, object_id.decode() if kind == b"blob" else MISSING_CONTENT))
    hashes = _blob_content_hashes(root, [oid for _path, oid in scoped if oid != MISSING_CONTENT])
    digest = hashlib.sha256()
    for raw_path, oid in sorted(scoped):
        digest.update(raw_path)
        digest.update(b"\0")
        digest.update(hashes.get(oid, MISSING_CONTENT).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def code_scope_changes(root: Path, base: str, head: str, prefixes: Sequence[str] | None = None) -> list[str]:
    """`base`..`head` 에서 **코드 스코프**(지문에 들어가는 범위)가 바뀐 경로.

    비어 있으면 두 리비전의 코드 트리는 같다 — 기록 커밋이 `docs/` 전용이었는지를 이 한 줄로
    판정할 수 있다(attempt-013 F-22: 기록 커밋이 `README.md` 를 고쳐 지문을 옮겼다).
    """
    excluded = FINGERPRINT_EXCLUDED_PREFIXES if prefixes is None else tuple(prefixes)
    listing = subprocess.run(
        ["git", "diff", "--name-only", "-z", base, head],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout.split(b"\0")
    names = [entry.decode("utf-8", "surrogateescape") for entry in listing if entry]
    return [name for name in names if not name.startswith(excluded)]


def _load_manifest(path: Path) -> Manifest:
    return Manifest.model_validate_json(path.read_bytes())


def _gate_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for variable in PYTHON_ENVIRONMENT_VARIABLES:
        environment.pop(variable, None)
    return environment


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


def _run_gate(gate: Gate, root: Path) -> tuple[GateResult, bool]:
    started_at = _utc_now()
    started = monotonic()
    try:
        process = subprocess.Popen(
            gate.command,
            cwd=root / gate.cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding=OUTPUT_ENCODING,
            errors=OUTPUT_ERRORS,
            env=_gate_environment(),
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
    result: GateResult = {
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


def _summary(results: Sequence[GateResult]) -> dict[str, int]:
    passed = sum(result["status"] == "passed" for result in results)
    required_failed = sum(result["required"] is True and result["status"] != "passed" for result in results)
    return {
        "failed": len(results) - passed,
        "passed": passed,
        "required_failed": required_failed,
        "total": len(results),
    }


class _CarriedError(ValueError):
    """이어받을 수 없는 이전 결과(다른 후보·다른 manifest)."""


def merge_refusal_reason(path: Path, sha: str, manifest_sha: str, tree_fingerprint: str) -> str | None:
    """이 보고서를 이어받을 수 없는 이유 — 이어받을 수 있으면 `None`.

    **규칙의 유일한 자리다.** 게이트(`_load_carried_gates`)와 마감 절차
    (`scripts/run_attempt_close.py`)가 둘 다 이 함수를 묻는다. 절차가 같은 규칙을 복제하면
    두 주체가 갈라지고 — 갈라지면 한쪽이 다른 쪽을 검사하지 못한다(F-27): 절차가
    "이어받는다"고 한 조합을 게이트가 거부해 실행이 중단되거나, 절차가 **조용히** 앞 배치의
    초록을 버린다.

    세 축을 본다: **후보 sha** · **manifest sha256** · **작업 트리 지문**. 하나라도 다르면
    이어받지 않는다 — 다른 코드 상태의 초록을 이 후보에 꿰매면 안 된다.
    """
    if not path.is_file():
        return None  # 이어받을 보고서가 없다 — 새로 시작해도 잃을 것이 없다
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return f"cannot read previous report {path}: {error}"
    if not isinstance(previous, dict):
        return f"previous report {path} is not an object"
    previous_sha = str((previous.get("git") or {}).get("sha", ""))
    if previous_sha != sha:
        return f"previous report is for candidate {previous_sha!r}, not {sha!r}"
    previous_manifest = str((previous.get("manifest") or {}).get("sha256", ""))
    if previous_manifest != manifest_sha:
        return "previous report was produced from a different gate manifest"
    previous_fingerprint = str((previous.get("git") or {}).get("tree_fingerprint", ""))
    if previous_fingerprint != tree_fingerprint:
        return (
            "previous report was produced from a different working tree "
            f"({previous_fingerprint[:16]}… != {tree_fingerprint[:16]}…) — "
            "results from another code state must not be stitched into this candidate"
        )
    return None


def _load_carried_gates(
    path: Path, sha: str, manifest_sha: str, tree_fingerprint: str
) -> dict[str, dict[str, JsonValue]]:
    """--merge-into: 이전 실행 결과를 같은 후보에 한해 이어받는다.

    한 번의 프로세스 창(예: 10분 clamp) 안에 20개 gate를 끝낼 수 없을 때 단계별로
    실행하되, **다른 후보나 다른 manifest의 결과는 절대 섞지 않는다**. 같은 gate id는
    이번 실행 결과로 교체되므로 오래된 초록이 남지 않는다.

    판단은 `merge_refusal_reason` **한 곳**이 한다 — 마감 절차도 같은 함수를 묻는다(F-27).
    """
    problem = merge_refusal_reason(path, sha, manifest_sha, tree_fingerprint)
    if problem is not None:
        raise _CarriedError(problem)
    if not path.is_file():
        return {}
    previous = json.loads(path.read_text(encoding="utf-8"))
    carried: dict[str, dict[str, JsonValue]] = {}
    for gate in previous.get("gates") or []:
        if isinstance(gate, dict) and gate.get("id"):
            carried[str(gate["id"])] = gate
    return carried


def _ordered_gates(manifest: Manifest, carried: dict[str, dict[str, JsonValue]]) -> list[dict[str, JsonValue]]:
    """manifest 순서로 정렬해 결과 목록을 만든다(결과를 dict 로 두면 순서가 흔들린다)."""
    return [carried[gate.id] for gate in manifest.gates if gate.id in carried]


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
    merge_into: Annotated[
        bool,
        typer.Option(
            "--merge-into",
            help="Carry earlier results from --output when they belong to the same candidate and manifest.",
        ),
    ] = False,
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
    sha = _git(root, "rev-parse", "HEAD")
    manifest_sha = _sha256(manifest_path)
    tree_fingerprint = worktree_fingerprint(root)
    carried: dict[str, dict[str, JsonValue]] = {}
    if merge_into:
        try:
            carried = _load_carried_gates(output, sha, manifest_sha, tree_fingerprint)
        except _CarriedError as error:
            typer.echo(f"cannot merge: {error}", err=True)
            raise typer.Exit(code=2) from error
    report: dict[str, JsonValue] = {
        "schema_version": 1,
        "generated_at": _utc_now(),
        "git": {
            "sha": sha,
            "dirty": bool(_git(root, "status", "--porcelain")),
            "tree_fingerprint": tree_fingerprint,
            "tree_fingerprint_scope": "code (docs/ and .omo/ excluded)",
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
        },
        "manifest": {"path": str(manifest_path), "sha256": manifest_sha},
        "output_decoding": {"encoding": OUTPUT_ENCODING, "errors": OUTPUT_ERRORS},
        "dependency_locks": locks,
        "merged": merge_into,
        "gates": [],
        "summary": {"failed": 0, "passed": 0, "required_failed": 0, "total": 0},
    }
    results: dict[str, GateResult] = {gate_id: gate for gate_id, gate in carried.items()}
    interrupted = False
    for gate in selected:
        typer.echo(f"[{gate.id}] {' '.join(gate.command)}")
        result, interrupted = _run_gate(gate, root)
        results[gate.id] = result
        report["gates"] = _ordered_gates(manifest, results)
        report["summary"] = _summary(report["gates"])
        _atomic_write(output, report)
        if interrupted:
            break
    ordered = _ordered_gates(manifest, results)
    report["gates"] = ordered
    report["summary"] = _summary(ordered)
    _atomic_write(output, report)
    if interrupted:
        raise typer.Exit(code=130)
    if _summary(ordered)["required_failed"] > 0:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    typer.run(main)
