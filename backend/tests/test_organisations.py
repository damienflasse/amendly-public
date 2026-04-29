"""
Organisation endpoint tests — covers /api/organisations/* routes.

Uses the same in-memory SQLite + ASGI fixture pattern as test_auth.py.
Each test gets a fresh HTTP client backed by a rolled-back DB session.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.auth import _magic_link_store
from app.core.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Shared fixtures (mirrors test_auth.py)
# ---------------------------------------------------------------------------


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
# Helper — create a user and return their Bearer token
# ---------------------------------------------------------------------------


async def _register_and_login(client: AsyncClient, email: str) -> str:
    """
    Register a new user via magic link and return the JWT access token.

    Parameters:
        client: Test HTTP client.
        email: Email address for the test user.

    Returns:
        JWT access token string.
    """
    await client.post("/api/auth/magic-link/request", json={"email": email})
    token = next(t for t, v in _magic_link_store.items() if v["email"] == email)
    res = await client.post("/api/auth/magic-link/verify", json={"token": token})
    return res.json()["access_token"]


# ---------------------------------------------------------------------------
# POST /api/organisations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_organisation_success(client):
    """Authenticated user can create an organisation and becomes the owner."""
    jwt = await _register_and_login(client, "owner@example.com")
    headers = {"Authorization": f"Bearer {jwt}"}

    res = await client.post(
        "/api/organisations",
        json={"name": "ACME Federation", "slug": "acme-federation"},
        headers=headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "ACME Federation"
    assert data["slug"] == "acme-federation"
    assert data["plan"] == "solo"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_organisation_unauthenticated(client):
    """Creating an organisation without a token returns 401 or 403."""
    res = await client.post(
        "/api/organisations",
        json={"name": "Ghost Org", "slug": "ghost-org"},
    )
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_organisation_invalid_slug(client):
    """Slug with invalid characters should return 422."""
    jwt = await _register_and_login(client, "badslug@example.com")
    headers = {"Authorization": f"Bearer {jwt}"}

    res = await client.post(
        "/api/organisations",
        json={"name": "Bad Slug Org", "slug": "Bad Slug!"},
        headers=headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_organisation_duplicate_slug(client):
    """Creating two organisations with the same slug returns 409 on the second."""
    jwt = await _register_and_login(client, "dupslug@example.com")
    headers = {"Authorization": f"Bearer {jwt}"}

    await client.post(
        "/api/organisations",
        json={"name": "First Org", "slug": "dup-slug-org"},
        headers=headers,
    )
    res = await client.post(
        "/api/organisations",
        json={"name": "Second Org", "slug": "dup-slug-org"},
        headers=headers,
    )
    assert res.status_code == 409


# ---------------------------------------------------------------------------
# GET /api/organisations/me
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_my_organisations_empty(client):
    """A brand-new user has no organisations — endpoint returns an empty list."""
    jwt = await _register_and_login(client, "newuser@example.com")
    headers = {"Authorization": f"Bearer {jwt}"}

    res = await client.get("/api/organisations/me", headers=headers)
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_list_my_organisations_after_create(client):
    """After creating an org the user's /me list includes it with role=owner."""
    jwt = await _register_and_login(client, "lister@example.com")
    headers = {"Authorization": f"Bearer {jwt}"}

    await client.post(
        "/api/organisations",
        json={"name": "Lister Org", "slug": "lister-org"},
        headers=headers,
    )

    res = await client.get("/api/organisations/me", headers=headers)
    assert res.status_code == 200
    orgs = res.json()
    assert len(orgs) == 1
    assert orgs[0]["slug"] == "lister-org"
    assert orgs[0]["role"] == "owner"


@pytest.mark.asyncio
async def test_list_my_organisations_unauthenticated(client):
    """Calling /me without a token returns 401 or 403."""
    res = await client.get("/api/organisations/me")
    assert res.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /api/organisations/{slug}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_organisation_by_slug_success(client):
    """Owner can fetch their organisation by slug."""
    jwt = await _register_and_login(client, "fetcher@example.com")
    headers = {"Authorization": f"Bearer {jwt}"}

    await client.post(
        "/api/organisations",
        json={"name": "Fetcher Org", "slug": "fetcher-org"},
        headers=headers,
    )

    res = await client.get("/api/organisations/fetcher-org", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["slug"] == "fetcher-org"
    assert data["name"] == "Fetcher Org"


@pytest.mark.asyncio
async def test_get_organisation_not_found(client):
    """Non-existent slug returns 404."""
    jwt = await _register_and_login(client, "notfound@example.com")
    headers = {"Authorization": f"Bearer {jwt}"}

    res = await client.get("/api/organisations/does-not-exist", headers=headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_organisation_non_member_returns_404(client):
    """A user who is not a member of an org gets 404 (no disclosure)."""
    # User A creates an org
    jwt_a = await _register_and_login(client, "owner-a@example.com")
    await client.post(
        "/api/organisations",
        json={"name": "Private Org", "slug": "private-org"},
        headers={"Authorization": f"Bearer {jwt_a}"},
    )

    # User B tries to fetch it
    jwt_b = await _register_and_login(client, "outsider-b@example.com")
    res = await client.get(
        "/api/organisations/private-org",
        headers={"Authorization": f"Bearer {jwt_b}"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_organisation_unauthenticated(client):
    """Fetching an org without a token returns 401 or 403."""
    res = await client.get("/api/organisations/some-org")
    assert res.status_code in (401, 403)
