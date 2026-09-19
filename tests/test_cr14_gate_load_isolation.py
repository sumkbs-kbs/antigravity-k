"""CR-14 F-21 계약 — wall-clock 임계값 테스트는 **기능 게이트 밖**에서 조용한 프로세스로 돈다.

발견(F-21, attempt-013)
=======================
F-18/F-19 로 게이트 환경을 lock 에 고정하자 `python-tests` 가 **1건 실패**했다:

    tests/test_benchmark_performance.py::test_context_enrich_total_latency
    context_enrich latency 6084.4ms exceeds threshold 6000ms

고립 실행은 안정적이었다 — 같은 환경에서 이 테스트만 돌리면 **2209 / 2209 / 2212ms**였다.
즉 6084ms 는 제품이 아니라 **6226개 테스트를 도는 프로세스 안에서 재었다는 사실**이 만든 값이다
(그 테스트의 주석도 임계값 근거로 "전체 suite 동시 실행 시 디스크 경합 헤드룸"을 적어 두었다 —
머신 부하를 임계값으로 덮는 방식이라, 더 느린 머신이나 더 무거운 환경에서는 그대로 깨진다).

게다가 그 파일의 실행 안내는 "느린 테스트 포함 실행 (기본: slow 마커로 skip)" 이라고 적고 있지만
**아무것도 그들을 deselect 하지 않는다**(`addopts`·collection hook 없음 — 실측: 두 마커 모두 게이트에서
그대로 실행됐다). 문서와 실제가 달랐던 또 하나의 자리다.

수정: 기능 게이트(`python-tests`)는 `-m "not benchmark"` 로 wall-clock 검사를 **제외**하고,
그 검사는 전용 게이트(`python-benchmark`, `-m benchmark`)에서 조용한 프로세스로 돈다.
검사를 빼는 것이 아니라 **재는 자리를 옮기는 것**이다 — 실측: `python-benchmark` 16 passed(16.9s).

이 파일의 계약
==============
  1. `tests/test_benchmark_performance.py` 의 모든 테스트는 `benchmark` 마커를 가진다
     (마커 없는 새 latency 테스트가 기능 게이트로 새는 것을 막는다).
  2. 기능 게이트는 그 마커를 제외하고, 전용 게이트가 그 마커를 **선별**해 required 로 돈다.
  3. 실제로 그 마커 표현식이 그 파일 전체를 제외한다(기능: 같은 인터프리터로 collect).
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE_FILE = REPO_ROOT / "scripts" / "commercial_ga_gates.json"
PERF_MODULE = REPO_ROOT / "tests" / "test_benchmark_performance.py"
BENCHMARK_MARKER = "benchmark"


def _gates() -> dict[str, dict[str, object]]:
    """게이트 id → 게이트 정의."""
    payload = json.loads(GATE_FILE.read_text(encoding="utf-8"))
    return {str(gate["id"]): gate for gate in payload["gates"]}


def _command(gate: dict[str, object]) -> list[str]:
    return [str(token) for token in gate["command"]]  # type: ignore[union-attr]


def _perf_test_functions() -> list[str]:
    """성능 모듈의 `test_*` 함수 이름 목록 (마커와 무관하게 전부)."""
    tree = ast.parse(PERF_MODULE.read_text(encoding="utf-8"))
    return [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
    ]


def _marked_benchmark() -> list[str]:
    """성능 모듈에서 `benchmark` 마커가 붙은 `test_*` 함수 이름 목록."""
    tree = ast.parse(PERF_MODULE.read_text(encoding="utf-8"))
    marked: list[str] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        for decorator in node.decorator_list:
            if BENCHMARK_MARKER in ast.unparse(decorator):
                marked.append(node.name)
                break
    return marked


def test_every_latency_test_carries_the_benchmark_marker() -> None:
    """정적 계약 — 성능 모듈의 모든 테스트가 `benchmark` 마커를 가진다.

    마커가 없으면 그 테스트는 기능 게이트로 새어 들어가 머신 부하로 required 게이트를 깬다.
    """
    all_tests = _perf_test_functions()
    marked = _marked_benchmark()

    assert all_tests, "성능 모듈에서 테스트를 찾지 못했다 — 파일이 바뀌었다"
    missing = sorted(set(all_tests) - set(marked))
    assert not missing, f"benchmark 마커 없는 latency 테스트: {missing}"


def test_functional_gate_excludes_and_dedicated_gate_selects_the_marker() -> None:
    """게이트 파일 계약 — 기능 게이트는 제외, 전용 게이트는 선별.

    둘 중 하나만 있어도 계약은 깨진다: 제외만 있으면 검사가 사라지고(커버리지 손실),
    선별만 있으면 머신 부하가 required 게이트를 흔든다.
    """
    gates = _gates()
    assert "python-tests" in gates, "기능 게이트가 사라졌다"
    assert "python-benchmark" in gates, "전용 성능 게이트가 없다 — 검사가 사라졌거나 도망갔다"

    functional = _command(gates["python-tests"])
    assert _marker_expression(functional) == f"not {BENCHMARK_MARKER}", (
        f"기능 게이트가 benchmark 마커를 제외하지 않는다: {' '.join(functional)}"
    )

    dedicated = _command(gates["python-benchmark"])
    assert _marker_expression(dedicated) == BENCHMARK_MARKER, (
        f"전용 게이트가 benchmark 만 선별하지 않는다: {' '.join(dedicated)}"
    )
    assert gates["python-benchmark"]["required"] is True, (
        "전용 성능 게이트가 required 가 아니다 — 성능 회귀가 승인 대상에서 빠진다"
    )


def _marker_expression(command: list[str]) -> str:
    """게이트 명령의 `-m <expr>` 값을 꺼낸다(없으면 빈 문자열)."""
    for index, token in enumerate(command[:-1]):
        if token == "-m":
            return command[index + 1]
    return ""


def _collect(expression: str) -> str:
    """같은 인터프리터로 성능 모듈을 collect 해 결과 요약을 돌려준다."""
    completed = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "pytest",
            str(PERF_MODULE.relative_to(REPO_ROOT)),
            "-m",
            expression,
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    return completed.stdout + completed.stderr


def test_marker_expression_really_deselects_the_whole_perf_module() -> None:
    """기능 계약 — 그 마커 표현식이 실제로 성능 모듈 전체를 제외하고, 전용 표현식은 전부 선별한다.

    게이트 파일과 pytest 의 실제 동작을 함께 잰다 — 문자열만 맞고 동작이 다르면 계약이 아니다.
    """
    expected = len(_perf_test_functions())

    excluded_output = _collect(f"not {BENCHMARK_MARKER}")
    assert "no tests collected" in excluded_output, f"기능 표현식이 성능 테스트를 남겼다:\n{excluded_output}"

    selected_output = _collect(BENCHMARK_MARKER)
    match = re.search(r"(\d+) tests? collected", selected_output)
    assert match is not None, f"전용 표현식의 collect 결과를 읽지 못했다:\n{selected_output}"
    assert int(match.group(1)) == expected, (
        f"전용 표현식이 {match.group(1)}건만 선별했다 — 성능 모듈은 {expected}건이다"
    )
