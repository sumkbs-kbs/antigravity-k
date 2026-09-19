"""CR-14 F-34 회귀 — **게이트는 자기가 재는 코드를 바꾸지 않는다**.

발견(F-34, attempt-025 가 실제로 멈춘 자리 / attempt-026 에서 등록·폐쇄)
=====================================================================
`src/antigravity_k/dashboard_dist/` 는 **추적되는** 빌드 산출물이고(F-01) 서버가 그것을 서빙한다
(`api/server.py`). `dashboard-build` 게이트는 `pnpm run build` 로 그 디렉터리를 **다시 쓴다**.

attempt-025 는 `ApprovalQueue.tsx` 의 동의 문구를 고친 뒤 번들을 다시 만들지 않고 후보를
커밋했고, 그 사실을 알아낸 것은 **게이트가 아니라 다음 배치의 이어받기 거부**였다(``previous
report was produced from a different working tree``). attempt-023 도 같은 성질을 기록했다
(추적 번들이 매 빌드마다 수십 개 삭제·생성 → HEAD 상태로 복원).

그러니까 결함은 두 겹이다:

  ① **낡은 출하물을 재는 자리가 없다** — 대시보드 소스를 고치고 번들을 안 만들면 게이트는
     21/21 초록이고, 나가는 화면에는 **고치기 전의 UI** 가 실린다.
  ② **게이트가 코드를 바꿔도 아무도 실패하지 않는다** — 보고서는 `git.tree_fingerprint` 하나로
     \"21개 초록이 이 코드 상태의 것\"이라고 주장하는데, `dashboard-build` 가 트리를 옮긴
     뒤의 초록은 **다른 코드 상태**의 것이다.

고침: 지문을 만들던 **한 곳**(`ga_gate.tree_digests`)이 경로별 내용 지도를 돌려주게 하고,
게이트 실행 **직전과 직후**의 지도를 비교한다. 차이가 있으면 그 게이트의 `status` 는
`tree_moved` 가 되고(명령의 `exit_code` 는 그대로 남긴다 — 명령은 성공했고 실패한 것은
\"게이트는 측정 대상을 바꾸지 않는다\"는 계약이다), 실행 전체가 exit 1 로 끝난다. required 여부로
거르지 않으므로 non-required 게이트로 같은 결함이 조용해질 수 없다.

계약
====
  C14-F34-1 지문과 이동 탐지는 **같은 규칙**에서 나온다 — 지문은 경로 지도의 digest 다.
  C14-F34-2 게이트가 코드를 쓰면 그 게이트가 `tree_moved` 로 기록되고 실행이 빨개진다.
  C14-F34-3 무시되는 산출물(`.artifacts/`)만 쓰는 게이트는 걸리지 않는다(과잉 탐지 금지).
  C14-F34-4 **non-required 게이트**가 트리를 옮겨도 실행이 빨개진다.
  C14-F34-5 승인 검증기(`ga_gate_verify.py`)는 `tree_moved` 를 구조 오류로 적지 않되,
            그 보고서를 승인하지도 않는다(빨간 실행은 빨갛게 남는다).
  C14-F34-6 마감 검사가 그 사실을 거부한다(`scripts/verify_attempt_close.py` 항목 9).
  C14-F34-7 그 검사에 **물릴 대상이 실제로 있다** — 이 저장소의 required 게이트 중 하나가 추적
            번들을 제자리에서 다시 쓴다. 그 게이트를 지우면 이 계약이 먼저 깨진다.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE_SCRIPT = REPO_ROOT / "scripts" / "ga_gate.py"
VERIFIER_SCRIPT = REPO_ROOT / "scripts" / "ga_gate_verify.py"
MANIFEST = REPO_ROOT / "scripts" / "commercial_ga_gates.json"
VITE_CONFIG = REPO_ROOT / "dashboard" / "vite.config.ts"

# 추적되는 빌드 산출물 — 이 저장소가 \"게이트가 제자리에서 다시 쓰는 대상\"을 가진 이유다.
TRACKED_BUNDLE = "src/antigravity_k/dashboard_dist"
_PROBE = REPO_ROOT / ".tree-moved-probe.tmp"
_IGNORED_PROBE = REPO_ROOT / ".artifacts" / "tree-moved-ignored-probe.tmp"
_OUTDIR_RE = re.compile(r"outDir:\s*path\.resolve\(__dirname,\s*'([^']+)'\)")


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gate_module() -> ModuleType:
    return _load(GATE_SCRIPT, "cr14_f34_ga_gate")


@pytest.fixture()
def probe() -> Iterator[Path]:
    """탐지에 물릴 **추적되지 않은, 무시되지도 않은** 파일 — 끝나면 반드시 지운다.

    지우지 않으면 이 테스트 자신이 다음 측정의 트리를 옮긴다(그것이 이 결함의 성질이다).
    """
    assert not _PROBE.exists(), f"앞선 실행이 남긴 파일이 있다: {_PROBE.name}"
    yield _PROBE
    _PROBE.unlink(missing_ok=True)


def _manifest(path: Path, *, gates: list[dict[str, object]]) -> Path:
    path.write_text(
        json.dumps({"schema_version": 1, "dependency_locks": ["uv.lock"], "gates": gates}),
        encoding="utf-8",
    )
    return path


def _gate(gate_id: str, script: str, *, required: bool = True) -> dict[str, object]:
    return {
        "id": gate_id,
        "category": "python_backend",
        "command": [sys.executable, "-c", script],
        "cwd": ".",
        "timeout_seconds": 60,
        "required": required,
        "finding_ids": ["CR-14 F-34"],
        "task_ids": ["REL-02"],
    }


def _run(manifest: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATE_SCRIPT), "--manifest", str(manifest), "--output", str(output)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _gate_result(report_path: Path, gate_id: str) -> dict[str, object]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return next(gate for gate in report["gates"] if gate["id"] == gate_id)


# ---------------------------------------------------------------------------
# C14-F34-1 — 지문과 이동 탐지는 같은 규칙에서 나온다
# ---------------------------------------------------------------------------


def test_fingerprint_is_the_digest_of_the_same_path_map_movement_uses(gate_module: ModuleType) -> None:
    digests = gate_module.tree_digests(REPO_ROOT)
    assert digests, "경로 지도가 비어 있다 — 이 계약은 관측을 시작할 수 없다"
    assert gate_module._fingerprint_of(digests) == gate_module.worktree_fingerprint(REPO_ROOT), (
        "지문이 경로 지도의 digest 가 아니다 — 두 관측이 다른 규칙을 쓰면 한쪽만 넓어져 조용한 자리가 생긴다"
    )


def test_changed_paths_names_content_changes_and_appearing_or_missing_files(gate_module: ModuleType) -> None:
    before = {"a.py": "1", "b.py": "2", "kept.py": "3"}
    after = {"a.py": "9", "c.py": "4", "kept.py": "3"}
    assert gate_module.changed_paths(before, after) == ["a.py", "b.py", "c.py"], (
        "내용 변경·등장·소실 중 하나라도 놓치면 그 자리로 코드가 조용히 움직일 수 있다"
    )
    assert gate_module.changed_paths(before, before) == []


# ---------------------------------------------------------------------------
# C14-F34-2/3/4 — 러너가 실제로 물고, 무시되는 산출물에는 물지 않는다
# ---------------------------------------------------------------------------


def test_gate_that_writes_into_the_code_tree_is_recorded_as_tree_moved(tmp_path: Path, probe: Path) -> None:
    manifest = _manifest(
        tmp_path / "gates.json",
        gates=[_gate("writes-code", f"from pathlib import Path; Path({str(probe)!r}).write_text('x')")],
    )
    output = tmp_path / "report.json"
    completed = _run(manifest, output)

    assert completed.returncode == 1, "게이트가 측정 대상 코드를 바꿨는데 실행이 초록으로 끝났다"
    gate = _gate_result(output, "writes-code")
    assert gate["status"] == "tree_moved", f"status={gate['status']!r} — 게이트가 코드를 바꾼 사실이 기록되지 않았다"
    assert gate["exit_code"] == 0, "명령 자체의 결과는 지우면 안 된다(명령은 성공했고 계약이 깨진 것이다)"
    assert gate["tree_moved"] == [probe.name] or probe.name in gate["tree_moved"], (
        f"바뀐 경로를 대지 않는다: {gate.get('tree_moved')!r}"
    )
    assert "TREE-MOVED" in str(gate["stderr"]), "왜 빨간지가 게이트 결과에 남아 있지 않다"


def test_gate_that_writes_only_ignored_outputs_is_not_flagged(tmp_path: Path) -> None:
    """과잉 탐지 금지 — 게이트는 정상적으로 무시되는 산출물(보고서·캐시)을 쓴다."""
    script = f"from pathlib import Path; p = Path({str(_IGNORED_PROBE)!r}); p.parent.mkdir(parents=True, exist_ok=True); p.write_text('x')"
    manifest = _manifest(tmp_path / "gates.json", gates=[_gate("writes-artifact", script)])
    output = tmp_path / "report.json"
    try:
        completed = _run(manifest, output)
        assert completed.returncode == 0, f"무시되는 산출물에 물었다: {completed.stderr}"
        assert _gate_result(output, "writes-artifact")["status"] == "passed"
    finally:
        _IGNORED_PROBE.unlink(missing_ok=True)


def test_run_is_red_even_when_the_gate_that_moved_the_tree_is_not_required(tmp_path: Path, probe: Path) -> None:
    """required 로 거르면 게이트를 non-required 로 추가하는 순간 같은 결함이 조용해진다."""
    manifest = _manifest(
        tmp_path / "gates.json",
        gates=[
            _gate("optional-writer", f"from pathlib import Path; Path({str(probe)!r}).write_text('x')", required=False)
        ],
    )
    output = tmp_path / "report.json"
    completed = _run(manifest, output)
    report = json.loads(output.read_text(encoding="utf-8"))

    assert completed.returncode == 1, "non-required 게이트가 트리를 옮겼는데 실행이 초록이다"
    assert report["summary"]["required_failed"] == 0, "이 테스트는 required 실패가 아니라 불변식 때문에 빨개야 한다"
    assert report["gates"][0]["status"] == "tree_moved"


# ---------------------------------------------------------------------------
# C14-F34-5 — 승인 검증기는 이 상태를 구조 오류로 적지 않되 승인하지도 않는다
# ---------------------------------------------------------------------------


def _verifier_problems(status: str, exit_code: int) -> list[str]:
    verifier = _load(VERIFIER_SCRIPT, "cr14_f34_ga_gate_verify")
    gates = [
        {
            "id": "alpha",
            "status": status,
            "exit_code": exit_code,
            "required": True,
            "duration_seconds": 1.0,
            "started_at": "2026-09-13T00:00:00+00:00",
            "finished_at": "2026-09-13T00:00:01+00:00",
        }
    ]
    report = {
        "git": {"sha": "a" * 40},
        "gates": gates,
        "summary": {
            "total": 1,
            "passed": 0 if status != "passed" else 1,
            "failed": 0 if status == "passed" else 1,
            "required_failed": 0 if status == "passed" else 1,
        },
    }
    manifest = {"gates": [{"id": "alpha", "required": True}]}
    return list(verifier.verify_gate_report(report, manifest, None))


def test_verifier_does_not_call_tree_moved_a_structural_error_but_still_refuses_it() -> None:
    problems = _verifier_problems("tree_moved", 0)
    assert not any("exit_code=0 but status" in problem for problem in problems), (
        f"명령이 성공한 상태를 구조 오류로 적었다(그러면 진짜 원인이 가려진다): {problems}"
    )
    assert any(problem.startswith("required_red") for problem in problems), (
        f"게이트가 측정 대상을 바꾼 보고서를 승인 가능하다고 봤다: {problems}"
    )


def test_verifier_still_flags_a_passed_gate_with_a_nonzero_exit_code() -> None:
    """이빨 — 완화가 기존 검사를 무디게 만들지 않았는지 확인한다."""
    problems = _verifier_problems("passed", 1)
    assert any("status 'passed' but exit_code=1" in problem for problem in problems), problems


# ---------------------------------------------------------------------------
# C14-F34-7 — 그 검사에 물릴 대상이 실제로 있다
# ---------------------------------------------------------------------------


def test_production_manifest_rebuilds_a_tracked_artifact_in_place() -> None:
    """이 불변식은 **제자리에서 다시 쓰는 게이트가 있을 때만** 의미가 있다.

    `dashboard-build` 를 지우거나 outDir 을 저장소 밖으로 옮기면, 낡은 번들이 후보가 되어도
    아무도 걸리지 않는다(F-34 가 되살아난다) — 그 사실을 여기서 잡는다.
    """
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    builders = [
        gate
        for gate in manifest["gates"]
        if gate.get("required") is True
        and gate.get("cwd") == "dashboard"
        and "build" in gate.get("command", [])
        and "run" in gate.get("command", [])
    ]
    assert builders, "대시보드를 다시 빌드하는 required 게이트가 없다 — 낡은 번들을 재는 자리가 사라졌다"

    match = _OUTDIR_RE.search(VITE_CONFIG.read_text(encoding="utf-8"))
    assert match is not None, "vite 의 `build.outDir` 선언을 찾지 못했다"
    out_dir = (VITE_CONFIG.parent / match.group(1)).resolve()
    assert out_dir == (REPO_ROOT / TRACKED_BUNDLE).resolve(), (
        f"빌드 산출물 위치가 추적 번들이 아니다({out_dir}) — 게이트가 쓴 것을 아무도 다시 보지 않는다"
    )
