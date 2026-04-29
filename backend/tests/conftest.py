"""
Shared pytest bootstrap for backend tests.
"""

import pytest
import httpx

from app.core.auth import TOOLING_AUTH_MODE_BEARER, TOOLING_AUTH_MODE_HEADER
from app.core.config import settings

# Backend tests should not inherit live integrations from the repo-root .env.
settings.resend_api_key = ""
settings.turnstile_secret_key = ""

# Rate-limit key prefixes written by the application (must stay in sync with api/).
_RL_PREFIXES = (
    "rl:magic:ip:",
    "rl:magic:email:",
    "rl:contribute:ip:",
    "rl:contact:ip:",
)


@pytest.fixture(autouse=True)
async def flush_rate_limit_keys():
    """
    Delete all Redis rate-limit keys before every individual test.

    The entire test suite runs from a single IP (the httpx testclient address),
    so rate-limit counters accumulate across tests and eventually block magic-link
    requests after ~10 calls.  Flushing before each test resets those counters
    without touching any other Redis keyspace.

    Only keys matching the application's own rl:* prefixes are removed.

    Side effects:
        Deletes matching keys from the Redis instance pointed to by settings.redis_url.
    """
    try:
        import redis.asyncio as aioredis  # type: ignore[import]

        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        for prefix in _RL_PREFIXES:
            keys = await client.keys(f"{prefix}*")
            if keys:
                await client.delete(*keys)
        await client.aclose()
    except Exception:
        # Redis unavailable — tests fall back to in-memory counters, nothing to flush.
        pass


@pytest.fixture(autouse=True)
def mark_bearer_test_requests(monkeypatch):
    """
    Mark test requests that use Authorization headers as explicit tooling flows.

    Production browser traffic now authenticates via the session cookie only.
    Backend tests still exercise the isolated Bearer-token path, so whenever an
    httpx request already contains Authorization we add the tooling-mode header
    expected by the backend.
    """
    original_build_request = httpx.AsyncClient.build_request

    def patched_build_request(self, method, url, **kwargs):
        headers = httpx.Headers(kwargs.get("headers"))
        if "authorization" in headers and TOOLING_AUTH_MODE_HEADER not in headers:
            headers[TOOLING_AUTH_MODE_HEADER] = TOOLING_AUTH_MODE_BEARER
        kwargs["headers"] = headers
        return original_build_request(self, method, url, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "build_request", patched_build_request)
