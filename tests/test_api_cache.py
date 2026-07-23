"""Tests for antigravity_k.engine.api_cache — in-memory API response cache."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from antigravity_k.engine.api_cache import (
    CACHE_DEFAULT_TTL,
    ApiCache,
    ApiCacheEntry,
    cached,
)

# ═══════════════════════════════════════════════════════════════════
# ApiCacheEntry tests
# ═══════════════════════════════════════════════════════════════════


class TestApiCacheEntry:
    """ApiCacheEntry — dataclass with TTL expiry logic."""

    def test_not_expired_fresh(self):
        """생성 직후는 만료되지 않음."""
        entry = ApiCacheEntry(key="k", value="v", ttl=60)
        assert not entry.is_expired

    def test_expired_after_ttl(self):
        """TTL 경과 후 만료."""
        import time

        entry = ApiCacheEntry(key="k", value="v", ttl=0.001, created_at=time.time() - 1)
        assert entry.is_expired

    def test_remaining_ttl_positive(self):
        """남은 TTL이 양수인 경우."""
        entry = ApiCacheEntry(key="k", value="v", ttl=60)
        assert 0 < entry.remaining_ttl <= 60

    def test_remaining_ttl_expired(self):
        """만료된 항목의 남은 TTL은 0."""
        import time

        entry = ApiCacheEntry(key="k", value="v", ttl=1, created_at=time.time() - 10)
        assert entry.remaining_ttl == 0.0

    def test_hit_count_increments(self):
        """hit_count 기본값 0."""
        entry = ApiCacheEntry(key="k", value="v", ttl=60)
        assert entry.hit_count == 0


# ═══════════════════════════════════════════════════════════════════
# ApiCache tests
# ═══════════════════════════════════════════════════════════════════


class TestApiCache:
    """ApiCache — in-memory cache with TTL, tags, stats."""

    @pytest.fixture
    def cache(self):
        """Fresh ApiCache for each test."""
        return ApiCache(default_ttl=60)

    @pytest.mark.asyncio
    async def test_get_missing_key(self, cache):
        """없는 키는 None 반환."""
        val = await cache.get("nonexistent")
        assert val is None

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache):
        """저장 후 조회."""
        await cache.set("name", "Antigravity-K")
        val = await cache.get("name")
        assert val == "Antigravity-K"

    @pytest.mark.asyncio
    async def test_get_expired(self, cache):
        """만료된 항목은 None 반환."""
        import time

        await cache.set("expired", "data", ttl=0.001)
        # Force expiry by accessing internal entry
        entry = cache._entries.get("expired")
        assert entry is not None
        entry.created_at = time.time() - 10
        val = await cache.get("expired")
        assert val is None

    @pytest.mark.asyncio
    async def test_delete_existing(self, cache):
        """존재하는 키 삭제."""
        await cache.set("to_delete", "value")
        result = await cache.delete("to_delete")
        assert result is True
        assert await cache.get("to_delete") is None

    @pytest.mark.asyncio
    async def test_delete_missing(self, cache):
        """없는 키 삭제는 False 반환."""
        result = await cache.delete("missing")
        assert result is False

    @pytest.mark.asyncio
    async def test_tag_invalidation(self, cache):
        """특정 태그의 모든 항목 무효화."""
        await cache.set("a", 1, tags=["group1"])
        await cache.set("b", 2, tags=["group1"])
        await cache.set("c", 3, tags=["group2"])

        removed = await cache.invalidate_tag("group1")
        assert removed == 2
        assert await cache.get("a") is None
        assert await cache.get("b") is None
        assert await cache.get("c") == 3  # 다른 태그는 영향 없음

    @pytest.mark.asyncio
    async def test_tag_invalidation_unknown_tag(self, cache):
        """없는 태그 무효화는 0 반환."""
        removed = await cache.invalidate_tag("unknown")
        assert removed == 0

    @pytest.mark.asyncio
    async def test_prefix_invalidation(self, cache):
        """특정 prefix의 모든 항목 무효화."""
        await cache.set("git:status", "s1")
        await cache.set("git:branches", "b1")
        await cache.set("fs:list", "l1")

        removed = await cache.invalidate_prefix("git:")
        assert removed == 2
        assert await cache.get("git:status") is None
        assert await cache.get("fs:list") == "l1"

    @pytest.mark.asyncio
    async def test_clear(self, cache):
        """전체 캐시 삭제."""
        await cache.set("a", 1)
        await cache.set("b", 2)
        cleared = await cache.clear()
        assert cleared == 2
        stats = await cache.get_stats()
        assert stats["total_entries"] == 0

    @pytest.mark.asyncio
    async def test_get_stats(self, cache):
        """통계 정보 반환."""
        await cache.set("x", 100, tags=["demo"])
        await cache.get("x")  # hit
        await cache.get("missing")  # miss

        stats = await cache.get_stats()
        assert stats["total_entries"] >= 1
        assert stats["total_tags"] >= 1
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1
        assert stats["hit_ratio"] > 0
        assert "memory_estimate_kb" in stats
        assert len(stats["entries"]) >= 1
        assert stats["entries"][0]["key"] == "x"

    @pytest.mark.asyncio
    async def test_get_or_set_miss(self, cache):
        """get_or_set: cache miss 시 factory 호출."""
        factory_called = False

        async def factory():
            nonlocal factory_called
            factory_called = True
            return "computed"

        val = await cache.get_or_set("computed_key", factory)
        assert val == "computed"
        assert factory_called

    @pytest.mark.asyncio
    async def test_get_or_set_hit(self, cache):
        """get_or_set: cache hit 시 factory 호출 안 함."""
        await cache.set("cached_key", "cached_value")
        factory_called = False

        async def factory():
            nonlocal factory_called
            factory_called = True
            return "should_not_call"

        val = await cache.get_or_set("cached_key", factory)
        assert val == "cached_value"
        assert not factory_called

    @pytest.mark.asyncio
    async def test_get_or_set_sync_factory(self, cache):
        """get_or_set: sync factory도 지원."""
        val = await cache.get_or_set("sync_key", lambda: "sync_value")
        assert val == "sync_value"

    @pytest.mark.asyncio
    async def test_clear_expired(self, cache):
        """만료된 항목만 정리."""
        import time

        await cache.set("fresh", "v1", ttl=60)
        await cache.set("stale", "v2", ttl=1)
        # Force stale entry expiry
        entry = cache._entries.get("stale")
        assert entry is not None
        entry.created_at = time.time() - 10

        removed = await cache.clear_expired()
        assert removed == 1
        assert await cache.get("fresh") == "v1"
        assert await cache.get("stale") is None

    @pytest.mark.asyncio
    async def test_max_size_eviction_oldest_removed(self):
        """max_size 초과 시 가장 오래된 항목이 제거됨."""
        cache = ApiCache(default_ttl=3600, max_size=3)

        await cache.set("oldest", "v1")
        await cache.set("middle", "v2")
        await cache.set("newest", "v3")

        # max_size=3, 3개 모두 저장됨
        assert await cache.get("oldest") == "v1"
        assert await cache.get("middle") == "v2"
        assert await cache.get("newest") == "v3"

        # 4번째 추가 → 가장 오래된 "oldest" 제거
        await cache.set("newer", "v4")

        assert await cache.get("oldest") is None  # 제거됨
        assert await cache.get("middle") == "v2"
        assert await cache.get("newest") == "v3"
        assert await cache.get("newer") == "v4"

        stats = await cache.get_stats()
        assert stats["total_entries"] == 3
        assert stats["eviction_count"] == 1
        assert stats["max_size"] == 3

    @pytest.mark.asyncio
    async def test_max_size_eviction_multiple(self):
        """max_size 초과 시 여러 개의 오래된 항목이 한 번에 제거됨."""
        cache = ApiCache(default_ttl=3600, max_size=2)

        await cache.set("a", 1)
        await cache.set("b", 2)
        await cache.set("c", 3)  # 3개 → 2개 초과 → 'a' 제거
        await cache.set("d", 4)  # 3개 → 2개 초과 → 'b' 제거

        assert await cache.get("a") is None
        assert await cache.get("b") is None
        assert await cache.get("c") == 3
        assert await cache.get("d") == 4

        stats = await cache.get_stats()
        assert stats["total_entries"] == 2
        assert stats["eviction_count"] == 2

    @pytest.mark.asyncio
    async def test_max_size_no_eviction_under_limit(self):
        """max_size 이하일 때는 제거가 발생하지 않음."""
        cache = ApiCache(default_ttl=3600, max_size=10)

        for i in range(5):
            await cache.set(f"key_{i}", i)

        for i in range(5):
            assert await cache.get(f"key_{i}") == i

        stats = await cache.get_stats()
        assert stats["total_entries"] == 5
        assert stats["eviction_count"] == 0

    @pytest.mark.asyncio
    async def test_max_size_tag_index_consistent(self):
        """제거된 항목의 태그 인덱스도 함께 정리됨."""
        cache = ApiCache(default_ttl=3600, max_size=1)

        await cache.set("first", "v1", tags=["group_a"])
        await cache.set("second", "v2", tags=["group_a"])

        # 첫 번째는 제거됨, 태그 인덱스도 정리됨
        assert await cache.get("first") is None
        assert await cache.get("second") == "v2"

        # 태그 무효화 시 "second"만 제거되어야 함
        removed = await cache.invalidate_tag("group_a")
        assert removed == 1

    @pytest.mark.asyncio
    async def test_concurrent_access(self, cache):
        """동시 접근 시 asyncio.Lock으로 보호."""

        async def writer():
            for i in range(10):
                await cache.set(f"key_{i}", i)

        async def reader():
            for i in range(10):
                await cache.get(f"key_{i}")

        await asyncio.gather(writer(), reader())
        stats = await cache.get_stats()
        assert stats["total_entries"] >= 1


# ═══════════════════════════════════════════════════════════════════
# @cached decorator tests
# ═══════════════════════════════════════════════════════════════════


class FakeRequest:
    """Mock FastAPI Request for decorator tests."""

    def __init__(self, method: str = "GET", path: str = "/test", query_params: str = ""):
        self.method = method
        self.url = MagicMock()
        self.url.path = path
        self.query_params = MagicMock()
        self.query_params.__str__ = lambda self: query_params
        self.query_params.__bool__ = lambda self: bool(query_params)


class TestCachedDecorator:
    """@cached decorator — endpoint caching."""

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """캐시 히트 시 함수 호출 없이 캐시된 값 반환."""
        call_count = 0

        @cached(ttl=60, tags=["test"])
        async def my_endpoint(request: FakeRequest) -> dict:
            nonlocal call_count
            call_count += 1
            return {"data": "expensive"}

        req = FakeRequest()
        result1 = await my_endpoint(request=req)
        assert result1 == {"data": "expensive"}
        assert call_count == 1

        result2 = await my_endpoint(request=req)
        assert result2 == {"data": "expensive"}
        assert call_count == 1  # 캐시 히트 — 함수 미호출

    @pytest.mark.asyncio
    async def test_diffrent_paths_different_cache(self):
        """다른 경로는 다른 캐시 키 사용."""
        call_count = 0

        @cached(ttl=60)
        async def my_endpoint(request: FakeRequest) -> dict:
            nonlocal call_count
            call_count += 1
            return {"data": call_count}

        req1 = FakeRequest(path="/api/a")
        req2 = FakeRequest(path="/api/b")

        result1 = await my_endpoint(request=req1)
        result2 = await my_endpoint(request=req2)
        assert result1["data"] == 1
        assert result2["data"] == 2  # 다른 키 — 함수 호출됨
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_post_not_cached(self):
        """POST 요청은 캐싱하지 않음."""
        call_count = 0

        @cached(ttl=60)
        async def my_endpoint(request: FakeRequest) -> dict:
            nonlocal call_count
            call_count += 1
            return {"data": call_count}

        req = FakeRequest(method="POST")
        result1 = await my_endpoint(request=req)
        assert result1["data"] == 1
        result2 = await my_endpoint(request=req)
        assert result2["data"] == 2  # POST — 항상 함수 호출
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_sync_function_support(self):
        """sync 함수도 @cached 적용 가능."""
        call_count = 0

        @cached(ttl=60)
        def sync_endpoint() -> dict:
            nonlocal call_count
            call_count += 1
            return {"data": "sync"}

        # Sync function called via async wrapper
        result = await sync_endpoint()
        assert result == {"data": "sync"}
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_tag_invalidation_via_decorator(self):
        """@cached의 tags로 등록된 항목이 태그 무효화 시 삭제됨."""
        from antigravity_k.engine.api_cache import api_cache as global_cache

        # Clear global cache first
        await global_cache.clear()

        @cached(ttl=60, tags=["demo_tag"])
        async def demo_endpoint(request: FakeRequest) -> dict:
            return {"data": "demo"}

        req = FakeRequest(path="/api/demo")
        await demo_endpoint(request=req)

        # Verify cached
        stats = await global_cache.get_stats()
        assert stats["total_entries"] >= 1

        # Invalidate tag
        removed = await global_cache.invalidate_tag("demo_tag")
        assert removed >= 1

    @pytest.mark.asyncio
    async def test_custom_key_builder(self):
        """key_builder로 커스텀 캐시 키 생성."""
        call_count = 0

        def my_key_builder(*args, **kwargs):
            return f"custom:{kwargs.get('user_id', 'anon')}"

        @cached(ttl=60, key_builder=my_key_builder)
        async def user_endpoint(user_id: str) -> dict:
            nonlocal call_count
            call_count += 1
            return {"id": user_id, "data": "profile"}

        result = await user_endpoint(user_id="alice")
        assert result["id"] == "alice"
        assert call_count == 1

        # Same user_id → cache hit
        result = await user_endpoint(user_id="alice")
        assert call_count == 1

        # Different user_id → cache miss
        result = await user_endpoint(user_id="bob")
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_default_ttl_constant(self):
        """CACHE_DEFAULT_TTL은 60초."""
        assert CACHE_DEFAULT_TTL == 60
