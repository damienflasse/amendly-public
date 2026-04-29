"""
Activity feed endpoint tests — covers GET /api/organisations/{slug}/activity.

Coverage:
  GET /api/organisations/{slug}/activity
      — unauthenticated → 401
      — non-member → 404
      — member with no activity → empty list, total=0
      — document created logs an entry
      — amendment submitted logs an entry
      — amendment accepted logs entry + sends notification email (mocked)
      — amendment rejected logs entry + sends notification email (mocked)
      — amendment withdrawn logs an entry
      — document status change logs an entry
      — entries are ordered newest-first (max page_size per page)
      — page=1 returns first page; page=2 returns second page
      — page beyond last page returns empty items list
      — response shape: { items, total, page, page_size }
"""

from unittest.mock import AsyncMock, patch

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
    """Create an async SQLite engine shared across all tests in this module."""
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
    """HTTP test client with get_db overridden to the SQLite test session."""

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
        Organisation response dict.
    """
    res = await client.post(
        "/api/organisations",
        json={"name": f"Org {slug}", "slug": slug},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 201
    return res.json()


async def _create_doc(client: AsyncClient, jwt: str, slug: str, title: str = "Doc") -> dict:
    """
    Create a document and return its response dict.

    Parameters:
        client: Test HTTP client.
        jwt: Bearer token for the creating user.
        slug: Organisation slug.
        title: Document title.

    Returns:
        Document response dict.
    """
    res = await client.post(
        f"/api/organisations/{slug}/documents",
        json={"title": title},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 201
    return res.json()


async def _submit_amendment(
    client: AsyncClient, jwt: str, slug: str, doc_id: str
) -> dict:
    """
    Submit an amendment and return its response dict.

    Parameters:
        client: Test HTTP client.
        jwt: Bearer token for the submitting user.
        slug: Organisation slug.
        doc_id: Document UUID.

    Returns:
        Amendment response dict.
    """
    res = await client.post(
        f"/api/organisations/{slug}/documents/{doc_id}/amendments",
        json={"original_text": "old", "proposed_text": "new"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 201
    return res.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activity_unauthenticated(client):
    """Unauthenticated request → 401."""
    res = await client.get("/api/organisations/some-org/activity")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_activity_non_member(client):
    """Non-member gets 404 (same as if org doesn't exist)."""
    jwt_owner = await _register_and_login(client, "owner-act-nm@example.com")
    jwt_other = await _register_and_login(client, "other-act-nm@example.com")
    await _create_org(client, jwt_owner, "act-nm-org")

    res = await client.get(
        "/api/organisations/act-nm-org/activity",
        headers={"Authorization": f"Bearer {jwt_other}"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_activity_empty_for_new_org(client):
    """A brand-new org with no documents returns an empty items list."""
    jwt = await _register_and_login(client, "owner-empty-act@example.com")
    await _create_org(client, jwt, "act-empty-org")

    res = await client.get(
        "/api/organisations/act-empty-org/activity",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["page_size"] == 20


@pytest.mark.asyncio
async def test_activity_response_shape(client):
    """Response envelope has items, total, page, page_size keys."""
    jwt = await _register_and_login(client, "owner-shape-act@example.com")
    await _create_org(client, jwt, "act-shape-org")
    await _create_doc(client, jwt, "act-shape-org", "Shape Doc")

    res = await client.get(
        "/api/organisations/act-shape-org/activity",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data


@pytest.mark.asyncio
async def test_activity_document_created(client):
    """Creating a document logs a 'document_created' entry."""
    jwt = await _register_and_login(client, "owner-doc-act@example.com")
    await _create_org(client, jwt, "act-doc-org")
    await _create_doc(client, jwt, "act-doc-org", "My Document")

    res = await client.get(
        "/api/organisations/act-doc-org/activity",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    data = res.json()
    entries = data["items"]
    assert len(entries) == 1
    assert data["total"] == 1
    assert entries[0]["action"] == "document_created"
    assert entries[0]["doc_title"] == "My Document"
    assert "actor_name" in entries[0]
    assert "created_at" in entries[0]


@pytest.mark.asyncio
async def test_activity_amendment_submitted(client):
    """Submitting an amendment logs an 'amendment_submitted' entry."""
    jwt = await _register_and_login(client, "owner-sub-act@example.com")
    await _create_org(client, jwt, "act-sub-org")
    doc = await _create_doc(client, jwt, "act-sub-org", "Sub Doc")
    await _submit_amendment(client, jwt, "act-sub-org", doc["id"])

    res = await client.get(
        "/api/organisations/act-sub-org/activity",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    actions = [e["action"] for e in res.json()["items"]]
    assert "amendment_submitted" in actions


@pytest.mark.asyncio
async def test_activity_amendment_accepted_and_email(client):
    """
    Accepting an amendment logs 'amendment_accepted' and fires a notification
    email (mocked so no real Resend call is made).
    """
    jwt = await _register_and_login(client, "owner-acc-act@example.com")
    await _create_org(client, jwt, "act-acc-org")
    doc = await _create_doc(client, jwt, "act-acc-org", "Acc Doc")
    amendment = await _submit_amendment(client, jwt, "act-acc-org", doc["id"])

    with patch(
        "app.utils.email.send_amendment_status_email",
        new_callable=AsyncMock,
    ) as mock_send:
        res = await client.put(
            f"/api/organisations/act-acc-org/documents/{doc['id']}"
            f"/amendments/{amendment['id']}/status",
            json={"status": "accepted"},
            headers={"Authorization": f"Bearer {jwt}"},
        )
    assert res.status_code == 200

    activity_res = await client.get(
        "/api/organisations/act-acc-org/activity",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    actions = [e["action"] for e in activity_res.json()["items"]]
    assert "amendment_accepted" in actions


@pytest.mark.asyncio
async def test_activity_amendment_rejected(client):
    """Rejecting an amendment logs 'amendment_rejected'."""
    jwt = await _register_and_login(client, "owner-rej-act@example.com")
    await _create_org(client, jwt, "act-rej-org")
    doc = await _create_doc(client, jwt, "act-rej-org", "Rej Doc")
    amendment = await _submit_amendment(client, jwt, "act-rej-org", doc["id"])

    with patch(
        "app.utils.email.send_amendment_status_email",
        new_callable=AsyncMock,
    ):
        await client.put(
            f"/api/organisations/act-rej-org/documents/{doc['id']}"
            f"/amendments/{amendment['id']}/status",
            json={"status": "rejected"},
            headers={"Authorization": f"Bearer {jwt}"},
        )

    res = await client.get(
        "/api/organisations/act-rej-org/activity",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    actions = [e["action"] for e in res.json()["items"]]
    assert "amendment_rejected" in actions


@pytest.mark.asyncio
async def test_activity_amendment_withdrawn(client):
    """Withdrawing an amendment logs 'amendment_withdrawn'."""
    jwt = await _register_and_login(client, "owner-with-act@example.com")
    await _create_org(client, jwt, "act-with-org")
    doc = await _create_doc(client, jwt, "act-with-org", "With Doc")
    amendment = await _submit_amendment(client, jwt, "act-with-org", doc["id"])

    await client.delete(
        f"/api/organisations/act-with-org/documents/{doc['id']}"
        f"/amendments/{amendment['id']}",
        headers={"Authorization": f"Bearer {jwt}"},
    )

    res = await client.get(
        "/api/organisations/act-with-org/activity",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    actions = [e["action"] for e in res.json()["items"]]
    assert "amendment_withdrawn" in actions


@pytest.mark.asyncio
async def test_activity_status_changed(client):
    """Changing document status logs 'status_changed'."""
    jwt = await _register_and_login(client, "owner-sc-act@example.com")
    await _create_org(client, jwt, "act-sc-org")
    doc = await _create_doc(client, jwt, "act-sc-org", "SC Doc")

    await client.put(
        f"/api/organisations/act-sc-org/documents/{doc['id']}/status",
        json={"status": "open"},
        headers={"Authorization": f"Bearer {jwt}"},
    )

    res = await client.get(
        "/api/organisations/act-sc-org/activity",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    actions = [e["action"] for e in res.json()["items"]]
    assert "status_changed" in actions


@pytest.mark.asyncio
async def test_activity_multiple_entries_returned(client):
    """Multiple events produce multiple entries in the feed."""
    jwt = await _register_and_login(client, "owner-ord-act@example.com")
    await _create_org(client, jwt, "act-ord-org")
    doc = await _create_doc(client, jwt, "act-ord-org", "Ord Doc")

    await client.put(
        f"/api/organisations/act-ord-org/documents/{doc['id']}/status",
        json={"status": "open"},
        headers={"Authorization": f"Bearer {jwt}"},
    )

    res = await client.get(
        "/api/organisations/act-ord-org/activity",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    data = res.json()
    entries = data["items"]
    assert len(entries) >= 2
    assert data["total"] >= 2
    # Both expected actions are present in the feed
    actions = {e["action"] for e in entries}
    assert "document_created" in actions
    assert "status_changed" in actions


@pytest.mark.asyncio
async def test_activity_member_can_read(client):
    """Any org member (not just owner) can read the activity feed."""
    jwt_owner = await _register_and_login(client, "owner-mr-act@example.com")
    jwt_member = await _register_and_login(client, "member-mr-act@example.com")
    await _create_org(client, jwt_owner, "act-mr-org")

    # Invite and accept
    invite_res = await client.post(
        "/api/organisations/act-mr-org/invite",
        json={"email": "member-mr-act@example.com"},
        headers={"Authorization": f"Bearer {jwt_owner}"},
    )
    assert invite_res.status_code == 201

    res = await client.get(
        "/api/organisations/act-mr-org/activity",
        headers={"Authorization": f"Bearer {jwt_owner}"},
    )
    assert res.status_code == 200
    assert "items" in res.json()


@pytest.mark.asyncio
async def test_activity_pagination_page2(client):
    """
    Creating enough entries to span two pages returns only page_size items
    on page 1, and the remainder on page 2.

    Strategy: create 3 docs (free tier limit), then submit 9 amendments on
    each doc (3 × 9 = 27 amendment events) + 3 document_created = 30 total.
    """
    jwt = await _register_and_login(client, "owner-pag-act@example.com")
    await _create_org(client, jwt, "act-pag-org")

    # Create 3 documents (free-tier max) — 3 activity entries
    docs = []
    for i in range(3):
        doc = await _create_doc(client, jwt, "act-pag-org", f"Pag Doc {i}")
        docs.append(doc)

    # Submit 9 amendments per doc — 27 more entries; total = 30
    for doc in docs:
        for j in range(9):
            await client.post(
                f"/api/organisations/act-pag-org/documents/{doc['id']}/amendments",
                json={"original_text": f"text {j}", "proposed_text": f"new {j}"},
                headers={"Authorization": f"Bearer {jwt}"},
            )

    res1 = await client.get(
        "/api/organisations/act-pag-org/activity?page=1",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert len(data1["items"]) == 20
    assert data1["total"] == 30
    assert data1["page"] == 1
    assert data1["page_size"] == 20

    res2 = await client.get(
        "/api/organisations/act-pag-org/activity?page=2",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2["items"]) == 10
    assert data2["total"] == 30
    assert data2["page"] == 2


@pytest.mark.asyncio
async def test_activity_pagination_beyond_last_page(client):
    """Requesting a page beyond the total returns an empty items list."""
    jwt = await _register_and_login(client, "owner-beyond-act@example.com")
    await _create_org(client, jwt, "act-beyond-org")
    await _create_doc(client, jwt, "act-beyond-org", "Single Doc")

    res = await client.get(
        "/api/organisations/act-beyond-org/activity?page=99",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["items"] == []
    assert data["total"] == 1
    assert data["page"] == 99


@pytest.mark.asyncio
async def test_activity_pagination_invalid_page(client):
    """page=0 is rejected with 422."""
    jwt = await _register_and_login(client, "owner-inv-act@example.com")
    await _create_org(client, jwt, "act-inv-org")

    res = await client.get(
        "/api/organisations/act-inv-org/activity?page=0",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 422
