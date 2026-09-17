"""NX-03 미완 항목 리허설: **구버전(tombstone 이전) 바이너리로 되돌리면** 삭제가 살아나는가.

체크리스트의 “tombstone 미지원 구버전 rollback 위험 통제 — 절차 문서화만 완료(자동 회귀 금지),
실리허설 미실시” 를 실측으로 바꾼다. 문서만으로는 “위험이 있다”는 주장이고, 여기서는 그 위험의
**크기와 경계**를 잰다 — 구버전이 되살린 데이터를 **다시 전진(roll-forward)했을 때 제품이 거절하는가**는
지금까지 아무도 재지 않았다.

세 국면(모두 임시 세션 디렉터리 — `~/.antigravity/sessions` 를 절대 쓰지 않는다):

  R1  구버전끼리: 같은 디렉터리에서 낡은 인스턴스가 삭제 뒤 저장하면 파일이 되살아나는가
      (NX-03 이 고친 결함의 원형 — 이 카드의 `before` 재현과 같은 모양).
  R2  되돌림 창: **현재 바이너리가 삭제**(tombstone 기록)한 뒤 **구버전이 그 id 를 되살릴 수 있는가.**
  R3  재전진: 구버전이 쓴 파일을 **현재 바이너리가 다시 읽을 때** 거절하는가, 아니면 본문이 보이는가
      (rollback 의 피해가 스스로 낫는지 — 이 리허설의 핵심 질문).

구버전 코드는 저장소 이력에서 꺼낸다(`d929da01^:src/antigravity_k/engine/session_manager.py`,
NX-03 이 커밋되기 직전 판). 그림자 트리(`<tmp>/shadow/src`)에 현재 `src/` 를 복사한 뒤 그 한 파일만
옛 판으로 바꿔 `PYTHONPATH` 로 실행하므로, 제품 트리는 읽기만 한다.

사용(저장소 루트):

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
        docs/qa/2026-09-16-followup/nx03/rollback_rehearsal.py

출력: 국면마다 JSON 한 줄 + 마지막 줄 `RESULT {…}` — exit 0 이면 세 국면 모두 계약대로.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
OLD_REV = "d929da01^"
OLD_SESSION_MANAGER = "src/antigravity_k/engine/session_manager.py"
MARKER = "ROLLBACK-REHEARSAL-MARKER"

# 자식 프로세스가 실행하는 드라이버. 모드마다 한 줄의 JSON 만 출력한다.
CHILD = r"""
import json, os, sys, time
from pathlib import Path
from antigravity_k.engine.session_manager import SessionManager

base = os.environ["NX03_BASE"]
workspace = os.environ["NX03_WS"]
signal = Path(os.environ["NX03_SIGNAL"])
mode = sys.argv[1]
marker = os.environ["NX03_MARKER"]
out = {"mode": mode}


def messages(manager):
    return [m.get("content", "") for m in manager.get_messages()]


def tombstones():
    d = Path(base) / ".tombstones"
    return sorted(p.name for p in d.glob("*.json")) if d.is_dir() else []


if mode == "create":
    a = SessionManager(base_dir=base)
    sid = a.start_session(project_path=workspace, resume=False)
    a.add_turn([{"role": "user", "content": marker}])
    a.save()
    out["session_id"] = sid
elif mode == "delete":
    a = SessionManager(base_dir=base)
    a.start_session(project_path=workspace, resume=True)
    out["deleted"] = a.clear_memory("all")
    out["tombstones"] = tombstones()
    out["file_gone"] = not (Path(base) / f"{a._session_id}.json").is_file()
elif mode == "stale_save":
    # 인스턴스를 띄워 세션을 메모리에 올린 뒤, 신호가 올 때까지 살아 있는다(긴 실행 프로세스 흉내).
    b = SessionManager(base_dir=base)
    sid = b.start_session(project_path=workspace, resume=True)
    out["loaded_id"] = sid
    deadline = time.time() + 60
    while not signal.exists() and time.time() < deadline:
        time.sleep(0.2)
    out["signalled"] = signal.exists()
    b.add_turn([{"role": "user", "content": "stale-writer-turn"}])
    try:
        b.save()
        out["save_ok"] = True
    except Exception as exc:  # noqa: BLE001 - 드라이버는 오류 클래스만 보고한다
        out["save_ok"] = False
        out["save_error"] = type(exc).__name__
    path = Path(base) / f"{sid}.json"
    out["file_after_save"] = path.is_file()
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        out["payload_markers"] = [m.get("content", "") for m in payload.get("messages", [])]
    out["tombstones"] = tombstones()
elif mode == "read":
    c = SessionManager(base_dir=base)
    try:
        sid = c.start_session(project_path=workspace, resume=True)
        out["resumed_id"] = sid
        out["messages"] = messages(c)
        out["marker_visible"] = marker in "\n".join(messages(c))
    except Exception as exc:  # noqa: BLE001
        out["error"] = type(exc).__name__
        out["marker_visible"] = False
    out["tombstones"] = tombstones()

print(json.dumps(out, ensure_ascii=False))
"""


def _emit(label: str, **fields: object) -> None:
    print(json.dumps({"boundary": label, **fields}, ensure_ascii=False, sort_keys=True), flush=True)


def _run(tree_src: Path, mode: str, *, base: Path, workspace: Path, signal: Path, wait: bool = False) -> dict:
    env = {
        **os.environ,
        "PYTHONPATH": str(tree_src),
        "PYTHONDONTWRITEBYTECODE": "1",
        "NX03_BASE": str(base),
        "NX03_WS": str(workspace),
        "NX03_SIGNAL": str(signal),
        "NX03_MARKER": MARKER,
    }
    proc = subprocess.Popen(
        [sys.executable, "-c", CHILD, mode],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if not wait:
        stdout, stderr = proc.communicate(timeout=120)
        if proc.returncode != 0:
            raise RuntimeError(f"{mode} 실패(exit {proc.returncode}): {stderr.strip()[-400:]}")
        return json.loads(stdout.strip().splitlines()[-1])
    return {"_process": proc}


def main() -> int:
    failures: list[str] = []
    observed: dict[str, object] = {}

    def check(name: str, condition: bool, detail: object) -> None:
        observed[name] = detail
        if not condition:
            failures.append(f"{name}: {detail}")

    with tempfile.TemporaryDirectory(prefix="nx03-rollback-") as tmp:
        root = Path(tmp)
        old_src = root / "shadow" / "src"
        shutil.copytree(REPO_ROOT / "src", old_src)
        old_text = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "show", f"{OLD_REV}:{OLD_SESSION_MANAGER}"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        (old_src / "antigravity_k" / "engine" / "session_manager.py").write_text(old_text, encoding="utf-8")
        current_src = REPO_ROOT / "src"
        has_tombstone_code = ".tombstones" in old_text
        check("old_revision_has_no_tombstones", not has_tombstone_code, {"old_rev": OLD_REV})
        workspace = root / "workspace"
        workspace.mkdir()

        # ── R1: 구버전끼리 — 삭제 뒤 낡은 인스턴스가 저장하면 되살아나는가 ─────────
        base1 = root / "r1" / "sessions"
        base1.mkdir(parents=True)
        created = _run(old_src, "create", base=base1, workspace=workspace, signal=root / "r1.signal")
        signal1 = root / "r1.signal"
        stale = _run(old_src, "stale_save", base=base1, workspace=workspace, signal=signal1, wait=True)
        deleted = _run(old_src, "delete", base=base1, workspace=workspace, signal=signal1)
        signal1.write_text("go", encoding="utf-8")
        proc = stale["_process"]
        stdout, _stderr = proc.communicate(timeout=120)
        stale_result = json.loads(stdout.strip().splitlines()[-1])
        check(
            "r1_old_binary_revives",
            bool(stale_result.get("file_after_save")) and MARKER in json.dumps(stale_result.get("payload_markers")),
            {
                "loaded_id": stale_result.get("loaded_id"),
                "created_id": created.get("session_id"),
                "file_after_save": stale_result.get("file_after_save"),
                "tombstones": deleted.get("tombstones"),
                "note": "NX-03 이전 코드는 표식이 없어 낡은 저장을 막지 못한다(원형 결함)",
            },
        )
        _emit(
            "r1_old_binary_no_tombstone",
            revived=bool(stale_result.get("file_after_save")),
            tombstone_files=deleted.get("tombstones"),
        )

        # ── R2/R3: 현재 바이너리가 삭제 → 구버전이 되살림 → 현재가 다시 읽음 ──────
        base2 = root / "r2" / "sessions"
        base2.mkdir(parents=True)
        created2 = _run(current_src, "create", base=base2, workspace=workspace, signal=root / "r2.signal")
        signal2 = root / "r2.signal"
        stale2 = _run(old_src, "stale_save", base=base2, workspace=workspace, signal=signal2, wait=True)
        deleted2 = _run(current_src, "delete", base=base2, workspace=workspace, signal=signal2)
        check(
            "r2_current_delete_writes_tombstone",
            bool(deleted2.get("tombstones")) and bool(deleted2.get("file_gone")),
            {"tombstones": deleted2.get("tombstones"), "file_gone": deleted2.get("file_gone")},
        )
        signal2.write_text("go", encoding="utf-8")
        stdout2, _stderr2 = stale2["_process"].communicate(timeout=120)
        stale2_result = json.loads(stdout2.strip().splitlines()[-1])
        check(
            "r2_old_binary_still_writes",
            bool(stale2_result.get("file_after_save")) is True,
            {
                "save_ok": stale2_result.get("save_ok"),
                "save_error": stale2_result.get("save_error"),
                "file_after_save": stale2_result.get("file_after_save"),
                "note": "구버전은 표식을 모르므로 되돌림 창에서는 삭제된 본문을 다시 쓴다",
            },
        )
        read_back = _run(current_src, "read", base=base2, workspace=workspace, signal=signal2)
        check(
            "r3_roll_forward_refuses_revived_content",
            bool(read_back.get("marker_visible")) is False,
            {
                "resumed_id": read_back.get("resumed_id"),
                "created_id": created2.get("session_id"),
                "marker_visible": read_back.get("marker_visible"),
                "error": read_back.get("error"),
                "tombstones": read_back.get("tombstones"),
                "note": "전진하면 표식 세대가 이겨 되살아난 본문이 읽기 표면에 나오지 않는다",
            },
        )
        _emit(
            "r2_rollback_window",
            old_binary_wrote=stale2_result.get("file_after_save"),
            tombstone_survived=read_back.get("tombstones"),
        )
        _emit(
            "r3_roll_forward",
            marker_visible=read_back.get("marker_visible"),
            resumed_id=read_back.get("resumed_id"),
            note="거절되면 rollback 피해는 창이 닫힐 때 국소화되고, 아니면 제품 결함으로 남는다",
        )

    print(
        "RESULT "
        + json.dumps({"boundaries": 3, "failures": failures, "observed": observed}, ensure_ascii=False, sort_keys=True)
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
