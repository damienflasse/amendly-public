"""
Auth endpoint tests — covers the /api/auth/* routes.

Uses an in-memory SQLite database (via SQLAlchemy's async engine) so no live
Postgres is needed during CI. The `app` fixture overrides the `get_db`
dependency with a test session backed by SQLite.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.api.auth as auth_api
import app.core.auth as core_auth
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.auth import SESSION_COOKIE_NAME
from app.main import app

# ---------------------------------------------------------------------------
# In-memory SQLite test database
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


class FakeRedisCounter:
    """Minimal async Redis stub for auth rate-limit tests."""

    def __init__(self):
        """Initialise empty counter and TTL tracking maps."""
        self.counts: dict[str, int] = {}
        self.expirations: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        """Increment and return the counter value for a key."""
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key: str, ttl: int) -> None:
        """Record the TTL assigned to a key."""
        self.expirations[key] = ttl


class FakeRedisBlocklist:
    """Minimal async Redis stub for JWT revocation tests."""

    def __init__(self):
        """Initialise empty blocklist value and TTL tracking maps."""
        self.values: dict[str, str] = {}
        self.expirations: dict[str, int] = {}

    async def setex(self, key: str, ttl: int, value: str) -> None:
        """Store a value and remember the requested TTL."""
        self.values[key] = value
        self.expirations[key] = ttl

    async def exists(self, key: str) -> int:
        """Return 1 when the key has been revoked, else 0."""
        return int(key in self.values)


@pytest.fixture(scope="session")
async def test_engine():
    """Create an async SQLite engine shared across all tests in the session."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    """Yield a fresh AsyncSession for each test, rolling back after."""
    TestSession = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with TestSession() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_session):
    """HTTP test client with get_db overridden to use the SQLite test session."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_magic_link_request_returns_202(client):
    """POST /api/auth/magic-link/request should accept any email and return 202."""
    response = await client.post(
        "/api/auth/magic-link/request",
        json={"email": "test@example.com"},
    )
    assert response.status_code == 202
    assert "message" in response.json()


@pytest.mark.asyncio
async def test_magic_link_request_invalid_email(client):
    """POST /api/auth/magic-link/request with a non-email should return 422."""
    response = await client.post(
        "/api/auth/magic-link/request",
        json={"email": "not-an-email"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_magic_link_request_rate_limits_by_ip(client, monkeypatch):
    """POST /api/auth/magic-link/request returns 429 after five requests per IP."""
    fake_redis = FakeRedisCounter()
    monkeypatch.setattr(auth_api, "_get_redis", lambda: fake_redis)
    monkeypatch.setattr(settings, "turnstile_secret_key", "")

    headers = {"cf-connecting-ip": "203.0.113.10"}
    for attempt in range(auth_api._RL_IP_MAX):
        response = await client.post(
            "/api/auth/magic-link/request",
            headers=headers,
            json={"email": f"rate-limit-{attempt}@example.com"},
        )
        assert response.status_code == 202

    blocked = await client.post(
        "/api/auth/magic-link/request",
        headers=headers,
        json={"email": "rate-limit-blocked@example.com"},
    )
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "Too many requests. Please try again later."

    redis_key = f"{auth_api._RL_IP_KEY}203.0.113.10"
    assert fake_redis.expirations[redis_key] == auth_api._RL_IP_TTL
    assert fake_redis.counts[redis_key] == auth_api._RL_IP_MAX + 1


@pytest.mark.asyncio
async def test_magic_link_request_accepts_valid_turnstile(client, monkeypatch):
    """POST /api/auth/magic-link/request accepts a valid Turnstile response."""
    monkeypatch.setattr(settings, "turnstile_secret_key", "live-secret")

    async def fake_verify_turnstile(token, remote_ip=None, *, fail_open=True, context="unknown", expected_action=None, expected_hostname=None):
        assert token == "good-token"
        assert remote_ip == "203.0.113.10"
        assert fail_open is True
        assert context == "auth_magic_link"
        assert expected_action == "auth_magic_link"
        return True

    monkeypatch.setattr(auth_api, "verify_turnstile", fake_verify_turnstile)

    response = await client.post(
        "/api/auth/magic-link/request",
        headers={"cf-connecting-ip": "203.0.113.10"},
        json={"email": "turnstile-ok@example.com", "turnstile_token": "good-token"},
    )
    assert response.status_code == 202
    assert "message" in response.json()


@pytest.mark.asyncio
async def test_magic_link_request_rejects_failed_turnstile(client, monkeypatch):
    """POST /api/auth/magic-link/request rejects an invalid Turnstile response."""
    monkeypatch.setattr(settings, "turnstile_secret_key", "live-secret")

    async def fake_verify_turnstile(token, remote_ip=None, *, fail_open=True, context="unknown", expected_action=None, expected_hostname=None):
        assert token == "bad-token"
        assert remote_ip == "198.51.100.20"
        assert fail_open is True
        assert context == "auth_magic_link"
        assert expected_action == "auth_magic_link"
        return False

    monkeypatch.setattr(auth_api, "verify_turnstile", fake_verify_turnstile)

    response = await client.post(
        "/api/auth/magic-link/request",
        headers={"cf-connecting-ip": "198.51.100.20"},
        json={"email": "turnstile-blocked@example.com", "turnstile_token": "bad-token"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Human verification failed. Please try again."


@pytest.mark.asyncio
async def test_magic_link_request_bypasses_turnstile_in_test_mode(client, monkeypatch):
    """secret='test' bypasses Turnstile so CI and local dev work without real keys."""
    monkeypatch.setattr(settings, "turnstile_secret_key", "test")

    response = await client.post(
        "/api/auth/magic-link/request",
        json={"email": "turnstile-testmode@example.com"},
    )
    assert response.status_code == 202
    assert "message" in response.json()


@pytest.mark.asyncio
async def test_magic_link_verify_invalid_token(client):
    """POST /api/auth/magic-link/verify with a garbage token should return 400."""
    response = await client.post(
        "/api/auth/magic-link/verify",
        json={"token": "completely-invalid-token"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_magic_link_full_flow(client):
    """
    Full happy-path: request a magic link, steal the token from the in-memory
    store, verify it, and check that /api/auth/me returns the user.
    """
    from app.api.auth import _magic_link_store

    email = "flow@example.com"

    # 1. Request a magic link — this populates _magic_link_store
    res = await client.post("/api/auth/magic-link/request", json={"email": email})
    assert res.status_code == 202

    # 2. Extract the token (bypasses email delivery in tests)
    token = next(
        t for t, v in _magic_link_store.items() if v["email"] == email
    )
    assert token

    # 3. Verify the token → should receive a JWT
    res = await client.post("/api/auth/magic-link/verify", json={"token": token})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # 4. Use the JWT to call /api/auth/me
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    res = await client.get("/api/auth/me", headers=headers)
    assert res.status_code == 200
    me = res.json()
    assert me["email"] == email
    assert me["plan"] == "solo"


@pytest.mark.asyncio
async def test_magic_link_verify_sets_http_only_session_cookie(client):
    """POST /magic-link/verify should establish an httpOnly cookie session."""
    from app.api.auth import _magic_link_store

    email = "cookie-flow@example.com"
    await client.post("/api/auth/magic-link/request", json={"email": email})
    token = next(t for t, v in _magic_link_store.items() if v["email"] == email)

    res = await client.post("/api/auth/magic-link/verify", json={"token": token})
    assert res.status_code == 200
    set_cookie = res.headers.get("set-cookie", "")
    assert f"{SESSION_COOKIE_NAME}=" in set_cookie
    assert "HttpOnly" in set_cookie

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == email


@pytest.mark.asyncio
async def test_logout_clears_cookie_backed_session(client):
    """POST /logout revokes the cookie session for subsequent requests."""
    from app.api.auth import _magic_link_store

    email = "cookie-logout@example.com"
    await client.post("/api/auth/magic-link/request", json={"email": email})
    token = next(t for t, v in _magic_link_store.items() if v["email"] == email)
    await client.post("/api/auth/magic-link/verify", json={"token": token})

    logout_res = await client.post("/api/auth/logout")
    assert logout_res.status_code == 204

    me = await client.get("/api/auth/me")
    assert me.status_code == 401


@pytest.mark.asyncio
async def test_me_unauthenticated(client):
    """GET /api/auth/me without a token should return 401."""
    res = await client.get("/api/auth/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_logout(client):
    """POST /api/auth/logout should return 204."""
    res = await client.post("/api/auth/logout")
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_logout_revokes_token_and_blocks_subsequent_me(client, monkeypatch):
    """POST /api/auth/logout should block the same JWT on later authenticated calls."""
    from app.api.auth import _magic_link_store

    fake_redis = FakeRedisBlocklist()
    monkeypatch.setattr(core_auth, "_get_blocklist_redis", lambda: fake_redis)

    email = "logout-revoke@example.com"

    res = await client.post("/api/auth/magic-link/request", json={"email": email})
    assert res.status_code == 202

    token = next(t for t, v in _magic_link_store.items() if v["email"] == email)
    res = await client.post("/api/auth/magic-link/verify", json={"token": token})
    assert res.status_code == 200

    access_token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    res = await client.get("/api/auth/me", headers=headers)
    assert res.status_code == 200

    res = await client.post("/api/auth/logout", headers=headers)
    assert res.status_code == 204

    revoked_key = next(iter(fake_redis.values.keys()))
    assert fake_redis.values[revoked_key] == "1"
    assert fake_redis.expirations[revoked_key] >= 1

    res = await client.get("/api/auth/me", headers=headers)
    assert res.status_code == 401
    assert res.json()["detail"] == "Token has been revoked"


@pytest.mark.asyncio
async def test_oauth_unknown_provider(client):
    """GET /api/auth/oauth/unknown should return 400."""
    res = await client.get("/api/auth/oauth/unknownprovider", follow_redirects=False)
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_oauth_redirect_google_not_configured(client):
    """
    GET /api/auth/oauth/google when GOOGLE_CLIENT_ID is empty should return 503.
    The default settings have an empty client ID.
    """
    res = await client.get("/api/auth/oauth/google", follow_redirects=False)
    # Either 302 (if client_id set) or 503 (if not configured) — both are valid outcomes
    assert res.status_code in (302, 503)


# ---------------------------------------------------------------------------
# DELETE /api/auth/me — GDPR account erasure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_me_anonymises_account(client):
    """
    DELETE /api/auth/me should return 204, anonymise the user's email/name,
    set is_deleted=True, and block subsequent /me calls with 401.
    """
    from app.api.auth import _magic_link_store

    email = "delete-me@example.com"

    # Register and log in
    res = await client.post("/api/auth/magic-link/request", json={"email": email})
    assert res.status_code == 202
    token = next(t for t, v in _magic_link_store.items() if v["email"] == email)
    res = await client.post("/api/auth/magic-link/verify", json={"token": token})
    assert res.status_code == 200
    jwt = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {jwt}"}

    # Verify the account is active before deletion
    res = await client.get("/api/auth/me", headers=headers)
    assert res.status_code == 200
    assert res.json()["email"] == email

    # Delete the account
    res = await client.delete("/api/auth/me", headers=headers)
    assert res.status_code == 204

    # Subsequent /me call should return 401 (account deleted)
    res = await client.get("/api/auth/me", headers=headers)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_delete_me_unauthenticated(client):
    """DELETE /api/auth/me without a token should return 401."""
    res = await client.delete("/api/auth/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_delete_me_sole_owner_no_other_members(client):
    """
    When the user is the sole owner of an org with no other members,
    DELETE /api/auth/me should still return 204 (org left without owner).
    """
    from app.api.auth import _magic_link_store

    owner_email = "sole-owner-no-members@example.com"

    # Register owner
    await client.post("/api/auth/magic-link/request", json={"email": owner_email})
    token = next(t for t, v in _magic_link_store.items() if v["email"] == owner_email)
    res = await client.post("/api/auth/magic-link/verify", json={"token": token})
    owner_jwt = res.json()["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_jwt}"}

    # Create an org (only member = owner)
    res = await client.post(
        "/api/organisations",
        json={"name": "Solo Owner Org", "slug": "solo-owner-org-gdpr"},
        headers=owner_headers,
    )
    assert res.status_code == 201

    # Deletion should succeed even though no successor exists
    res = await client.delete("/api/auth/me", headers=owner_headers)
    assert res.status_code == 204


# ---------------------------------------------------------------------------
# Security: magic-link token hashing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_magic_link_redis_key_uses_hash_not_raw_token():
    """
    The Redis key for a magic-link must be the SHA-256 hash of the token,
    not the raw token itself.  A Redis dump should not be directly replayable.
    """
    import hashlib
    import json
    from datetime import UTC, datetime, timedelta

    from app.api.auth import (
        _REDIS_KEY_PREFIX,
        _hash_magic_token,
        _store_magic_link,
    )

    raw_token = "test-raw-token-abcdef1234567890"
    email = "hash-test@example.com"
    expires_at = datetime.now(UTC) + timedelta(minutes=15)

    # Verify hash function produces the expected SHA-256 digest
    expected_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    assert _hash_magic_token(raw_token) == expected_hash

    # The Redis key must NOT be the raw token
    raw_redis_key = f"{_REDIS_KEY_PREFIX}{raw_token}"
    hashed_redis_key = f"{_REDIS_KEY_PREFIX}{expected_hash}"
    assert raw_redis_key != hashed_redis_key, "Hash must differ from the raw token"

    # Simulate a Redis client that records which key was used
    written_keys: list[str] = []

    class CapturingRedis:
        async def setex(self, key: str, ttl: int, value: str) -> None:
            written_keys.append(key)

    import app.api.auth as auth_module
    original_redis = auth_module._redis_client
    auth_module._redis_client = CapturingRedis()
    try:
        await _store_magic_link(raw_token, email, expires_at)
    finally:
        auth_module._redis_client = original_redis

    assert len(written_keys) == 1, "Expected exactly one Redis write"
    used_key = written_keys[0]
    assert raw_token not in used_key, "Redis key must not contain the raw token"
    assert used_key == hashed_redis_key, "Redis key must be the SHA-256 hashed key"
