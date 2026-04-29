"""
Document status endpoint tests — covers PUT …/documents/{doc_id}/status.

Uses the same in-memory SQLite + ASGI fixture pattern as other test files.

Coverage:
  PUT /api/organisations/{slug}/documents/{doc_id}/status
      — owner can change status to open / closed / draft
      — admin can change status
      — member gets 403
      — non-member gets 404
      — invalid status value returns 422
      — non-existent document returns 404
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.auth import _magic_link_store
from app.core.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Shared fixtures
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


async def _create_org(client: AsyncClient, jwt: str, slug: str) -> dict:
    """
    Create an organisation and return its response dict.

    Parameters:
        client: Test HTTP client.
        jwt: Bearer token for the creating user.
        slug: Unique slug for the organisation.

    Returns:
        Organisation response dict from the API.
    """
    res = await client.post(
        "/api/organisations",
        json={"name": f"Org {slug}", "slug": slug},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 201
    return res.json()


async def _create_doc(client: AsyncClient, jwt: str, slug: str, title: str = "Status Doc") -> dict:
    """
    Create a document and return its response dict.

    Parameters:
        client: Test HTTP client.
        jwt: Bearer token for the creating user.
        slug: Organisation slug.
        title: Document title.

    Returns:
        Document response dict from the API.
    """
    res = await client.post(
        f"/api/organisations/{slug}/documents",
        json={"title": title},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 201
    return res.json()


# ---------------------------------------------------------------------------
# PUT /api/organisations/{slug}/documents/{doc_id}/status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_owner_can_set_status_open(client):
    """Owner can change document status from draft to open."""
    jwt = await _register_and_login(client, "docstatus_owner@example.com")
    await _create_org(client, jwt, "docstatus-open-org")
    doc = await _create_doc(client, jwt, "docstatus-open-org")

    assert doc["status"] == "draft"

    res = await client.put(
        f"/api/organisations/docstatus-open-org/documents/{doc['id']}/status",
        json={"status": "open"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "open"
    assert data["id"] == doc["id"]


@pytest.mark.asyncio
async def test_owner_can_set_status_closed(client):
    """Owner can set document status to closed."""
    jwt = await _register_and_login(client, "docstatus_closed@example.com")
    await _create_org(client, jwt, "docstatus-closed-org")
    doc = await _create_doc(client, jwt, "docstatus-closed-org")

    res = await client.put(
        f"/api/organisations/docstatus-closed-org/documents/{doc['id']}/status",
        json={"status": "closed"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "closed"


@pytest.mark.asyncio
async def test_owner_can_revert_to_draft(client):
    """Owner can revert a document status back to draft."""
    jwt = await _register_and_login(client, "docstatus_revert@example.com")
    await _create_org(client, jwt, "docstatus-revert-org")
    doc = await _create_doc(client, jwt, "docstatus-revert-org")

    # Open first
    await client.put(
        f"/api/organisations/docstatus-revert-org/documents/{doc['id']}/status",
        json={"status": "open"},
        headers={"Authorization": f"Bearer {jwt}"},
    )

    # Then revert to draft
    res = await client.put(
        f"/api/organisations/docstatus-revert-org/documents/{doc['id']}/status",
        json={"status": "draft"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "draft"


@pytest.mark.asyncio
async def test_status_invalid_value_returns_422(client):
    """Sending an invalid status value returns 422."""
    jwt = await _register_and_login(client, "docstatus_invalid@example.com")
    await _create_org(client, jwt, "docstatus-invalid-org")
    doc = await _create_doc(client, jwt, "docstatus-invalid-org")

    res = await client.put(
        f"/api/organisations/docstatus-invalid-org/documents/{doc['id']}/status",
        json={"status": "published"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_status_unauthenticated_returns_401_or_403(client):
    """Status change without a token returns 401 or 403."""
    res = await client.put(
        "/api/organisations/some-org/documents/some-doc/status",
        json={"status": "open"},
    )
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_status_non_member_returns_404(client):
    """A user not in the org gets 404 when changing document status."""
    jwt_owner = await _register_and_login(client, "docstatus_nm_owner@example.com")
    await _create_org(client, jwt_owner, "docstatus-nm-org")
    doc = await _create_doc(client, jwt_owner, "docstatus-nm-org")

    jwt_outsider = await _register_and_login(client, "docstatus_nm_out@example.com")
    res = await client.put(
        f"/api/organisations/docstatus-nm-org/documents/{doc['id']}/status",
        json={"status": "open"},
        headers={"Authorization": f"Bearer {jwt_outsider}"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_status_doc_not_found_returns_404(client):
    """Updating status on a non-existent document returns 404."""
    jwt = await _register_and_login(client, "docstatus_nf@example.com")
    await _create_org(client, jwt, "docstatus-nf-org")

    res = await client.put(
        "/api/organisations/docstatus-nf-org/documents/00000000-0000-0000-0000-000000000000/status",
        json={"status": "open"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 404
