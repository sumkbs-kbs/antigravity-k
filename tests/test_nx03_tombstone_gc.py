"""NX-03 후속: 삭제 표식(tombstone)의 GC 정책과 운영자 회수.

NX-03 은 삭제를 "표식 선기록 → 가시 데이터 제거"로 고정했지만, 표식은 **삭제된 ID 당 1개씩
무기한 누적**되고 GC 정책이 없었다. 이 시험은 그 정책을 고정한다:

* 자동 만료는 없다(`automatic_expiry: False`) — 임의 TTL 금지.
* 회수는 **운영자가 명시적으로** 호출하고, `older_than_seconds` 를 반드시 정한다(>0).
  `0`/음수로 "전부 만료"하는 사고를 코드가 거부한다.
* 기본은 dry-run 이고, 실제 회수도 **삭제가 아니라 이동**이다 — 아카이브에 남아 되돌릴 수 있고
  `gc-report.json` 이 감사 기록을 남긴다.
* 나이 기준보다 젊은 표식은 남는다(경계).
* 회수 뒤의 새 삭제는 다시 표식을 남긴다(보호는 계속 동작한다).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from antigravity_k.engine.session_manager import SESSION_TOMBSTONE_DIR_NAME, SessionManager


def _manager(tmp_path: Path) -> SessionManager:
    return SessionManager(base_dir=str(tmp_path / "sessions"))


def _delete(manager: SessionManager) -> str:
    """삭제 경로로 표식을 만든다 — 표식을 손으로 쓰지 않고 제품 경로를 쓴다.

    NX-03 시험과 같은 방식(`start_session` → `clear_memory("all")`)이라, 이 시험이
    관측하는 표식은 실제 삭제 경로가 만든 것이다. 매번 새 세션 id 가 생긴다.
    """
    workspace = Path(manager.base_dir).parent / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    session_id = manager.start_session(project_path=str(workspace), resume=False)
    _ = manager.clear_memory("all")
    # 빈 세션이라 제거 건수는 0 일 수 있다 — 중요한 것은 삭제 경로가 표식을 남기는 것이다.
    assert any((Path(manager.base_dir) / SESSION_TOMBSTONE_DIR_NAME).glob("*.json")), (
        "삭제 경로가 tombstone 을 남기지 않았다"
    )
    return session_id


def _tombstones(manager: SessionManager) -> Path:
    return Path(manager.base_dir) / SESSION_TOMBSTONE_DIR_NAME


def _age(path: Path, seconds: float) -> None:
    """표식의 mtime 을 과거로 밀어 나이 기준을 만든다(파일 내용은 건드리지 않는다)."""
    stamp = time.time() - seconds
    import os

    os.utime(path, (stamp, stamp))


def test_usage_reports_counts_and_ages_without_automatic_expiry(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    _delete(manager)
    _delete(manager)

    usage = manager.tombstone_usage()
    assert usage["count"] >= 2
    assert int(usage["total_bytes"]) > 0
    assert usage["automatic_expiry"] is False
    assert float(usage["newest_age_seconds"]) >= 0.0
    assert float(usage["oldest_age_seconds"]) >= float(usage["newest_age_seconds"])


def test_dry_run_reports_candidates_and_moves_nothing(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    _delete(manager)
    marker = next(_tombstones(manager).glob("*.json"))
    _age(marker, 3600)

    before = manager.tombstone_usage()["count"]
    report = manager.collect_tombstones(older_than_seconds=60, dry_run=True)

    assert report["dry_run"] is True
    assert report["count"] >= 1
    assert marker.name in report["candidates"]
    assert report["moved"] == []
    assert report["archive_dir"] is None
    assert marker.is_file(), "dry-run 이 파일을 건드렸다"
    assert manager.tombstone_usage()["count"] == before


def test_collect_moves_old_markers_into_a_reversible_archive(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    _delete(manager)
    old_marker = next(_tombstones(manager).glob("*.json"))
    _age(old_marker, 7200)

    report = manager.collect_tombstones(older_than_seconds=3600, dry_run=False)

    assert report["dry_run"] is False
    assert report["moved"] == [old_marker.name]
    archive = Path(str(report["archive_dir"]))
    assert archive.is_dir()
    # 삭제가 아니라 이동이다: 아카이브에서 되돌릴 수 있고 감사 기록이 남는다.
    assert (archive / old_marker.name).is_file()
    assert not old_marker.exists()
    audit = json.loads((archive / "gc-report.json").read_text(encoding="utf-8"))
    assert audit["schema"] == "agk.session-tombstone-gc.v1"
    assert audit["moved"] == [old_marker.name]
    assert audit["older_than_seconds"] == 3600.0
    # 활성 표식 집계에서 빠진다(아카이브는 재귀적으로 세지 않는다).
    assert manager.tombstone_usage()["count"] == 0


def test_collect_keeps_markers_younger_than_the_threshold(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    _delete(manager)
    _delete(manager)
    markers = sorted(_tombstones(manager).glob("*.json"))
    assert len(markers) >= 2
    _age(markers[0], 7200)  # 하나만 늙게 만든다

    report = manager.collect_tombstones(older_than_seconds=3600, dry_run=False)

    assert report["moved"] == [markers[0].name]
    assert markers[1].is_file(), "젊은 표식을 회수했다"


def test_collect_refuses_a_nonpositive_age_threshold(tmp_path: Path) -> None:
    """`0`/음수는 "전부 만료"라는 뜻이 되므로 코드가 거부한다."""
    manager = _manager(tmp_path)
    _delete(manager)

    for bad in (0, -1.0, 0.0):
        with pytest.raises(ValueError):
            _ = manager.collect_tombstones(older_than_seconds=bad, dry_run=False)
    assert manager.tombstone_usage()["count"] >= 1


def test_deletion_after_collection_still_writes_a_protection_marker(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    _delete(manager)
    marker = next(_tombstones(manager).glob("*.json"))
    _age(marker, 7200)
    _ = manager.collect_tombstones(older_than_seconds=3600, dry_run=False)
    assert manager.tombstone_usage()["count"] == 0

    _delete(manager)
    assert manager.tombstone_usage()["count"] >= 1, "회수 뒤 새 삭제가 표식을 남기지 않았다"
