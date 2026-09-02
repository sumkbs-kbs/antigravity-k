import contextlib
import importlib
import io
import json
import os
import shlex
import subprocess
import unittest
from datetime import date
from pathlib import Path
from typing import Callable, Protocol, cast
from unittest import mock

subway_lost_property = importlib.import_module("scripts.subway_lost_property")


class SearchQueryLike(Protocol):
    station: str
    item: str | None
    start_date: date
    end_date: date


class SearchPlanLike(Protocol):
    query: SearchQueryLike
    payload: dict[str, str]
    suggested_keywords: list[str]
    official_sources: list[dict[str, str]]


LOST112_LIST_URL = cast(str, getattr(subway_lost_property, "LOST112_LIST_URL"))
SEOUL_METRO_LOST_CENTER_URL = cast(str, getattr(subway_lost_property, "SEOUL_METRO_LOST_CENTER_URL"))
SearchQuery = cast(Callable[..., SearchQueryLike], getattr(subway_lost_property, "SearchQuery"))
build_curl_command = cast(Callable[[dict[str, str]], str], getattr(subway_lost_property, "build_curl_command"))
build_search_payload = cast(
    Callable[[SearchQueryLike], dict[str, str]], getattr(subway_lost_property, "build_search_payload")
)
build_search_plan = cast(Callable[..., SearchPlanLike], getattr(subway_lost_property, "build_search_plan"))
expand_station_keywords = cast(Callable[[str], list[str]], getattr(subway_lost_property, "expand_station_keywords"))
main = cast(Callable[[list[str] | None], None], getattr(subway_lost_property, "main"))
probe_source = cast(Callable[..., dict[str, str]], getattr(subway_lost_property, "probe_source"))


class SubwayLostPropertyQueryTest(unittest.TestCase):
    def test_build_search_payload_defaults_to_external_agency_search(self):
        payload = build_search_payload(
            SearchQuery(
                station="강남역",
                item="지갑",
                start_date=date(2026, 4, 1),
                end_date=date(2026, 4, 10),
            )
        )

        self.assertEqual(payload["START_YMD"], "20260401")
        self.assertEqual(payload["END_YMD"], "20260410")
        self.assertEqual(payload["PRDT_NM"], "지갑")
        self.assertEqual(payload["DEP_PLACE"], "강남역")
        self.assertEqual(payload["SITE"], "V")
        self.assertEqual(payload["pageIndex"], "1")

    def test_expand_station_keywords_keeps_station_and_strips_suffix(self):
        self.assertEqual(expand_station_keywords(" 강남역 "), ["강남역", "강남"])

    def test_build_search_plan_serializes_official_sources_and_guidance(self):
        plan = build_search_plan(
            station="강남역",
            item="지갑",
            days=14,
            today=date(2026, 4, 10),
        )

        self.assertEqual(plan.query.station, "강남역")
        self.assertEqual(plan.query.item, "지갑")
        self.assertEqual(plan.query.start_date.isoformat(), "2026-03-27")
        self.assertEqual(plan.query.end_date.isoformat(), "2026-04-10")
        self.assertEqual(plan.official_sources[0]["url"], LOST112_LIST_URL)
        self.assertEqual(plan.official_sources[1]["url"], SEOUL_METRO_LOST_CENTER_URL)
        self.assertIn("강남역", plan.suggested_keywords)
        self.assertIn("강남", plan.suggested_keywords)
        command = shlex.split(build_curl_command(plan.payload))
        self.assertNotIn("-L", command)
        self.assertIn("--max-time", command)
        self.assertEqual(command[command.index("--max-time") + 1], "60")
        self.assertIn("--referer", command)
        self.assertEqual(command[command.index("--referer") + 1], "https://www.lost112.go.kr/")
        self.assertIn("--output", command)
        self.assertEqual(command[command.index("--output") + 1], "lost112-search-result.html")
        self.assertIn("SITE=V", " ".join(command))
        self.assertEqual(command[-1], LOST112_LIST_URL)

    def test_blank_station_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "station"):
            _ = build_search_plan(station="   ")


class SubwayLostPropertyProbeTest(unittest.TestCase):
    def test_probe_source_marks_successful_fetch_as_reachable(self):
        runner = mock.Mock(return_value=mock.Mock(returncode=0, stdout="<html></html>", stderr=""))

        status = probe_source("LOST112", LOST112_LIST_URL, runner=runner)

        self.assertEqual(status["status"], "reachable")
        command = cast(list[str], runner.call_args.args[0])
        self.assertEqual(command[0], "curl")
        self.assertIn("--http1.1", command)
        self.assertEqual(command[command.index("--tls-max") + 1], "1.2")
        self.assertEqual(command[command.index("--max-time") + 1], "15")
        self.assertEqual(command[-1], LOST112_LIST_URL)

    def test_probe_source_marks_timeouts_cleanly(self):
        runner = mock.Mock(
            side_effect=subprocess.CalledProcessError(28, ["curl"], stderr="Operation timed out")
        )

        status = probe_source("서울교통공사", SEOUL_METRO_LOST_CENTER_URL, runner=runner)

        self.assertEqual(status["status"], "timeout")
        self.assertIn("timed out", status["detail"].lower())


class SubwayLostPropertyCliShapeTest(unittest.TestCase):
    def test_cli_prints_json_plan(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            _ = main(["--station", "강남역", "--item", "지갑", "--days", "14"])

        payload = cast(dict[str, object], json.loads(stdout.getvalue()))
        query = cast(dict[str, object], payload["query"])
        search_payload = cast(dict[str, object], payload["payload"])
        sources = cast(list[dict[str, object]], payload["official_sources"])
        self.assertEqual(query["station"], "강남역")
        self.assertEqual(search_payload["SITE"], "V")
        self.assertIn("curl", cast(str, payload["curl_example"]))
        self.assertEqual(sources[0]["url"], LOST112_LIST_URL)

    def test_helper_scripts_are_executable_python_entrypoints(self):
        repo_root = Path(__file__).resolve().parent.parent
        for helper in (
            repo_root / "scripts" / "subway_lost_property.py",
            repo_root / "subway-lost-property" / "scripts" / "subway_lost_property.py",
        ):
            with self.subTest(helper=helper):
                self.assertTrue(os.access(helper, os.X_OK), f"{helper} should be executable")
                self.assertTrue(
                    helper.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3\n"),
                    f"{helper} should start with a Python shebang",
                )


if __name__ == "__main__":
    _ = unittest.main()
