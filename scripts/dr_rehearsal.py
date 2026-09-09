"""OBS-01 재해 복구(DR) 리허설 — backup/restore + DB corruption + project migration.

GA-100 plan §OBS-01 수용기준:
  - backup/restore rehearsal 기록이 있다.
  - DB corruption, orphan worktree, project migration rehearsal 기록이 있다.

모든 리허설은 임시 디렉터리에서 실제 파일을 대상으로 실행한다 (프로덕션 데이터
무변경). 실행 결과를 JSON으로 stdout에 내보내 증거 팩에 첨부한다.

실행: uv run --no-sync python scripts/dr_rehearsal.py --output /tmp/dr-rehearsal.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Any

# ProjectRegistry 임포트는 스크립트 본문에서 수행 (project root 의존 최소화)


def scenario_backup_restore(tmp: Path) -> dict[str, Any]:
    """레지스트리 backup→restore 리허설: primary 손상 시 .bak에서 복구된다."""
    from antigravity_k.engine.project_registry import ProjectRegistry

    result: dict[str, Any] = {"scenario": "backup_restore"}
    storage = tmp / "registry" / "projects.json"
    storage.parent.mkdir(parents=True, exist_ok=True)

    registry = ProjectRegistry(storage_path=storage)
    p1 = registry.add_project("dr-alpha", str(tmp / "alpha"))
    _ = (tmp / "alpha").mkdir(exist_ok=True)
    # bak 회전은 "저장 직전 primary"를 남긴다 → p2 저장 시 bak이 p1 시점이 되고,
    # 마지막 switch_project 저장 전 상태가 bak에 반영되도록 활성 전환을 한 번 더 한다
    p2 = registry.add_project("dr-beta", str(tmp / "beta"))
    _ = (tmp / "beta").mkdir(exist_ok=True)
    _ = registry.switch_project(p1.id)  # bak ← (p1+p2 상태의 primary)
    _ = registry.switch_project(p2.id)  # 최종 활성 p2, bak ← p2 활성 직전 primary
    result["projects_before"] = 2
    result["backup_created"] = registry._backup_path.exists()

    # primary 파손 → 새 인스턴스가 bak에서 복구해야 한다 (bak은 p1+p2 시점 스냅샷)
    storage.write_text("{corrupted!!", encoding="utf-8")
    registry2 = ProjectRegistry(storage_path=storage)
    recovered = {p["id"] if isinstance(p, dict) else p.id for p in registry2.list_projects()}
    result["recovered_ids"] = sorted(recovered)
    result["restore_ok"] = {p1.id, p2.id} <= recovered
    active = registry2.get_active_project()
    result["active_preserved"] = (active.id if not isinstance(active, dict) else active["id"]) in {p1.id, p2.id}
    return result


def scenario_db_corruption(tmp: Path) -> dict[str, Any]:
    """TaskStateStore DB corruption 리허설: 손상 DB 감지 + 재초기화 복구."""
    from antigravity_k.engine.task_state_store import TaskStateStore

    result: dict[str, Any] = {"scenario": "db_corruption"}
    db = tmp / "tasks-corrupt.db"

    store = TaskStateStore(str(db))
    store.initialize()
    task_id = f"task-dr-{int(time.time())}"
    store.create_task(task_id, prompt="dr", status="running", created_at="2026-09-09T00:00:00Z")
    result["task_created"] = store.get_task(task_id) is not None

    # 파일 상단을 garbage로 덮어 SQLite header 손상
    raw = bytearray(db.read_bytes())
    raw[0:16] = b"XX" * 8
    db.write_bytes(bytes(raw))

    detected = False
    try:
        broken = TaskStateStore(str(db))
        broken.initialize()
        with broken._connection() as conn:
            conn.execute("SELECT count(*) FROM task_history").fetchone()
    except sqlite3.DatabaseError:
        detected = True
    except Exception:
        detected = True
    result["corruption_detected"] = detected

    # 복구 절차: 손상 파일 격리(quarantine) 후 재초기화 — runbook 절차와 동일
    quarantine = tmp / "quarantine"
    quarantine.mkdir(exist_ok=True)
    shutil.move(str(db), str(quarantine / db.name))
    fresh = TaskStateStore(str(db))
    fresh.initialize()
    result["reinit_ok"] = fresh.get_task(task_id) is None  # 새 DB — 과거 task 없음(정상)
    probe = f"task-post-{int(time.time())}"
    fresh.create_task(probe, prompt="post", status="running", created_at="2026-09-09T00:00:00Z")
    result["write_after_recovery"] = fresh.get_task(probe) is not None
    return result


def scenario_project_migration(tmp: Path) -> dict[str, Any]:
    """프로젝트 마이그레이션 리허설: path 이동 → registry 갱신 → 활성 전환."""
    from antigravity_k.engine.project_registry import ProjectRegistry

    result: dict[str, Any] = {"scenario": "project_migration"}
    storage = tmp / "mig-registry" / "projects.json"
    storage.parent.mkdir(parents=True, exist_ok=True)

    old_root = tmp / "mig-old"
    new_root = tmp / "mig-new"
    old_root.mkdir()
    registry = ProjectRegistry(storage_path=storage)
    record = registry.add_project("mig-proj", str(old_root))

    # 실제 디렉터리 이동 (실측성)
    old_root.rename(new_root)

    switched = registry.switch_project(record.id)  # id로 재활성
    result["switch_ok"] = switched is not None
    # path 갱신: v2에서는 remove+add로 이주 (path는 불변 id의 식별자)
    registry.remove_project(record.id)
    migrated = registry.add_project("mig-proj", str(new_root))
    result["migrated_id"] = migrated.id
    result["migrated_path"] = migrated.path
    result["path_points_to_new_root"] = Path(migrated.path) == new_root.resolve() or migrated.path == str(new_root)
    result["active_after_migration"] = registry.get_active_project().id == migrated.id
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="OBS-01 DR rehearsal")
    parser.add_argument("--output", type=Path, default=None, help="결과 JSON 저장 경로")
    args = parser.parse_args()

    scenarios: list[dict[str, Any]] = []
    failures = 0
    with tempfile.TemporaryDirectory(prefix="agk-dr-") as td:
        tmp = Path(td)
        for fn in (scenario_backup_restore, scenario_db_corruption, scenario_project_migration):
            try:
                res = fn(tmp / fn.__name__.replace("scenario_", ""))
                res["ok"] = all(v for k, v in res.items() if isinstance(v, bool))
                if not res["ok"]:
                    failures += 1
            except Exception as exc:  # noqa: BLE001 — 리허설은 실패도 기록이 목적
                res = {"scenario": fn.__name__, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
                failures += 1
            scenarios.append(res)

    report = {
        "rehearsal": "OBS-01 DR",
        "executed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "scenarios": scenarios,
        "all_ok": failures == 0,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
