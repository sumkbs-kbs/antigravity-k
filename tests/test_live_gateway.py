"""Comprehensive Async TDD Tests for Demo Microservice Suite."""

import asyncio

import pytest

from demo_service.auth_engine import SimpleJWTAuthEngine
from demo_service.distributed_cache import AsyncTTLCache
from demo_service.gateway_router import MicroserviceGateway
from demo_service.token_bucket import AsyncTokenBucketLimiter


@pytest.mark.asyncio
async def test_token_bucket_limiting():
    limiter = AsyncTokenBucketLimiter(capacity=2.0, refill_rate_per_sec=1.0)

    # 1st acquire allowed
    res1 = await limiter.acquire(1.0)
    assert res1.allowed is True

    # 2nd acquire allowed
    res2 = await limiter.acquire(1.0)
    assert res2.allowed is True

    # 3rd acquire throttled
    res3 = await limiter.acquire(1.0)
    assert res3.allowed is False
    assert res3.retry_after_seconds > 0.0


@pytest.mark.asyncio
async def test_async_ttl_cache_eviction():
    cache = AsyncTTLCache(default_ttl_seconds=0.1)
    await cache.set("k1", {"data": "test"})

    # Immediate get
    val1 = await cache.get("k1")
    assert val1 == {"data": "test"}

    # Wait for TTL expiration
    await asyncio.sleep(0.15)
    val2 = await cache.get("k1")
    assert val2 is None


def test_jwt_auth_engine_issuance_and_expiry():
    auth = SimpleJWTAuthEngine(secret_key="unit-test-secret")
    token = auth.issue_token(user_id="user_42", roles=["admin"], ttl_seconds=3600)

    claims = auth.verify_token(token)
    assert claims is not None
    assert claims.user_id == "user_42"
    assert "admin" in claims.roles

    # Tampered token
    tampered = token[:-4] + "xxxx"
    assert auth.verify_token(tampered) is None


@pytest.mark.asyncio
async def test_microservice_gateway_end_to_end():
    gateway = MicroserviceGateway()
    token = gateway.auth.issue_token(user_id="user_1", roles=["user"])

    # 1. Normal authenticated request with cache
    resp1 = await gateway.handle_request("/api/data", auth_token=token, cache_key="cache_1")
    assert resp1.status_code == 200
    assert resp1.from_cache is False

    # 2. Subsequent request served from cache
    resp2 = await gateway.handle_request("/api/data", auth_token=token, cache_key="cache_1")
    assert resp2.status_code == 200
    assert resp2.from_cache is True

    # 3. Invalid token returns 401
    resp3 = await gateway.handle_request("/api/data", auth_token="invalid.jwt.token")
    assert resp3.status_code == 401
