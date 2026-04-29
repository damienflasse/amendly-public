"""
Amendment withdraw endpoint tests — covers DELETE …/amendments/{amendment_id}.

Uses the same in-memory SQLite + ASGI fixture pattern as other test files.

Coverage:
  DELETE /api/organisations/{slug}/documents/{doc_id}/amendments/{amendment_id}
      — author can withdraw a pending amendment → 204
      — amendment row stays in DB with status='withdrawn'
      — non-author member gets 403
      — owner (not author) gets 403
      — non-member gets 404
      — non-existent amendment returns 404
      — non-pending amendment (accepted) returns 403
      — unauthenticated returns 401 or 403
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.auth import _magic_link_store
from app.core.database import Base, get_db
from app.main import app
from app.models.invitation import Invitation

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


async def _create_doc(client: AsyncClient, jwt: str, slug: str, title: str = "Withdraw Doc") -> dict:
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


async def _invite_member(
    client: AsyncClient,
    db_session: AsyncSession,
    owner_jwt: str,
    member_jwt: str,
    slug: str,
    member_email: str,
) -> None:
    """
    Invite a user by email and have them accept with their JWT.

    Parameters:
        client: Test HTTP client.
        db_session: Test DB session used to retrieve the invite token.
        owner_jwt: Bearer token for the organisation owner.
        member_jwt: Bearer token for the new member.
        slug: Organisation slug.
        member_email: Email of the user being invited.
    """
    invite_res = await client.post(
        f"/api/organisations/{slug}/invite",
        json={"email": member_email},
        headers={"Authorization": f"Bearer {owner_jwt}"},
    )
    assert invite_res.status_code == 201

    # Fetch the invite token from the DB (same approach as test_invitations.py)
    result = await db_session.execute(
        select(Invitation.token).where(Invitation.email == member_email)
    )
    inv_token = result.scalar_one()

    accept_res = await client.post(
        "/api/invitations/accept",
        json={"token": inv_token},
        headers={"Authorization": f"Bearer {member_jwt}"},
    )
    assert accept_res.status_code == 200


# ---------------------------------------------------------------------------
# DELETE /api/organisations/{slug}/documents/{doc_id}/amendments/{amendment_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_author_can_withdraw_pending_amendment(client):
    """Amendment author can withdraw a pending amendment — returns 204."""
    jwt = await _register_and_login(client, "withdraw_author@example.com")
    await _create_org(client, jwt, "withdraw-author-org")
    doc = await _create_doc(client, jwt, "withdraw-author-org")
    amendment = await _create_amendment(client, jwt, "withdraw-author-org", doc["id"])

    res = await client.delete(
        f"/api/organisations/withdraw-author-org/documents/{doc['id']}/amendments/{amendment['id']}",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_withdrawn_amendment_status_is_withdrawn(client):
    """After withdrawal, fetching the amendment shows status='withdrawn'."""
    jwt = await _register_and_login(client, "withdraw_status@example.com")
    await _create_org(client, jwt, "withdraw-status-org")
    doc = await _create_doc(client, jwt, "withdraw-status-org")
    amendment = await _create_amendment(client, jwt, "withdraw-status-org", doc["id"])

    # Withdraw
    del_res = await client.delete(
        f"/api/organisations/withdraw-status-org/documents/{doc['id']}/amendments/{amendment['id']}",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert del_res.status_code == 204

    # Fetch and verify status
    get_res = await client.get(
        f"/api/organisations/withdraw-status-org/documents/{doc['id']}/amendments/{amendment['id']}",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "withdrawn"


@pytest.mark.asyncio
async def test_non_author_member_cannot_withdraw(client, db_session):
    """A member who is not the author gets 403 when trying to withdraw."""
    jwt_author = await _register_and_login(client, "withdraw_nonauth_author@example.com")
    jwt_other = await _register_and_login(client, "withdraw_nonauth_other@example.com")
    await _create_org(client, jwt_author, "withdraw-nonauth-org")
    doc = await _create_doc(client, jwt_author, "withdraw-nonauth-org")

    # Invite the other user as a member
    await _invite_member(client, db_session, jwt_author, jwt_other, "withdraw-nonauth-org", "withdraw_nonauth_other@example.com")

    # Author submits an amendment
    amendment = await _create_amendment(client, jwt_author, "withdraw-nonauth-org", doc["id"])

    # Other member tries to withdraw it → 403
    res = await client.delete(
        f"/api/organisations/withdraw-nonauth-org/documents/{doc['id']}/amendments/{amendment['id']}",
        headers={"Authorization": f"Bearer {jwt_other}"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_owner_cannot_withdraw_other_users_amendment(client, db_session):
    """An owner who is not the author gets 403 when trying to withdraw."""
    jwt_owner = await _register_and_login(client, "withdraw_owner_na@example.com")
    jwt_member = await _register_and_login(client, "withdraw_member_na@example.com")
    await _create_org(client, jwt_owner, "withdraw-ownerna-org")
    doc = await _create_doc(client, jwt_owner, "withdraw-ownerna-org")

    # Invite the member
    await _invite_member(client, db_session, jwt_owner, jwt_member, "withdraw-ownerna-org", "withdraw_member_na@example.com")

    # Member submits an amendment
    amendment = await _create_amendment(client, jwt_member, "withdraw-ownerna-org", doc["id"])

    # Owner tries to withdraw the member's amendment → 403
    res = await client.delete(
        f"/api/organisations/withdraw-ownerna-org/documents/{doc['id']}/amendments/{amendment['id']}",
        headers={"Authorization": f"Bearer {jwt_owner}"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_cannot_withdraw_accepted_amendment(client):
    """Attempting to withdraw an accepted amendment returns 403."""
    jwt = await _register_and_login(client, "withdraw_accepted@example.com")
    await _create_org(client, jwt, "withdraw-accepted-org")
    doc = await _create_doc(client, jwt, "withdraw-accepted-org")
    amendment = await _create_amendment(client, jwt, "withdraw-accepted-org", doc["id"])

    # Accept the amendment first
    await client.put(
        f"/api/organisations/withdraw-accepted-org/documents/{doc['id']}/amendments/{amendment['id']}/status",
        json={"status": "accepted"},
        headers={"Authorization": f"Bearer {jwt}"},
    )

    # Try to withdraw
    res = await client.delete(
        f"/api/organisations/withdraw-accepted-org/documents/{doc['id']}/amendments/{amendment['id']}",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_withdraw_non_member_returns_404(client):
    """A user not in the org gets 404 when trying to withdraw."""
    jwt_owner = await _register_and_login(client, "withdraw_nm_owner@example.com")
    await _create_org(client, jwt_owner, "withdraw-nm-org")
    doc = await _create_doc(client, jwt_owner, "withdraw-nm-org")
    amendment = await _create_amendment(client, jwt_owner, "withdraw-nm-org", doc["id"])

    jwt_outsider = await _register_and_login(client, "withdraw_nm_out@example.com")
    res = await client.delete(
        f"/api/organisations/withdraw-nm-org/documents/{doc['id']}/amendments/{amendment['id']}",
        headers={"Authorization": f"Bearer {jwt_outsider}"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_withdraw_non_existent_amendment_returns_404(client):
    """Withdrawing a non-existent amendment ID returns 404."""
    jwt = await _register_and_login(client, "withdraw_nf@example.com")
    await _create_org(client, jwt, "withdraw-nf-org")
    doc = await _create_doc(client, jwt, "withdraw-nf-org")

    res = await client.delete(
        f"/api/organisations/withdraw-nf-org/documents/{doc['id']}/amendments/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_withdraw_unauthenticated_returns_401_or_403(client):
    """Withdraw without a token returns 401 or 403."""
    res = await client.delete(
        "/api/organisations/some-org/documents/some-doc/amendments/some-id",
    )
    assert res.status_code in (401, 403)
