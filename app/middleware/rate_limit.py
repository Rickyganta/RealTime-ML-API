from fastapi import HTTPException, Request

from app.core.config import settings
from app.services.cache import CacheClient


class RateLimiter:
    def __init__(self, cache: CacheClient) -> None:
        self.cache = cache
        self.max_per_min = settings.rate_limit_per_minute

    def check(self, request: Request) -> None:
        token = settings.loadtest_bypass_token
        if token and request.headers.get("x-loadtest-bypass") == token:
            return
        ip = request.client.host if request.client else "unknown"
        key = f"rate_limit:{ip}"
        count = self.cache.incr(key)
        if count == 1:
            self.cache.expire(key, 60)
        if count > self.max_per_min:
            raise HTTPException(status_code=429, detail="Rate limit exceeded (100 req/min)")
