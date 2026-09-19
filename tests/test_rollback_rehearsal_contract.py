"""NX-03 rollback 리허설의 **계약 시험**(승격본) — “되돌리면 삭제가 살아나는가”를 고정한다.

무엇을 지키는가:

  1. **고정 판(version pin)**: 그림자 트리에 넣는 구버전 판에 **표식 코드가 없어야** 한다. 없으면 리허설이
     “현재 코드끼리 비교”하는 무의미한 시험이 된다(그림자 트리가 잘못 만들어지면 조용히 초록이 된다).
  2. **세 국면 계약**: ① 구버전끼리는 되살아난다(원형 결함) ② 현재가 삭제한 뒤에도 구버전은 다시 쓴다
     ③ **복귀하면 현재 코드가 거절한다**(되살아난 본문이 읽기 표면에 안 나오고 id 도 이어받지 않는다).
     ③ 이 롤백 위험의 **경계**를 정의하는 문장이고, 이 카드가 문서로만 주장하던 것을 실측으로 바꾼 곳이다.
  3. **이빨**: 프로브가 없으면 **실패**한다.
  4. **위생**: 리허설은 임시 경로만 쓴다(저장소 git status 델타 0).

탐색 순서는 승격 선례대로 승격 위치(`scripts/`) 우선, 스테이징(`docs/qa/…/nx03/`) 나중이다.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


def _repo_root() -> Path:
    """루트를 **걸어 올라가며** 찾는다 — 스테이징(`docs/…/promote2/`)과 승격 위치(`tests/`) 둘 다에서 살아야 한다."""
    override = os.environ.get("AGK_REPO_ROOT")
    if override:
        return Path(override).resolve()
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file() and (candidate / "src" / "antigravity_k").is_dir():
            return candidate
    raise RuntimeError("저장소 루트를 찾지 못했다 — AGK_REPO_ROOT 로 지정한다")


REPO_ROOT = _repo_root()
PROBE_CANDIDATES = (
    REPO_ROOT / "scripts" / "rollback_rehearsal.py",
    REPO_ROOT / "docs" / "qa" / "2026-09-16-followup" / "nx03" / "rollback_rehearsal.py",
)


def _probe_path() -> Path:
    for candidate in PROBE_CANDIDATES:
        if candidate.is_file():
            return candidate
    pytest.fail(
        "rollback 리허설 프로브를 찾지 못했다 — 승격 위치/스테이징 어디에도 없다: "
        + ", ".join(str(path) for path in PROBE_CANDIDATES)
    )


def _run_probe() -> tuple[int, str, dict[str, Any]]:
    path = _probe_path()
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(
        [sys.executable, str(path)], capture_output=True, text=True, cwd=str(REPO_ROOT), env=env, timeout=600
    )
    lines = [line for line in proc.stdout.splitlines() if line.startswith("RESULT ")]
    result = json.loads(lines[-1][len("RESULT ") :]) if lines else {}
    return proc.returncode, proc.stdout + proc.stderr, result


def test_pinned_revision_exists_and_predates_tombstones():
    """그림자 트리에 넣는 판이 실제로 **표식 이전**인가 — 아니면 리허설은 거짓말을 한다."""
    path = _probe_path()
    spec = importlib.util.spec_from_file_location("agk_rollback_rehearsal_probe", path)
    assert spec and spec.loader, f"프로브를 불러올 수 없다: {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    show = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "show", f"{module.OLD_REV}:src/antigravity_k/engine/session_manager.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    if show.returncode != 0:
        pytest.fail(
            f"구버전 판({module.OLD_REV})을 꺼낼 수 없다 — 얕은 클론이면 해당 커밋까지 받거나 리허설의 판을 "
            f"다시 고정해야 한다(그냥 넘어가면 리허설이 무의미해진다): {show.stderr.strip()[:300]}"
        )
    assert ".tombstones" not in show.stdout, (
        f"{module.OLD_REV} 판에 이미 표식 코드가 있다 — 이 판은 NX-03 **이후**이므로 그림자 비교가 성립하지 않는다"
    )


def test_three_boundaries_hold():
    """① 되살아남 · ② 되돌림 창에서 구버전은 다시 쓴다 · ③ 복귀하면 현재가 거절한다."""
    code, output, result = _run_probe()
    assert code == 0, f"리허설이 실패했다(exit {code}):\n{output[-2000:]}"
    assert result.get("failures") == [], f"경계 실패: {result.get('failures')}"
    assert result.get("boundaries") == 3, result.get("boundaries")
    observed = result["observed"]
    assert observed["old_revision_has_no_tombstones"]["old_rev"], "고정 판을 기록하지 않았다"
    assert observed["r1_old_binary_revives"]["file_after_save"] is True, (
        "구버전끼리 되살아나지 않는다고 나왔다 — 원형 결함 재현이 사라졌다면 리허설이 다른 것을 재고 있다"
    )
    assert observed["r2_current_delete_writes_tombstone"]["file_gone"] is True
    assert observed["r2_old_binary_still_writes"]["file_after_save"] is True, (
        "되돌림 창에서 구버전이 더 이상 쓰지 못한다 — 그렇다면 자동 회귀 금지의 근거를 다시 써야 한다"
    )
    assert observed["r3_roll_forward_refuses_revived_content"]["marker_visible"] is False, (
        "복귀 뒤에도 되살아난 본문이 읽힌다 — 롤백 피해가 창을 넘어 살아남는 **제품 결함**이다"
    )


def test_roll_forward_does_not_reuse_the_deleted_id():
    """③ 의 두 번째 조각: 삭제된 id 를 이어받지 않고 **새 id** 로 시작해야 한다(표식 세대가 이긴다)."""
    code, output, result = _run_probe()
    assert code == 0, f"리허설이 실패했다(exit {code}):\n{output[-2000:]}"
    observed = result["observed"]
    assert (
        observed["r3_roll_forward_refuses_revived_content"]["resumed_id"]
        != observed["r3_roll_forward_refuses_revived_content"]["created_id"]
    ), "삭제된 세션 id 를 그대로 이어받았다 — id 재사용 금지 계약이 깨졌다"


def test_rehearsal_does_not_dirty_the_repository():
    """위생: 그림자 트리도 임시 경로에 만든다."""
    before = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, cwd=str(REPO_ROOT), check=False
    ).stdout
    code, output, _result = _run_probe()
    assert code == 0, f"리허설이 실패했다(exit {code}):\n{output[-2000:]}"
    after = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, cwd=str(REPO_ROOT), check=False
    ).stdout
    new = set(after.splitlines()) - set(before.splitlines())
    assert not new, f"리허설이 저장소에 흔적을 남겼다: {sorted(new)}"
