"""
Shared request IP and Redis-backed rate-limit helpers.
"""

import logging
from typing import Any

from fastapi import Request

from app.core.config import settings

_redis_clients: dict[str, Any | None] = {}


def get_client_ip(request: Request, *, trust_x_forwarded_for: bool = False) -> str:
    """
    Extract the best available client IP from a proxied FastAPI request.

    Parameters:
        request: FastAPI Request carrying proxy headers and socket metadata.
        trust_x_forwarded_for: Whether to read the first IP from X-Forwarded-For.

    Returns:
        The client IP address string, or "unknown" when unavailable.
    """
    forwarded = request.headers.get("cf-connecting-ip")
    if forwarded:
        return forwarded.strip()

    forwarded = request.headers.get("x-real-ip")
    if forwarded:
        return forwarded.strip()

    if trust_x_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

    return request.client.host if request.client else "unknown"


def get_redis_client(
    cache_key: str,
    *,
    logger: logging.Logger,
    unavailable_message: str,
) -> Any | None:
    """
    Return a lazily created Redis client for a named backend use case.

    Parameters:
        cache_key: Stable logical name used to cache the client instance.
        logger: Logger used when Redis initialisation fails.
        unavailable_message: Warning message emitted on initialisation failure.

    Returns:
        A redis.asyncio client, or None when Redis cannot be initialised.
    """
    if cache_key in _redis_clients:
        return _redis_clients[cache_key]

    try:
        import redis.asyncio as aioredis  # type: ignore[import]

        client = aioredis.from_url(settings.redis_url, decode_responses=True)
    except Exception:
        logger.warning(unavailable_message)
        client = None

    _redis_clients[cache_key] = client
    return client


async def check_redis_rate_limit(
    redis: Any | None,
    key: str,
    *,
    max_count: int,
    ttl_seconds: int,
    logger: logging.Logger | None = None,
    failure_message: str | None = None,
) -> bool | None:
    """
    Increment a Redis counter and evaluate whether the request stays within limit.

    Parameters:
        redis: Redis client returned by get_redis_client().
        key: Counter key to increment.
        max_count: Maximum allowed requests in the active window.
        ttl_seconds: Window length, applied when the counter is first created.
        logger: Optional logger used if the Redis operation fails.
        failure_message: Optional warning message emitted on Redis failure.

    Returns:
        True when the request is within limit, False when it exceeds the limit,
        or None when Redis is unavailable and the caller should fall back.
    """
    if redis is None:
        return None

    try:
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, ttl_seconds)
        return count <= max_count
    except Exception:
        if logger is not None and failure_message:
            logger.warning(failure_message)
        return None
