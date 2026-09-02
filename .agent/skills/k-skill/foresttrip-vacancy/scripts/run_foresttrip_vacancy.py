#!/usr/bin/env python3
"""Read-only foresttrip.go.kr vacancy lookup helper.

The script logs in with Playwright to obtain a CSRF token and session cookies,
extracts forest IDs from the official monthly reservation status page, then
queries the read-only monthly availability JSON endpoint.

It intentionally does not click booking buttons, submit reservation forms,
handle payment, solve captcha, or bypass queues.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol, cast

LOGIN_URL = "https://www.foresttrip.go.kr/com/login.do"
RSRVT_PAGE = "https://www.foresttrip.go.kr/rep/or/sssn/monthRsrvtSmplStatus.do"
POST_URL = "https://www.foresttrip.go.kr/rep/or/selectRsrvtAvailInfoListForMonthRsrvtSmpl.do"
DEFAULT_CONCURRENCY = 4
MAX_CONCURRENCY = 5
DEFAULT_WEEK_RANGE = 1
CATEGORY_CODES = {"01", "02"}

Payload = dict[str, object]


def _as_mapping(value: object) -> Payload:
    if not isinstance(value, Mapping):
        return {}
    raw = cast(Mapping[object, object], value)
    return {str(key): item for key, item in raw.items()}


def _as_mapping_list(value: object) -> list[Payload]:
    if not isinstance(value, list):
        return []
    return [_as_mapping(cast(object, item)) for item in cast(list[object], value) if isinstance(item, Mapping)]


def _as_text(value: object, default: str = "") -> str:
    if value is None:
        return default
    return value if isinstance(value, str) else str(value)


def _as_str_map(value: object) -> dict[str, str]:
    mapping = _as_mapping(value)
    return {key: _as_text(item) for key, item in mapping.items()}


class _HTTPResponse(Protocol):
    status: int

    def read(self) -> bytes: ...

    def close(self) -> None: ...


@dataclass
class Session:
    cookies: dict[str, str]
    csrf: str
    user_agent: str
    forests: dict[str, str]
    expires_at: float


def parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_categories(value: str) -> tuple[str, ...]:
    categories = parse_csv(value)
    if not categories:
        raise argparse.ArgumentTypeError("must include at least one category code")
    invalid = [category for category in categories if category not in CATEGORY_CODES]
    if invalid:
        raise argparse.ArgumentTypeError(
            "unknown category code(s): " + ", ".join(invalid) + " (allowed: 01=lodging, 02=camping)"
        )
    return tuple(dict.fromkeys(categories))


def parse_dates(value: str) -> tuple[str, ...]:
    dates = parse_csv(value)
    if not dates:
        raise argparse.ArgumentTypeError("must include at least one YYYYMMDD date")

    today = datetime.now().date()
    normalized: list[str] = []
    for raw_date in dates:
        try:
            parsed = datetime.strptime(raw_date, "%Y%m%d").date()
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"invalid YYYYMMDD date: {raw_date}") from exc
        if parsed.strftime("%Y%m%d") != raw_date:
            raise argparse.ArgumentTypeError(f"invalid YYYYMMDD date: {raw_date}")
        if parsed < today:
            raise argparse.ArgumentTypeError(f"date is in the past: {raw_date}")
        normalized.append(raw_date)
    return tuple(sorted(dict.fromkeys(normalized)))


def parse_concurrency(value: str) -> int:
    try:
        concurrency = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if not 1 <= concurrency <= MAX_CONCURRENCY:
        raise argparse.ArgumentTypeError(f"must be between 1 and {MAX_CONCURRENCY}")
    return concurrency


def parse_week_range(value: str) -> int:
    try:
        week_range = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if week_range < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return week_range


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only foresttrip.go.kr vacancy lookup.",
    )
    target = parser.add_argument_group("target selection")
    _ = target.add_argument("--all", action="store_true", help="Scan all extracted forest IDs.")
    _ = target.add_argument(
        "--forest-id",
        action="append",
        help="ForestTrip insttId. Can be passed multiple times or comma-separated.",
    )
    _ = target.add_argument(
        "--forest-name",
        action="append",
        help="Substring to match against official forest names.",
    )

    output = parser.add_mutually_exclusive_group()
    _ = output.add_argument("--json", action="store_true", help="Print JSON output.")
    _ = output.add_argument("--text", action="store_true", help="Print human-readable output.")
    _ = parser.add_argument("--dates", type=parse_dates, help="Comma-separated YYYYMMDD dates.")
    _ = parser.add_argument(
        "--categories",
        type=parse_categories,
        default=("01", "02"),
        help="Comma-separated category codes: 01=lodging, 02=camping.",
    )
    _ = parser.add_argument(
        "--concurrency",
        type=parse_concurrency,
        default=DEFAULT_CONCURRENCY,
        help=f"Parallel POST workers, 1-{MAX_CONCURRENCY}.",
    )
    _ = parser.add_argument(
        "--week-range",
        type=parse_week_range,
        help="Weeks ahead to scan when --dates is omitted.",
    )
    _ = parser.add_argument("--refresh-session", action="store_true", help="Ignore session cache.")
    _ = parser.add_argument(
        "--check-deps",
        action="store_true",
        help="Check Python and Playwright runtime dependencies.",
    )
    _ = parser.add_argument(
        "--session-cache",
        default="~/.cache/k-skill/foresttrip-vacancy/session.json",
        help="Session cache path.",
    )
    args = parser.parse_args()
    all_targets = cast(bool, getattr(args, "all", False))
    forest_ids = cast(list[str] | None, getattr(args, "forest_id", None))
    forest_names = cast(list[str] | None, getattr(args, "forest_name", None))
    dates = cast(tuple[str, ...] | None, getattr(args, "dates", None))
    week_range = cast(int | None, getattr(args, "week_range", None))
    if all_targets and (forest_ids or forest_names):
        parser.error("--all cannot be combined with --forest-id or --forest-name")
    if dates and week_range is not None:
        parser.error("--week-range cannot be combined with --dates; the lookup range is derived from --dates")
    return args


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"missing required environment variable: {name}")
    return value


def check_dependencies(*, launch_browser: bool = True) -> None:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit("playwright is required. Install with: python3 -m pip install playwright") from exc

    if not launch_browser:
        return

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
    except PlaywrightError as exc:
        raise SystemExit(
            "playwright chromium browser is required. Install with: python3 -m playwright install chromium"
        ) from exc


def load_session_cache(path: Path) -> Session | None:
    if not path.exists():
        return None
    try:
        data = _as_mapping(cast(object, json.loads(path.read_text(encoding="utf-8"))))
        if time.time() > cast(float, data.get("expires_at", 0.0)):
            return None
        return Session(
            cookies=_as_str_map(data.get("cookies")),
            csrf=_as_text(data.get("csrf")),
            user_agent=_as_text(data.get("user_agent")),
            forests=_as_str_map(data.get("forests")),
            expires_at=cast(float, data["expires_at"]),
        )
    except Exception:
        return None


def save_session_cache(path: Path, session: Session) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(json.dumps(asdict(session), ensure_ascii=False), encoding="utf-8")
    try:
        _ = path.chmod(0o600)
    except OSError:
        pass


def bootstrap_session(*, forest_id: str, forest_pw: str, ttl_sec: int = 600) -> Session:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            "playwright is required. Install with: python3 -m pip install playwright "
            + "&& python3 -m playwright install chromium"
        ) from exc

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except PlaywrightError as exc:
            raise SystemExit(
                "playwright chromium browser is required. Install with: python3 -m playwright install chromium"
            ) from exc
        page = browser.new_page()
        _ = page.goto(LOGIN_URL)
        page.fill("#mmberId", forest_id)
        page.fill("#gnrlMmberPssrd", forest_pw)
        page.click("input.loginBtn")
        page.wait_for_load_state("networkidle")
        _ = page.goto(RSRVT_PAGE)
        page.wait_for_load_state("networkidle")

        csrf_locator = page.locator('input[name="_csrf"]')
        if csrf_locator.count() == 0:
            browser.close()
            raise SystemExit("login succeeded page did not expose a CSRF token")
        csrf = csrf_locator.first.get_attribute("value") or ""

        forests: dict[str, str] = {}
        regions = _as_mapping_list(cast(object, page.evaluate(
            """
            () => Array.from(document.querySelector('#srchSido').options)
              .slice(1)
              .map(o => ({ value: o.value, text: o.textContent.trim() }))
            """
        )))
        for region in regions:
            value = _as_text(region.get("value"))
            if not value:
                continue
            _ = page.select_option("#srchSido", value=value)
            page.wait_for_timeout(500)
            options = _as_mapping_list(cast(object, page.evaluate(
                """
                () => Array.from(document.querySelector('#srchInstt').options)
                  .slice(1)
                  .map(o => ({ value: o.value, text: o.textContent.trim() }))
                """
            )))
            for opt in options:
                fid = _as_text(opt.get("value")).strip()
                name = _as_text(opt.get("text")).strip()
                if fid and name:
                    forests[fid] = name

        cookies = {
            str(cookie.get("name")): str(cookie.get("value", ""))
            for cookie in page.context.cookies()
            if cookie.get("name")
        }
        user_agent = cast(str, page.evaluate("() => navigator.userAgent"))
        browser.close()

    if not csrf or not cookies:
        raise SystemExit("failed to bootstrap foresttrip session")
    if not forests:
        raise SystemExit("failed to extract forest list from reservation page")
    return Session(
        cookies=cookies,
        csrf=csrf,
        user_agent=user_agent,
        forests=forests,
        expires_at=time.time() + ttl_sec,
    )


def get_session(args: argparse.Namespace) -> Session:
    cache_path = Path(cast(str, getattr(args, "session_cache", ""))).expanduser()
    if not cast(bool, getattr(args, "refresh_session", False)):
        cached = load_session_cache(cache_path)
        if cached is not None:
            return cached
    session = bootstrap_session(
        forest_id=require_env("KSKILL_FORESTTRIP_ID"),
        forest_pw=require_env("KSKILL_FORESTTRIP_PASSWORD"),
    )
    save_session_cache(cache_path, session)
    return session


def split_csv(values: list[str] | None) -> list[str]:
    out: list[str] = []
    for value in values or []:
        out.extend(part.strip() for part in value.split(",") if part.strip())
    return out


def resolve_targets(args: argparse.Namespace, forests: dict[str, str]) -> dict[str, str]:
    all_targets = cast(bool, getattr(args, "all", False))
    forest_ids = cast(list[str] | None, getattr(args, "forest_id", None))
    forest_names = cast(list[str] | None, getattr(args, "forest_name", None))
    if all_targets:
        return dict(sorted(forests.items(), key=lambda item: item[1]))

    requested_ids = split_csv(forest_ids)
    requested_names = split_csv(forest_names)
    targets: dict[str, str] = {}
    for fid in requested_ids:
        targets[fid] = forests.get(fid, fid)
    for needle in requested_names:
        matches = {fid: name for fid, name in forests.items() if needle.replace(" ", "") in name.replace(" ", "")}
        targets.update(matches)

    if not targets:
        raise SystemExit("choose a target with --all, --forest-id, or --forest-name")
    return dict(sorted(targets.items(), key=lambda item: item[1]))


def build_headers(session: Session) -> dict[str, str]:
    cookie_header = "; ".join(f"{k}={v}" for k, v in session.cookies.items())
    return {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Content-Type": "application/json; charset=UTF-8",
        "Cookie": cookie_header,
        "Origin": "https://www.foresttrip.go.kr",
        "Referer": RSRVT_PAGE,
        "User-Agent": session.user_agent,
        "X-CSRF-Token": session.csrf,
        "X-Requested-With": "XMLHttpRequest",
    }


def fetch_one(
    *,
    session: Session,
    forest_id: str,
    category: str,
    today: str,
    last_day: str,
) -> tuple[str, str, list[Payload] | None, str | None]:
    payload = {
        "insttId": forest_id,
        "upperGoodsClsscCd": category,
        "srchDate": today,
        "lastDay": last_day,
        "inqurSctin": "02",
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        POST_URL,
        data=body,
        headers=build_headers(session),
        method="POST",
    )
    try:
        response = cast(_HTTPResponse, urllib.request.urlopen(request, timeout=30))
        try:
            if response.status != 200:
                return forest_id, category, None, f"http_{response.status}"
            data = cast(object, json.loads(response.read().decode("utf-8")))
            if isinstance(data, list):
                return forest_id, category, _as_mapping_list(cast(object, data)), None
            return forest_id, category, None, "unexpected_payload"
        finally:
            response.close()
    except urllib.error.HTTPError as exc:
        return forest_id, category, None, f"http_{exc.code}"
    except Exception as exc:
        return forest_id, category, None, str(exc)


def is_available(row: Payload) -> bool:
    return row.get("rsrvtAvail") == "Y" and row.get("rsrvtCnt") == 0


def normalize_row(row: Payload, forests: dict[str, str]) -> Payload:
    instt_id = str(row.get("insttId") or "")
    return {
        "forest_id": instt_id,
        "forest": forests.get(instt_id, row.get("insttNm") or instt_id),
        "use_dt": row.get("useDt") or "",
        "day": row.get("dywkDtTpcd"),
        "name": row.get("goodsNm") or "",
        "area": row.get("insttArea"),
        "capacity": row.get("mxmmAccptCnt"),
        "category": row.get("goodsClsscNm"),
        "region": row.get("insttAreaNm"),
        "waiting_possible": row.get("wtngPssblYn"),
    }


def collect_results(
    *,
    session: Session,
    targets: dict[str, str],
    categories: tuple[str, ...],
    dates: tuple[str, ...] | None,
    week_range: int | None,
    concurrency: int,
) -> dict[str, object]:
    now = datetime.now()
    today = now.strftime("%Y%m%d")
    last_day = max(dates) if dates else (now + timedelta(weeks=week_range or DEFAULT_WEEK_RANGE)).strftime("%Y%m%d")
    date_filter = set(dates) if dates else None
    failures: list[dict[str, str]] = []
    rows: list[Payload] = []

    jobs = [(forest_id, category) for forest_id in targets for category in categories]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        futures = [
            pool.submit(
                fetch_one,
                session=session,
                forest_id=forest_id,
                category=category,
                today=today,
                last_day=last_day,
            )
            for forest_id, category in jobs
        ]
        for future in concurrent.futures.as_completed(futures):
            forest_id, category, data, error = future.result()
            if error is not None or data is None:
                failures.append(
                    {
                        "forest_id": forest_id,
                        "category": category,
                        "error": error or "unknown",
                    }
                )
                continue
            for row in data:
                if not is_available(row):
                    continue
                normalized = normalize_row(row, session.forests)
                if date_filter is not None and normalized["use_dt"] not in date_filter:
                    continue
                rows.append(normalized)

    grouped: dict[str, dict[str, list[Payload]]] = {}
    for row in sorted(rows, key=lambda item: (str(item["forest"]), str(item["use_dt"]), str(item["name"]))):
        forest_name = str(row["forest"])
        use_dt = str(row["use_dt"])
        grouped.setdefault(forest_name, {}).setdefault(use_dt, []).append(row)

    return {
        "forests_scanned": len(targets),
        "filter_hits": len(rows),
        "fetch_failures": len(failures),
        "failures": failures[:20],
        "concurrency": concurrency,
        "date_range": {"from": today, "to": last_day},
        "results": [
            {
                "forest": forest_name,
                "dates": [{"use_dt": use_dt, "rooms": rooms} for use_dt, rooms in sorted(rows_by_date.items())],
            }
            for forest_name, rows_by_date in sorted(grouped.items())
        ],
    }


def print_text(payload: dict[str, object]) -> None:
    print("=== ForestTrip Vacancy Lookup ===")
    print(
        f"filter_hits: {payload['filter_hits']}   "
        + f"fetch_failures: {payload['fetch_failures']}   "
        + f"forests_scanned: {payload['forests_scanned']}"
    )
    if not payload["results"]:
        print("(no available rooms at lookup time)")
        return
    for forest in _as_mapping_list(payload.get("results")):
        print(f"\n{_as_text(forest.get('forest'))}")
        for date_group in _as_mapping_list(forest.get("dates")):
            rooms = _as_mapping_list(date_group.get("rooms"))
            print(f"  {_as_text(date_group.get('use_dt'))} - {len(rooms)} slot(s)")
            for room in rooms[:8]:
                capacity = room.get("capacity") if room.get("capacity") is not None else "?"
                area = room.get("area") if room.get("area") is not None else "?"
                print(f"    - {_as_text(room.get('name'))} / {_as_text(room.get('category'))} / {area}sqm / max {capacity}")


def main() -> int:
    args = parse_args()
    check_deps = cast(bool, getattr(args, "check_deps", False))
    if check_deps:
        check_dependencies()
        print("foresttrip-vacancy dependencies look ready")
        return 0
    session = get_session(args)
    targets = resolve_targets(args, session.forests)
    categories = cast(tuple[str, ...], getattr(args, "categories", ("01", "02")))
    dates = cast(tuple[str, ...] | None, getattr(args, "dates", None))
    week_range = cast(int | None, getattr(args, "week_range", None))
    concurrency = cast(int, getattr(args, "concurrency", DEFAULT_CONCURRENCY))
    payload = collect_results(
        session=session,
        targets=targets,
        categories=categories,
        dates=dates,
        week_range=week_range,
        concurrency=concurrency,
    )

    text_output = cast(bool, getattr(args, "text", False))
    json_output = cast(bool, getattr(args, "json", False))
    if text_output and not json_output:
        print_text(payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["fetch_failures"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
