import asyncio
from collections import OrderedDict
from typing import Any, Callable, Generic, TypeVar, Optional
from weakref import WeakValueDictionary

T = TypeVar("T")
K = TypeVar("K")


class AsyncLRUCache(Generic[K, T]):
    """
    An asynchronous LRU cache with TTL support.

    Args:
        max_size (int): Maximum number of items to store in the cache.
        ttl (float): Time-to-live for each item in seconds.
    """

    def __init__(self, max_size: int, ttl: float):
        self._max_size = max_size
        self._ttl = ttl
        self._cache: OrderedDict[K, asyncio.Future[T]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def _get_or_create(self, key: K, factory: Callable[[], Awaitable[T]]) -> T:
        future = self._cache.get(key)
        if future is None or future.done():
            async with self._lock:
                # Double-check after acquiring the lock
                future = self._cache.get(key)
                if future is None or future.done():
                    future = asyncio.create_task(self._create_and_store(key, factory))
                    self._cache[key] = future
        return await future

    async def _create_and_store(self, key: K, factory: Callable[[], Awaitable[T]]) -> T:
        try:
            value = await factory()
            # Store the result in a new future to avoid overwriting if the same key is requested again
            new_future = asyncio.Future()
            new_future.set_result(value)
            self._cache.move_to_end(key)
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)
            return value
        finally:
            # Remove expired items
            current_time = asyncio.get_running_loop().time()
            to_remove = [
                k
                for k, f in self._cache.items()
                if f.done() and (current_time - f.result_info[1]) > self._ttl
            ]
            for k in to_remove:
                del self._cache[k]

    async def get_or_compute(self, key: K, factory: Callable[[], Awaitable[T]]) -> T:
        """
        Retrieves the value associated with the given key from the cache or computes it using the provided factory function.

        Args:
            key (K): The key to retrieve or compute a value for.
            factory (Callable[[], Awaitable[T]]): An asynchronous factory function that computes the value if not in the cache.

        Returns:
            T: The value associated with the key.
        """
        return await self._get_or_create(key, factory)
