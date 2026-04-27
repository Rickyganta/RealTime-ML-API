import json
from typing import Any

import redis

from app.core.config import settings


class CacheClient:
    def __init__(self) -> None:
        self.client = redis.Redis.from_url(settings.redis_url, decode_responses=True)

    def get_json(self, key: str) -> Any | None:
        value = self.client.get(key)
        if value is None:
            return None
        return json.loads(value)

    def set_json(self, key: str, value: Any, ttl: int | None = None) -> None:
        self.client.set(key, json.dumps(value), ex=ttl or settings.cache_ttl_seconds)

    def incr(self, key: str) -> int:
        return self.client.incr(key)

    def expire(self, key: str, seconds: int) -> None:
        self.client.expire(key, seconds)
