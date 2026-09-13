"""CR-14 F-18 계약 — 파이썬 게이트의 도구는 **lock 이 정의한 환경**에서 와야 한다.

발견(F-18, attempt-013)
=======================
`scripts/commercial_ga_gates.json` 의 파이썬 게이트 5종은 모두

    uv run --isolated --frozen <tool> ...

형태였다. 그런데 이 프로젝트의 dev 도구는 `[project.optional-dependencies].dev` 에 있고
`uv run` 은 그 extra 를 기본으로 설치하지 않는다 — 그래서 `--isolated` 가 만드는 임시 환경에는
`pytest`·`ruff`·`mypy`·`basedpyright` 가 **없었다**(실측: 임시환경 bin 목록에 없음,
`importlib.util.find_spec("pytest") is None`). 도구가 환경에 없으면 uv 는 **호출 셸의 PATH** 에서
찾는다. 그래서 같은 `uv.lock` sha256 으로 두 번 돌린 게이트가 서로 다른 환경을 검증했다:

    attempt-011  pytest-9.1.1, plugins cov/asyncio/anyio,        .../.venv/bin/python3
    attempt-012  pytest-9.0.3, plugins cov/anyio/asyncio/typeguard/hypothesis,
                                                                /Users/mr.k/miniforge3/bin/python3.13

경고 수(1 vs 16)와 수집 수(6213 vs 6221)도 함께 달라졌다. 증인은 PATH 앞에 가짜 도구를 두고
게이트 명령을 그대로 실행한다 — 수정 전에는 **가짜가 실행됐고**(HIJACKED), 스위트는 조용히
ambient 환경을 통과시켰다. 즉 게이트 초록이 "lock 이 검증됐다"를 뜻하지 않았다.

수정은 게이트 명령에 `--extra dev --extra rag` 를 넣어 도구를 lock 이 결정하게 하는 것이다
(`rag` 는 chromadb 때문이다 — F-19: dev 만 넣으면 `VectorStore` 를 만드는 테스트들이
`ModuleNotFoundError: chromadb` 로 **실패**한다. ambient 환경에는 chromadb 가 있었기 때문에
지금까지 초록이었다).

이 파일의 계약
==============
  1. 정적: 파이썬 게이트는 `--isolated --frozen` 뒤에 필요한 extra 를 명시한다.
  2. 기능: **게이트 명령 자체를** PATH 오염 상태에서 실행해도 가짜 도구를 쓰지 않는다.
  3. 기능: 게이트가 쓰는 pytest/chromadb 는 lock 이 만든 환경 안에 있다(ambient 가 아니다).

기능 계약은 게이트 파일에서 명령을 **그대로 읽어** 접두사로 쓴다 — 게이트에서 extra 가 사라지면
정적·기능 계약이 함께 깨진다(하드코딩하면 게이트 파일이 바뀌어도 초록이 유지된다).
`uv` 가 없으면 기능 계약은 스킵한다 — 잴 수 없으면 거짓 초록 대신 정직한 스킵.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE_FILE = REPO_ROOT / "scripts" / "commercial_ga_gates.json"
SHIM_MARKER = "AMBIENT_SHIM_RAN"
REQUIRED_EXTRAS = ("dev", "rag")
PROBE_TOOLS = ("pytest", "ruff", "mypy", "basedpyright")

requires_uv = pytest.mark.skipif(shutil.which("uv") is None, reason="uv 없이는 게이트 환경을 잴 수 없다")


def _python_gate_commands() -> list[tuple[str, list[str]]]:
    """게이트 파일에서 `python_backend` 게이트의 (id, command) 를 꺼낸다."""
    payload = json.loads(GATE_FILE.read_text(encoding="utf-8"))
    return [
        (str(gate["id"]), [str(token) for token in gate["command"]])
        for gate in payload["gates"]
        if gate["category"] == "python_backend"
    ]


def _env_prefix(command: list[str]) -> list[str]:
    """게이트 명령에서 도구 토큰 앞까지 — 즉 `uv run ... --extra ...` 환경 부분."""
    for index, token in enumerate(command):
        if token in PROBE_TOOLS:
            return command[:index]
    raise AssertionError(f"게이트 명령에서 도구 토큰을 찾지 못했다: {command}")


def _find_pair(command: list[str], extra: str) -> list[str]:
    """`--extra <extra>` 쌍을 찾는다(없으면 빈 목록)."""
    for index, token in enumerate(command[:-1]):
        if token == "--extra" and command[index + 1] == extra:
            return [token, command[index + 1]]
    return []


def test_every_python_gate_pins_its_extras() -> None:
    """정적 계약 — 파이썬 게이트는 uv 의 `--isolated --frozen` 형태이고 필요한 extra 를 명시한다.

    extra 명시가 사라지면 도구가 다시 호출 셸에서 온다 — 그 순간 게이트는 후보가 아니라
    실행자의 머신을 검증하게 된다.
    """
    gates = _python_gate_commands()
    assert gates, "python_backend 게이트가 하나도 없다 — 게이트 파일이 잘못됐다"

    for gate_id, command in gates:
        assert command[:2] == ["uv", "run"], f"{gate_id}: uv run 형태가 아니다 — {command}"
        assert "--isolated" in command, f"{gate_id}: --isolated 가 없다 — 도구 출처가 ambient 가 된다"
        assert "--frozen" in command, f"{gate_id}: --frozen 이 없다 — lock 이 고정되지 않는다"
        for extra in REQUIRED_EXTRAS:
            assert _find_pair(command, extra) == ["--extra", extra], (
                f"{gate_id}: --extra {extra} 가 없다 — 이 extra 의 도구가 호출 셸에서 온다"
            )


def _make_shims(directory: Path) -> None:
    """PATH 앞에 둘 가짜 도구 — 실행되면 자기 이름을 출력하고 0으로 끝난다."""
    for tool in PROBE_TOOLS:
        path = directory / tool
        path.write_text(f'#!/bin/sh\necho "{SHIM_MARKER} {tool}"\nexit 0\n')
        path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _run_with_poisoned_path(command: list[str], shim_dir: Path) -> subprocess.CompletedProcess[str]:
    """게이트 명령을 PATH 오염 상태에서 실행한다(호출 셸의 VIRTUAL_ENV 도 제거)."""
    env = dict(os.environ)
    env.pop("VIRTUAL_ENV", None)
    env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")
    return subprocess.run(  # noqa: S603 — 게이트 명령 그대로
        command,
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )


@requires_uv
def test_gate_tools_are_not_taken_from_the_calling_shell() -> None:
    """기능 계약 — 각 파이썬 게이트의 **환경 접두사**로 pytest 를 실행해도 가짜가 잡히지 않는다.

    PATH 앞에 가짜 `pytest` 를 두고 게이트 명령의 환경 접두사만 그대로 쓴다. 게이트에서
    `--extra dev` 가 사라지면 pytest 가 임시환경에 없어 uv 가 PATH 로 떨어지고, 가짜가 실행되어
    이 테스트가 깨진다(F-18 의 정확한 재현).
    """
    gates = _python_gate_commands()
    assert gates
    failures: list[str] = []

    with tempfile.TemporaryDirectory(prefix="f18-shim-") as tmp:
        shim_dir = Path(tmp)
        _make_shims(shim_dir)

        for gate_id, command in gates:
            probe = [*_env_prefix(command), "pytest", "--version"]
            completed = _run_with_poisoned_path(probe, shim_dir)
            combined = completed.stdout + completed.stderr
            if SHIM_MARKER in combined:
                failures.append(f"{gate_id}: 호출 셸의 pytest 를 실행했다 — {' '.join(probe)}")

    assert not failures, "게이트 도구 출처가 lock 이 아니다:\n" + "\n".join(failures)


@requires_uv
def test_gate_pytest_comes_from_the_locked_environment() -> None:
    """기능 계약 — 게이트가 쓰는 pytest/chromadb 는 lock 이 만든 임시 환경 안에 있다.

    ambient(`.../.venv`, `~/miniforge3`)에서 왔다면 그 환경이 게이트 결과를 결정한다는 뜻이고,
    증빙의 `dependency_locks` sha256 은 그 사실을 보증하지 못한다.
    `chromadb` 는 F-19 의 핵심 의존성이다 — dev extra 만으로는 `VectorStore` 테스트가 실패한다.
    """
    gates = dict(_python_gate_commands())
    tests_command = gates["python-tests"]
    probe = (
        "import sys, pytest, chromadb;"
        "print('PYTEST=' + str(pytest.__file__));"
        "print('CHROMADB=' + str(chromadb.__file__))"
    )
    completed = subprocess.run(  # noqa: S603
        [*_env_prefix(tests_command), "python", "-c", probe],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    output = completed.stdout + completed.stderr
    assert completed.returncode == 0, output

    for label in ("pytest", "chromadb"):
        path = _value_of(output, label.upper() + "=")
        assert path, f"{label}: 경로를 얻지 못했다\n{output}"
        assert "/.venv/" not in path, f"{label} 가 후보의 .venv 에서 왔다: {path}"
        assert "miniforge3" not in path, f"{label} 가 conda base 에서 왔다: {path}"


def _value_of(output: str, prefix: str) -> str:
    """`PREFIX=...` 한 줄의 값을 꺼낸다."""
    for line in output.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return ""
