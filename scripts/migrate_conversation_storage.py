#!/usr/bin/env python
"""CR-01: one-time, verified migration of conversation storage to the v2 layout.

Layout history
--------------
legacy: ``<storage>/<sanitised-project>/<sanitised-conversation>.json``
v2    : ``<storage>/v2/<sha256(project_id)>/<sha256(conversation_id)>.json``

The legacy layout substituted/truncated id characters, so distinct raw ids
(``a.b`` vs ``a_b``, ``Conv`` vs ``conv`` on a case-insensitive volume) shared
one file. The v2 layout keys on the full SHA-256 of the raw UTF-8 ids and every
read re-verifies the ids embedded in the record body.

Contract implemented here (plan CR-01 §3-4)
-------------------------------------------
1. Ids are taken from the **record body**, never reverse-engineered from paths.
2. Dry-run (default) never writes: it prints the plan and the conflict list.
3. ``--apply`` backs up every source file first, then creates each v2 record
   atomically, then re-reads and verifies it before touching anything else.
4. Corrupt, ambiguous, or duplicating sources are refused: nothing is written
   and the completion marker is not created (non-zero exit).
5. Re-running is idempotent: already-present identical v2 files are not
   rewritten, and a completed migration is reported without further writes.
6. Legacy source files are preserved; deletion is an operator decision.

Usage
-----
    uv run --no-sync python scripts/migrate_conversation_storage.py --dry-run
    uv run --no-sync python scripts/migrate_conversation_storage.py --apply \
        --backup-dir ~/.antigravity/conversations-backup-2026-09-11
    uv run --no-sync python scripts/migrate_conversation_storage.py --verify-only

Exit codes: 0 = planned/completed/verified, 2 = conflicts or verification
failure (nothing written), 3 = usage/environment error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from antigravity_k.engine.conversation_store import (  # noqa: E402
    MIGRATION_MARKER_NAME,
    conversation_storage_relative_path,
)

REPORT_SCHEMA = "cr01-conversation-migration/1"
DEFAULT_STORAGE_DIR = Path(os.path.expanduser("~")) / ".antigravity" / "conversations"
IGNORED_ENTRIES = frozenset({MIGRATION_MARKER_NAME, ".cas.lock", ".DS_Store"})
EXIT_OK = 0
EXIT_CONFLICT = 2
EXIT_USAGE = 3


@dataclass
class PlanEntry:
    """One legacy record to move (or one already-migrated record to skip)."""

    project_id: str
    conversation_id: str
    digest: str
    sources: list[Path] = field(default_factory=list)
    target_exists_identical: bool = False

    @property
    def target(self) -> Path:
        return conversation_storage_relative_path(self.project_id, self.conversation_id)


@dataclass
class Conflict:
    kind: str
    detail: str
    sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "detail": self.detail, "sources": self.sources}


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _legacy_candidates(storage_dir: Path) -> list[Path]:
    """Enumerate pre-v2 record files (paths only; ids come from the body)."""
    if not storage_dir.is_dir():
        return []
    found: list[Path] = []
    for entry in sorted(storage_dir.iterdir()):
        name = entry.name
        if name in IGNORED_ENTRIES or name.startswith("."):
            continue
        if entry.is_dir():
            if name == "v2":
                continue
            found.extend(sorted(p for p in entry.rglob("*.json") if p.is_file()))
        elif entry.is_file() and entry.suffix == ".json":
            found.append(entry)
    return found


def _load_identity(source: Path) -> tuple[str, str, bytes] | Conflict:
    """Read ids from a record body; never derive them from the file name."""
    try:
        payload = source.read_bytes()
    except OSError as exc:
        return Conflict(kind="unreadable", detail=f"{type(exc).__name__}: {exc}", sources=[str(source)])
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return Conflict(kind="corrupt", detail=f"{type(exc).__name__}: {exc}", sources=[str(source)])
    if not isinstance(data, dict):
        return Conflict(kind="corrupt", detail="record is not a JSON object", sources=[str(source)])
    project_id = data.get("project_id")
    conversation_id = data.get("conversation_id")
    if not isinstance(project_id, str) or not project_id:
        return Conflict(kind="missing_ids", detail="record has no non-empty project_id", sources=[str(source)])
    if not isinstance(conversation_id, str) or not conversation_id:
        return Conflict(kind="missing_ids", detail="record has no non-empty conversation_id", sources=[str(source)])
    return project_id, conversation_id, payload


def build_plan(storage_dir: Path) -> tuple[list[PlanEntry], list[Conflict]]:
    """Build the migration plan from record bodies plus an explicit conflict list."""
    plan: dict[tuple[str, str], PlanEntry] = {}
    conflicts: list[Conflict] = []
    for source in _legacy_candidates(storage_dir):
        loaded = _load_identity(source)
        if isinstance(loaded, Conflict):
            conflicts.append(loaded)
            continue
        project_id, conversation_id, payload = loaded
        digest = _sha256_bytes(payload)
        entry = plan.get((project_id, conversation_id))
        if entry is None:
            plan[(project_id, conversation_id)] = PlanEntry(
                project_id=project_id,
                conversation_id=conversation_id,
                digest=digest,
                sources=[source],
            )
            continue
        if entry.digest != digest:
            conflicts.append(
                Conflict(
                    kind="identity_duplicate",
                    detail=(
                        "two legacy files carry the same (project_id, conversation_id) "
                        "with different bytes; refusing to choose one"
                    ),
                    sources=[str(p) for p in [*entry.sources, source]],
                )
            )
            continue
        entry.sources.append(source)

    entries = sorted(plan.values(), key=lambda e: (e.project_id, e.conversation_id))
    for entry in entries:
        target = storage_dir / entry.target
        if target.is_file():
            if _sha256_bytes(target.read_bytes()) == entry.digest:
                entry.target_exists_identical = True
            else:
                conflicts.append(
                    Conflict(
                        kind="target_conflict",
                        detail="v2 target already exists with different bytes",
                        sources=[str(p) for p in [*entry.sources, target]],
                    )
                )
    return entries, conflicts


def _atomic_write_bytes(target: Path, payload: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _default_backup_dir(storage_dir: Path) -> Path:
    """Sibling backup root (never inside the storage root)."""
    base = storage_dir.parent / f"{storage_dir.name}.migration-backup"
    candidate = Path(f"{base}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}")
    counter = 1
    while candidate.exists():
        candidate = Path(f"{base}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{counter}")
        counter += 1
    return candidate


def _backup_sources(storage_dir: Path, backup_dir: Path, plan: list[PlanEntry]) -> list[dict[str, str]]:
    if backup_dir == storage_dir or storage_dir in backup_dir.parents:
        raise ValueError(f"backup directory must live outside the storage root: {backup_dir}")
    if backup_dir.exists() and any(backup_dir.iterdir()):
        raise FileExistsError(f"backup directory is not empty: {backup_dir}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    copied: list[dict[str, str]] = []
    for entry in plan:
        for source in entry.sources:
            relative = source.relative_to(storage_dir)
            destination = backup_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied.append({"source": str(relative), "backup": str(destination)})
    return copied


def _verify_plan(storage_dir: Path, plan: list[PlanEntry]) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    for entry in plan:
        target = storage_dir / entry.target
        if not target.is_file():
            failures.append({"target": str(entry.target), "reason": "missing"})
            continue
        payload = target.read_bytes()
        if _sha256_bytes(payload) != entry.digest:
            failures.append({"target": str(entry.target), "reason": "hash_mismatch"})
            continue
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            failures.append({"target": str(entry.target), "reason": "not_json"})
            continue
        if not isinstance(data, dict) or data.get("project_id") != entry.project_id:
            failures.append({"target": str(entry.target), "reason": "project_id_mismatch"})
            continue
        if data.get("conversation_id") != entry.conversation_id:
            failures.append({"target": str(entry.target), "reason": "conversation_id_mismatch"})
    return failures


def _write_marker(storage_dir: Path, plan: list[PlanEntry], plan_digest: str) -> None:
    marker = storage_dir / MIGRATION_MARKER_NAME
    payload = {
        "layout": "v2",
        "completed": True,
        "schema": REPORT_SCHEMA,
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "record_count": len(plan),
        "plan_digest": plan_digest,
    }
    _atomic_write_bytes(marker, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))


def _plan_digest(plan: list[PlanEntry]) -> str:
    lines = [f"{e.project_id}\x1f{e.conversation_id}\x1f{e.digest}" for e in plan]
    return _sha256_bytes("\n".join(sorted(lines)).encode("utf-8"))


def _marker_state(storage_dir: Path) -> str:
    marker = storage_dir / MIGRATION_MARKER_NAME
    if not marker.is_file():
        return "absent"
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unreadable"
    if isinstance(data, dict) and data.get("layout") == "v2" and data.get("completed") is True:
        return "completed"
    return "invalid"


def run(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    storage_dir = Path(args.storage_dir).expanduser().resolve()
    if not storage_dir.is_dir():
        return EXIT_USAGE, {
            "state": "storage_dir_missing",
            "storage_dir": str(storage_dir),
            "hint": "pass --storage-dir for a different root (nothing was created)",
        }

    plan, conflicts = build_plan(storage_dir)
    report: dict[str, Any] = {
        "tool": "migrate_conversation_storage",
        "schema": REPORT_SCHEMA,
        "storage_dir": str(storage_dir),
        "mode": "verify-only" if args.verify_only else ("apply" if args.apply else "dry-run"),
        "marker_path": str(storage_dir / MIGRATION_MARKER_NAME),
        "marker_state": _marker_state(storage_dir),
        "legacy_record_count": sum(len(e.sources) for e in plan) + sum(len(c.sources) for c in conflicts),
        "planned": [
            {
                "project_id": e.project_id,
                "conversation_id": e.conversation_id,
                "target": str(e.target),
                "sources": [str(p.relative_to(storage_dir)) for p in e.sources],
                "action": "already_present" if e.target_exists_identical else "copy",
            }
            for e in plan
        ],
        "conflicts": [c.to_dict() for c in conflicts],
        "backup_dir": None,
        "marker_written": False,
    }

    if args.verify_only:
        failures = _verify_plan(storage_dir, plan)
        report["verification_failures"] = failures
        completed = report["marker_state"] == "completed"
        report["state"] = "verified" if completed and not failures and not conflicts else "not_verified"
        ok = bool(completed and not failures and not conflicts)
        return (EXIT_OK if ok else EXIT_CONFLICT), report

    if conflicts:
        report["state"] = "blocked_conflicts"
        report["hint"] = "resolve or quarantine the conflicting sources; nothing was written"
        return EXIT_CONFLICT, report

    if not args.apply:
        report["state"] = "dry_run"
        return EXIT_OK, report

    if report["marker_state"] == "completed":
        failures = _verify_plan(storage_dir, plan)
        report["verification_failures"] = failures
        report["state"] = "already_migrated" if not failures else "verification_failed"
        return (EXIT_OK if not failures else EXIT_CONFLICT), report

    backup_dir = Path(args.backup_dir).expanduser().resolve() if args.backup_dir else _default_backup_dir(storage_dir)
    try:
        report["backed_up"] = _backup_sources(storage_dir, backup_dir, plan)
    except (OSError, ValueError) as exc:
        report["state"] = "backup_failed"
        report["backup_dir"] = str(backup_dir)
        report["hint"] = f"{type(exc).__name__}: {exc}"
        return EXIT_USAGE, report
    report["backup_dir"] = str(backup_dir)

    written = 0
    for entry in plan:
        if entry.target_exists_identical:
            continue
        source_payload = json.loads(entry.sources[0].read_text(encoding="utf-8"))
        _atomic_write_bytes(
            storage_dir / entry.target,
            json.dumps(source_payload, ensure_ascii=False, indent=2).encode("utf-8"),
        )
        written += 1
    report["records_written"] = written

    failures = _verify_plan(storage_dir, plan)
    report["verification_failures"] = failures
    if failures:
        report["state"] = "verification_failed"
        report["hint"] = "marker not written; legacy sources are intact and a backup exists"
        return EXIT_CONFLICT, report

    _write_marker(storage_dir, plan, _plan_digest(plan))
    report["marker_written"] = True
    report["marker_state"] = "completed"
    report["state"] = "applied"
    return EXIT_OK, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CR-01 conversation storage v2 migration")
    parser.add_argument("--storage-dir", default=str(DEFAULT_STORAGE_DIR), help="conversation storage root")
    parser.add_argument("--apply", action="store_true", help="perform the migration (default is dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="explicitly request a no-write plan (default)")
    parser.add_argument("--verify-only", action="store_true", help="verify an applied migration and exit")
    parser.add_argument("--backup-dir", default=None, help="backup destination (must be empty/absent)")
    parser.add_argument("--report", default=None, help="write the JSON report to this path")
    args = parser.parse_args(argv)
    if args.apply and args.verify_only:
        parser.error("--apply and --verify-only are mutually exclusive")

    code, report = run(args)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)
    if args.report:
        Path(args.report).write_text(payload, encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
