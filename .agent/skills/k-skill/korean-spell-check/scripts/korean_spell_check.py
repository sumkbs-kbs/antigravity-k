from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from html import unescape
from pathlib import Path
from typing import Callable, Protocol, cast

DEFAULT_RESULTS_URL = "https://nara-speller.co.kr/old_speller/results"
DEFAULT_MAX_CHARS = 1500
DEFAULT_TIMEOUT = 30
DEFAULT_THROTTLE_SECONDS = 1.2
RESULT_PAYLOAD_PATTERN = re.compile(r"data\s*=\s*(\[[\s\S]*?\]);\s*pageIdx\s*=")
NO_ISSUES_PATTERN = re.compile(r"맞춤법과\s*문법\s*오류를\s*찾지\s*못했습니다", re.MULTILINE)
TAG_PATTERN = re.compile(r"<[^>]+>")
LINE_BREAK_PATTERN = re.compile(r"<br\s*/?>", re.IGNORECASE)
SENTENCE_BOUNDARY_PATTERN = re.compile(r"(?<=[.!?。！？])\s+")
PARAGRAPH_SEPARATOR_PATTERN = re.compile(r"\n(?:[ \t]*\n)+")

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko,en-US;q=0.9,en;q=0.8",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://nara-speller.co.kr",
    "Referer": "https://nara-speller.co.kr/old_speller/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
}

Payload = dict[str, object]


def _as_text(value: object, default: str = "") -> str:
    if value is None:
        return default
    return value if isinstance(value, str) else str(value)


def _as_int(value: object, default: int = -1) -> int:
    if value is None or value == "":
        return default
    if not isinstance(value, (str, int, float)):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_payload(value: object) -> Payload:
    if not isinstance(value, dict):
        return {}
    raw = cast(dict[object, object], value)
    return {str(key): item for key, item in raw.items()}


def _as_payload_list(value: object) -> list[Payload]:
    if not isinstance(value, list):
        return []
    items = cast(list[object], value)
    return [_as_payload(cast(object, item)) for item in items if isinstance(item, dict)]


class _HTTPResponse(Protocol):
    def read(self) -> bytes: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class SpellCheckIssue:
    chunk_index: int
    page_index: int
    issue_index: int
    sentence: str
    original: str
    suggestions: list[str]
    reason: str
    start: int | None
    end: int | None
    correct_method: int | None
    error_message: str


def strip_html(value: str | None) -> str:
    text = LINE_BREAK_PATTERN.sub("\n", value or "")
    text = TAG_PATTERN.sub("", text)
    return unescape(text).strip()


def split_candidates(value: str | None) -> list[str]:
    return [candidate.strip() for candidate in str(value or "").split("|") if candidate.strip()]


def parse_positive_int(raw_value: str) -> int:
    value = int(raw_value)
    if value <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return value


def split_text_into_chunks(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> list[str]:
    original = str(text or "")
    if not original.strip():
        return []

    units = split_paragraph_units(original)
    chunks: list[str] = []
    current = ""

    for unit in units:
        candidate = unit if not current else f"{current}{unit}"

        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        if len(unit) <= max_chars:
            current = unit
            continue

        separator = ""
        body = unit
        separator_match = PARAGRAPH_SEPARATOR_PATTERN.search(unit)

        if separator_match and separator_match.end() == len(unit):
            separator = separator_match.group(0)
            body = unit[: separator_match.start()]

        for sentence in split_long_paragraph(body, max_chars=max_chars):
            if len(sentence) <= max_chars:
                chunks.append(sentence)
                continue

            start = 0
            while start < len(sentence):
                chunks.append(sentence[start : start + max_chars])
                start += max_chars

        if separator:
            if chunks and len(chunks[-1]) + len(separator) <= max_chars:
                chunks[-1] += separator
            else:
                current = separator

    if current:
        chunks.append(current)

    return chunks


def split_paragraph_units(text: str) -> list[str]:
    units: list[str] = []
    start = 0

    for match in PARAGRAPH_SEPARATOR_PATTERN.finditer(text):
        paragraph = text[start : match.start()]
        separator = match.group(0)

        if paragraph:
            units.append(paragraph + separator)
        elif units:
            units[-1] += separator
        else:
            units.append(separator)

        start = match.end()

    tail = text[start:]
    if tail:
        units.append(tail)

    return units


def split_long_paragraph(paragraph: str, *, max_chars: int) -> list[str]:
    sentence_boundaries = list(SENTENCE_BOUNDARY_PATTERN.finditer(paragraph))

    if not sentence_boundaries:
        return [paragraph]

    sentences: list[str] = []
    start = 0

    for boundary in sentence_boundaries:
        sentences.append(paragraph[start : boundary.end()])
        start = boundary.end()

    if start < len(paragraph):
        sentences.append(paragraph[start:])

    groups: list[str] = []
    current = ""

    for sentence in sentences:
        candidate = sentence if not current else f"{current}{sentence}"

        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            groups.append(current)
        current = sentence

    if current:
        groups.append(current)

    return groups


def fetch_spell_check_html(
    text: str,
    *,
    strong_rules: bool = True,
    timeout: int = DEFAULT_TIMEOUT,
    url: str = DEFAULT_RESULTS_URL,
) -> str:
    body = {
        "text1": text,
        "chkKey": "",
    }

    if strong_rules:
        body["btnModeChange"] = "on"

    request = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(body).encode("utf-8"),
        headers=DEFAULT_HEADERS,
        method="POST",
    )

    try:
        response = cast(_HTTPResponse, urllib.request.urlopen(request, timeout=timeout))
        try:
            raw_body = response.read()
            return raw_body.decode("utf-8", "ignore")
        finally:
            response.close()
    except urllib.error.HTTPError as error:  # type: ignore[attr-defined]
        if error.code == 403:
            raise RuntimeError(
                "The spell-check service returned HTTP 403. "
                + "This environment may be hitting a Cloudflare/browser challenge. "
                + "Retry later with lower request volume or from a browser-friendly network."
            ) from error

        raise RuntimeError(f"The spell-check service returned HTTP {error.code}.") from error


def extract_result_payload(html: str) -> list[Payload]:
    match = RESULT_PAYLOAD_PATTERN.search(html)

    if not match:
        if NO_ISSUES_PATTERN.search(html):
            return []
        raise ValueError("Unable to find the spell-check payload in the returned HTML.")

    payload = cast(object, json.loads(match.group(1)))

    if not isinstance(payload, list):
        raise ValueError("The extracted spell-check payload was not a list.")

    return _as_payload_list(cast(object, payload))


def apply_page_corrections(page: Payload) -> str:
    source = _as_text(page.get("str"))
    corrected = source

    for error in sorted(
        _as_payload_list(page.get("errInfo")),
        key=lambda item: _as_int(item.get("start")),
        reverse=True,
    ):
        suggestions = split_candidates(_as_text(error.get("candWord")))
        original = _as_text(error.get("orgStr"))

        if not suggestions:
            continue

        start = _as_int(error.get("start"))
        end = _as_int(error.get("end"))

        if start < 0 or end < start or end >= len(source):
            continue

        slice_end = end + 1
        if original:
            while (
                slice_end > start and source[start:slice_end] != original and source[start : slice_end - 1] == original
            ):
                slice_end -= 1

        corrected = f"{corrected[:start]}{suggestions[0]}{corrected[slice_end:]}"

    return corrected


def build_visible_text_index(text: str) -> tuple[str, list[int], list[int | None]]:
    visible_chars: list[str] = []
    visible_indices: list[int] = []
    visible_lookup: list[int | None] = []

    for index, char in enumerate(text):
        if char.isspace():
            visible_lookup.append(None)
            continue

        visible_lookup.append(len(visible_indices))
        visible_chars.append(char)
        visible_indices.append(index)

    return "".join(visible_chars), visible_indices, visible_lookup


def preserve_original_layout(original: str, suggestion: str) -> str:
    if "\n" not in original:
        return suggestion

    original_visible, original_visible_indices, _ = build_visible_text_index(original)
    suggestion_visible, suggestion_visible_indices, _ = build_visible_text_index(suggestion)

    if original_visible != suggestion_visible:
        return suggestion

    if not original_visible_indices or not suggestion_visible_indices:
        return original if original.strip() else suggestion

    merged: list[str] = []
    leading_original = original[: original_visible_indices[0]]
    leading_suggestion = suggestion[: suggestion_visible_indices[0]]
    merged.append(leading_original if leading_original.isspace() else leading_suggestion)

    for ordinal, suggestion_index in enumerate(suggestion_visible_indices):
        merged.append(suggestion[suggestion_index])

        next_original_index = (
            original_visible_indices[ordinal + 1] if ordinal + 1 < len(original_visible_indices) else None
        )
        next_suggestion_index = (
            suggestion_visible_indices[ordinal + 1] if ordinal + 1 < len(suggestion_visible_indices) else None
        )

        original_gap = (
            original[original_visible_indices[ordinal] + 1 : next_original_index]
            if next_original_index is not None
            else original[original_visible_indices[ordinal] + 1 :]
        )
        suggestion_gap = (
            suggestion[suggestion_index + 1 : next_suggestion_index]
            if next_suggestion_index is not None
            else suggestion[suggestion_index + 1 :]
        )

        merged.append(original_gap if "\n" in original_gap else suggestion_gap)

    return "".join(merged)


def apply_chunk_corrections(chunk: str, pages: list[Payload]) -> str:
    combined_source = "".join(_as_text(page.get("str")) for page in pages)
    fallback = "".join(apply_page_corrections(page) for page in pages) or chunk

    if not combined_source:
        return fallback

    chunk_visible, chunk_visible_indices, _ = build_visible_text_index(chunk)
    source_visible, _, source_visible_lookup = build_visible_text_index(combined_source)

    if chunk_visible != source_visible:
        return fallback

    replacements: list[tuple[int, int, str, str]] = []
    page_offset = 0

    for page in pages:
        for error in _as_payload_list(page.get("errInfo")):
            suggestions = split_candidates(_as_text(error.get("candWord")))
            if not suggestions:
                continue

            start = _as_int(error.get("start"))
            end = _as_int(error.get("end"))

            if start < 0 or end < start:
                continue

            start += page_offset
            end += page_offset

            visible_ordinals = [
                ordinal
                for index in range(start, min(end + 1, len(source_visible_lookup)))
                if (ordinal := source_visible_lookup[index]) is not None
            ]

            if not visible_ordinals:
                continue

            original_start = chunk_visible_indices[visible_ordinals[0]]
            original_end = chunk_visible_indices[visible_ordinals[-1]]
            replacements.append(
                (
                    original_start,
                    original_end,
                    suggestions[0],
                    _as_text(error.get("orgStr")),
                )
            )

        page_offset += len(_as_text(page.get("str")))

    if not replacements:
        return chunk

    corrected = chunk

    for start, end, suggestion, original in sorted(replacements, key=lambda item: item[0], reverse=True):
        slice_end = end + 1
        if original:
            while (
                slice_end > start
                and corrected[start:slice_end] != original
                and corrected[start : slice_end - 1] == original
            ):
                slice_end -= 1

        original_slice = corrected[start:slice_end]
        replacement = preserve_original_layout(original_slice, suggestion)
        corrected = f"{corrected[:start]}{replacement}{corrected[slice_end:]}"

    return corrected


def build_issue(
    chunk_index: int,
    page_index: int,
    issue_index: int,
    page: Payload,
    error: Payload,
) -> SpellCheckIssue:
    return SpellCheckIssue(
        chunk_index=chunk_index,
        page_index=page_index,
        issue_index=issue_index,
        sentence=_as_text(page.get("str")),
        original=_as_text(error.get("orgStr")),
        suggestions=split_candidates(_as_text(error.get("candWord"))),
        reason=strip_html(_as_text(error.get("help"))) or strip_html(_as_text(error.get("errMsg"))),
        start=_as_int(error.get("start"), default=0) if _as_text(error.get("start")).strip() else None,
        end=_as_int(error.get("end"), default=0) if _as_text(error.get("end")).strip() else None,
        correct_method=(_as_int(error.get("correctMethod"), default=0) if _as_text(error.get("correctMethod")).strip() else None),
        error_message=strip_html(_as_text(error.get("errMsg"))),
    )


def check_text(
    text: str,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    strong_rules: bool = True,
    timeout: int = DEFAULT_TIMEOUT,
    throttle_seconds: float = DEFAULT_THROTTLE_SECONDS,
    requester: Callable[..., str] = fetch_spell_check_html,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, object]:
    chunks = split_text_into_chunks(text, max_chars=max_chars)
    corrected_chunks: list[str] = []
    issues: list[SpellCheckIssue] = []
    chunk_reports: list[Payload] = []

    for chunk_index, chunk in enumerate(chunks):
        if chunk_index > 0 and throttle_seconds > 0:
            sleep_fn(throttle_seconds)

        html = requester(chunk, strong_rules=strong_rules, timeout=timeout)
        pages = extract_result_payload(html)
        corrected_chunk = apply_chunk_corrections(chunk, pages)

        corrected_chunks.append(corrected_chunk)
        chunk_reports.append(
            {
                "chunk_index": chunk_index,
                "original_text": chunk,
                "corrected_text": corrected_chunk,
                "page_count": len(pages),
            }
        )

        for page_index, page in enumerate(pages):
            for issue_index, error in enumerate(_as_payload_list(page.get("errInfo"))):
                issues.append(build_issue(chunk_index, page_index, issue_index, page, error))

    return {
        "original_text": str(text or ""),
        "corrected_text": "".join(corrected_chunks),
        "chunks": chunk_reports,
        "issues": issues,
        "meta": {
            "chunk_count": len(chunks),
            "strong_rules": strong_rules,
            "max_chars": max_chars,
        },
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the official Nara/PNU Korean spell checker.")
    _ = parser.add_argument("--text", help="Inline Korean text to inspect.")
    _ = parser.add_argument("--file", help="UTF-8 text/markdown file to inspect.")
    _ = parser.add_argument("--max-chars", type=parse_positive_int, default=DEFAULT_MAX_CHARS)
    _ = parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    _ = parser.add_argument("--throttle-seconds", type=float, default=DEFAULT_THROTTLE_SECONDS)
    _ = parser.add_argument("--weak-rules", action="store_true", help="Disable the strong-rules checkbox.")
    _ = parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args(argv)

    text_value = cast(str | None, getattr(args, "text", None))
    file_value = cast(str | None, getattr(args, "file", None))
    if not text_value and not file_value:
        parser.error("Either --text or --file is required.")

    return args


def load_input(args: argparse.Namespace) -> str:
    text_value = cast(str | None, getattr(args, "text", None))
    if text_value:
        return text_value

    file_value = cast(str, getattr(args, "file", ""))
    return Path(file_value).read_text(encoding="utf-8")


def serialize_report(report: dict[str, object]) -> dict[str, object]:
    issues = cast(list[SpellCheckIssue], report.get("issues", []))
    return {
        **report,
        "issues": [cast(dict[str, object], asdict(issue)) for issue in issues],
    }


def print_text_report(report: dict[str, object]) -> None:
    print("# corrected_text")
    print(_as_text(report.get("corrected_text")))
    print()
    print("# issues")

    for issue in cast(list[SpellCheckIssue], report.get("issues", [])):
        print(f"- chunk={issue.chunk_index} page={issue.page_index} issue={issue.issue_index}")
        print(f"  original: {issue.original}")
        print(f"  suggestions: {', '.join(issue.suggestions) if issue.suggestions else '(없음)'}")
        print(f"  reason: {issue.reason or '(없음)'}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    report = check_text(
        load_input(args),
        max_chars=cast(int, getattr(args, "max_chars", DEFAULT_MAX_CHARS)),
        strong_rules=not cast(bool, getattr(args, "weak_rules", False)),
        timeout=cast(int, getattr(args, "timeout", DEFAULT_TIMEOUT)),
        throttle_seconds=cast(float, getattr(args, "throttle_seconds", DEFAULT_THROTTLE_SECONDS)),
    )

    if cast(str, getattr(args, "format", "json")) == "json":
        print(json.dumps(serialize_report(report), ensure_ascii=False, indent=2))
    else:
        print_text_report(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
