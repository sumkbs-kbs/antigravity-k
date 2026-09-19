#!/usr/bin/env python
"""NX-02 후속 — **실제 사용자 저장소의 복사본**에서 격리 절차를 리허설한다.

`docs/09` 의 복구 표에는 두 항목이 "미실시"로 남아 있었다:
  - CR-01 대화 저장소 migration: **문서화만** (실제 사용자 storage 에 대해 돌린 적 없음)
  - 손상 대화 격리·폐기: 프로브(합성 데이터)까지만

이 스크립트는 **실데이터 사본**으로 둘을 한 번에 리허설한다. 원본은 **읽기만** 한다:
시작·종료에 sha256 전수 해시를 떠서 동일함을 확인하고, 다르면 스스로 실패로 보고한다.

순서 (현실의 운영 순서와 같다):
  1. 원본 저장소 전수 해시 → 사본 생성
  2. 사본에서 migration dry-run → apply → verify-only
  3. 사본에서 대화 하나를 손상 → **제안한 운영 절차**(루트 밖 격리 + 삭제 표식) 적용
  4. 검증: 대상은 삭제됨, **다른 대화는 멀쩡함**, id 재사용 금지
  5. 음성 대조군: 격리 디렉터리를 **루트 안**에 두면 형제 대화까지 실패하는지
  6. 원본 해시 재확인 → 동일해야 통과

실행: .venv/bin/python docs/qa/2026-09-16-followup/nx02/rehearse_real_store_quarantine.py
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
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

REAL_STORE = Path(os.environ.get("AGK_REHEARSAL_SOURCE_STORE") or (Path.home() / ".antigravity" / "conversations"))
MIGRATE = REPO / "scripts" / "migrate_conversation_storage.py"
PYTHON = str(REPO / ".venv" / "bin" / "python")
FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' — ' + detail) if detail else ''}")
    if not ok:
        FAILURES.append(label)


def tree_hashes(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        if path.is_file():
            out[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def ids_of(store_dir: Path, rel_view: Path) -> tuple[str, str]:
    """Read only the two id fields — never print conversation content."""
    data = json.loads((store_dir / rel_view).read_text(encoding="utf-8"))
    return str(data["project_id"]), str(data["conversation_id"])


def view_journal_seq_gaps(store_dir: Path) -> list[str]:
    """migration 이 view 와 journal 의 seq 를 맞춰 놓았는지 **읽기 없이** 검사한다.

    읽기가 먼저 일어나면 제품이 스스로 view 를 재생성해 버려서(설계된 reconcile 경로)
    migration 의 결과를 관측할 수 없다 — 그래서 파일만 직접 본다.
    """
    from antigravity_k.engine.conversation_journal import ConversationJournal

    gaps: list[str] = []
    for view in sorted(store_dir.rglob("v2/**/*.json")):
        rel = view.relative_to(store_dir).as_posix()
        if rel.endswith(".deleted.json"):
            continue
        try:
            data = json.loads(view.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - 손상 view 는 이 검사의 대상이 아니다
            continue
        journal = ConversationJournal(view.with_suffix(".jsonl"))
        if not journal.exists():
            gaps.append(f"{rel}: journal 없음")
            continue
        tail = journal.tail().seq
        view_seq = int(data.get("journal_seq") or 0)
        if view_seq != tail:
            gaps.append(f"{rel}: view_seq={view_seq} journal_seq={tail}")
    return gaps


def migrate(store_dir: Path, work: Path, label: str) -> dict[str, object]:
    """migration 3단계. 백업 디렉터리는 **케이스별로 분리**한다(비어 있지 않으면 거절된다 — 실측)."""
    print(f"\n=== CR-01 migration 리허설 ({label}) ===")
    report: dict[str, object] = {}
    backup = work / f"backup-{label.replace(' ', '-')}"
    for label_, args in (
        ("dry-run", ["--storage-dir", str(store_dir)]),
        ("apply", ["--storage-dir", str(store_dir), "--apply", "--backup-dir", str(backup)]),
        ("verify-only", ["--storage-dir", str(store_dir), "--verify-only"]),
    ):
        proc = subprocess.run(
            ["uv", "run", "--no-sync", "python", str(MIGRATE), *args],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        report[label_] = {"exit": proc.returncode, "stdout_tail": proc.stdout.strip().splitlines()[-3:]}
        check(f"migration {label_} exit 0", proc.returncode == 0, f"exit={proc.returncode}")
    print(f"  report: {json.dumps(report, ensure_ascii=False)}")
    return report


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    work = Path(tempfile.mkdtemp(prefix=f"nx02-rehearsal-{stamp}-"))
    print(f"원본: {REAL_STORE}")
    print(f"작업: {work}")
    before = tree_hashes(REAL_STORE)
    check("원본 저장소에 파일이 있다", bool(before), f"{len(before)}개 파일")

    try:
        # ── 1. 사본 ──────────────────────────────────────────────────────────
        store = work / "store"
        shutil.copytree(REAL_STORE, store, symlinks=True)
        check("사본이 원본과 동일", tree_hashes(store) == before)

        # 원본 레거시 파일을 읽어 id 를 얻는다(내용은 출력하지 않는다).
        legacy_views = sorted(p.relative_to(store).as_posix() for p in store.rglob("*.json"))
        pairs = [ids_of(store, Path(rel)) for rel in legacy_views]
        print(f"  리허설 대상 대화 {len(pairs)}개 (id 개수 기준)")

        # ── 2. migration ────────────────────────────────────────────────────
        migrate(store, work, "실데이터 사본")
        migrated = sorted(p.relative_to(store).as_posix() for p in store.rglob("v2/**/*.json"))
        check("migration 후 v2 레이아웃 생성", bool(migrated), f"{len(migrated)}개 view")
        state = ConversationStore(storage_dir=store).storage_layout_state()
        check("layout == v2", state == "v2", state)
        # 단언이 아니라 **관측**이다(도구가 이미 정당하다고 문서화한 상태 — §관측 참조).
        gaps = view_journal_seq_gaps(store)
        print(f"  [관측] 백필 직후 view/journal seq 불일치 {len(gaps)}건" + (f": {gaps}" if gaps else ""))
        print("         → 첫 읽기에서 view 가 journal 로부터 재생성된다(제품의 설계된 reconcile 경로).")

        # ── 3. 손상 + 운영 절차 ─────────────────────────────────────────────
        print("\n=== 손상 대화 격리·폐기 리허설 (실데이터 사본) ===")
        target_project, target_conv = pairs[0]
        victim_rel = Path(conversation_storage_relative_path(target_project, target_conv))
        victim = store / victim_rel
        if not victim.is_file():
            # migration 이 view 를 옮겼다면 v2 경로에서 다시 찾는다
            candidates = [p for p in Path(store).rglob("*.json") if "v2/" in p.as_posix()]
            victim = candidates[0]
            target_project, target_conv = ids_of(store, victim.relative_to(store))
        control_project, control_conv = pairs[1] if len(pairs) > 1 else (pairs[0][0], pairs[0][1] + "-control")

        victim.write_text("{ corrupted by rehearsal", encoding="utf-8")
        broken = ConversationStore(storage_dir=store)
        try:
            broken.get(project_id=target_project, conversation_id=target_conv)
            check("손상 view 읽기가 거절된다", False, "예외 없이 통과했다")
        except Exception as exc:  # noqa: BLE001
            check("손상 view 읽기가 거절된다", True, type(exc).__name__)

        quarantine = work / "quarantine" / stamp  # ← 저장소 **밖**
        quarantine.mkdir(parents=True, exist_ok=True)
        moved = []
        for suffix in (".json", ".jsonl"):
            src = victim.with_suffix(suffix)
            if src.is_file():
                shutil.move(str(src), str(quarantine / src.name))
                moved.append(src.name)
        write_deletion_marker(victim, project_id=target_project, conversation_id=target_conv, seq=0, revision=0)
        check(
            "view 가 저장소에서 사라지고 표식이 생겼다", not victim.exists() and deletion_marker_path(victim).is_file()
        )
        check("격리본이 보존됐다", bool(moved), f"{len(moved)}개 파일")

        healed = ConversationStore(storage_dir=store)
        state = healed.history_state(project_id=target_project, conversation_id=target_conv)
        check("대상은 삭제됨으로 보인다", state["deleted"] is True and state["exists"] is False, str(state))
        try:
            healed.append(
                project_id=target_project, conversation_id=target_conv, expected_revision=0, role="user", content="x"
            )
            check("삭제된 id 재사용이 금지된다", False, "append 가 통과했다")
        except Exception as exc:  # noqa: BLE001
            check("삭제된 id 재사용이 금지된다", True, type(exc).__name__)
        try:
            sibling = healed.get(project_id=control_project, conversation_id=control_conv)
            check("형제 대화는 여전히 읽힌다", sibling is not None)
        except Exception as exc:  # noqa: BLE001
            check("형제 대화는 여전히 읽힌다", False, type(exc).__name__)

        # ── 5. 음성 대조군: 격리 위치를 루트 안에 두면 ───────────────────────
        # **합성 데이터 프로브에서 "항상 치명적"으로 보였던 것이 실데이터 사본에서는
        # 재현되지 않았다. 그래서 "마이그레이션 완료 표식이 있는가" 두 상태를 나눠 측정한다.
        print("\n=== 음성 대조군 A: 마이그레이션 **전** 저장소 + 루트 안 격리 ===")
        a_store = work / "store-inside-unmigrated"
        shutil.copytree(REAL_STORE, a_store, symlinks=True)
        a_q = a_store / "quarantine"
        a_q.mkdir(parents=True, exist_ok=True)
        legacy_json = next(p for p in a_store.rglob("*.json"))
        shutil.copy2(legacy_json, a_q / legacy_json.name)
        a_inside = ConversationStore(storage_dir=a_store)
        a_layout = a_inside.storage_layout_state()
        check(
            "표식 없는 저장소는 레거시로 오인된다(검사가 fail-closed)",
            a_layout == "legacy_requires_migration",
            a_layout,
        )
        try:
            a_inside.get(project_id=control_project, conversation_id=control_conv)
            check("무관한 대화도 실패한다", False, "읽기가 통과했다 — 함정이 재현되지 않았다")
        except Exception as exc:  # noqa: BLE001
            check("무관한 대화도 실패한다", True, type(exc).__name__)

        print("\n=== 음성 대조군 B: 마이그레이션 **후** 저장소 + 루트 안 격리 (관측) ===")
        b_store = work / "store-inside-migrated"
        shutil.copytree(REAL_STORE, b_store, symlinks=True)
        migrate(b_store, work, "음성 대조군 B")
        b_views = sorted(b_store.rglob("v2/**/*.json"))
        if not b_views:
            check("음성 대조군 B 전제(v2 view 존재)", False, "migration 이 적용되지 않았다")
        else:
            b_q = b_store / "quarantine"
            b_q.mkdir(parents=True, exist_ok=True)
            shutil.copy2(b_views[0], b_q / b_views[0].name)
            b_inside = ConversationStore(storage_dir=b_store)
            b_layout = b_inside.storage_layout_state()
            check(
                "표식이 있으면 루트 안 잉여 파일을 견딘다(관측)",
                b_layout == "v2",
                b_layout,
            )
            try:
                sibling_b = b_inside.get(project_id=control_project, conversation_id=control_conv)
                check("그 상태에서도 대화는 읽힌다(관측)", sibling_b is not None)
            except Exception as exc:  # noqa: BLE001
                check("그 상태에서도 대화는 읽힌다(관측)", False, type(exc).__name__)
            verify = subprocess.run(
                ["uv", "run", "--no-sync", "python", str(MIGRATE), "--storage-dir", str(b_store), "--verify-only"],
                cwd=REPO,
                capture_output=True,
                text=True,
            )
            check(
                "검증기(verify-only)는 잉여 파일에도 통과한다(관측)",
                verify.returncode == 0,
                f"exit={verify.returncode} {verify.stdout.strip().splitlines()[-3:]}",
            )
    finally:
        after = tree_hashes(REAL_STORE)
        print("\n=== 원본 무변경 확인 ===")
        check("원본 저장소 해시 동일", after == before, f"before={len(before)} after={len(after)}")
        shutil.rmtree(work, ignore_errors=True)
        print(f"(작업 디렉터리 정리: {work})")

    print(f"\n결과: {'ALL PASS' if not FAILURES else 'FAILURES: ' + ', '.join(FAILURES)}")
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    sys.exit(main())
