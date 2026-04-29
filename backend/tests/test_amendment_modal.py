"""
Amendment modal endpoint tests — focused on GET /{amendment_id} returning the correct
fields required by the amendment detail modal (session 66).

Coverage:
  GET /api/organisations/{slug}/documents/{doc_id}/amendments/{amendment_id}
      — returns all required fields: id, doc_id, amendment_type, section,
        original_text, proposed_text, justification, status, author_id,
        author_name, author_email, decision_reason, created_at
      — decision_reason is populated after accept/reject
      — author_name and author_email are returned for the amendment author
      — non-member returns 404
      — non-existent amendment returns 404
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.auth import _magic_link_store
from app.core.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Fixtures
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
    """Yield a fresh AsyncSession for each test, rolled back after."""
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


async def _submit_amendment(
    client: AsyncClient,
    jwt: str,
    slug: str,
    doc_id: str,
    original_text: str = "The current text",
    proposed_text: str = "The improved text",
    justification: str | None = "Better wording",
    section: str | None = "Article 1",
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
        justification: Optional justification.
        section: Optional section reference.

    Returns:
        Amendment response dict from the API.
    """
    res = await client.post(
        f"/api/organisations/{slug}/documents/{doc_id}/amendments",
        json={
            "original_text": original_text,
            "proposed_text": proposed_text,
            "justification": justification,
            "section": section,
        },
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 201
    return res.json()


# ---------------------------------------------------------------------------
# Tests — GET /{amendment_id} field completeness
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_amendment_returns_required_fields(client):
    """GET /{amendment_id} returns all fields required by the detail modal."""
    jwt = await _register_and_login(client, "modal_fields@example.com")
    await _create_org(client, jwt, "modal-fields-org")
    doc = await _create_doc(client, jwt, "modal-fields-org")
    amendment = await _submit_amendment(client, jwt, "modal-fields-org", doc["id"])

    res = await client.get(
        f"/api/organisations/modal-fields-org/documents/{doc['id']}/amendments/{amendment['id']}",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    data = res.json()

    # Core identity fields
    assert data["id"] == amendment["id"]
    assert data["doc_id"] == doc["id"]
    assert data["amendment_type"] == "text_change"
    assert data["status"] == "pending"

    # Content fields
    assert data["original_text"] == "The current text"
    assert data["proposed_text"] == "The improved text"
    assert data["justification"] == "Better wording"
    assert data["section"] == "Article 1"

    # decision_reason is None for pending amendments
    assert data["decision_reason"] is None

    # Timestamps
    assert "created_at" in data
    assert data["created_at"]  # non-empty ISO-8601 string

    # Author fields — populated from the submitting user
    assert "author_id" in data
    assert data["author_id"] is not None
    assert "author_email" in data
    assert data["author_email"] == "modal_fields@example.com"
    assert "author_name" in data  # may be None if user has no display name set


@pytest.mark.asyncio
async def test_get_amendment_decision_reason_after_accept(client):
    """decision_reason is returned after an owner accepts an amendment."""
    jwt = await _register_and_login(client, "modal_accept@example.com")
    await _create_org(client, jwt, "modal-accept-org")
    doc = await _create_doc(client, jwt, "modal-accept-org")
    amendment = await _submit_amendment(client, jwt, "modal-accept-org", doc["id"])

    # Accept with a reason
    accept_res = await client.put(
        f"/api/organisations/modal-accept-org/documents/{doc['id']}/amendments/{amendment['id']}/status",
        json={"status": "accepted", "decision_reason": "Well argued, approved."},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert accept_res.status_code == 200

    # Fetch the amendment and verify decision_reason is present
    res = await client.get(
        f"/api/organisations/modal-accept-org/documents/{doc['id']}/amendments/{amendment['id']}",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "accepted"
    assert data["decision_reason"] == "Well argued, approved."
    assert data["author_id"] is not None
    assert data["author_email"] == "modal_accept@example.com"


@pytest.mark.asyncio
async def test_get_amendment_decision_reason_after_reject(client):
    """decision_reason is returned after an owner rejects an amendment."""
    jwt = await _register_and_login(client, "modal_reject@example.com")
    await _create_org(client, jwt, "modal-reject-org")
    doc = await _create_doc(client, jwt, "modal-reject-org")
    amendment = await _submit_amendment(client, jwt, "modal-reject-org", doc["id"])

    reject_res = await client.put(
        f"/api/organisations/modal-reject-org/documents/{doc['id']}/amendments/{amendment['id']}/status",
        json={"status": "rejected", "decision_reason": "Out of scope for this revision."},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert reject_res.status_code == 200

    res = await client.get(
        f"/api/organisations/modal-reject-org/documents/{doc['id']}/amendments/{amendment['id']}",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "rejected"
    assert data["decision_reason"] == "Out of scope for this revision."


@pytest.mark.asyncio
async def test_get_amendment_decision_reason_none_when_not_set(client):
    """decision_reason is None when the status is changed without a reason."""
    jwt = await _register_and_login(client, "modal_noreason@example.com")
    await _create_org(client, jwt, "modal-noreason-org")
    doc = await _create_doc(client, jwt, "modal-noreason-org")
    amendment = await _submit_amendment(client, jwt, "modal-noreason-org", doc["id"])

    await client.put(
        f"/api/organisations/modal-noreason-org/documents/{doc['id']}/amendments/{amendment['id']}/status",
        json={"status": "accepted"},
        headers={"Authorization": f"Bearer {jwt}"},
    )

    res = await client.get(
        f"/api/organisations/modal-noreason-org/documents/{doc['id']}/amendments/{amendment['id']}",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "accepted"
    assert data["decision_reason"] is None


@pytest.mark.asyncio
async def test_get_amendment_author_email_matches_submitter(client):
    """author_email in the GET response matches the email of the user who submitted."""
    jwt = await _register_and_login(client, "modal_author_check@example.com")
    await _create_org(client, jwt, "modal-author-org")
    doc = await _create_doc(client, jwt, "modal-author-org")
    amendment = await _submit_amendment(client, jwt, "modal-author-org", doc["id"])

    res = await client.get(
        f"/api/organisations/modal-author-org/documents/{doc['id']}/amendments/{amendment['id']}",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["author_email"] == "modal_author_check@example.com"
    assert data["author_id"] is not None


@pytest.mark.asyncio
async def test_get_amendment_non_member_returns_404(client):
    """Non-member receives 404 for GET /{amendment_id}."""
    jwt_owner = await _register_and_login(client, "modal_nm_owner@example.com")
    await _create_org(client, jwt_owner, "modal-nm-org")
    doc = await _create_doc(client, jwt_owner, "modal-nm-org")
    amendment = await _submit_amendment(client, jwt_owner, "modal-nm-org", doc["id"])

    jwt_outsider = await _register_and_login(client, "modal_nm_outsider@example.com")
    res = await client.get(
        f"/api/organisations/modal-nm-org/documents/{doc['id']}/amendments/{amendment['id']}",
        headers={"Authorization": f"Bearer {jwt_outsider}"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_amendment_not_found_returns_404(client):
    """Non-existent amendment ID returns 404."""
    jwt = await _register_and_login(client, "modal_nf@example.com")
    await _create_org(client, jwt, "modal-nf-org")
    doc = await _create_doc(client, jwt, "modal-nf-org")

    res = await client.get(
        f"/api/organisations/modal-nf-org/documents/{doc['id']}/amendments/00000000-0000-0000-0000-000000000099",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 404
