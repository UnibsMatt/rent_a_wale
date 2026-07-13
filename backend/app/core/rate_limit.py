"""Redis fixed-window rate limiting as a FastAPI dependency.

Fail-open by design: if Redis is briefly unavailable the platform stays usable and the
event is logged — availability of the control plane beats strictness of the limiter.
"""

from __future__ import annotations

import redis as redis_lib
from fastapi import Depends, Request

from app.core.exceptions import RateLimitedError
from app.core.logging import get_logger
from app.core.redis import get_redis

log = get_logger("app")


class RateLimiter:
    def __init__(self, *, times: int, seconds: int, scope: str) -> None:
        self.times = times
        self.seconds = seconds
        self.scope = scope

    def __call__(self, request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        key = f"ratelimit:{self.scope}:{client_ip}"
        try:
            r = get_redis()
            current = r.incr(key)
            if current == 1:
                r.expire(key, self.seconds)
            if current > self.times:
                raise RateLimitedError(
                    f"Too many requests, retry in up to {self.seconds}s",
                )
        except redis_lib.RedisError:
            log.warning("rate_limit_backend_unavailable", scope=self.scope)


# Route-class limiters
auth_limiter = Depends(RateLimiter(times=10, seconds=60, scope="auth"))
deploy_limiter = Depends(RateLimiter(times=30, seconds=60, scope="deploy"))
read_limiter = Depends(RateLimiter(times=240, seconds=60, scope="read"))
