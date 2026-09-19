#!/usr/bin/env python
"""NX-02 후속 — **손상된 대화를 운영자가 어떻게 폐기하는가** 실측 프로브.

배경: `docs/09_OPERATION_GUIDE.md` 는 \"손상 대화 폐기 경로 없음\"을 기대하지 말 것 목록에
남겨 두었다(운영 절차 소유자 미정). 이 스크립트는 그 빈칸을 **추측이 아니라 실행으로** 채운다.

측정하는 것:
  1. view 가 손상됐을 때  (a) 읽기  (b) 제품의 delete  — 각각 무슨 일이 나는가
  2. journal 이 손상됐을 때 (a) 읽기  (b) 제품의 delete — 각각
  3. 제안하는 운영 절차(파일 격리 이동 + 삭제 표식)를 적용한 뒤의 상태
  4. 함정 확인: 격리 디렉터리를 **저장소 루트 안**에 두면 무슨 일이 나는가

전부 임시 디렉터리에서 돈다(저장소를 건드리지 않는다). 실행:
    .venv/bin/python docs/qa/2026-09-16-followup/nx02/repro_corrupt_disposal.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "src"))

from antigravity_k.engine.conversation_journal import (  # noqa: E402
    deletion_marker_path,
    write_deletion_marker,
)
from antigravity_k.engine.conversation_store import (  # noqa: E402
    ConversationStore,
    conversation_storage_relative_path,
)

PROJECT = "proj_nx02_quarantine"
CONV = "conv_nx02_quarantine"


def report(label: str, value: object) -> None:
    print(f"{label}: {value}")


def outcome(fn) -> str:
    """Run one call and describe the observable outcome (never raise)."""
    try:
        result = fn()
    except Exception as exc:  # noqa: BLE001 - 프로브는 모든 결과를 문자열로 남긴다
        return f"{type(exc).__name__}({getattr(exc, 'detail', '')[:70]})"
    return f"ok → {result!r}" if result is not None else "ok → None"


def new_store(root: Path) -> ConversationStore:
    os.environ["AGK_CONVERSATION_STORE_DIR"] = str(root)
    return ConversationStore(storage_dir=root)


def seed(root: Path) -> ConversationStore:
    store = new_store(root)
    store.append(project_id=PROJECT, conversation_id=CONV, expected_revision=0, role="user", content="원본 1")
    store.append(project_id=PROJECT, conversation_id=CONV, expected_revision=1, role="assistant", content="원본 2")
    return store


def paths(root: Path) -> dict[str, Path]:
    rel = conversation_storage_relative_path(PROJECT, CONV)
    view = root / rel
    return {
        "view": view,
        "journal": view.with_suffix(".jsonl"),
        "marker": deletion_marker_path(view),
        "lock": root / ".cas.lock",
    }


def case_view_corrupt(base: Path) -> None:
    print("\n=== 1. view 만 손상 (journal 은 정상) ===")
    root = base / "view-corrupt"
    seed(root)
    p = paths(root)
    p["view"].write_text("{ this is not json", encoding="utf-8")
    store = new_store(root)
    report("  read(get)", outcome(lambda: store.get(project_id=PROJECT, conversation_id=CONV)))
    report("  history_state", outcome(lambda: store.history_state(project_id=PROJECT, conversation_id=CONV)))
    report("  product delete", outcome(lambda: store.delete_conversation(project_id=PROJECT, conversation_id=CONV)))


def case_journal_corrupt(base: Path) -> None:
    print("\n=== 2. journal 손상 (중간 줄에 쓰레기) ===")
    root = base / "journal-corrupt"
    seed(root)
    p = paths(root)
    lines = p["journal"].read_text(encoding="utf-8").splitlines()
    lines.insert(max(1, len(lines) // 2), "{ not a journal event")
    p["journal"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    store = new_store(root)
    report("  original_history", outcome(lambda: store.original_history(project_id=PROJECT, conversation_id=CONV)))
    report("  read(get)", outcome(lambda: store.get(project_id=PROJECT, conversation_id=CONV)))
    report("  product delete", outcome(lambda: store.delete_conversation(project_id=PROJECT, conversation_id=CONV)))


def case_operator_procedure(base: Path) -> None:
    print("\n=== 3. 제안한 운영 절차: 격리 이동 + 삭제 표식 (코드 변경 없음) ===")
    root = base / "operator"
    seed(root)
    p = paths(root)
    # 손상을 만든다: journal 중간 줄 + view 는 손대지 않는다(view 도 같이 망가지면 둘 다 재현된다).
    lines = p["journal"].read_text(encoding="utf-8").splitlines()
    lines.insert(max(1, len(lines) // 2), "{ not a journal event")
    p["journal"].write_text("\n".join(lines) + "\n", encoding="utf-8")

    quarantine = base / "quarantine-20260916"  # 저장소 **밖**(§4 의 함정 회피)
    quarantine.mkdir(parents=True, exist_ok=True)
    moved: list[str] = []
    for key in ("view", "journal"):
        src = p[key]
        if src.exists():
            dst = quarantine / src.name
            shutil.move(str(src), str(dst))
            moved.append(f"{key} → {dst.name}")
    # 표식을 남긴다 → id 재사용 금지(제품 의미론과 동일하게 \"삭제됨\"으로 보이게).
    write_deletion_marker(p["view"], project_id=PROJECT, conversation_id=CONV, seq=0, revision=1)
    report("  격리 이동", moved)
    report("  표식 파일", p["marker"].exists())

    store = new_store(root)
    report("  history_state", outcome(lambda: store.history_state(project_id=PROJECT, conversation_id=CONV)))
    report("  read(get)", outcome(lambda: store.get(project_id=PROJECT, conversation_id=CONV)))
    report(
        "  id 재생성 시도(append rev0)",
        outcome(
            lambda: store.append(
                project_id=PROJECT, conversation_id=CONV, expected_revision=0, role="user", content="새 대화?"
            )
        ),
    )
    report("  격리본 보존", sorted(x.name for x in quarantine.iterdir()))


def case_quarantine_inside_root(base: Path) -> None:
    print("\n=== 4. 함정: 격리 디렉터리를 저장소 **안**에 두면 ===")
    root = base / "inside"
    seed(root)
    # 무관한 정상 대화 하나를 더 만든다(다른 대화까지 영향받는지 보려고).
    other = new_store(root)
    other.append(
        project_id="proj_other", conversation_id="conv_other", expected_revision=0, role="user", content="정상"
    )
    p = paths(root)
    inside = root / "quarantine"  # ← 저장소 루트 안
    inside.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p["view"], inside / p["view"].name)
    store = new_store(root)
    report("  storage_layout_state", outcome(lambda: store.storage_layout_state()))
    report(
        "  무관한 정상 대화 읽기",
        outcome(lambda: store.get(project_id="proj_other", conversation_id="conv_other")),
    )


def main() -> None:
    base = Path(tempfile.mkdtemp(prefix="nx02-quarantine-probe-"))
    print(f"임시 디렉터리: {base}")
    try:
        case_view_corrupt(base)
        case_journal_corrupt(base)
        case_operator_procedure(base)
        case_quarantine_inside_root(base)
    finally:
        shutil.rmtree(base, ignore_errors=True)
        print("\n(임시 디렉터리 정리 완료)")


if __name__ == "__main__":
    main()
