"""테스트: SecretScanner 보조 계약 — 마스킹/재귀/경로 판정.
================================================
기존 스캔 테스트를 보완해 URL 자격증명 마스킹, 재귀 마스킹,
민감 파일/메모리 경로 판정의 엣지를 잠근다.
"""

import re
from typing import cast

from antigravity_k.engine.secret_scanner import (
    CREDENTIAL_PLACEHOLDER,
    _redact_match_partial,
    _redact_url_partial,
    is_credential_field,
    is_memory_path,
    is_sensitive_file,
    redact,
    redact_full,
    redact_url,
    scan_for_secrets,
    strip_credentials,
)


class TestScanEdgeCases:
    def test_non_string_or_empty_content_yields_no_matches(self):
        assert scan_for_secrets("") == []
        assert scan_for_secrets(cast(str, cast(object, None))) == []

    def test_duplicate_secret_values_are_deduplicated(self):
        text = "api_key=sk-abcdefghijklmnop1234 api_key=sk-abcdefghijklmnop1234"

        matches = scan_for_secrets(text)

        names = [m.pattern for m in matches]
        assert len(names) == len(set(names))


class TestRedaction:
    def test_redact_keeps_first_four_chars(self):
        masked = redact("token sk-proj-abcdef1234567890 end")

        assert "sk-p" in masked
        assert "abcdef1234567890" not in masked

    def test_redact_full_replaces_env_assignment_and_bearer(self):
        text = "NVIDIA_API_KEY=nvabc123 Bearer eyJhbGciOiJIUzI1NiJ9.x.y done"

        result = redact_full(text)

        assert "nvabc123" not in result
        assert "eyJhbGciOiJIUzI1NiJ9" not in result
        assert "<REDACTED>" in result

    def test_redact_full_passthrough_non_string(self):
        assert redact_full(cast(str, cast(object, 123))) == 123

    def test_short_matched_value_fully_masked(self):
        assert _redact_match_partial(match_like("ab")) == "****"

    def test_url_partial_masks_userinfo_but_keeps_host_and_port(self):
        masked = _redact_url_partial(match_like("https://user:secret@db.host:5432/path"))

        assert "secret" not in masked
        assert "db.host:5432" in masked

    def test_url_without_credentials_returned_as_is(self):
        url = "https://example.com/path"

        assert _redact_url_partial(match_like(url)) == url


def match_like(value: str):
    """re.Match 흉내: group(0)가 value를 반환하는 최소 객체."""

    class _Match:
        def group(self, index: int = 0) -> str:
            if index == 0:
                return value
            raise IndexError(index)

    return cast(re.Match[str], cast(object, _Match()))


class TestRedactUrl:
    def test_strips_basic_auth_and_masks_signed_query(self):
        cleaned = redact_url("https://user:pass@api.example.com/v1/x?api_key=SECRET&ok=1#frag")

        assert cleaned is not None
        assert "user:pass@" not in cleaned
        assert "SECRET" not in cleaned
        assert "api_key=" in cleaned
        assert "ok=1" in cleaned
        assert "#frag" not in cleaned  # fragment 제거

    def test_port_preserved_after_auth_strip(self):
        cleaned = redact_url("https://u:p@example.com:8443/x")

        assert cleaned == "https://example.com:8443/x"

    def test_empty_or_non_string_returns_none(self):
        assert redact_url("") is None
        assert redact_url(cast(str, cast(object, None))) is None


class TestCredentialClassification:
    def test_known_field_and_pattern_field_are_sensitive(self):
        assert is_credential_field("password") is True
        assert is_credential_field("accessToken") is True
        assert is_credential_field("nickname") is False

    def test_strip_credentials_masks_nested_sensitive_fields(self):
        payload = {
            "user": {
                "access_token": "tok",
                "name": "kim",
                "tags": ["a"],
                "clientSecret": "s3cret",
            },
            "count": 3,
        }

        cleaned = strip_credentials(payload)

        assert cleaned["user"]["access_token"] == CREDENTIAL_PLACEHOLDER
        assert cleaned["user"]["clientSecret"] == CREDENTIAL_PLACEHOLDER
        assert cleaned["user"]["name"] == "kim"
        assert cleaned["user"]["tags"] == ["a"]
        assert cleaned["count"] == 3

    def test_scalar_passthrough(self):
        assert strip_credentials((1, 2)) == (1, 2)


class TestPathClassification:
    def test_sensitive_basenames_excluded(self):
        assert is_sensitive_file(".env.local") is True
        assert is_sensitive_file("notes.md") is False

    def test_memory_paths_protected(self):
        assert is_memory_path("/repo/vault_data/memory.json") is True
        assert is_memory_path("/repo/.env") is True
        assert is_memory_path("/repo/src/main.py") is False
