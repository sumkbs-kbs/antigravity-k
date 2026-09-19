"""CR-14 F-18 계약 — `uv run` 게이트의 도구는 **lock 이 정의한 환경**에서 와야 한다.

발견(F-18, attempt-013)
=======================
`scripts/commercial_ga_gates.json` 의 게이트들이 `uv run --isolated --frozen <tool> ...` 형태로
돌았는데, 이 프로젝트의 dev 도구는 `[project.optional-dependencies].dev` 에 있고 `uv run` 은 그
extra 를 기본으로 설치하지 않는다 — 그래서 `--isolated` 가 만드는 임시 환경에는
`pytest`·`ruff`·`mypy`·`basedpyright` 가 **없었다**(실측: 임시환경 bin 목록에 없음,
`importlib.util.find_spec("pytest") is None`). 도구가 환경에 없으면 uv 는 **호출 셸의 PATH** 에서
찾는다. 그래서 같은 `uv.lock` sha256 으로 두 번 돌린 게이트가 서로 다른 환경을 검증했다:

    attempt-011  pytest-9.1.1, plugins cov/asyncio/anyio,        .../.venv/bin/python3
    attempt-012  pytest-9.0.3, plugins cov/anyio/asyncio/typeguard/hypothesis,
                                                                /Users/mr.k/miniforge3/bin/python3.13

경고 수(1 vs 16)와 수집 수(6213 vs 6221)도 함께 달라졌다. 증인은 PATH 앞에 가짜 도구를 두고
게이트 명령을 그대로 실행한다 — 수정 전에는 **가짜가 실행됐고**(HIJACKED), 스위트는 조용히
ambient 환경을 통과시켰다. 즉 게이트 초록이 "lock 이 검증됐다"를 뜻하지 않았다.

같은 결함이 범주를 가리지 않았다 — 보안 게이트 `security-bandit` 의 `bandit` 은 pyproject 에
**선언조차 없었고**(실측: conda base 의 `bandit 1.9.4` 를 썼다) 그래서 처음 쓴 계약은
`python_backend` 만 덮고 있어 그것을 놓쳤다. 이 계약은 이제 **`uv run` 을 쓰는 모든 게이트**를
덮는다. bandit 은 dev extra 에 선언돼 lock 에 들어갔다(`dev` + `bandit 1.9.4`).

수정은 게이트 명령이 필요한 extra 를 명시해 도구를 lock 이 결정하게 하는 것이다. `rag` 는
chromadb 때문이다 — F-19: dev 만 넣으면 `VectorStore` 를 만드는 테스트들이
`ModuleNotFoundError: chromadb` 로 **실패**한다(ambient 환경에는 chromadb 가 항상 있어서
지금까지 초록이었다).

이 파일의 계약
==============
  1. 정적: `uv run` 게이트는 `--isolated --frozen` 뒤에 필요한 extra 를 명시한다.
  2. 기능: **게이트 명령 자체를** PATH 오염 상태에서 실행해도 가짜 도구를 쓰지 않는다
     (게이트마다 그 게이트가 쓰는 도구를 가짜로 세운다).

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
# `documents` 는 **출하하는 선택 extra** 다(data_recipes 의 PDF/DOCX 수집). 스위트에는 그 능력을
# 재는 테스트가 23건 있는데, 이 extra 가 게이트 환경에 없으면 그 23건이 **조용히 스킵**된다 —
# 게이트는 초록이고 아무도 그 능력을 재지 않는다(CR-14 F-30). 순수 파이썬 의존성이라
# (pypdf·python-docx) 설치 비용이 사실상 없고 lock 에도 있다.
PYTHON_BACKEND_EXTRAS = ("dev", "rag", "documents")
COMMON_EXTRAS = ("dev",)

requires_uv = pytest.mark.skipif(shutil.which("uv") is None, reason="uv 없이는 게이트 환경을 잴 수 없다")


def _gate_commands() -> list[tuple[str, str, list[str]]]:
    """게이트 파일에서 (id, category, command) 를 꺼낸다."""
    payload = json.loads(GATE_FILE.read_text(encoding="utf-8"))
    return [
        (str(gate["id"]), str(gate["category"]), [str(token) for token in gate["command"]]) for gate in payload["gates"]
    ]


def _uv_run_gates() -> list[tuple[str, str, list[str]]]:
    """`uv run` 으로 도는 게이트만 — 도구 출처가 lock 이어야 하는 게이트들."""
    return [gate for gate in _gate_commands() if gate[2][:2] == ["uv", "run"]]


def _env_prefix_and_tool(command: list[str]) -> tuple[list[str], str]:
    """게이트 명령을 (환경 접두사, 도구 토큰) 으로 가른다.

    예: `uv run --isolated --frozen --extra dev --extra rag pytest tests/ ...` →
        (["uv","run","--isolated","--frozen","--extra","dev","--extra","rag"], "pytest")
    """
    index = 2  # "uv", "run" 다음부터
    while index < len(command):
        token = command[index]
        if token == "--extra":
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        return command[:index], token
    raise AssertionError(f"게이트 명령에서 도구 토큰을 찾지 못했다: {command}")


def _find_pair(command: list[str], extra: str) -> list[str]:
    """`--extra <extra>` 쌍을 찾는다(없으면 빈 목록)."""
    for index, token in enumerate(command[:-1]):
        if token == "--extra" and command[index + 1] == extra:
            return [token, command[index + 1]]
    return []


def test_every_uv_gate_pins_its_extras() -> None:
    """정적 계약 — 도구가 lock 에서 오려면 게이트가 필요한 extra 를 명시해야 한다.

    `python_backend` 게이트는 스위트를 돌리므로 chromadb(`rag`)까지 필요하다 —
    그것이 빠지면 F-19 로 16건이 실패한다. 같은 이유로 출하 extra `documents` 도 필요하다:
    그 extra 를 재는 테스트가 스킵되지 않아야 한다는 것이 F-30 이다(스킵되면 게이트는 초록인데
    그 능력은 어디서도 검증되지 않는다).

    도구가 `python`(`python -m <module>` 형태)이면 extra 를 요구하지 않는다 — 인터프리터와
    프로젝트 패키지는 임시환경이 항상 제공한다(그 사실은 기능 계약이 PATH 오염으로 잰다).
    """
    gates = _uv_run_gates()
    assert gates, "uv run 게이트가 하나도 없다 — 게이트 파일이 잘못됐다"

    for gate_id, category, command in gates:
        assert "--isolated" in command, f"{gate_id}: --isolated 가 없다 — 도구 출처가 ambient 가 된다"
        assert "--frozen" in command, f"{gate_id}: --frozen 이 없다 — lock 이 고정되지 않는다"

        _, tool = _env_prefix_and_tool(command)
        if tool == "python":
            continue
        required = PYTHON_BACKEND_EXTRAS if category == "python_backend" else COMMON_EXTRAS
        for extra in required:
            assert _find_pair(command, extra) == ["--extra", extra], (
                f"{gate_id}: --extra {extra} 가 없다 — 이 extra 의 도구가 호출 셸에서 온다"
            )


def test_every_uv_gate_declares_its_tool_as_a_dependency() -> None:
    """정적 계약 — 게이트가 쓰는 도구는 pyproject 에 선언돼 있어야 lock 에 들어간다.

    선언 없는 도구(`bandit` 이 그랬다)는 `--extra` 를 붙여도 환경에 들어가지 않으므로
    여전히 PATH 로 떨어진다.
    """
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    dev_section = pyproject.split("dev = [", 1)
    assert len(dev_section) == 2, "pyproject 에서 dev extra 를 찾지 못했다"
    dev = dev_section[1].split("]", 1)[0]

    for gate_id, _, command in _uv_run_gates():
        _, tool = _env_prefix_and_tool(command)
        if tool == "python":  # `python -m module` 형태는 인터프리터 자체가 도구다
            continue
        assert f'"{tool}' in dev, f"{gate_id}: 도구 `{tool}` 이 dev extra 에 선언되지 않았다 — lock 밖에서 온다"


def _make_shims(directory: Path, tools: set[str]) -> None:
    """PATH 앞에 둘 가짜 도구 — 실행되면 자기 이름을 출력하고 0으로 끝난다."""
    for tool in tools:
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
    """기능 계약 — 게이트마다 그 게이트의 도구를 가짜로 세워도 게이트는 그것을 실행하지 않는다.

    게이트 명령의 **환경 접두사**를 그대로 쓰고 도구만 자기 것으로 바꾼다. 게이트에서 그 도구의
    extra 가 사라지면 도구가 임시환경에 없어 uv 가 PATH 로 떨어지고, 가짜가 실행되어 이 테스트가
    깨진다(F-18 의 정확한 재현).
    """
    gates = _uv_run_gates()
    assert gates

    probes = []
    for gate_id, _, command in gates:
        prefix, tool = _env_prefix_and_tool(command)
        probes.append((gate_id, prefix, tool))

    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="f18-shim-") as tmp:
        shim_dir = Path(tmp)
        _make_shims(shim_dir, {tool for _, _, tool in probes})

        for gate_id, prefix, tool in probes:
            probe = [*prefix, tool, "--version"]
            completed = _run_with_poisoned_path(probe, shim_dir)
            combined = completed.stdout + completed.stderr
            if SHIM_MARKER in combined:
                failures.append(f"{gate_id}: 호출 셸의 {tool} 를 실행했다 — {' '.join(probe)}")

    assert not failures, "게이트 도구 출처가 lock 이 아니다:\n" + "\n".join(failures)


@requires_uv
def test_gate_pytest_comes_from_the_locked_environment() -> None:
    """기능 계약 — 게이트가 쓰는 pytest/chromadb/bandit 은 lock 이 만든 환경 안에 있다.

    ambient(`.../.venv`, `~/miniforge3`)에서 왔다면 그 환경이 게이트 결과를 결정한다는 뜻이고,
    증빙의 `dependency_locks` sha256 은 그 사실을 보증하지 못한다.
    `chromadb` 는 F-19, `bandit` 은 보안 게이트의 F-18 자리다.
    """
    gates = {gate_id: command for gate_id, _, command in _uv_run_gates()}
    probe = (
        "import pytest, chromadb, bandit;"
        "print('PYTEST=' + str(pytest.__file__));"
        "print('CHROMADB=' + str(chromadb.__file__));"
        "print('BANDIT=' + str(bandit.__file__))"
    )
    completed = subprocess.run(  # noqa: S603
        [*_env_prefix_and_tool(gates["python-tests"])[0], "python", "-c", probe],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    output = completed.stdout + completed.stderr
    assert completed.returncode == 0, output

    for label in ("pytest", "chromadb", "bandit"):
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
