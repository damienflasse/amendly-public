"""
Consolidation endpoint tests — covers GET /api/organisations/{slug}/documents/{id}/consolidated.

Uses the same in-memory SQLite + ASGI fixture pattern as other test modules.
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
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
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
    await client.post("/api/auth/magic-link/request", json={"email": email})
    token = next(t for t, v in _magic_link_store.items() if v["email"] == email)
    res = await client.post("/api/auth/magic-link/verify", json={"token": token})
    return res.json()["access_token"]


async def _setup(client: AsyncClient, slug: str, email: str):
    """Create a user, org, and document; return (jwt, headers, doc_id)."""
    jwt = await _register_and_login(client, email)
    headers = {"Authorization": f"Bearer {jwt}"}
    await client.post(
        "/api/organisations",
        json={"name": slug.title(), "slug": slug},
        headers=headers,
    )
    doc_res = await client.post(
        f"/api/organisations/{slug}/documents",
        json={"title": "Test Doc", "body": "The quick brown fox jumped over the lazy dog."},
        headers=headers,
    )
    doc_id = doc_res.json()["id"]
    return jwt, headers, doc_id


# ---------------------------------------------------------------------------
# GET .../consolidated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_consolidated_no_amendments(client):
    """With no accepted amendments the body is returned unchanged."""
    _, headers, doc_id = await _setup(client, "con-org-1", "con1@example.com")

    res = await client.get(
        f"/api/organisations/con-org-1/documents/{doc_id}/consolidated",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Test Doc"
    assert "quick" in data["body_with_amendments_applied"]
    assert data["amendments_applied"] == 0


@pytest.mark.asyncio
async def test_consolidated_applies_accepted_amendment(client):
    """An accepted amendment replaces its original_text with proposed_text."""
    _, headers, doc_id = await _setup(client, "con-org-2", "con2@example.com")

    # Submit an amendment
    amend_res = await client.post(
        f"/api/organisations/con-org-2/documents/{doc_id}/amendments",
        json={
            "original_text": "quick brown fox",
            "proposed_text": "swift red fox",
        },
        headers=headers,
    )
    assert amend_res.status_code == 201
    amendment_id = amend_res.json()["id"]

    # Accept it
    accept_res = await client.put(
        f"/api/organisations/con-org-2/documents/{doc_id}/amendments/{amendment_id}/status",
        json={"status": "accepted"},
        headers=headers,
    )
    assert accept_res.status_code == 200

    # Check consolidated
    res = await client.get(
        f"/api/organisations/con-org-2/documents/{doc_id}/consolidated",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert "swift red fox" in data["body_with_amendments_applied"]
    assert "quick brown fox" not in data["body_with_amendments_applied"]
    assert data["amendments_applied"] == 1


@pytest.mark.asyncio
async def test_consolidated_ignores_pending_amendments(client):
    """Pending amendments are not applied in the consolidated view."""
    _, headers, doc_id = await _setup(client, "con-org-3", "con3@example.com")

    # Submit a pending amendment (do not accept it)
    await client.post(
        f"/api/organisations/con-org-3/documents/{doc_id}/amendments",
        json={
            "original_text": "quick brown fox",
            "proposed_text": "slow white cat",
        },
        headers=headers,
    )

    res = await client.get(
        f"/api/organisations/con-org-3/documents/{doc_id}/consolidated",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert "quick brown fox" in data["body_with_amendments_applied"]
    assert "slow white cat" not in data["body_with_amendments_applied"]
    assert data["amendments_applied"] == 0


@pytest.mark.asyncio
async def test_consolidated_ignores_rejected_amendments(client):
    """Rejected amendments are not applied in the consolidated view."""
    _, headers, doc_id = await _setup(client, "con-org-4", "con4@example.com")

    amend_res = await client.post(
        f"/api/organisations/con-org-4/documents/{doc_id}/amendments",
        json={
            "original_text": "lazy dog",
            "proposed_text": "energetic rabbit",
        },
        headers=headers,
    )
    amendment_id = amend_res.json()["id"]

    # Reject it
    await client.put(
        f"/api/organisations/con-org-4/documents/{doc_id}/amendments/{amendment_id}/status",
        json={"status": "rejected"},
        headers=headers,
    )

    res = await client.get(
        f"/api/organisations/con-org-4/documents/{doc_id}/consolidated",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert "lazy dog" in data["body_with_amendments_applied"]
    assert "energetic rabbit" not in data["body_with_amendments_applied"]
    assert data["amendments_applied"] == 0


@pytest.mark.asyncio
async def test_consolidated_multiple_amendments_applied_in_order(client):
    """Multiple accepted amendments are applied oldest-first."""
    _, headers, doc_id = await _setup(client, "con-org-5", "con5@example.com")

    # Amendment 1: replace "quick"
    amend1 = await client.post(
        f"/api/organisations/con-org-5/documents/{doc_id}/amendments",
        json={"original_text": "quick", "proposed_text": "nimble"},
        headers=headers,
    )
    a1_id = amend1.json()["id"]

    # Amendment 2: replace "lazy"
    amend2 = await client.post(
        f"/api/organisations/con-org-5/documents/{doc_id}/amendments",
        json={"original_text": "lazy", "proposed_text": "sleepy"},
        headers=headers,
    )
    a2_id = amend2.json()["id"]

    # Accept both
    await client.put(
        f"/api/organisations/con-org-5/documents/{doc_id}/amendments/{a1_id}/status",
        json={"status": "accepted"},
        headers=headers,
    )
    await client.put(
        f"/api/organisations/con-org-5/documents/{doc_id}/amendments/{a2_id}/status",
        json={"status": "accepted"},
        headers=headers,
    )

    res = await client.get(
        f"/api/organisations/con-org-5/documents/{doc_id}/consolidated",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    body = data["body_with_amendments_applied"]
    assert "nimble" in body
    assert "sleepy" in body
    assert "quick" not in body
    assert "lazy" not in body
    assert data["amendments_applied"] == 2


@pytest.mark.asyncio
async def test_consolidated_not_found_returns_404(client):
    """Non-existent document returns 404."""
    _, headers, _ = await _setup(client, "con-org-6", "con6@example.com")

    res = await client.get(
        "/api/organisations/con-org-6/documents/nonexistent-id/consolidated",
        headers=headers,
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_consolidated_non_member_returns_404(client):
    """Non-member cannot access the consolidated endpoint (404, not 403)."""
    _, headers, doc_id = await _setup(client, "con-org-7", "con7owner@example.com")
    outsider_jwt = await _register_and_login(client, "con7outsider@example.com")
    outsider_headers = {"Authorization": f"Bearer {outsider_jwt}"}

    res = await client.get(
        f"/api/organisations/con-org-7/documents/{doc_id}/consolidated",
        headers=outsider_headers,
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_consolidated_unauthenticated_returns_401(client):
    """Unauthenticated request returns 401."""
    res = await client.get(
        "/api/organisations/some-org/documents/some-doc/consolidated"
    )
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_consolidated_empty_body(client):
    """Document with no body returns empty string after consolidation."""
    jwt = await _register_and_login(client, "con8@example.com")
    headers = {"Authorization": f"Bearer {jwt}"}
    await client.post(
        "/api/organisations",
        json={"name": "Con Org Eight", "slug": "con-org-8"},
        headers=headers,
    )
    doc_res = await client.post(
        "/api/organisations/con-org-8/documents",
        json={"title": "No Body Doc"},
        headers=headers,
    )
    doc_id = doc_res.json()["id"]

    res = await client.get(
        f"/api/organisations/con-org-8/documents/{doc_id}/consolidated",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["body_with_amendments_applied"] == ""
    assert data["amendments_applied"] == 0
