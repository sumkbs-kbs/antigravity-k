"""Master Microservice Gateway Router — Coordinates Rate Limiting, Caching, and Auth."""

import logging
from dataclasses import dataclass
from typing import Any

from demo_service.auth_engine import SimpleJWTAuthEngine
from demo_service.distributed_cache import AsyncTTLCache
from demo_service.token_bucket import AsyncTokenBucketLimiter

logger = logging.getLogger(__name__)


@dataclass
class GatewayResponse:
    """Standardized gateway response payload."""

    status_code: int
    data: dict[str, Any]
    from_cache: bool = False
    rate_limited: bool = False


class MicroserviceGateway:
    """Coordinates incoming requests with Rate Limiting, Cache, and Auth."""

    def __init__(
        self,
        limiter: AsyncTokenBucketLimiter | None = None,
        cache: AsyncTTLCache | None = None,
        auth: SimpleJWTAuthEngine | None = None,
    ):
        self.limiter = limiter or AsyncTokenBucketLimiter(capacity=5.0, refill_rate_per_sec=2.0)
        self.cache = cache or AsyncTTLCache(default_ttl_seconds=30.0)
        self.auth = auth or SimpleJWTAuthEngine()

    async def handle_request(
        self,
        path: str,
        auth_token: str | None = None,
        cache_key: str | None = None,
    ) -> GatewayResponse:
        """Handle request through full pipeline."""
        # 1. Rate Limiting Check
        rate_res = await self.limiter.acquire(1.0)
        if not rate_res.allowed:
            return GatewayResponse(
                status_code=429,
                data={"error": "Rate limit exceeded", "retry_after": rate_res.retry_after_seconds},
                rate_limited=True,
            )

        # 2. Authentication Check
        if auth_token is not None:
            claims = self.auth.verify_token(auth_token)
            if claims is None:
                return GatewayResponse(
                    status_code=401,
                    data={"error": "Unauthorized: Invalid or expired token"},
                )

        # 3. Cache Lookup
        if cache_key:
            cached_data = await self.cache.get(cache_key)
            if cached_data is not None:
                return GatewayResponse(
                    status_code=200,
                    data=cached_data,
                    from_cache=True,
                )

        # 4. Dispatch Response & Populate Cache
        response_data = {"message": f"Processed path: {path}", "status": "ok"}
        if cache_key:
            await self.cache.set(cache_key, response_data)

        return GatewayResponse(
            status_code=200,
            data=response_data,
            from_cache=False,
        )
