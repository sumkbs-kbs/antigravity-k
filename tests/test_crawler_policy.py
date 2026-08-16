import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from antigravity_k.tools.crawler_policy import LegalTermsPolicy, RobotsRateLimitPolicy


def test_legal_policy_audit_allows_missing_record_and_enforce_denies_it():
    audit = LegalTermsPolicy(mode="audit")
    enforce = LegalTermsPolicy(mode="enforce")

    assert audit.evaluate("https://example.com/page").allowed is True
    assert audit.evaluate("https://example.com/page").reason == "missing_policy_audit"
    assert enforce.evaluate("https://example.com/page").allowed is False
    assert enforce.evaluate("https://example.com/page").reason == "missing_policy"


def test_legal_policy_requires_current_attestation_and_allowed_purpose():
    now = datetime(2026, 8, 9, tzinfo=UTC)
    policy = LegalTermsPolicy(mode="enforce", now=lambda: now)
    policy.register(
        domain="example.com",
        terms_url="https://example.com/terms",
        allowed_purposes=("research",),
        attested_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=1),
    )

    allowed = policy.evaluate("https://example.com/page", purpose="research")
    denied = policy.evaluate("https://example.com/page", purpose="training")

    assert allowed.allowed is True
    assert allowed.reason == "policy_attested"
    assert denied.allowed is False
    assert denied.reason == "purpose_not_allowed"


def test_legal_policy_denies_expired_attestation():
    now = datetime(2026, 8, 9, tzinfo=UTC)
    policy = LegalTermsPolicy(mode="enforce", now=lambda: now)
    policy.register(
        domain="example.com",
        terms_url="https://example.com/terms",
        allowed_purposes=("research",),
        attested_at=now - timedelta(days=2),
        expires_at=now - timedelta(days=1),
    )

    decision = policy.evaluate("https://example.com/page")

    assert decision.allowed is False
    assert decision.reason == "policy_expired"


def test_legal_policy_loads_enforce_records_from_environment_file(tmp_path, monkeypatch):
    now = datetime(2026, 8, 9, tzinfo=UTC)
    policy_path = tmp_path / "legal-policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "domain": "example.com",
                        "terms_url": "https://example.com/terms",
                        "allowed_purposes": ["research"],
                        "attested_at": "2026-08-08T00:00:00+00:00",
                        "expires_at": "2026-08-10T00:00:00+00:00",
                    },
                ],
            },
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AGK_CRAWLER_LEGAL_POLICY_MODE", "enforce")
    monkeypatch.setenv("AGK_CRAWLER_LEGAL_POLICY_FILE", str(policy_path))

    decision = LegalTermsPolicy.from_env(now=lambda: now).evaluate("https://example.com/page")

    assert decision.allowed is True
    assert decision.reason == "policy_attested"


@pytest.mark.asyncio
async def test_robots_policy_allows_and_throttles_allowed_path():
    policy = RobotsRateLimitPolicy(min_interval=0)
    client = MagicMock()
    client.get = AsyncMock(
        return_value=MagicMock(
            status_code=200,
            text="User-agent: *\nAllow: /public\nCrawl-delay: 0",
        ),
    )

    assert await policy.authorize("https://example.com/public", client) is True
    assert await policy.authorize("https://example.com/public/next", client) is True
    assert client.get.await_count == 1


@pytest.mark.asyncio
async def test_robots_policy_blocks_disallowed_path():
    policy = RobotsRateLimitPolicy(min_interval=0)
    client = MagicMock()
    client.get = AsyncMock(
        return_value=MagicMock(status_code=200, text="User-agent: *\nDisallow: /private"),
    )

    assert await policy.authorize("https://example.com/private", client) is False
    assert client.get.await_count == 1


@pytest.mark.asyncio
async def test_robots_policy_blocks_unavailable_robots_endpoint():
    policy = RobotsRateLimitPolicy(min_interval=0)
    client = MagicMock()
    client.get = AsyncMock(return_value=MagicMock(status_code=503, text=""))

    assert await policy.authorize("https://example.com/public", client) is False
