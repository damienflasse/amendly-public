"""
Amendment reaction endpoint tests.

Covers POST /api/organisations/{slug}/documents/{doc_id}/amendments/{id}/react:

  - react (support)    — creates a support reaction; counts and user_reaction updated
  - react (oppose)     — creates an oppose reaction; counts and user_reaction updated
  - toggle off (null)  — posting the same type twice cancels the reaction
  - plan gate          — solo plan returns 402 (payment required)
  - unauthenticated    — returns 401

Uses in-memory SQLite + ASGI fixture pattern (same as other test modules).
The org plan is upgraded to 'organisation' inline for positive tests.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.auth import _magic_link_store
from app.core.database import Base, get_db
from app.main import app
from app.models.organisation import Organisation, OrgPlan

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Fixtures
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
# Helpers
# ---------------------------------------------------------------------------


async def _register_and_login(client: AsyncClient, email: str) -> str:
    """Register a new user via magic link and return the JWT access token.

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


async def _create_org(client: AsyncClient, jwt: str, slug: str) -> dict:
    """Create an organisation and return its response dict.

    Parameters:
        client: Test HTTP client.
        jwt: Bearer token.
        slug: Unique slug for the organisation.

    Returns:
        Organisation response dict.
    """
    res = await client.post(
        "/api/organisations",
        json={"name": f"Org {slug}", "slug": slug},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 201
    return res.json()


async def _create_doc(client: AsyncClient, jwt: str, slug: str) -> dict:
    """Create a document and return its response dict.

    Parameters:
        client: Test HTTP client.
        jwt: Bearer token.
        slug: Organisation slug.

    Returns:
        Document response dict.
    """
    res = await client.post(
        f"/api/organisations/{slug}/documents",
        json={"title": "Reaction Test Doc"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 201
    return res.json()


async def _create_amendment(client: AsyncClient, jwt: str, slug: str, doc_id: str) -> dict:
    """Submit an amendment and return its response dict.

    Parameters:
        client: Test HTTP client.
        jwt: Bearer token.
        slug: Organisation slug.
        doc_id: Document UUID.

    Returns:
        Amendment response dict.
    """
    res = await client.post(
        f"/api/organisations/{slug}/documents/{doc_id}/amendments",
        json={
            "original_text": "The original passage",
            "proposed_text": "The revised passage",
        },
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 201
    return res.json()


async def _upgrade_to_organisation(db_session: AsyncSession, slug: str) -> None:
    """Upgrade an organisation's plan to 'organisation' directly in the database.

    Parameters:
        db_session: Active async DB session.
        slug: Organisation slug.
    """
    result = await db_session.execute(
        select(Organisation).where(Organisation.slug == slug)
    )
    org = result.scalar_one()
    org.plan = OrgPlan.organisation
    await db_session.flush()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_react_support(client, db_session):
    """Posting 'support' records the reaction and returns updated counts."""
    jwt = await _register_and_login(client, "react_support@example.com")
    await _create_org(client, jwt, "react-support-org")
    await _upgrade_to_organisation(db_session, "react-support-org")
    doc = await _create_doc(client, jwt, "react-support-org")
    amendment = await _create_amendment(client, jwt, "react-support-org", doc["id"])

    res = await client.post(
        f"/api/organisations/react-support-org/documents/{doc['id']}/amendments/{amendment['id']}/react",
        json={"type": "support"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["support_count"] == 1
    assert data["oppose_count"] == 0
    assert data["user_reaction"] == "support"


@pytest.mark.asyncio
async def test_react_oppose(client, db_session):
    """Posting 'oppose' records the reaction and returns updated counts."""
    jwt = await _register_and_login(client, "react_oppose@example.com")
    await _create_org(client, jwt, "react-oppose-org")
    await _upgrade_to_organisation(db_session, "react-oppose-org")
    doc = await _create_doc(client, jwt, "react-oppose-org")
    amendment = await _create_amendment(client, jwt, "react-oppose-org", doc["id"])

    res = await client.post(
        f"/api/organisations/react-oppose-org/documents/{doc['id']}/amendments/{amendment['id']}/react",
        json={"type": "oppose"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["support_count"] == 0
    assert data["oppose_count"] == 1
    assert data["user_reaction"] == "oppose"


@pytest.mark.asyncio
async def test_react_toggle_off(client, db_session):
    """Posting the same reaction type twice cancels the reaction (toggle off)."""
    jwt = await _register_and_login(client, "react_toggle@example.com")
    await _create_org(client, jwt, "react-toggle-org")
    await _upgrade_to_organisation(db_session, "react-toggle-org")
    doc = await _create_doc(client, jwt, "react-toggle-org")
    amendment = await _create_amendment(client, jwt, "react-toggle-org", doc["id"])

    react_url = (
        f"/api/organisations/react-toggle-org/documents/{doc['id']}"
        f"/amendments/{amendment['id']}/react"
    )
    headers = {"Authorization": f"Bearer {jwt}"}

    # First post — creates the reaction
    res1 = await client.post(react_url, json={"type": "support"}, headers=headers)
    assert res1.status_code == 200
    assert res1.json()["support_count"] == 1
    assert res1.json()["user_reaction"] == "support"

    # Second post (same type) — cancels the reaction
    res2 = await client.post(react_url, json={"type": "support"}, headers=headers)
    assert res2.status_code == 200
    data = res2.json()
    assert data["support_count"] == 0
    assert data["user_reaction"] is None


@pytest.mark.asyncio
async def test_react_plan_gate_solo(client):
    """Solo plan returns 402 Payment Required when attempting to react."""
    jwt = await _register_and_login(client, "react_solo@example.com")
    await _create_org(client, jwt, "react-solo-org")
    # Leave org on default solo plan — no upgrade
    doc = await _create_doc(client, jwt, "react-solo-org")
    amendment = await _create_amendment(client, jwt, "react-solo-org", doc["id"])

    res = await client.post(
        f"/api/organisations/react-solo-org/documents/{doc['id']}/amendments/{amendment['id']}/react",
        json={"type": "support"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 402


@pytest.mark.asyncio
async def test_react_unauthenticated(client, db_session):
    """Unauthenticated request to the react endpoint returns 401."""
    jwt = await _register_and_login(client, "react_unauth@example.com")
    await _create_org(client, jwt, "react-unauth-org")
    await _upgrade_to_organisation(db_session, "react-unauth-org")
    doc = await _create_doc(client, jwt, "react-unauth-org")
    amendment = await _create_amendment(client, jwt, "react-unauth-org", doc["id"])

    # Clear the authenticated session cookie so the request is truly anonymous.
    client.cookies.clear()
    res = await client.post(
        f"/api/organisations/react-unauth-org/documents/{doc['id']}/amendments/{amendment['id']}/react",
        json={"type": "support"},
    )
    assert res.status_code == 401
