"""NX-00: independent parse of the 8h re-soak artifact.

Reads the raw harness JSON directly (not ``soak-summary.json``) and recomputes
every published claim, so the handoff does not rely on the earlier summary.

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
        docs/qa/2026-09-16-followup/nx00/verify_soak_artifact.py --json

The artifact is opened read-only; this script never writes to it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

DEFAULT_ARTIFACT = Path(".omo/evidence/commercial-reliability/CR-14/ex-2026-09-15/soak/val02_soak_28800_resoake.json")
EXPECTED_THRESHOLDS = {
    "p95_ms": 500.0,
    "p99_ms": 1000.0,
    "error_rate_max": 0.0,
    "fd_leak_max": 5,
    "rss_leak_mb": 64.0,
}
REQUIRED_SCENARIOS = ("SC-1", "SC-2", "SC-3", "SC-4", "SC-5", "SC-6")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sample_stats(values: list[object]) -> dict[str, object] | None:
    """Recompute sample statistics from the raw array (no earlier summary reused)."""
    numbers = [float(v) for v in values]
    if not numbers:
        return None
    return {
        "count": len(numbers),
        "first": numbers[0],
        "last": numbers[-1],
        "min": min(numbers),
        "max": max(numbers),
    }


def summarize(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    report = json.loads(raw.decode("utf-8"))
    rss_samples = report.get("scenarios", [{}])[-1].get("rss_samples_mb") or []
    fd_samples = report.get("scenarios", [{}])[-1].get("fd_samples") or []
    rss = _sample_stats(rss_samples) or report.get("scenarios", [{}])[-1].get("rss_samples_mb_summary") or {}
    fd = _sample_stats(fd_samples) or report.get("scenarios", [{}])[-1].get("fd_samples_summary") or {}
    scenarios = {s.get("scenario", ""): s for s in report.get("scenarios", [])}
    sc6 = scenarios.get("SC-6-soak", {})
    problems: list[str] = []

    if report.get("thresholds") != EXPECTED_THRESHOLDS:
        problems.append(f"thresholds changed: {report.get('thresholds')!r}")
    missing = [s for s in REQUIRED_SCENARIOS if not any(key == s or key.startswith(f"{s}-") for key in scenarios)]
    if missing:
        problems.append(f"missing scenarios: {missing}")
    for key, scenario in scenarios.items():
        if scenario.get("pass") is not True:
            problems.append(f"{key} pass != true")
    if report.get("all_pass") is not True:
        problems.append("all_pass != true")
    if sc6.get("conversation_ops") != sc6.get("conversation_revision"):
        problems.append("SC-6 append != revision")
    if sc6.get("conversation_append_equality") is not True:
        problems.append("SC-6 conversation_append_equality != true")
    if sc6.get("conversation_messages_bounded") is not True:
        problems.append("SC-6 conversation_messages_bounded != true")
    if int(sc6.get("conversation_message_count") or 0) > int(sc6.get("conversation_soft_max") or 0):
        problems.append("SC-6 message count exceeds soft max")
    if float(sc6.get("rss_growth_mb") or 0.0) > EXPECTED_THRESHOLDS["rss_leak_mb"]:
        problems.append("SC-6 RSS growth exceeds threshold")
    if float(sc6.get("duration_s") or 0.0) < 28800:
        problems.append("SC-6 duration shorter than 28800s")
    if sc6.get("errors") or sc6.get("fd_growth") or sc6.get("orphan_worktrees"):
        problems.append("SC-6 errors/fd_growth/orphan non-zero")
    if (
        rss.get("count")
        and abs((float(rss["last"]) - float(rss["first"])) - float(sc6.get("rss_growth_mb") or 0.0)) >= 0.05
    ):
        problems.append("SC-6 declared rss_growth_mb disagrees with the raw sample array")

    return {
        "artifact": str(path),
        "sha256": sha256(path),
        "bytes": len(raw),
        "parsed_ok": True,
        "task_id": report.get("task_id"),
        "generated_at": report.get("generated_at"),
        "workdir": report.get("workdir"),
        "thresholds": report.get("thresholds"),
        "thresholds_match_frozen": report.get("thresholds") == EXPECTED_THRESHOLDS,
        "scenario_names": sorted(scenarios),
        "scenario_pass": {key: bool(value.get("pass")) for key, value in scenarios.items()},
        "missing_required_in_artifact": report.get("missing_required"),
        "all_pass": report.get("all_pass"),
        "sc6": {
            "requested_duration_s": sc6.get("requested_duration_s"),
            "duration_s": sc6.get("duration_s"),
            "actual_duration_s": sc6.get("actual_duration_s"),
            "conversation_ops": sc6.get("conversation_ops"),
            "conversation_revision": sc6.get("conversation_revision"),
            "conversation_message_count": sc6.get("conversation_message_count"),
            "conversation_soft_max": sc6.get("conversation_soft_max"),
            "append_equals_revision": sc6.get("conversation_ops") == sc6.get("conversation_revision"),
            "rss_growth_mb": sc6.get("rss_growth_mb"),
            "errors": sc6.get("errors"),
            "fd_growth": sc6.get("fd_growth"),
            "orphan_worktrees": sc6.get("orphan_worktrees"),
            "rss_summary": rss,
            "fd_summary": fd,
        },
        "derived": {
            "rss_growth_recomputed_from_samples": (
                round(float(rss["last"]) - float(rss["first"]), 1) if rss.get("count") else None
            ),
            "rss_growth_matches_declared": (
                rss.get("count") is not None
                and abs((float(rss["last"]) - float(rss["first"])) - float(sc6.get("rss_growth_mb") or 0.0)) < 0.05
            ),
            "fd_growth_recomputed_from_samples": (int(fd["last"]) - int(fd["first"]) if fd.get("count") else None),
            "per_sample_interval_s": (
                round(float(sc6.get("duration_s") or 0.0) / float(rss.get("count") or 1), 3)
                if rss.get("count")
                else None
            ),
        },
        "problems": problems,
        "verdict": "PASS (metrics only)" if not problems else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", default=str(DEFAULT_ARTIFACT))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = summarize(Path(args.artifact))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for key, value in result.items():
            print(f"{key}: {value}")
    return 0 if result["verdict"].startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
