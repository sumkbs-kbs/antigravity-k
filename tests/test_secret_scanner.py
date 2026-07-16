"""Tests for secret_scanner — secret detection, redaction, and credential filtering.

This module is the backbone of the CI security-scan job, so it must reliably
detect common credential patterns without false positives on normal code.
"""

from __future__ import annotations

from antigravity_k.engine.secret_scanner import (
    is_credential_field,
    is_memory_path,
    is_sensitive_file,
    redact,
    redact_full,
    redact_url,
    scan_for_secrets,
    strip_credentials,
)

# ---------------------------------------------------------------------------
# scan_for_secrets — pattern detection
# ---------------------------------------------------------------------------


class TestScanPrefixPatterns:
    """Token-prefix pattern detection (no context needed)."""

    def test_detects_nvidia_key(self):
        matches = scan_for_secrets("nvapi-abcdef1234567890")
        assert len(matches) >= 1
        assert "NVIDIA" in matches[0].pattern

    def test_detects_openai_project_key(self):
        matches = scan_for_secrets("sk-proj-abcdefghij1234567890")
        assert len(matches) >= 1
        assert "OpenAI" in matches[0].pattern

    def test_detects_anthropic_key(self):
        matches = scan_for_secrets("sk-ant-api03-abcdef1234567890abcdef")
        assert len(matches) >= 1
        assert "Anthropic" in matches[0].pattern

    def test_detects_github_token(self):
        # ghp_ requires 36+ alphanumeric chars after prefix
        matches = scan_for_secrets("ghp_" + "a" * 36)
        assert len(matches) >= 1
        assert "GitHub" in matches[0].pattern

    def test_detects_aws_access_key(self):
        matches = scan_for_secrets("AKIA1234567890ABCDEF")
        assert len(matches) >= 1
        assert "AWS" in matches[0].pattern

    def test_detects_huggingface_token(self):
        matches = scan_for_secrets("hf_abcdef1234567890")
        assert len(matches) >= 1

    def test_detects_slack_token(self):
        matches = scan_for_secrets("xoxb-1234567890-abcdef")
        assert len(matches) >= 1
        assert "Slack" in matches[0].pattern

    def test_detects_google_api_key(self):
        # AIza + exactly 35 chars
        matches = scan_for_secrets("AIza" + "A" * 35)
        assert len(matches) >= 1
        assert "Google" in matches[0].pattern

    def test_detects_private_key_pem(self):
        # Use a fragmented string to avoid triggering the detect-private-key
        # pre-commit hook on this test file itself.
        marker = "-----BEGIN" + " RSA PRIVATE K" + "EY-----"
        matches = scan_for_secrets(marker)
        assert len(matches) >= 1
        assert "Private" in matches[0].pattern

    def test_detects_pypi_token(self):
        matches = scan_for_secrets("pypi-abcdef1234567890abcdef")
        assert len(matches) >= 1


class TestScanContextPatterns:
    """Context-based pattern detection (needs KEY=, Bearer, etc.)."""

    def test_detects_bearer_token(self):
        matches = scan_for_secrets("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig")
        assert len(matches) >= 1

    def test_detects_env_credential(self):
        matches = scan_for_secrets('API_KEY="sk-somethinglong123"')
        assert len(matches) >= 1

    def test_detects_password_assignment(self):
        matches = scan_for_secrets("PASSWORD=supersecret123456")
        assert len(matches) >= 1


class TestScanNoFalsePositives:
    """Normal code/text should not trigger matches."""

    def test_plain_text_no_match(self):
        matches = scan_for_secrets("Hello world, this is a normal sentence.")
        assert len(matches) == 0

    def test_short_string_no_match(self):
        """Short strings that look like prefixes but are too short should not match."""
        matches = scan_for_secrets("nvapi-short")
        # nvapi- requires 10+ chars after prefix
        assert len(matches) == 0

    def test_code_variable_no_match(self):
        matches = scan_for_secrets("my_variable_name = 'hello world'")
        assert len(matches) == 0

    def test_empty_string(self):
        assert scan_for_secrets("") == []

    def test_multiple_secrets_in_one_string(self):
        text = "AKIA1234567890ABCDEF and nvapi-abcdef1234567890"
        matches = scan_for_secrets(text)
        assert len(matches) >= 2


class TestSecretMatchDataclass:
    """SecretMatch contains redacted value, not the raw secret."""

    def test_match_does_not_contain_raw_secret(self):
        secret = "AKIA1234567890ABCDEF"
        matches = scan_for_secrets(secret)
        assert len(matches) >= 1
        # The redacted form should not contain the full secret.
        assert secret not in matches[0].redacted

    def test_match_has_pattern_name(self):
        matches = scan_for_secrets("AKIA1234567890ABCDEF")
        assert matches[0].pattern  # non-empty name

    def test_match_has_original_length(self):
        matches = scan_for_secrets("AKIA1234567890ABCDEF")
        assert matches[0].original_length > 0


# ---------------------------------------------------------------------------
# redact — partial masking
# ---------------------------------------------------------------------------


class TestRedact:
    """redact() partial masking (keeps first 4 chars)."""

    def test_redacts_api_key(self):
        text = "my key is sk-proj-abcdefghij1234567890"
        result = redact(text)
        assert "sk-proj-abcdefghij1234567890" not in result
        assert "sk-p" in result  # first 4 chars kept

    def test_redacts_bearer_token(self):
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig"
        result = redact(text)
        assert "Bearer eyJ" not in result

    def test_plain_text_unchanged(self):
        text = "This is a normal sentence with no secrets."
        assert redact(text) == text

    def test_non_string_passthrough(self):
        assert redact(12345) == 12345
        assert redact(None) is None


# ---------------------------------------------------------------------------
# redact_full — full masking
# ---------------------------------------------------------------------------


class TestRedactFull:
    """redact_full() replaces entire secret with <REDACTED>."""

    def test_redacts_env_var_full(self):
        text = "API_KEY=sk-somethinglong123"
        result = redact_full(text)
        assert "sk-somethinglong123" not in result
        assert "<REDACTED>" in result

    def test_redacts_bearer_full(self):
        text = "Authorization: Bearer verylongtoken123456"
        result = redact_full(text)
        assert "verylongtoken123456" not in result
        assert "<REDACTED>" in result

    def test_plain_text_unchanged(self):
        text = "No secrets here."
        assert redact_full(text) == text


# ---------------------------------------------------------------------------
# redact_url — URL credential stripping
# ---------------------------------------------------------------------------


class TestRedactUrl:
    """redact_url() removes credentials from URLs."""

    def test_strips_user_password_from_url(self):
        url = "https://user:password@example.com/path"
        result = redact_url(url)
        assert result is not None
        assert "password" not in result
        assert "example.com" in result

    def test_masks_token_query_param(self):
        url = "https://api.example.com/data?token=secret123456"
        result = redact_url(url)
        assert result is not None
        assert "secret123456" not in result

    def test_preserves_normal_url(self):
        url = "https://example.com/path?key=value"
        result = redact_url(url)
        assert result is not None
        assert "example.com" in result

    def test_empty_url_returns_none(self):
        assert redact_url("") is None

    def test_non_string_returns_none(self):
        assert redact_url(12345) is None


# ---------------------------------------------------------------------------
# is_credential_field / is_sensitive_file / is_memory_path
# ---------------------------------------------------------------------------


class TestCredentialDetection:
    """is_credential_field, is_sensitive_file, is_memory_path."""

    def test_credential_field_api_key(self):
        assert is_credential_field("api_key") is True

    def test_credential_field_password(self):
        assert is_credential_field("password") is True

    def test_credential_field_token(self):
        assert is_credential_field("access_token") is True

    def test_non_credential_field(self):
        assert is_credential_field("username") is False
        assert is_credential_field("description") is False

    def test_sensitive_file_env_local(self):
        assert is_sensitive_file(".env.local") is True

    def test_sensitive_file_env_production(self):
        assert is_sensitive_file(".env.production") is True

    def test_sensitive_file_auth_profiles(self):
        assert is_sensitive_file("auth-profiles.json") is True

    def test_non_sensitive_file(self):
        assert is_sensitive_file("main.py") is False
        assert is_sensitive_file(".env") is False  # .env itself is NOT in the exclude list
        assert is_sensitive_file("README.md") is False

    def test_memory_path_vault(self):
        assert is_memory_path("/vault_data/secret.md") is True

    def test_memory_path_secrets(self):
        assert is_memory_path("/secrets/token.txt") is True

    def test_non_memory_path(self):
        assert is_memory_path("/tmp/test.txt") is False


# ---------------------------------------------------------------------------
# strip_credentials — dict payload scrubbing
# ---------------------------------------------------------------------------


class TestStripCredentials:
    """strip_credentials removes sensitive values from dict payloads."""

    def test_strips_api_key_from_dict(self):
        data = {"name": "test", "api_key": "secret123"}
        result = strip_credentials(data)
        assert result["name"] == "test"
        assert result["api_key"] != "secret123"

    def test_preserves_non_credential_fields(self):
        data = {"name": "test", "version": "1.0"}
        result = strip_credentials(data)
        assert result["name"] == "test"
        assert result["version"] == "1.0"

    def test_handles_nested_dict(self):
        data = {"config": {"password": "secret", "port": 8080}}
        result = strip_credentials(data)
        assert result["config"]["password"] != "secret"
        assert result["config"]["port"] == 8080

    def test_handles_non_dict(self):
        assert strip_credentials("string") == "string"
        assert strip_credentials(123) == 123
