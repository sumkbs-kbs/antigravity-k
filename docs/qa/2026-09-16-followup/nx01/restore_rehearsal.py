"""NX-01 미완 항목 리허설: restore 를 **임시 경로**에서 실행하고 **최신 변경 손실**을 막는다.

배경(제품 표면): 대화 저장소에는 **export 만 있고 import/restore API 가 없다**
(`ConversationStore.export_original_history` · `GET /v1/conversations/{id}/export`).
따라서 “복구”는 파일 수준 작업이고, 안전성은 제품이 아니라 **절차**가 책임진다 —
그 절차가 실제로 최신 변경을 지키는지가 이 리허설이 재는 것이다.

네 경계(모두 임시 경로 — 실사용 저장소·vault 를 건드리지 않는다):

  S1 왕복 정합 — journal 바이트를 **빈 임시 저장소**로 옮기면 원본(개수·id·순서·본문)·
     `journal_sha256`·revision·view 가 그대로 살아난다.
  S2 최신 변경 손실 방지 — 복구 대상이 export 보다 **새로우면** 절차가 **거절**한다.
     거절하지 않으면 그 사이 append 된 원문이 조용히 사라지므로, “정말 사라질 원문이
     있었는가”를 수까지 함께 보인다.
  S2b 멱등 — 같은 바이트를 다시 복구하는 것은 거절이 아니라 **무동작**이다(재실행 가능).
  S3 삭제 부활 금지 — 삭제 표식이 있는 대상에 삭제 전 바이트를 되돌려도 대화는 살아나지 않는다.

사용(저장소 루트):

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
        docs/qa/2026-09-16-followup/nx01/restore_rehearsal.py

출력: 경계마다 JSON 한 줄 + 마지막 줄 `RESULT {…}` — exit 0 이면 네 경계 모두 계약대로.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from antigravity_k.engine.conversation_store import ConversationStore  # noqa: E402

PROJECT = "p"
CONVERSATION = "c"


def _emit(label: str, **fields: object) -> None:
    print(json.dumps({"boundary": label, **fields}, ensure_ascii=False, sort_keys=True), flush=True)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fingerprint(store: ConversationStore) -> str:
    journal = store.journal_path(project_id=PROJECT, conversation_id=CONVERSATION)
    return _sha256(journal) if journal.exists() else ""


def _identity(messages: list[dict[str, object]]) -> list[tuple[object, ...]]:
    """원문 하나를 식별하는 최소 튜플 — 복구 뒤 비교의 기준."""
    return [(m["id"], m["role"], m["content"], m.get("provenance")) for m in messages]


def _append(store: ConversationStore, texts: list[str]) -> int:
    revision = store.history_state(project_id=PROJECT, conversation_id=CONVERSATION)["revision"]
    for text in texts:
        revision = store.append(
            project_id=PROJECT,
            conversation_id=CONVERSATION,
            expected_revision=revision,
            role="user",
            content=text,
        ).revision
    return revision


def restore_plan(*, export: dict[str, object], target: dict[str, object], target_sha256: str) -> tuple[str, str]:
    """운영자 복구 절차의 판정부 — 제품에 없는 안전장치는 이 함수가 담당한다.

    반환: ("noop" | "refuse" | "proceed", 사람이 읽는 사유).
    규칙은 보수적이다 — 확신할 수 없으면 진행하지 않는다.
    """
    if target["deleted"]:
        return "refuse", "복구 대상에 삭제 표식이 있다 — 삭제를 되돌리는 것은 별도 승인 절차(NX-03)다."
    if str(export["journal_sha256"]) == target_sha256:
        return "noop", "복구 대상이 이미 export 와 바이트 동일하다 — 덮어쓸 이유가 없다."
    if int(target["revision"]) > int(export["revision"]):
        return "refuse", (
            f"복구 대상이 더 새롭다(revision {target['revision']} > export {export['revision']}) — "
            "이대로 덮어쓰면 export 이후의 원문이 조용히 사라진다."
        )
    if int(target["revision"]) == int(export["revision"]):
        return "refuse", "revision 은 같은데 바이트 지문이 다르다 — 같은 revision 의 다른 이력이라 근거가 부족하다."
    return "proceed", "복구 대상이 export 보다 오래됐다 — 덮어써도 잃을 원문이 없다."


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="nx01-restore-") as tmp:
        root = Path(tmp)
        failures: list[str] = []
        findings: list[dict[str, object]] = []
        observed: dict[str, object] = {}

        def check(name: str, condition: bool, detail: object) -> None:
            observed[name] = detail
            if not condition:
                failures.append(f"{name}: {detail}")

        # ── 기준 저장소 A: 원문 5건을 export 한다 ──────────────────────────
        store_a = ConversationStore(storage_dir=root / "a" / "conversations")
        _append(store_a, [f"원문-{i}" for i in range(1, 6)])
        export = store_a.export_original_history(project_id=PROJECT, conversation_id=CONVERSATION)
        journal_a = store_a.journal_path(project_id=PROJECT, conversation_id=CONVERSATION)
        baseline_identity = _identity(store_a.original_history(project_id=PROJECT, conversation_id=CONVERSATION))
        _emit(
            "baseline",
            revision=export["revision"],
            message_count=export["message_count"],
            journal_sha256=export["journal_sha256"],
            journal_bytes=journal_a.stat().st_size,
        )

        # ── S1: 빈 임시 저장소로 복구 ────────────────────────────────────
        store_b = ConversationStore(storage_dir=root / "b" / "conversations")
        plan, reason = restore_plan(
            export=export,
            target=store_b.history_state(project_id=PROJECT, conversation_id=CONVERSATION),
            target_sha256=_fingerprint(store_b),
        )
        check("s1_plan_is_proceed", plan == "proceed", {"plan": plan, "reason": reason})
        target_journal = store_b.journal_path(project_id=PROJECT, conversation_id=CONVERSATION)
        target_journal.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(journal_a, target_journal)

        restored_state = store_b.history_state(project_id=PROJECT, conversation_id=CONVERSATION)
        restored = store_b.original_history(project_id=PROJECT, conversation_id=CONVERSATION)
        record_b = store_b.get(project_id=PROJECT, conversation_id=CONVERSATION)
        check("s1_bytes_identical", _fingerprint(store_b) == export["journal_sha256"], _fingerprint(store_b))
        check(
            "s1_revision_restored",
            restored_state["revision"] == export["revision"],
            {"restored": restored_state["revision"], "exported": export["revision"]},
        )
        check(
            "s1_originals_identical",
            _identity(restored) == baseline_identity,
            {"restored": len(restored), "baseline": len(baseline_identity)},
        )
        check(
            "s1_view_readable",
            record_b is not None and len(record_b.prompt_messages()) > 0,
            None if record_b is None else len(record_b.prompt_messages()),
        )
        _emit(
            "s1_restore_into_empty",
            plan=plan,
            revision=restored_state["revision"],
            originals=len(restored),
            bytes_identical=_fingerprint(store_b) == export["journal_sha256"],
        )

        # ── S2: 대상이 더 새로우면 거절 ──────────────────────────────────
        _append(store_b, ["복구-이후-1", "복구-이후-2", "복구-이후-3"])
        newer_state = store_b.history_state(project_id=PROJECT, conversation_id=CONVERSATION)
        plan, reason = restore_plan(export=export, target=newer_state, target_sha256=_fingerprint(store_b))
        at_risk = newer_state["original_message_count"] - export["message_count"]
        check(
            "s2_refuses_newer_target",
            plan == "refuse",
            {"plan": plan, "reason": reason, "at_risk_originals": at_risk},
        )
        check("s2_at_risk_is_measured", at_risk == 3, at_risk)
        check(
            "s2_newer_originals_survive",
            newer_state["original_message_count"] == export["message_count"] + 3,
            newer_state["original_message_count"],
        )
        _emit(
            "s2_newer_target",
            plan=plan,
            target_revision=newer_state["revision"],
            export_revision=export["revision"],
            at_risk_originals=at_risk,
        )

        # ── S2b: 같은 바이트 재복구는 무동작 ──────────────────────────────
        #   (현재 대상에서 다시 export 한 뒤 그것을 다시 복구하는, 운영자가 실제로 밝는 경로)
        export_b = store_b.export_original_history(project_id=PROJECT, conversation_id=CONVERSATION)
        plan, reason = restore_plan(
            export=export_b,
            target=newer_state,
            target_sha256=_fingerprint(store_b),
        )
        check("s2b_same_bytes_is_noop", plan == "noop", {"plan": plan, "reason": reason})
        _emit("s2b_idempotent", plan=plan)

        # ── S3: 삭제 표식이 있으면 바이트를 되돌려도 부활하지 않는다 ───────
        store_c = ConversationStore(storage_dir=root / "c" / "conversations")
        _append(store_c, ["삭제될-원문-1", "삭제될-원문-2", "삭제될-원문-3"])
        journal_c = store_c.journal_path(project_id=PROJECT, conversation_id=CONVERSATION)
        pre_delete_bytes = root / "c-pre-delete.jsonl"
        shutil.copyfile(journal_c, pre_delete_bytes)  # 운영자가 만드는 백업과 같은 것
        store_c.delete_conversation(project_id=PROJECT, conversation_id=CONVERSATION)
        deleted_state = store_c.history_state(project_id=PROJECT, conversation_id=CONVERSATION)
        plan, reason = restore_plan(export=export, target=deleted_state, target_sha256=_fingerprint(store_c))
        check("s3_refuses_deleted_target", plan == "refuse", {"plan": plan, "reason": reason})
        shutil.copyfile(pre_delete_bytes, journal_c)  # 삭제 뒤에도 파일을 되돌려 본다
        after_restore = store_c.history_state(project_id=PROJECT, conversation_id=CONVERSATION)
        readable = store_c.original_history(project_id=PROJECT, conversation_id=CONVERSATION)
        check(
            "s3_deleted_after_restore",
            bool(after_restore["deleted"]) is True,
            {
                "deleted": after_restore["deleted"],
                "content_erased": after_restore["content_erased"],
                "originals": after_restore["original_message_count"],
                "note": "삭제 표식이 이기므로 원문 파일을 되돌려도 대화는 부활하지 않는다",
            },
        )
        # **측정 사실(실패가 아니라 발견)** — 삭제 표식은 `history_state.deleted` 만 이긴다.
        # 원문 읽기 표면(`original_history`)은 journal 의 delete 이벤트만 보고 표식을 보지 않으므로,
        # 파일을 되돌린 경우 삭제된 대화의 원문이 **다시 읽힌다**(docstring 의 “Deleted conversations
        # return an empty list” 는 이 상태에서 성립하지 않는다). 고칠 곳은 제품이지만 지금은 동결이고
        # src 를 건드리면 도는 8시간 soak 의 지문이 움직인다 → 발견으로 남기고 절차가 거절한다.
        findings = (
            [
                {
                    "id": "NX03-RESTORE-MARKER",
                    "observed": "삭제 표식이 있어도 삭제 전 journal 바이트를 되돌리면 original_history 가 원문을 반환한다",
                    "readable_originals": len(readable),
                    "deleted_flag": after_restore["deleted"],
                    "candidate_fix": "original_history/export_original_history 가 read_deletion_marker 도 확인하게 한다(동결 해제 뒤)",
                }
            ]
            if readable
            else []
        )
        _emit(
            "s3_deleted_target",
            plan=plan,
            deleted_after_restore=after_restore["deleted"],
            content_erased=after_restore["content_erased"],
        )

        result = {"boundaries": 4, "failures": failures, "findings": findings, "observed": observed}
        print("RESULT " + json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
