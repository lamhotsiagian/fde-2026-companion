import json
import redis.asyncio as aioredis
from typing import List, Optional

class RedisMemoryCache:
    """
    Durable Redis cache wrapper for fast memory lookups.
    Ensures absolute data scoping by user_id keys.
    """
    def __init__(self, redis_url: str):
        self.client = aioredis.from_url(redis_url, decode_responses=True)

    def _make_key(self, user_id: str) -> str:
        return f"user:memories:{user_id}"

    async def get_memories(self, user_id: str) -> Optional[List[dict]]:
        """
        Retrieves cached active memories. Returns None on cache miss.
        """
        key = self._make_key(user_id)
        cached_data = await self.client.get(key)
        if cached_data:
            return json.loads(cached_data)
        return None

    async def set_memories(self, user_id: str, memories: List[dict], ttl: int = 3600) -> None:
        """
        Populates the user's memory cache with a TTL (e.g. 1 hour).
        """
        key = self._make_key(user_id)
        await self.client.set(key, json.dumps(memories), ex=ttl)

    async def invalidate(self, user_id: str) -> None:
        """
        Invalidates the cache. Crucial on memory writes or consolidations.
        """
        key = self._make_key(user_id)
        await self.client.delete(key)
