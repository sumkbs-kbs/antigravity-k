"""Tests for error_classifier — LLM API error classification and recovery hints.

Covers ClassifiedError properties, FailoverReason enum, and the main
classify_api_error() pipeline for common HTTP status codes and patterns.
"""

from __future__ import annotations

from antigravity_k.engine.error_classifier import (
    ClassifiedError,
    FailoverReason,
    classify_api_error,
)

# ---------------------------------------------------------------------------
# ClassifiedError properties
# ---------------------------------------------------------------------------


class TestClassifiedError:
    """ClassifiedError computed properties and serialization."""

    def test_is_auth_for_auth_reason(self):
        err = ClassifiedError(reason=FailoverReason.auth)
        assert err.is_auth is True

    def test_is_auth_for_auth_permanent(self):
        err = ClassifiedError(reason=FailoverReason.auth_permanent)
        assert err.is_auth is True

    def test_is_auth_false_for_other(self):
        err = ClassifiedError(reason=FailoverReason.timeout)
        assert err.is_auth is False

    def test_is_context_related_for_overflow(self):
        err = ClassifiedError(reason=FailoverReason.context_overflow)
        assert err.is_context_related is True

    def test_is_context_related_for_payload(self):
        err = ClassifiedError(reason=FailoverReason.payload_too_large)
        assert err.is_context_related is True

    def test_is_context_related_false_for_other(self):
        err = ClassifiedError(reason=FailoverReason.server_error)
        assert err.is_context_related is False

    def test_to_dict_contains_reason(self):
        err = ClassifiedError(reason=FailoverReason.timeout, status_code=408)
        d = err.to_dict()
        assert d["reason"] == "timeout"
        assert d["status_code"] == 408

    def test_defaults_are_retryable(self):
        """By default, an error is retryable."""
        err = ClassifiedError(reason=FailoverReason.unknown)
        assert err.retryable is True

    def test_to_dict_round_trips_retryable(self):
        err = ClassifiedError(reason=FailoverReason.billing, retryable=False)
        assert err.to_dict()["retryable"] is False


# ---------------------------------------------------------------------------
# classify_api_error — status code classification
# ---------------------------------------------------------------------------


class TestClassifyByStatus:
    """classify_api_error routes by HTTP status code."""

    def test_429_classified_as_rate_limit(self):
        """HTTP 429 → rate_limit."""
        err = Exception("Too many requests")
        err.status_code = 429  # type: ignore[attr-defined]
        result = classify_api_error(err, provider="ollama", model="test")
        assert result.reason == FailoverReason.rate_limit
        assert result.retryable is True

    def test_401_classified_as_auth(self):
        """HTTP 401 → auth."""
        err = Exception("Unauthorized")
        err.status_code = 401  # type: ignore[attr-defined]
        result = classify_api_error(err)
        assert result.reason == FailoverReason.auth
        assert result.is_auth is True

    def test_403_classified_as_auth(self):
        """HTTP 403 → auth."""
        err = Exception("Forbidden")
        err.status_code = 403  # type: ignore[attr-defined]
        result = classify_api_error(err)
        assert result.reason == FailoverReason.auth

    def test_404_classified_as_model_not_found(self):
        """HTTP 404 → model_not_found."""
        err = Exception("Model not found")
        err.status_code = 404  # type: ignore[attr-defined]
        result = classify_api_error(err)
        assert result.reason == FailoverReason.model_not_found

    def test_500_classified_as_server_error(self):
        """HTTP 500 → server_error."""
        err = Exception("Internal server error")
        err.status_code = 500  # type: ignore[attr-defined]
        result = classify_api_error(err)
        assert result.reason == FailoverReason.server_error
        assert result.retryable is True

    def test_503_classified_as_overloaded(self):
        """HTTP 503 → overloaded."""
        err = Exception("Service unavailable")
        err.status_code = 503  # type: ignore[attr-defined]
        result = classify_api_error(err)
        assert result.reason == FailoverReason.overloaded

    def test_413_classified_as_payload_too_large(self):
        """HTTP 413 → payload_too_large (context related)."""
        err = Exception("Request entity too large")
        err.status_code = 413  # type: ignore[attr-defined]
        result = classify_api_error(err)
        assert result.reason == FailoverReason.payload_too_large
        assert result.is_context_related is True


# ---------------------------------------------------------------------------
# classify_api_error — pattern matching (no status code)
# ---------------------------------------------------------------------------


class TestClassifyByPattern:
    """classify_api_error falls back to message pattern matching."""

    def test_billing_pattern_detected(self):
        """Message containing 'insufficient credits' → billing."""
        err = Exception("insufficient credits remaining")
        result = classify_api_error(err)
        assert result.reason == FailoverReason.billing

    def test_quota_pattern_detected(self):
        """Message containing 'insufficient_quota' → billing."""
        err = Exception("insufficient_quota exceeded")
        result = classify_api_error(err)
        assert result.reason == FailoverReason.billing

    def test_context_overflow_pattern(self):
        """Message mentioning context length → context_overflow."""
        err = Exception("maximum context length exceeded")
        result = classify_api_error(err)
        assert result.reason == FailoverReason.context_overflow
        assert result.should_compress is True

    def test_thinking_signature_pattern(self):
        """Status 400 + thinking + signature → thinking_signature."""
        err = Exception("invalid thinking block signature")
        err.status_code = 400  # type: ignore[attr-defined]
        result = classify_api_error(err)
        assert result.reason == FailoverReason.thinking_signature


# ---------------------------------------------------------------------------
# classify_api_error — fallback
# ---------------------------------------------------------------------------


class TestClassifyFallback:
    """Unknown errors fall through to 'unknown'."""

    def test_unknown_error(self):
        """An unclassifiable error → unknown."""
        err = Exception("something totally weird happened")
        result = classify_api_error(err)
        assert result.reason == FailoverReason.unknown

    def test_result_preserves_provider_and_model(self):
        """The classified result preserves provider and model metadata."""
        err = Exception("error")
        result = classify_api_error(err, provider="anthropic", model="claude-3")
        assert result.provider == "anthropic"
        assert result.model == "claude-3"

    def test_result_preserves_message(self):
        """The classified result preserves the error message (truncated)."""
        err = Exception("detailed error message")
        result = classify_api_error(err)
        assert "detailed error message" in result.message


# ---------------------------------------------------------------------------
# classify_api_error — status code 4xx/5xx fallback ranges
# ---------------------------------------------------------------------------


class TestClassifyByStatusFallback:
    """Edge-case status codes that fall to fallback branches."""

    def test_402_with_transient_signal_is_rate_limit(self):
        err = Exception("402 try again later")
        err.status_code = 402  # type: ignore[attr-defined]
        result = classify_api_error(err)
        assert result.reason == FailoverReason.rate_limit
        assert result.retryable is True

    def test_402_without_transient_is_billing(self):
        err = Exception("402 payment required")
        err.status_code = 402  # type: ignore[attr-defined]
        result = classify_api_error(err)
        assert result.reason == FailoverReason.billing
        assert result.retryable is False

    def test_403_key_limit_exceeded_is_billing(self):
        err = Exception("key limit exceeded for your plan")
        err.status_code = 403  # type: ignore[attr-defined]
        result = classify_api_error(err)
        assert result.reason == FailoverReason.billing

    def test_404_without_model_pattern_is_unknown(self):
        err = Exception("Not Found")
        err.status_code = 404  # type: ignore[attr-defined]
        result = classify_api_error(err)
        assert result.reason == FailoverReason.unknown
        assert result.retryable is True

    def test_400_unknown_is_format_error(self):
        err = Exception("Bad Request")
        err.status_code = 400  # type: ignore[attr-defined]
        result = classify_api_error(err)
        assert result.reason == FailoverReason.format_error

    def test_400_with_large_context_is_context_overflow(self):
        err = Exception("Bad Request")
        err.status_code = 400  # type: ignore[attr-defined]
        result = classify_api_error(err, approx_tokens=100_000, context_length=200_000)
        assert result.reason == FailoverReason.context_overflow

    def test_4xx_range_is_format_error(self):
        err = Exception("Method Not Allowed")
        err.status_code = 405  # type: ignore[attr-defined]
        result = classify_api_error(err)
        assert result.reason == FailoverReason.format_error
        assert result.retryable is False

    def test_5xx_range_is_server_error(self):
        err = Exception("Web server error")
        err.status_code = 521  # type: ignore[attr-defined]
        result = classify_api_error(err)
        assert result.reason == FailoverReason.server_error
        assert result.retryable is True

    def test_chinese_context_overflow_detected(self):
        err = Exception("超过最大长度")
        result = classify_api_error(err)
        assert result.reason == FailoverReason.context_overflow

    def test_chinese_context_window_detected(self):
        err = Exception("上下文长度限制")
        result = classify_api_error(err)
        assert result.reason == FailoverReason.context_overflow


# ---------------------------------------------------------------------------
# classify_api_error — transport / disconnect patterns
# ---------------------------------------------------------------------------


class TestClassifyTransport:
    """Transport and disconnect error patterns."""

    def test_timeout_error_type(self):
        err = TimeoutError("timed out")
        result = classify_api_error(err)
        assert result.reason == FailoverReason.timeout

    def test_connection_error_type(self):
        err = ConnectionError("connection refused")
        result = classify_api_error(err)
        assert result.reason == FailoverReason.timeout

    def test_os_error_type(self):
        err = OSError("socket error")
        result = classify_api_error(err)
        assert result.reason == FailoverReason.timeout

    def test_server_disconnect_small_session_is_timeout(self):
        err = Exception("server disconnected")
        result = classify_api_error(err, approx_tokens=1000, context_length=200_000)
        assert result.reason == FailoverReason.timeout

    def test_server_disconnect_large_session_is_context_overflow(self):
        err = Exception("peer closed connection")
        result = classify_api_error(err, approx_tokens=150_000, context_length=200_000)
        assert result.reason == FailoverReason.context_overflow

    def test_connection_reset_by_peer(self):
        err = Exception("connection reset by peer")
        result = classify_api_error(err)
        assert result.reason == FailoverReason.timeout

    def test_network_connection_lost(self):
        err = Exception("network connection lost")
        result = classify_api_error(err, approx_tokens=1000)
        assert result.reason == FailoverReason.timeout


# ---------------------------------------------------------------------------
# _extract_status_code / _extract_error_body coverage
# ---------------------------------------------------------------------------


class TestExtractUtils:
    """Internal extraction utilities — status code and error body."""

    def test_extract_status_code_from_status_attr(self):
        err = Exception("error")
        err.status = 418  # type: ignore[attr-defined]
        result = classify_api_error(err)
        assert result.reason == FailoverReason.format_error

    def test_extract_status_code_from_code_attr(self):
        err = Exception("error")
        err.code = 429  # type: ignore[attr-defined]
        result = classify_api_error(err)
        assert result.reason == FailoverReason.rate_limit

    def test_extract_status_code_from_response_obj(self):
        class MockResponse:
            status_code = 503

        err = Exception("error")
        err.response = MockResponse()  # type: ignore[attr-defined]
        result = classify_api_error(err)
        assert result.reason == FailoverReason.overloaded

    def test_status_code_none_fallback(self):
        err = Exception("generic error no pattern match")
        result = classify_api_error(err)
        assert result.reason == FailoverReason.unknown

    def test_model_not_found_via_400(self):
        err = Exception("model not found")
        err.status_code = 400  # type: ignore[attr-defined]
        result = classify_api_error(err)
        assert result.reason == FailoverReason.model_not_found

    def test_rate_limit_via_400(self):
        err = Exception("rate limit exceeded via 400")
        err.status_code = 400  # type: ignore[attr-defined]
        result = classify_api_error(err)
        assert result.reason == FailoverReason.rate_limit

    def test_auth_via_message_pattern(self):
        err = Exception("invalid api key provided")
        result = classify_api_error(err)
        assert result.reason == FailoverReason.auth

    def test_extract_error_body_with_response_json(self):
        class MockResponse:
            status_code = 400

            def json(self):
                return {"error": {"message": "context length exceeded"}}

        err = Exception("error")
        err.response = MockResponse()  # type: ignore[attr-defined]
        result = classify_api_error(err)
        assert result.reason == FailoverReason.context_overflow

    def test_extract_error_body_with_text_fallback(self):
        class MockResponse:
            status_code = 401
            text = '{"error": "unauthorized"}'

            def json(self):
                raise Exception("no json")

        err = Exception("error")
        err.response = MockResponse()  # type: ignore[attr-defined]
        result = classify_api_error(err)
        assert result.reason == FailoverReason.auth

    def test_spending_limit_403_is_billing(self):
        err = Exception("spending limit reached for this month")
        err.status_code = 403  # type: ignore[attr-defined]
        result = classify_api_error(err)
        assert result.reason == FailoverReason.billing

    def test_400_with_many_messages_is_context_overflow(self):
        err = Exception("Bad Request")
        err.status_code = 400  # type: ignore[attr-defined]
        result = classify_api_error(err, num_messages=100)
        assert result.reason == FailoverReason.context_overflow
