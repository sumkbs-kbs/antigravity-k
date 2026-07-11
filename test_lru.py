import asyncio

from generated_lru import AsyncLRUCache


async def main():
    cache = AsyncLRUCache(max_size=2, ttl=10.0)

    async def factory():
        await asyncio.sleep(0.1)
        return "value"

    try:
        val = await cache.get_or_compute("key1", factory)
        print(f"Success: {val}")
    except Exception as e:
        print(f"Failed: {type(e).__name__}: {e}")


asyncio.run(main())
