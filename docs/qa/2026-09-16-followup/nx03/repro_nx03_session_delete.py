"""NX-03 repro/verification driver: can a stale writer resurrect a deleted session?

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python \
        docs/qa/2026-09-16-followup/nx03/repro_nx03_session_delete.py --label before

Uses an isolated temporary session directory only (never ~/.antigravity/sessions).
Prints one JSON object so the same driver can be compared before/after the fix.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from antigravity_k.engine.session_manager import SessionManager  # noqa: E402

MARKER = "SYNTHETIC-DELETED-MARKER"


def _messages(manager: SessionManager) -> list[str]:
    return [m.get("content", "") for m in manager.get_messages()]


def _probe(base_dir: Path, workspace: Path) -> dict[str, object]:
    out: dict[str, object] = {}
    a = SessionManager(base_dir=str(base_dir))
    session_id = a.start_session(project_path=str(workspace), resume=False)
    a.add_turn([{"role": "user", "content": MARKER}])
    a.save()
    out["session_id"] = session_id
    out["file_after_create"] = (base_dir / f"{session_id}.json").is_file()

    b = SessionManager(base_dir=str(base_dir))
    b.start_session(project_path=str(workspace), resume=True)
    out["b_loaded_same_id"] = b._session_id == session_id

    out["deleted_count"] = a.clear_memory("all")
    out["files_after_clear"] = sorted(p.name for p in base_dir.glob("*.json"))
    out["file_after_clear"] = (base_dir / f"{session_id}.json").is_file()
    out["tombstones_after_clear"] = (
        sorted(p.name for p in (base_dir / ".tombstones").glob("*.json")) if (base_dir / ".tombstones").is_dir() else []
    )

    b.add_turn([{"role": "user", "content": "stale-writer-turn"}])
    error = ""
    try:
        b.save()
        saved = True
    except Exception as exc:  # noqa: BLE001 - the driver reports the error class
        saved = False
        error = type(exc).__name__
    out["b_save_succeeded"] = saved
    out["b_save_error"] = error
    path = base_dir / f"{session_id}.json"
    out["file_after_b_save"] = path.is_file()
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        out["payload_messages_after_b_save"] = [m.get("content", "") for m in payload.get("messages", [])]
        out["payload_revision_after_b_save"] = payload.get("revision")
    out["marker_present_after_b_save"] = MARKER in json.dumps(
        [p.read_text(encoding="utf-8") for p in base_dir.rglob("*.json")], ensure_ascii=False
    )

    c = SessionManager(base_dir=str(base_dir))
    resumed = c.start_session(project_path=str(workspace), resume=True)
    out["restart_resumed_id"] = resumed
    out["restart_resumed_original"] = resumed == session_id
    out["restart_messages"] = _messages(c)
    out["marker_present_after_restart"] = MARKER in "\n".join(_messages(c))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="run")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="nx03-repro-") as tmp:
        base = Path(tmp) / "sessions"
        workspace = Path(tmp) / "workspace"
        workspace.mkdir()
        result = {"label": args.label, "sequential_two_instance": _probe(base, workspace)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
