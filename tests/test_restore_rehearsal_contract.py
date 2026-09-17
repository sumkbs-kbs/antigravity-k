"""NX-01 restore 리허설의 **계약 시험**(승격본) — 절차가 최신 변경을 조용히 버리지 못하게 고정한다.

무엇을 지키는가(이 시험이 없으면 리허설은 `docs/` 안에서 조용히 낡는다 — NX-10 창이 그 구멍을
닫으려고 검사기·판정기·프로브를 승격한 것과 같은 이유다):

  1. **판정부 계약**: `restore_plan` 의 네 가지 결정(진행 · 무동작 · 더 새로우면 거절 · 삭제면 거절).
     순수 함수라 제품 없이도 고정할 수 있고, 여기가 “최신 변경 손실 방지”의 심장이다.
  2. **리허설이 실제로 돈다**: 프로브를 별도 인터프리터로 실행해 exit 0 과 RESULT 의 경계 수·실패 0을 본다.
  3. **삭제 표식 계약**: 삭제된 대상에 바이트를 되돌려도 `deleted` 는 참이어야 한다(그 뒤 원문이 읽히는지
     여부는 아래 `DOCUMENTED_FINDING` 참조 — 미수리 결함은 **기록**으로 고정하고, 고쳐지면 통과한다).
  4. **이빨**: 프로브 파일이 없으면 **실패**한다(초록이 조용한 스킵이 아니다).
  5. **위생**: 리허설이 저장소를 더럽히지 않는다(git status 델타 0 — 임시 경로만 쓴다).

탐색 순서는 승격 선례를 따른다: 승격 위치(`scripts/`)를 먼저, 스테이징(`docs/qa/…/nx01/`)을 나중에 본다.
그래서 이 파일은 이동 전에도 초록이고 이동 뒤에도 초록이다.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _repo_root() -> Path:
    """루트를 **걸어 올라가며** 찾는다 — 스테이징(`docs/…/promote2/`)과 승격 위치(`tests/`) 둘 다에서 살아야 한다.

    `parents[1]` 를 쓰면 승격 뒤에만 맞고 스테이징에서는 nx10 디렉터리를 루트로 착각해
    모든 시험이 수집 단계에서 죽는다(승격 리허설이 잡으려는 함정을 실제로 밟은 자리).
    """
    override = os.environ.get("AGK_REPO_ROOT")
    if override:
        return Path(override).resolve()
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file() and (candidate / "src" / "antigravity_k").is_dir():
            return candidate
    raise RuntimeError("저장소 루트를 찾지 못했다 — AGK_REPO_ROOT 로 지정한다")


REPO_ROOT = _repo_root()
PROBE_CANDIDATES = (
    REPO_ROOT / "scripts" / "restore_rehearsal.py",
    REPO_ROOT / "docs" / "qa" / "2026-09-16-followup" / "nx01" / "restore_rehearsal.py",
)
DOCUMENTED_FINDING = "NX03-RESTORE-MARKER"


def _probe_path() -> Path:
    for candidate in PROBE_CANDIDATES:
        if candidate.is_file():
            return candidate
    pytest.fail(
        "restore 리허설 프로브를 찾지 못했다 — 승격 위치/스테이징 어디에도 없다: "
        + ", ".join(str(path) for path in PROBE_CANDIDATES)
    )


def _load_probe():
    path = _probe_path()
    spec = importlib.util.spec_from_file_location("agk_restore_rehearsal_probe", path)
    assert spec and spec.loader, f"프로브를 불러올 수 없다: {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repo_root_detection_survives_the_move():
    """프로브가 저장소 루트를 **걸어 올라가며** 찾는가 — 승격으로 깊이가 바뀌어도 살아야 한다."""
    module = _load_probe()
    assert Path(module.REPO_ROOT) == REPO_ROOT or (Path(module.REPO_ROOT) / "pyproject.toml").is_file(), (
        "프로브가 저장소 루트를 잘못 계산한다 — 승격 위치에서 src 경로가 어긋난다"
    )


@pytest.mark.parametrize(
    ("target", "fingerprint", "expected"),
    [
        ({"deleted": False, "revision": 3}, "old", "proceed"),
        ({"deleted": False, "revision": 5}, "same-bytes", "noop"),
        ({"deleted": False, "revision": 8}, "newer", "refuse"),
        ({"deleted": True, "revision": 0}, "", "refuse"),
        ({"deleted": False, "revision": 5}, "different-bytes", "refuse"),
    ],
)
def test_restore_plan_decisions(target: dict, fingerprint: str, expected: str):
    """판정부의 다섯 결정 — “최신 변경 손실 방지”가 여기 있다."""
    module = _load_probe()
    export = {"revision": 5, "journal_sha256": "same-bytes" if fingerprint == "same-bytes" else "export-bytes"}
    target_sha = (
        "same-bytes"
        if fingerprint == "same-bytes"
        else ("different-bytes" if fingerprint == "different-bytes" else "target-bytes")
    )
    plan, reason = module.restore_plan(export=export, target=target, target_sha256=target_sha)
    assert plan == expected, f"기대 {expected}, 실제 {plan} — {reason}"
    assert reason, "사유 없는 판정은 운영자에게 쓸모가 없다"


def test_rehearsal_runs_and_reports_four_boundaries():
    """프로브 전체 실행 — exit 0 과 RESULT 의 경계·실패 수를 본다."""
    path = _probe_path()
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(
        [sys.executable, str(path)], capture_output=True, text=True, cwd=str(REPO_ROOT), env=env, timeout=300
    )
    assert proc.returncode == 0, (
        f"리허설이 실패했다(exit {proc.returncode}):\n{proc.stdout[-2000:]}\n{proc.stderr[-1000:]}"
    )
    result_lines = [line for line in proc.stdout.splitlines() if line.startswith("RESULT ")]
    assert result_lines, f"RESULT 줄이 없다:\n{proc.stdout[-2000:]}"
    result = json.loads(result_lines[-1][len("RESULT ") :])
    assert result["failures"] == [], f"경계 실패: {result['failures']}"
    assert result["boundaries"] == 4, result["boundaries"]


def test_deleted_target_keeps_its_marker_after_bytes_return():
    """삭제 표식은 바이트를 되돌려도 이긴다 — 이 계약이 깨지면 restore 가 삭제를 되살린다."""
    path = _probe_path()
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(
        [sys.executable, str(path)], capture_output=True, text=True, cwd=str(REPO_ROOT), env=env, timeout=300
    )
    result = json.loads([line for line in proc.stdout.splitlines() if line.startswith("RESULT ")][-1][len("RESULT ") :])
    observed = result["observed"]
    assert observed["s3_refuses_deleted_target"]["plan"] == "refuse"
    assert observed["s3_deleted_after_restore"]["deleted"] is True, (
        "삭제 표식이 바이트 복구에 밀렸다 — 삭제가 되살아난다는 뜻이다"
    )


def test_documented_finding_still_reported_or_the_defect_is_fixed():
    """미수리 결함(`NX03-RESTORE-MARKER`)은 **기록으로** 고정한다.

    지금: 삭제 전 바이트를 되돌리면 원문이 다시 읽힌다(표식은 상태 플래그에만 적용된다).
    수리 뒤: 읽기 표면이 거절해야 하며, 그때는 이 시험이 그쪽을 요구한다.
    어느 쪽이든 “아무 일도 없었다”로 넘어가면 실패한다.
    """
    path = _probe_path()
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(
        [sys.executable, str(path)], capture_output=True, text=True, cwd=str(REPO_ROOT), env=env, timeout=300
    )
    result = json.loads([line for line in proc.stdout.splitlines() if line.startswith("RESULT ")][-1][len("RESULT ") :])
    findings = [item for item in result.get("findings", []) if item["id"] == DOCUMENTED_FINDING]
    if findings:
        assert findings[0]["readable_originals"] > 0, "발견을 적어 놓고 읽힌 원문 수를 안 남겼다"
        return
    # 수리된 경우: 원문이 읽히지 않아야 한다(프로브가 그때 경계를 하나 더 남긴다).
    assert result.get("s3_originals_withheld") or result["boundaries"] >= 5, (
        f"{DOCUMENTED_FINDING} 이 사라졌는데 대체 근거가 없다 — 수리했으면 원문이 읽히지 않음을 남겨야 한다"
    )


def test_rehearsal_does_not_dirty_the_repository():
    """위생: 임시 경로만 쓴다 — 리허설이 저장소를 바꾸면 그 뒤 게이트의 지문이 흔들린다."""
    path = _probe_path()
    before = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, cwd=str(REPO_ROOT), check=False
    ).stdout
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    subprocess.run(
        [sys.executable, str(path)], capture_output=True, text=True, cwd=str(REPO_ROOT), env=env, timeout=300
    )
    after = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, cwd=str(REPO_ROOT), check=False
    ).stdout
    new = set(after.splitlines()) - set(before.splitlines())
    assert not new, f"리허설이 저장소에 흔적을 남겼다: {sorted(new)}"
