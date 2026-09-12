"""Redis-backed rate limiter for expensive endpoints (AI generation, PDF
processing -- product spec section 28).

Fixed-window counter via Redis INCR+EXPIRE, keyed by (bucket, user_id) --
correct across multiple worker processes/instances since the counter lives
in Redis, not in-process. tests/conftest.py swaps `get_redis()` for an
in-memory fake so the suite needs no real Redis.
"""

from fastapi import Depends, HTTPException, status

import app.core.redis_client as redis_client_module
from app.core.config import settings
from app.core.deps import get_current_user
from app.models.user import User


def rate_limit(bucket: str, window_seconds: int = 60):
    """Returns a FastAPI dependency enforcing settings.ai_rate_limit_per_minute
    requests per `window_seconds` for the current user, scoped to `bucket`.

    The limit is read from `settings` freshly on every call (not captured at
    route-registration time) specifically so tests can monkeypatch
    `settings.ai_rate_limit_per_minute` per-test and have it actually take
    effect -- capturing it as a plain function argument here would bake in
    whatever value existed when the module was first imported.
    """

    def dependency(current_user: User = Depends(get_current_user)) -> None:
        limit = settings.ai_rate_limit_per_minute
        key = f"ratelimit:{bucket}:{current_user.id}"
        r = redis_client_module.get_redis()
        count = r.incr(key)
        if count == 1:
            r.expire(key, window_seconds)

        if count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: max {limit} requests per {window_seconds}s for this action. Try again shortly.",
            )

    return dependency
