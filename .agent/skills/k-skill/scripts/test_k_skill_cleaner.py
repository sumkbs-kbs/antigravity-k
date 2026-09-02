import importlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import NotRequired, Protocol, TypedDict, cast
from unittest.mock import patch

k_skill_cleaner = importlib.import_module("k_skill_cleaner")


class AgentUsageSource(TypedDict):
    agent: str
    paths: list[str]
    method: str
    confidence: str
    fallback: NotRequired[str]


class CleanupCandidate(TypedDict):
    skill: str
    action: str
    trigger_count: int
    score: int
    reasons: list[str]


class UsageJsonReport(TypedDict):
    applied: bool
    path: str
    caveat: str


class ScannedLogsReport(TypedDict):
    count: int
    paths: list[str]
    caveat: str


class TimeWindowReport(TypedDict):
    since: str | None
    days: int | None
    scope: str
    fallback: str


class CleanerReport(TypedDict):
    skill_count: int
    candidates: list[CleanupCandidate]
    agent_usage_sources: list[AgentUsageSource]
    time_window: TimeWindowReport
    usage_json: UsageJsonReport
    scanned_logs: ScannedLogsReport
    safety: str


class _CleanerModule(Protocol):
    AGENT_USAGE_SOURCES: list[AgentUsageSource]
    collect_skill_usage: Callable[..., dict[str, int]]
    find_skill_dirs: Callable[[Path | str], list[str]]
    rank_cleanup_candidates: Callable[..., list[CleanupCandidate]]


_typed_cleaner = cast(_CleanerModule, cast(object, k_skill_cleaner))
AGENT_USAGE_SOURCES = _typed_cleaner.AGENT_USAGE_SOURCES
collect_skill_usage = _typed_cleaner.collect_skill_usage
find_skill_dirs = _typed_cleaner.find_skill_dirs
rank_cleanup_candidates = _typed_cleaner.rank_cleanup_candidates


class KSkillCleanerTest(unittest.TestCase):
    def test_finds_root_skill_dirs_only_by_skill_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "keep-me").mkdir()
            _ = (root / "keep-me" / "SKILL.md").write_text("---\nname: keep-me\n", encoding="utf-8")
            _ = (root / "docs").mkdir()
            _ = (root / "docs" / "SKILL.md").write_text("not a root skill", encoding="utf-8")
            _ = (root / "no-skill").mkdir()

            self.assertEqual(find_skill_dirs(root), ["keep-me"])

    def test_collects_counts_from_jsonl_and_plain_agent_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _ = (root / "codex.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"event": "skill_triggered", "skill": "kbo-results"}),
                        json.dumps({"message": "Using $kbo-results for sports lookup"}),
                        "Claude loaded skill: korean-law-search",
                        json.dumps({"tool": {"name": "korean-law-search"}}),
                    ]
                ),
                encoding="utf-8",
            )

            counts = collect_skill_usage([root / "codex.jsonl"], ["kbo-results", "korean-law-search", "unused"])

            self.assertEqual(counts["kbo-results"], 2)
            self.assertEqual(counts["korean-law-search"], 2)
            self.assertEqual(counts["unused"], 0)

    def test_collects_usage_with_since_window_and_mtime_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recent_log = root / "recent.jsonl"
            _ = recent_log.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "timestamp": "2026-04-20T12:00:00+09:00",
                                "skill": "kbo-results",
                            }
                        ),
                        json.dumps(
                            {
                                "timestamp": "2026-01-10T12:00:00+09:00",
                                "skill": "korean-law-search",
                            }
                        ),
                        "loaded skill: fallback-skill",
                    ]
                ),
                encoding="utf-8",
            )
            old_log = root / "old.log"
            _ = old_log.write_text("loaded skill: old-fallback", encoding="utf-8")

            # Lines without parseable timestamps use file mtime as the fallback signal.
            recent_mtime = 1_776_643_200  # 2026-04-24T00:00:00Z
            old_mtime = 1_766_275_200  # 2025-12-20T00:00:00Z
            _ = recent_log.touch()
            _ = old_log.touch()
            import os

            _ = os.utime(recent_log, (recent_mtime, recent_mtime))
            _ = os.utime(old_log, (old_mtime, old_mtime))

            counts = collect_skill_usage(
                [recent_log, old_log],
                ["kbo-results", "korean-law-search", "fallback-skill", "old-fallback"],
                since="2026-04-01T00:00:00+09:00",
            )

            self.assertEqual(counts["kbo-results"], 1)
            self.assertEqual(counts["korean-law-search"], 0)
            self.assertEqual(counts["fallback-skill"], 1)
            self.assertEqual(counts["old-fallback"], 0)

    def test_collect_skill_usage_streams_log_files_without_reading_whole_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "codex.jsonl"
            _ = log_path.write_text(json.dumps({"skill": "kbo-results"}) + "\n", encoding="utf-8")

            with patch.object(
                Path,
                "read_text",
                side_effect=AssertionError("collect_skill_usage must stream logs"),
            ):
                counts = collect_skill_usage([log_path], ["kbo-results", "unused"])

            self.assertEqual(counts["kbo-results"], 1)
            self.assertEqual(counts["unused"], 0)

    def test_cli_reports_usage_json_provenance_and_window_caveat(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / "kbo-results"
            _ = skill_dir.mkdir()
            _ = (skill_dir / "SKILL.md").write_text("---\nname: kbo-results\n", encoding="utf-8")
            usage_json = root / "usage.json"
            _ = usage_json.write_text(json.dumps({"kbo-results": 3}), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    ("import sys; from k_skill_cleaner import main; sys.exit(main(sys.argv[1:]))"),
                    "--skills-root",
                    str(root),
                    "--usage-json",
                    str(usage_json),
                    "--days",
                    "90",
                ],
                check=True,
                text=True,
                capture_output=True,
                cwd=Path(__file__).resolve().parent,
            )
            report = cast(CleanerReport, cast(object, json.loads(result.stdout)))

            self.assertTrue(report["usage_json"]["applied"])
            self.assertEqual(report["usage_json"]["path"], str(usage_json))
            self.assertIn("pre-windowed", report["usage_json"]["caveat"])
            self.assertEqual(report["scanned_logs"]["count"], 0)
            self.assertIn("usage JSON", report["time_window"]["scope"])

    def test_ranks_deletion_candidates_with_interview_and_usage_reasons(self):
        candidates = rank_cleanup_candidates(
            skill_names=["unused", "rare", "protected", "active"],
            usage_counts={"unused": 0, "rare": 1, "protected": 0, "active": 12},
            never_use={"unused"},
            keep={"protected"},
            low_usage_threshold=1,
        )

        self.assertEqual([candidate["skill"] for candidate in candidates], ["unused", "rare"])
        self.assertEqual(candidates[0]["action"], "remove")
        self.assertIn("interview_never_use", candidates[0]["reasons"])
        self.assertEqual(candidates[1]["action"], "review")
        self.assertIn("low_usage", candidates[1]["reasons"])

    def test_documents_agent_specific_usage_sources(self):
        agents = {source["agent"] for source in AGENT_USAGE_SOURCES}
        expected_agents = {
            "Claude Code",
            "Codex",
            "OpenCode",
            "OpenClaw/ClawHub",
            "Hermes Agent",
        }

        self.assertTrue(expected_agents.issubset(agents))
        for source in AGENT_USAGE_SOURCES:
            self.assertTrue(source["paths"] or source.get("fallback"))
            self.assertIn("confidence", source)

    def test_skill_local_helper_autodetects_parent_skills_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills_root = Path(tmp)
            cleaner_dir = skills_root / "k-skill-cleaner"
            cleaner_scripts = cleaner_dir / "scripts"
            cleaner_scripts.mkdir(parents=True)
            _ = (cleaner_dir / "SKILL.md").write_text("---\nname: k-skill-cleaner\n", encoding="utf-8")
            _ = shutil.copyfile(
                Path(__file__).resolve().parents[1] / "k-skill-cleaner" / "scripts" / "k_skill_cleaner.py",
                cleaner_scripts / "k_skill_cleaner.py",
            )

            for skill in ["kbo-results", "k-skill-setup"]:
                skill_dir = skills_root / skill
                _ = skill_dir.mkdir()
                _ = (skill_dir / "SKILL.md").write_text(f"---\nname: {skill}\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/k_skill_cleaner.py",
                    "--skills-root",
                    ".",
                    "--never-use",
                    "kbo-results",
                    "--keep",
                    "k-skill-setup",
                ],
                cwd=cleaner_dir,
                check=True,
                text=True,
                capture_output=True,
            )
            report = cast(CleanerReport, cast(object, json.loads(result.stdout)))

            self.assertEqual(report["skill_count"], 3)
            self.assertEqual(report["candidates"][0]["skill"], "kbo-results")
            self.assertEqual(report["candidates"][0]["action"], "remove")


if __name__ == "__main__":
    _ = unittest.main()
