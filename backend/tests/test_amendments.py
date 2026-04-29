"""
Amendment endpoint tests — covers /api/organisations/{slug}/documents/{doc_id}/amendments/* routes.

Uses the same in-memory SQLite + ASGI fixture pattern as test_documents.py.
Each test gets a fresh HTTP client backed by a rolled-back DB session.

Coverage:
  POST /api/organisations/{slug}/documents/{doc_id}/amendments
      — any member can submit; unauthenticated/non-member get 401/404
  GET  /api/organisations/{slug}/documents/{doc_id}/amendments
      — any member can list; paginated
  GET  /api/organisations/{slug}/documents/{doc_id}/amendments/{amendment_id}
      — any member can fetch one
  PUT  /api/organisations/{slug}/documents/{doc_id}/amendments/{amendment_id}/status
      — owner/admin only; member gets 403; non-member gets 404
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


async def _create_doc(client: AsyncClient, jwt: str, slug: str, title: str = "Test Doc") -> dict:
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


async def _create_amendment(
    client: AsyncClient,
    jwt: str,
    slug: str,
    doc_id: str,
    original_text: str = "Original passage",
    proposed_text: str = "Proposed replacement",
) -> dict:
    """
    Submit an amendment and return its response dict.

    Parameters:
        client: Test HTTP client.
        jwt: Bearer token for the submitting user.
        slug: Organisation slug.
        doc_id: Document UUID.
        original_text: Text being amended.
        proposed_text: Replacement text.

    Returns:
        Amendment response dict from the API.
    """
    res = await client.post(
        f"/api/organisations/{slug}/documents/{doc_id}/amendments",
        json={"original_text": original_text, "proposed_text": proposed_text},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 201
    return res.json()


# ---------------------------------------------------------------------------
# POST /api/organisations/{slug}/documents/{doc_id}/amendments
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_amendment_success(client):
    """Owner can submit an amendment — returns 201 with correct fields."""
    jwt = await _register_and_login(client, "amend_create@example.com")
    await _create_org(client, jwt, "amend-create-org")
    doc = await _create_doc(client, jwt, "amend-create-org")

    res = await client.post(
        f"/api/organisations/amend-create-org/documents/{doc['id']}/amendments",
        json={
            "original_text": "The quick brown fox",
            "proposed_text": "A swift auburn fox",
            "justification": "More precise language",
            "section": "Preamble",
        },
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["original_text"] == "The quick brown fox"
    assert data["proposed_text"] == "A swift auburn fox"
    assert data["justification"] == "More precise language"
    assert data["section"] == "Preamble"
    assert data["status"] == "pending"
    assert data["doc_id"] == doc["id"]
    assert "id" in data
    assert "author_id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_amendment_minimal(client):
    """Submitting an amendment without optional fields is allowed."""
    jwt = await _register_and_login(client, "amend_minimal@example.com")
    await _create_org(client, jwt, "amend-minimal-org")
    doc = await _create_doc(client, jwt, "amend-minimal-org")

    res = await client.post(
        f"/api/organisations/amend-minimal-org/documents/{doc['id']}/amendments",
        json={"original_text": "Old text", "proposed_text": "New text"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["section"] is None
    assert data["justification"] is None
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_create_amendment_unauthenticated(client):
    """Submitting without a token returns 401 or 403."""
    res = await client.post(
        "/api/organisations/some-org/documents/some-doc/amendments",
        json={"original_text": "a", "proposed_text": "b"},
    )
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_amendment_non_member_returns_404(client):
    """A user not in the org gets 404 when submitting an amendment."""
    jwt_owner = await _register_and_login(client, "amend_owner_nm@example.com")
    await _create_org(client, jwt_owner, "amend-nm-org")
    doc = await _create_doc(client, jwt_owner, "amend-nm-org")

    jwt_outsider = await _register_and_login(client, "amend_out_nm@example.com")
    res = await client.post(
        f"/api/organisations/amend-nm-org/documents/{doc['id']}/amendments",
        json={"original_text": "a", "proposed_text": "b"},
        headers={"Authorization": f"Bearer {jwt_outsider}"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_create_amendment_doc_not_found(client):
    """Creating an amendment for a non-existent doc returns 404."""
    jwt = await _register_and_login(client, "amend_nodoc@example.com")
    await _create_org(client, jwt, "amend-nodoc-org")

    res = await client.post(
        "/api/organisations/amend-nodoc-org/documents/00000000-0000-0000-0000-000000000000/amendments",
        json={"original_text": "a", "proposed_text": "b"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_create_amendment_empty_text_returns_422(client):
    """Submitting empty original_text returns 422."""
    jwt = await _register_and_login(client, "amend_empty@example.com")
    await _create_org(client, jwt, "amend-empty-org")
    doc = await _create_doc(client, jwt, "amend-empty-org")

    res = await client.post(
        f"/api/organisations/amend-empty-org/documents/{doc['id']}/amendments",
        json={"original_text": "   ", "proposed_text": "New text"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/organisations/{slug}/documents/{doc_id}/amendments
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_amendments_empty(client):
    """New document has no amendments — list returns empty items with total=0."""
    jwt = await _register_and_login(client, "amend_list_empty@example.com")
    await _create_org(client, jwt, "amend-list-empty-org")
    doc = await _create_doc(client, jwt, "amend-list-empty-org")

    res = await client.get(
        f"/api/organisations/amend-list-empty-org/documents/{doc['id']}/amendments",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["page_size"] == 20


@pytest.mark.asyncio
async def test_list_amendments_after_create(client):
    """After submitting an amendment the list includes it."""
    jwt = await _register_and_login(client, "amend_list_after@example.com")
    await _create_org(client, jwt, "amend-listafter-org")
    doc = await _create_doc(client, jwt, "amend-listafter-org")
    await _create_amendment(client, jwt, "amend-listafter-org", doc["id"])

    res = await client.get(
        f"/api/organisations/amend-listafter-org/documents/{doc['id']}/amendments",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["original_text"] == "Original passage"


@pytest.mark.asyncio
async def test_list_amendments_pagination(client):
    """Pagination returns correct slices and total count."""
    jwt = await _register_and_login(client, "amend_paginate@example.com")
    await _create_org(client, jwt, "amend-paginate-org")
    doc = await _create_doc(client, jwt, "amend-paginate-org")

    for i in range(25):
        await _create_amendment(
            client, jwt, "amend-paginate-org", doc["id"],
            original_text=f"Original {i:02d}", proposed_text=f"Proposed {i:02d}"
        )

    res1 = await client.get(
        f"/api/organisations/amend-paginate-org/documents/{doc['id']}/amendments?page=1",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res1.status_code == 200
    d1 = res1.json()
    assert d1["total"] == 25
    assert len(d1["items"]) == 20

    res2 = await client.get(
        f"/api/organisations/amend-paginate-org/documents/{doc['id']}/amendments?page=2",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res2.status_code == 200
    d2 = res2.json()
    assert len(d2["items"]) == 5


@pytest.mark.asyncio
async def test_list_amendments_unauthenticated(client):
    """Listing without a token returns 401 or 403."""
    res = await client.get("/api/organisations/some-org/documents/some-doc/amendments")
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_amendments_non_member_returns_404(client):
    """Non-member gets 404 on amendment list."""
    jwt_owner = await _register_and_login(client, "amend_list_owner@example.com")
    await _create_org(client, jwt_owner, "amend-listnm-org")
    doc = await _create_doc(client, jwt_owner, "amend-listnm-org")

    jwt_outsider = await _register_and_login(client, "amend_list_out@example.com")
    res = await client.get(
        f"/api/organisations/amend-listnm-org/documents/{doc['id']}/amendments",
        headers={"Authorization": f"Bearer {jwt_outsider}"},
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/organisations/{slug}/documents/{doc_id}/amendments/{amendment_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_amendment_success(client):
    """Owner can fetch an amendment by ID."""
    jwt = await _register_and_login(client, "amend_get@example.com")
    await _create_org(client, jwt, "amend-get-org")
    doc = await _create_doc(client, jwt, "amend-get-org")
    a = await _create_amendment(client, jwt, "amend-get-org", doc["id"])

    res = await client.get(
        f"/api/organisations/amend-get-org/documents/{doc['id']}/amendments/{a['id']}",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    assert res.json()["id"] == a["id"]


@pytest.mark.asyncio
async def test_get_amendment_not_found(client):
    """Fetching a non-existent amendment ID returns 404."""
    jwt = await _register_and_login(client, "amend_nf@example.com")
    await _create_org(client, jwt, "amend-nf-org")
    doc = await _create_doc(client, jwt, "amend-nf-org")

    res = await client.get(
        f"/api/organisations/amend-nf-org/documents/{doc['id']}/amendments/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_amendment_non_member_returns_404(client):
    """Non-member gets 404 when fetching an amendment."""
    jwt_owner = await _register_and_login(client, "amend_getnm_owner@example.com")
    await _create_org(client, jwt_owner, "amend-getnm-org")
    doc = await _create_doc(client, jwt_owner, "amend-getnm-org")
    a = await _create_amendment(client, jwt_owner, "amend-getnm-org", doc["id"])

    jwt_outsider = await _register_and_login(client, "amend_getnm_out@example.com")
    res = await client.get(
        f"/api/organisations/amend-getnm-org/documents/{doc['id']}/amendments/{a['id']}",
        headers={"Authorization": f"Bearer {jwt_outsider}"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_amendment_unauthenticated(client):
    """Fetching an amendment without a token returns 401 or 403."""
    res = await client.get("/api/organisations/some-org/documents/some-doc/amendments/some-id")
    assert res.status_code in (401, 403)


# ---------------------------------------------------------------------------
# PUT /api/organisations/{slug}/documents/{doc_id}/amendments/{amendment_id}/status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_accept_amendment(client):
    """Owner can accept an amendment — status changes to 'accepted'."""
    jwt = await _register_and_login(client, "amend_accept@example.com")
    await _create_org(client, jwt, "amend-accept-org")
    doc = await _create_doc(client, jwt, "amend-accept-org")
    a = await _create_amendment(client, jwt, "amend-accept-org", doc["id"])

    res = await client.put(
        f"/api/organisations/amend-accept-org/documents/{doc['id']}/amendments/{a['id']}/status",
        json={"status": "accepted"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "accepted"


@pytest.mark.asyncio
async def test_reject_amendment(client):
    """Owner can reject an amendment — status changes to 'rejected'."""
    jwt = await _register_and_login(client, "amend_reject@example.com")
    await _create_org(client, jwt, "amend-reject-org")
    doc = await _create_doc(client, jwt, "amend-reject-org")
    a = await _create_amendment(client, jwt, "amend-reject-org", doc["id"])

    res = await client.put(
        f"/api/organisations/amend-reject-org/documents/{doc['id']}/amendments/{a['id']}/status",
        json={"status": "rejected"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_status_invalid_value_returns_422(client):
    """Sending an invalid status value returns 422."""
    jwt = await _register_and_login(client, "amend_invalid_status@example.com")
    await _create_org(client, jwt, "amend-invalid-status-org")
    doc = await _create_doc(client, jwt, "amend-invalid-status-org")
    a = await _create_amendment(client, jwt, "amend-invalid-status-org", doc["id"])

    res = await client.put(
        f"/api/organisations/amend-invalid-status-org/documents/{doc['id']}/amendments/{a['id']}/status",
        json={"status": "pending"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_status_update_unauthenticated(client):
    """Status update without a token returns 401 or 403."""
    res = await client.put(
        "/api/organisations/some-org/documents/some-doc/amendments/some-id/status",
        json={"status": "accepted"},
    )
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_status_update_non_member_returns_404(client):
    """Non-member gets 404 when trying to update status."""
    jwt_owner = await _register_and_login(client, "amend_stat_owner@example.com")
    await _create_org(client, jwt_owner, "amend-statnm-org")
    doc = await _create_doc(client, jwt_owner, "amend-statnm-org")
    a = await _create_amendment(client, jwt_owner, "amend-statnm-org", doc["id"])

    jwt_outsider = await _register_and_login(client, "amend_stat_out@example.com")
    res = await client.put(
        f"/api/organisations/amend-statnm-org/documents/{doc['id']}/amendments/{a['id']}/status",
        json={"status": "accepted"},
        headers={"Authorization": f"Bearer {jwt_outsider}"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_status_update_amendment_not_found(client):
    """Updating status on a non-existent amendment returns 404."""
    jwt = await _register_and_login(client, "amend_stat_nf@example.com")
    await _create_org(client, jwt, "amend-statnf-org")
    doc = await _create_doc(client, jwt, "amend-statnf-org")

    res = await client.put(
        f"/api/organisations/amend-statnf-org/documents/{doc['id']}/amendments/00000000-0000-0000-0000-000000000000/status",
        json={"status": "accepted"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 404
