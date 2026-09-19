from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from html import unescape
from typing import Protocol, cast

PROXY_BASE_URL_ENV_VAR = "KSKILL_PROXY_BASE_URL"
DEFAULT_PROXY_BASE_URL = "https://k-skill-proxy.nomadamas.org"

Payload = dict[str, object]
RequestJson = Callable[[urllib.request.Request | str], Payload]


def _as_mapping(value: object) -> Payload:
    if not isinstance(value, Mapping):
        return {}
    raw = cast(Mapping[object, object], value)
    return {str(key): item for key, item in raw.items()}


class _HTTPResponse(Protocol):
    def read(self) -> bytes: ...

    def close(self) -> None: ...


class ApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, url: str | None = None):
        super().__init__(message)
        self.status_code: int | None = status_code
        self.url: str | None = url


def summarize_text(value: object) -> str:
    if value is None:
        return ""
    text = unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def resolve_proxy_base_url(explicit_base_url: str | None = None, env: Mapping[str, str] | None = None) -> str:
    environment = env or os.environ
    candidate = summarize_text(explicit_base_url or environment.get(PROXY_BASE_URL_ENV_VAR))
    if candidate.casefold() in {"off", "false", "0", "disable", "disabled", "none"}:
        raise ValueError("KSKILL_PROXY_BASE_URL 가 비활성화되어 있습니다.")
    if candidate and candidate != "replace-me":
        return candidate.rstrip("/")
    return DEFAULT_PROXY_BASE_URL


def build_food_interview(question: str | None = None, symptoms: str | None = None) -> Payload:
    return {
        "domain": "food",
        "question": summarize_text(question),
        "symptoms": summarize_text(symptoms),
        "must_ask": [
            "누가 먹었거나 먹으려는지 알려주세요. (본인/아이/임산부/고령자)",
            "무엇을 언제 먹었는지, 얼마나 먹었는지 알려주세요.",
            "같이 먹은 음식이나 술, 복용 중인 약이 있는지 알려주세요.",
            "복통·구토·설사·발진 같은 증상이 언제부터 시작됐는지 알려주세요.",
            "기저질환, 임신 여부, 알레르기 여부를 알려주세요.",
        ],
        "red_flags": [
            "호흡곤란, 입술·혀 붓기 같은 급성 알레르기 반응",
            "혈변 또는 검은변",
            "심한 탈수, 소변 감소, 계속되는 구토",
            "의식저하, 고열, 심한 복통",
        ],
        "urgent_action": "red flag 가 있으면 식품 조회보다 즉시 응급실·119·의료진 연결을 우선하세요.",
        "policy": "이 helper 는 공식 식품 안전정보 조회 전에 반드시 되묻기 흐름을 제공하며, 먹어도 되는지 단정하지 않습니다.",
    }


def normalize_food_recall_row(row: Payload) -> Payload:
    return {
        "source": "foodsafetykorea_recall",
        "product_name": summarize_text(row.get("product_name") or row.get("PRDLST_NM") or row.get("PRDTNM")),
        "company_name": summarize_text(row.get("company_name") or row.get("BSSH_NM") or row.get("BSSHNM")),
        "reason": summarize_text(row.get("reason") or row.get("RTRVLPRVNS")),
        "created_at": summarize_text(row.get("created_at") or row.get("CRET_DTM")),
        "distribution_deadline": summarize_text(row.get("distribution_deadline") or row.get("DISTBTMLMT")),
        "category": summarize_text(row.get("category") or row.get("PRDLST_TYPE") or row.get("PRDLST_CD_NM")),
    }


def normalize_improper_food_item(item: Payload) -> Payload:
    reason_parts = [
        summarize_text(item.get("reason") or item.get("IMPROPT_ITM")),
        summarize_text(item.get("INSPCT_RESULT")),
    ]
    return {
        "source": "mfds_improper_food",
        "product_name": summarize_text(item.get("product_name") or item.get("PRDUCT")),
        "company_name": summarize_text(item.get("company_name") or item.get("ENTRPS")),
        "reason": "; ".join(part for part in reason_parts if part),
        "created_at": summarize_text(item.get("created_at") or item.get("REGIST_DT")),
        "category": summarize_text(item.get("category") or item.get("FOOD_TY")),
    }


def filter_food_items(items: list[Payload], query: str) -> list[Payload]:
    needle = summarize_text(query).casefold()
    if not needle:
        return items

    product_matches = [item for item in items if needle in summarize_text(item.get("product_name")).casefold()]
    if product_matches:
        return product_matches

    company_matches = [item for item in items if needle in summarize_text(item.get("company_name")).casefold()]
    if company_matches:
        return company_matches

    return [item for item in items if needle in summarize_text(item.get("reason")).casefold()]


def read_json_response(request: urllib.request.Request | str) -> Payload:
    try:
        response = cast(_HTTPResponse, urllib.request.urlopen(request, timeout=30))
        try:
            return _as_mapping(cast(object, json.loads(response.read().decode("utf-8"))))
        finally:
            response.close()
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        try:
            payload = cast(object, json.loads(body))
        except json.JSONDecodeError:
            payload = {}

        payload_mapping = _as_mapping(cast(object, payload))
        if payload_mapping.get("message"):
            raise ApiError(
                summarize_text(payload_mapping["message"]),
                status_code=error.code,
                url=getattr(error, "url", None),
            ) from error
        raise ApiError(
            f"MFDS food proxy request failed with HTTP {error.code}",
            status_code=error.code,
            url=getattr(error, "url", None),
        ) from error
    except urllib.error.URLError as error:
        raise ApiError(f"MFDS food proxy request failed: {error.reason}") from error


def search_food_safety(
    query: str,
    *,
    limit: int = 10,
    base_url: str | None = None,
    request_json: RequestJson = read_json_response,
) -> Payload:
    resolved_base_url = resolve_proxy_base_url(base_url)
    url = f"{resolved_base_url}/v1/mfds/food-safety/search"
    params = urllib.parse.urlencode({"query": query, "limit": str(limit)})
    request = urllib.request.Request(
        f"{url}?{params}",
        headers={"Accept": "application/json", "User-Agent": "k-skill-mfds/1.0"},
    )
    return request_json(request)


def search_health_food_ingredient(
    query: str,
    *,
    limit: int = 10,
    base_url: str | None = None,
    request_json: RequestJson = read_json_response,
) -> Payload:
    resolved_base_url = resolve_proxy_base_url(base_url)
    url = f"{resolved_base_url}/v1/mfds/food-safety/health-food-ingredient"
    params = urllib.parse.urlencode({"query": query, "limit": str(limit)})
    request = urllib.request.Request(
        f"{url}?{params}",
        headers={"Accept": "application/json", "User-Agent": "k-skill-mfds/1.0"},
    )
    return request_json(request)


def search_product_report(
    query: str,
    *,
    limit: int = 10,
    base_url: str | None = None,
    request_json: RequestJson = read_json_response,
) -> Payload:
    resolved_base_url = resolve_proxy_base_url(base_url)
    url = f"{resolved_base_url}/v1/mfds/food-safety/product-report"
    params = urllib.parse.urlencode({"query": query, "limit": str(limit)})
    request = urllib.request.Request(
        f"{url}?{params}",
        headers={"Accept": "application/json", "User-Agent": "k-skill-mfds/1.0"},
    )
    return request_json(request)


def search_inspection_fail(
    query: str,
    *,
    limit: int = 10,
    base_url: str | None = None,
    request_json: RequestJson = read_json_response,
) -> Payload:
    resolved_base_url = resolve_proxy_base_url(base_url)
    url = f"{resolved_base_url}/v1/mfds/food-safety/inspection-fail"
    params = urllib.parse.urlencode({"query": query, "limit": str(limit)})
    request = urllib.request.Request(
        f"{url}?{params}",
        headers={"Accept": "application/json", "User-Agent": "k-skill-mfds/1.0"},
    )
    return request_json(request)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MFDS food-safety helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    interview = subparsers.add_parser("interview", help="print the mandatory symptom follow-up interview")
    _ = interview.add_argument("--question", default="")
    _ = interview.add_argument("--symptoms", default="")

    search = subparsers.add_parser("search", help="search official food-safety records through k-skill-proxy")
    _ = search.add_argument("--query", required=True)
    _ = search.add_argument("--limit", type=int, default=10)
    _ = search.add_argument("--proxy-base-url")

    product_report = subparsers.add_parser("product-report", help="search health food product manufacturing reports")
    _ = product_report.add_argument("--query", required=True)
    _ = product_report.add_argument("--limit", type=int, default=10)
    _ = product_report.add_argument("--proxy-base-url")

    ingredient = subparsers.add_parser(
        "health-food-ingredient",
        help="search health food ingredient recognition status",
    )
    _ = ingredient.add_argument("--query", required=True)
    _ = ingredient.add_argument("--limit", type=int, default=10)
    _ = ingredient.add_argument("--proxy-base-url")

    inspection = subparsers.add_parser("inspection-fail", help="search domestic inspection failure records")
    _ = inspection.add_argument("--query", required=True)
    _ = inspection.add_argument("--limit", type=int, default=10)
    _ = inspection.add_argument("--proxy-base-url")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = cast(str, getattr(args, "command", ""))

    if command == "interview":
        question = cast(str, getattr(args, "question", ""))
        symptoms = cast(str, getattr(args, "symptoms", ""))
        print(
            json.dumps(
                build_food_interview(question=question, symptoms=symptoms),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if command == "search":
        query = cast(str, getattr(args, "query", ""))
        limit = cast(int, getattr(args, "limit", 10))
        proxy_base_url = cast(str | None, getattr(args, "proxy_base_url", None))
        try:
            payload = search_food_safety(query, limit=limit, base_url=proxy_base_url)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        except (ValueError, ApiError) as error:
            print(
                json.dumps({"error": str(error)}, ensure_ascii=False, indent=2),
                file=sys.stderr,
            )
            return 1

    if command == "product-report":
        query = cast(str, getattr(args, "query", ""))
        limit = cast(int, getattr(args, "limit", 10))
        proxy_base_url = cast(str | None, getattr(args, "proxy_base_url", None))
        try:
            payload = search_product_report(query, limit=limit, base_url=proxy_base_url)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        except (ValueError, ApiError) as error:
            print(
                json.dumps({"error": str(error)}, ensure_ascii=False, indent=2),
                file=sys.stderr,
            )
            return 1

    if command == "health-food-ingredient":
        query = cast(str, getattr(args, "query", ""))
        limit = cast(int, getattr(args, "limit", 10))
        proxy_base_url = cast(str | None, getattr(args, "proxy_base_url", None))
        try:
            payload = search_health_food_ingredient(query, limit=limit, base_url=proxy_base_url)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        except (ValueError, ApiError) as error:
            print(
                json.dumps({"error": str(error)}, ensure_ascii=False, indent=2),
                file=sys.stderr,
            )
            return 1

    if command == "inspection-fail":
        query = cast(str, getattr(args, "query", ""))
        limit = cast(int, getattr(args, "limit", 10))
        proxy_base_url = cast(str | None, getattr(args, "proxy_base_url", None))
        try:
            payload = search_inspection_fail(query, limit=limit, base_url=proxy_base_url)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        except (ValueError, ApiError) as error:
            print(
                json.dumps({"error": str(error)}, ensure_ascii=False, indent=2),
                file=sys.stderr,
            )
            return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
