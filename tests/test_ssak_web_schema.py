"""ssak-web v1 계약 시험.

S의 `contracts/ssak-web/v1/` 이 계약 원본이며, 이 시험은 다음을 실제 bytes로 검증한다.

- golden fixture가 해당 capability schema로 실제 통과한다.
- 소비자 거절 규칙(필수 필드 누락, partial 인데 실패 목록 없음, POLICY_DENIED 가 retryable,
  truncated 인데 절단 정보 없음, json_ld 인데 structured_data 없음)이 실제로 빨개진다.
- 알 수 없는 major는 소비자가 거절하고 minor는 통과한다.
- manifest의 sha256이 실제 파일과 일치한다(양 repo 사본 drift 차단).
- fixture에 secret/PII 형태가 없다.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

CONTRACTS_DIR = Path(__file__).resolve().parents[1] / "contracts" / "ssak-web" / "v1"
FIXTURES_DIR = CONTRACTS_DIR / "fixtures"

# fixture 이름 접두어 → 검증할 capability schema. legacy wire fixture는 계약 이전 형태라 제외한다.
SCHEMA_FOR_FIXTURE = {
    "search.ok.json": "search.schema.json",
    "search.partial.json": "search.schema.json",
    "extract.ok.json": "extract.schema.json",
    "extract.blocked.policy-denied.json": "extract.schema.json",
    "deep-research.cancelled.json": "deep-research.schema.json",
    "deep-research.error.upstream-unavailable.json": "deep-research.schema.json",
    "blocked.unsupported-capability.json": "search.schema.json",
    "legacy.text-fallback.expected.json": "search.schema.json",
}

SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{16,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{16,}"),
    re.compile(r"(?i)(api[_-]?key|secret|password|access[_-]?token)\s*[:=]\s*[\"'][^\"']{8,}[\"']"),
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _registry() -> Registry:
    resources: list[tuple[str, Resource[Any]]] = []
    for schema_path in sorted(CONTRACTS_DIR.glob("*.schema.json")):
        contents = _load(schema_path)
        resource = Resource.from_contents(contents, default_specification=DRAFT202012)
        resources.append((schema_path.name, resource))
        resources.append((contents["$id"], resource))
    return Registry().with_resources(resources)


def _validate(schema_name: str, payload: dict[str, Any]) -> None:
    schema = _load(CONTRACTS_DIR / schema_name)
    Draft202012Validator(schema, registry=_registry()).validate(payload)


def _fixture(name: str) -> dict[str, Any]:
    return _load(FIXTURES_DIR / name)


def _is_valid(schema_name: str, payload: dict[str, Any]) -> bool:
    schema = _load(CONTRACTS_DIR / schema_name)
    return Draft202012Validator(schema, registry=_registry()).is_valid(payload)


# ── 계약 원본 자체 ────────────────────────────────────────────────────────────


def test_every_contract_file_is_tracked_in_the_manifest_with_the_real_hash() -> None:
    manifest = _load(CONTRACTS_DIR / "manifest.json")
    listed = manifest["files"]

    on_disk = {
        str(path.relative_to(CONTRACTS_DIR)).replace(os.sep, "/"): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in CONTRACTS_DIR.rglob("*.json")
        if path.name != "manifest.json"
    }

    assert set(listed) == set(on_disk), "manifest에 없는 계약 파일이거나, 사라진 파일이 manifest에 남아 있다"
    for name, expected in listed.items():
        assert on_disk[name] == expected, f"{name} bytes가 manifest와 다르다 — 계약 사본 drift"


def test_manifest_declares_this_directory_as_the_source_of_truth() -> None:
    manifest = _load(CONTRACTS_DIR / "manifest.json")
    assert manifest["source_of_truth"]["repo"] == "S"
    assert manifest["schema_version"] == "1.0"
    assert manifest["mirror"]["root_env"] == "SSAK_WEB_W_ROOT"


def test_schemas_are_self_describing_and_version_pinned() -> None:
    for schema_path in sorted(CONTRACTS_DIR.glob("*.schema.json")):
        schema = _load(schema_path)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["$id"].endswith(f"contracts/ssak-web/v1/{schema_path.name}"), (
            "스키마 $id가 버전 경로를 담지 않으면 사본이 어느 버전인지 구분할 수 없다"
        )


# ── golden fixture ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("fixture_name", sorted(SCHEMA_FOR_FIXTURE))
def test_golden_fixture_validates_against_its_capability_schema(fixture_name: str) -> None:
    _validate(SCHEMA_FOR_FIXTURE[fixture_name], _fixture(fixture_name))


def test_every_required_result_state_has_a_golden_fixture() -> None:
    states = {_fixture(name)["status"] for name in SCHEMA_FOR_FIXTURE}
    assert states == {"ok", "partial", "blocked", "error", "cancelled"}, f"결과 상태 fixture가 빠졌다: {states}"

    codes = {
        fixture["error"]["code"] for name, fixture in ((n, _fixture(n)) for n in SCHEMA_FOR_FIXTURE) if fixture["error"]
    }
    assert {"POLICY_DENIED", "UNSUPPORTED_CAPABILITY", "CANCELLED", "UPSTREAM_UNAVAILABLE"} <= codes


def test_partial_fixture_keeps_per_source_failures_and_is_not_an_error() -> None:
    fixture = _fixture("search.partial.json")
    assert fixture["status"] == "partial"
    assert fixture["error"] is None, "partial 을 error 로 보고하면 상위 계층이 성공 소스를 버린다"
    assert fixture["data"]["results"], "partial 인데 성공 결과가 없다"
    assert len(fixture["data"]["source_failures"]) >= 2
    assert all(failure["source"] for failure in fixture["data"]["source_failures"])


def test_unmeasured_usage_stays_null_and_is_never_disguised_as_zero() -> None:
    error_fixture = _fixture("deep-research.error.upstream-unavailable.json")
    assert error_fixture["usage"]["content_tokens"] is None
    blocked_fixture = _fixture("extract.blocked.policy-denied.json")
    assert blocked_fixture["usage"] is None

    measured = _fixture("search.ok.json")
    assert measured["usage"]["content_tokens"] == measured["evidence"][0]["content"]["token_count"]


def test_extract_fixtures_respect_the_declared_token_budget() -> None:
    for name in ("extract.ok.json",):
        data = _fixture(name)["data"]
        assert data["max_token_budget"] is not None
        assert data["token_count"] <= data["max_token_budget"], f"{name}: 선언한 budget을 넘겨 반환했다"


def test_retrieval_score_and_claim_verification_are_separate_channels() -> None:
    ok = _fixture("search.ok.json")
    for result in ok["data"]["results"]:
        assert 0.0 <= result["retrieval_score"] <= 1.0
    assert ok["data"]["claim_verification"] is None, "검증을 수행하지 않았으면 retrieval_score로 대체하지 않는다"


# ── 소비자 거절 규칙 (mutation이 실제로 빨개지는지) ──────────────────────────


def test_missing_required_field_is_rejected() -> None:
    broken = copy.deepcopy(_fixture("search.ok.json"))
    del broken["request_id"]
    assert not _is_valid("search.schema.json", broken), "request_id 없이도 통과하면 span 추적이 끊긴다"


def test_unknown_status_is_rejected() -> None:
    broken = copy.deepcopy(_fixture("search.ok.json"))
    broken["status"] = "done"
    assert not _is_valid("search.schema.json", broken)


def test_partial_without_source_failures_is_rejected() -> None:
    broken = copy.deepcopy(_fixture("search.partial.json"))
    broken["data"]["source_failures"] = []
    assert not _is_valid("search.schema.json", broken), "partial 인데 실패 목록이 비면 부분 성공 사실이 사라진다"


def test_policy_denied_must_not_be_retryable() -> None:
    broken = copy.deepcopy(_fixture("extract.blocked.policy-denied.json"))
    broken["error"]["retryable"] = True
    assert not _is_valid("extract.schema.json", broken), "정책 거절을 retryable로 두면 fallback 우회가 가능해진다"

    wrong_stage = copy.deepcopy(_fixture("extract.blocked.policy-denied.json"))
    wrong_stage["error"]["stage"] = "fetch"
    assert not _is_valid("extract.schema.json", wrong_stage)


def test_ok_and_partial_cannot_carry_an_error_object() -> None:
    broken = copy.deepcopy(_fixture("search.ok.json"))
    broken["error"] = _fixture("deep-research.error.upstream-unavailable.json")["error"]
    assert not _is_valid("search.schema.json", broken)


def test_error_state_requires_an_error_object() -> None:
    broken = copy.deepcopy(_fixture("deep-research.error.upstream-unavailable.json"))
    broken["error"] = None
    assert not _is_valid("deep-research.schema.json", broken)


def test_truncated_evidence_requires_truncation_details() -> None:
    broken = copy.deepcopy(_fixture("search.partial.json"))
    broken["evidence"][0]["truncated"] = True
    broken["evidence"][0]["truncation"] = None
    assert not _is_valid("search.schema.json", broken), "절단 사실만 남고 범위가 없으면 소비자가 원문 크기를 오해한다"


def test_json_ld_depth_requires_structured_data() -> None:
    broken = copy.deepcopy(_fixture("extract.ok.json"))
    broken["data"]["extract_depth"] = "json_ld"
    broken["data"]["structured_data"] = None
    assert not _is_valid("extract.schema.json", broken)


def test_extract_without_source_failures_key_is_rejected() -> None:
    broken = copy.deepcopy(_fixture("extract.ok.json"))
    del broken["data"]["source_failures"]
    assert not _is_valid("extract.schema.json", broken)


def test_deep_research_with_no_sources_cannot_aggregate_context() -> None:
    broken = copy.deepcopy(_fixture("deep-research.error.upstream-unavailable.json"))
    broken["data"]["aggregated_context"] = "출처 없는 요약"
    assert not _is_valid("deep-research.schema.json", broken)


def test_unsupported_capability_must_be_reported_at_negotiation() -> None:
    broken = copy.deepcopy(_fixture("blocked.unsupported-capability.json"))
    broken["error"]["stage"] = "fetch"
    assert not _is_valid("search.schema.json", broken)


# ── 버전 규칙 ────────────────────────────────────────────────────────────────


def _consumer_accepts(schema_version: str) -> bool:
    """host 소비자의 버전 수용 규칙 — 알 수 없는 major는 거절, minor는 수용한다."""
    major = int(str(schema_version).split(".", 1)[0])
    manifest = _load(CONTRACTS_DIR / "manifest.json")
    return major in manifest["compatibility"]["accepted_majors"]


def test_consumer_rejects_unknown_major_and_accepts_minor() -> None:
    assert _consumer_accepts("1.0")
    assert _consumer_accepts("1.1"), "minor 추가는 거절 대상이 아니다"
    assert not _consumer_accepts("2.0"), "알 수 없는 major는 거절해야 한다"


def test_schema_pattern_allows_minor_but_consumer_rule_is_what_rejects_major_two() -> None:
    future = copy.deepcopy(_fixture("search.ok.json"))
    future["schema_version"] = "2.0"
    assert _is_valid("search.schema.json", future), "스키마는 문자열 형태만 보고 major를 판정하지 않는다"
    assert not _consumer_accepts(future["schema_version"]), "그래서 소비자 규칙이 별도로 필요하다"


# ── legacy text fallback ─────────────────────────────────────────────────────


def test_legacy_wire_fixture_is_the_pre_contract_shape() -> None:
    wire = _fixture("legacy.text-fallback.wire.json")
    assert "schema_version" not in wire, "wire fixture 는 계약 이전 형태여야 한다"
    assert wire["content"][0]["type"] == "text"
    payload = json.loads(wire["content"][0]["text"])
    assert {"query", "hits", "aborted_backends", "signal_confidence"} <= set(payload)


def test_legacy_wire_payload_maps_to_the_partial_envelope_it_is_shipped_with() -> None:
    wire = _fixture("legacy.text-fallback.wire.json")
    payload = json.loads(wire["content"][0]["text"])
    expected = _fixture("legacy.text-fallback.expected.json")

    assert expected["status"] == ("ok" if not payload["aborted_backends"] else "partial")
    assert {failure["source"] for failure in expected["data"]["source_failures"]} == set(payload["aborted_backends"])
    assert [result["url"] for result in expected["data"]["results"]] == [hit["url"] for hit in payload["hits"]]
    assert [result["retrieval_score"] for result in expected["data"]["results"]] == [
        hit["score"] for hit in payload["hits"]
    ]
    assert expected["timings"]["total_ms"] == float(payload["took_ms"])


def test_legacy_expected_envelope_is_valid_by_this_contract() -> None:
    _validate("search.schema.json", _fixture("legacy.text-fallback.expected.json"))


# ── 비밀·PII ─────────────────────────────────────────────────────────────────


def test_contract_files_carry_no_secret_or_pii_shapes() -> None:
    for path in sorted(CONTRACTS_DIR.rglob("*.json")):
        text = path.read_text(encoding="utf-8")
        for pattern in SECRET_PATTERNS:
            assert not pattern.search(text), f"{path.name} 예시에 secret/PII 형태가 들어 있다: {pattern.pattern}"


# ── 사본 drift ───────────────────────────────────────────────────────────────


def test_mirror_copy_matches_these_bytes_when_the_W_checkout_exists() -> None:
    manifest = _load(CONTRACTS_DIR / "manifest.json")
    root = Path(os.environ.get(manifest["mirror"]["root_env"], manifest["mirror"]["default_root"]))
    mirror_dir = root / manifest["mirror"]["path"]

    if not mirror_dir.is_dir():
        # W checkout 이 없는 환경에서는 위 manifest 무결성 시험이 pinning 을 검증한다.
        assert manifest["files"], "사본이 없을 때는 manifest가 유일한 핀이다"
        return

    for name, expected in manifest["files"].items():
        mirror_file = mirror_dir / name
        assert mirror_file.is_file(), f"W 사본에 {name} 이 없다"
        actual = hashlib.sha256(mirror_file.read_bytes()).hexdigest()
        assert actual == expected, f"W 사본 {name} 이 S 계약 원본과 다르다 — drift"
