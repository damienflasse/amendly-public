"""
Member-management endpoint tests.

Covers:
  GET    /api/organisations/{slug}/members               — list members (any member)
  PUT    /api/organisations/{slug}/members/{user_id}/role — change role (owner only)
  DELETE /api/organisations/{slug}/members/{user_id}     — remove member (owner or admin)

Uses the same in-memory SQLite + ASGI fixture pattern as test_invitations.py.
The invite token is retrieved directly from the DB session (same approach as
test_invitations.py's _get_invite_token helper).
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
    """Async SQLite engine shared across the test session."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    """Fresh AsyncSession per test, rolled back after."""
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
    """HTTP test client wired to the SQLite session."""

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


async def _register(client: AsyncClient, email: str) -> tuple[str, str]:
    """
    Create a user via magic link and return (jwt, user_id).

    Parameters:
        client: Test HTTP client.
        email: Email address for the test user.

    Returns:
        Tuple of (JWT access token, user UUID string).
    """
    await client.post("/api/auth/magic-link/request", json={"email": email})
    magic_token = next(t for t, v in _magic_link_store.items() if v["email"] == email)
    res = await client.post("/api/auth/magic-link/verify", json={"token": magic_token})
    jwt = res.json()["access_token"]
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {jwt}"})
    return jwt, me.json()["id"]


async def _create_org(client: AsyncClient, jwt: str, name: str, slug: str) -> dict:
    """
    Create an organisation and return the response body.

    Parameters:
        client: Test HTTP client.
        jwt: Bearer token for the creating user.
        name: Organisation display name.
        slug: Organisation slug.

    Returns:
        Organisation response dict.
    """
    res = await client.post(
        "/api/organisations",
        json={"name": name, "slug": slug},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 201, res.text
    return res.json()


async def _get_invite_token(db_session: AsyncSession, email: str) -> str:
    """
    Retrieve the most recent pending invite token for a given email from the DB.

    Parameters:
        db_session: Active async DB session.
        email: The email address of the invitee.

    Returns:
        Invite token string.
    """
    result = await db_session.execute(
        select(Invitation.token)
        .where(Invitation.email == email, Invitation.accepted_at.is_(None))
        .order_by(Invitation.created_at.desc())
        .limit(1)
    )
    token = result.scalar_one_or_none()
    assert token is not None, f"No pending invite found for {email}"
    return token


async def _invite_and_accept(
    client: AsyncClient,
    db_session: AsyncSession,
    slug: str,
    owner_jwt: str,
    invitee_email: str,
    invitee_jwt: str,
) -> None:
    """
    Invite invitee_email and have invitee_jwt accept it.

    Parameters:
        client: Test HTTP client.
        db_session: Active async DB session (used to retrieve the invite token).
        slug: Organisation slug.
        owner_jwt: JWT of the owner sending the invite.
        invitee_email: Email address of the invitee.
        invitee_jwt: JWT of the user accepting the invite.
    """
    invite_res = await client.post(
        f"/api/organisations/{slug}/invite",
        json={"email": invitee_email},
        headers={"Authorization": f"Bearer {owner_jwt}"},
    )
    assert invite_res.status_code == 201, invite_res.text

    token = await _get_invite_token(db_session, invitee_email)
    accept_res = await client.post(
        "/api/invitations/accept",
        json={"token": token},
        headers={"Authorization": f"Bearer {invitee_jwt}"},
    )
    assert accept_res.status_code == 200, accept_res.text


# ---------------------------------------------------------------------------
# GET /api/organisations/{slug}/members
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_members_owner_only(client, db_session):
    """Owner can list members — returns a list with the owner as the sole entry."""
    jwt, uid = await _register(client, "members-owner@example.com")
    await _create_org(client, jwt, "Members Org", "members-org-1")

    res = await client.get(
        "/api/organisations/members-org-1/members",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["user_id"] == uid
    assert data[0]["role"] == "owner"
    assert data[0]["email"] == "members-owner@example.com"
    assert "joined_at" in data[0]


@pytest.mark.asyncio
async def test_list_members_unauthenticated(client, db_session):
    """Unauthenticated request returns 401 or 403."""
    res = await client.get("/api/organisations/any-org/members")
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_members_non_member_returns_404(client, db_session):
    """Non-member gets 404 (no disclosure)."""
    jwt_a, _ = await _register(client, "lm-owner@example.com")
    jwt_b, _ = await _register(client, "lm-outsider@example.com")
    await _create_org(client, jwt_a, "LM Org", "lm-org-1")

    res = await client.get(
        "/api/organisations/lm-org-1/members",
        headers={"Authorization": f"Bearer {jwt_b}"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_list_members_after_invite_accepted(client, db_session):
    """After a member accepts an invite, list returns both owner and new member."""
    jwt_owner, _ = await _register(client, "lm2-owner@example.com")
    jwt_member, _ = await _register(client, "lm2-member@example.com")
    await _create_org(client, jwt_owner, "LM2 Org", "lm2-org")

    await _invite_and_accept(
        client, db_session, "lm2-org", jwt_owner, "lm2-member@example.com", jwt_member
    )

    res = await client.get(
        "/api/organisations/lm2-org/members",
        headers={"Authorization": f"Bearer {jwt_owner}"},
    )
    assert res.status_code == 200
    members = res.json()
    assert len(members) == 2
    roles = {m["role"] for m in members}
    assert roles == {"owner", "member"}


@pytest.mark.asyncio
async def test_list_members_member_can_view(client, db_session):
    """A plain member can also call the list endpoint (any-role access)."""
    jwt_owner, _ = await _register(client, "lm3-owner@example.com")
    jwt_member, _ = await _register(client, "lm3-member@example.com")
    await _create_org(client, jwt_owner, "LM3 Org", "lm3-org")

    await _invite_and_accept(
        client, db_session, "lm3-org", jwt_owner, "lm3-member@example.com", jwt_member
    )

    res = await client.get(
        "/api/organisations/lm3-org/members",
        headers={"Authorization": f"Bearer {jwt_member}"},
    )
    assert res.status_code == 200
    assert len(res.json()) == 2


# ---------------------------------------------------------------------------
# PUT /api/organisations/{slug}/members/{user_id}/role
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_change_role_owner_can_promote_to_admin(client, db_session):
    """Owner can promote a member to admin."""
    jwt_owner, _ = await _register(client, "cr-owner@example.com")
    jwt_member, uid_member = await _register(client, "cr-member@example.com")
    await _create_org(client, jwt_owner, "CR Org", "cr-org")

    await _invite_and_accept(
        client, db_session, "cr-org", jwt_owner, "cr-member@example.com", jwt_member
    )

    res = await client.put(
        f"/api/organisations/cr-org/members/{uid_member}/role",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {jwt_owner}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "admin"
    assert data["user_id"] == uid_member


@pytest.mark.asyncio
async def test_change_role_owner_can_demote_admin_to_member(client, db_session):
    """Owner can demote an admin back to member."""
    jwt_owner, _ = await _register(client, "cr2-owner@example.com")
    jwt_member, uid_member = await _register(client, "cr2-member@example.com")
    await _create_org(client, jwt_owner, "CR2 Org", "cr2-org")

    await _invite_and_accept(
        client, db_session, "cr2-org", jwt_owner, "cr2-member@example.com", jwt_member
    )
    # Promote first
    await client.put(
        f"/api/organisations/cr2-org/members/{uid_member}/role",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {jwt_owner}"},
    )
    # Demote
    res = await client.put(
        f"/api/organisations/cr2-org/members/{uid_member}/role",
        json={"role": "member"},
        headers={"Authorization": f"Bearer {jwt_owner}"},
    )
    assert res.status_code == 200
    assert res.json()["role"] == "member"


@pytest.mark.asyncio
async def test_change_role_non_owner_returns_403(client, db_session):
    """An admin cannot change another member's role — only the owner can."""
    jwt_owner, _ = await _register(client, "cr3-owner@example.com")
    jwt_admin, uid_admin = await _register(client, "cr3-admin@example.com")
    jwt_member, uid_member = await _register(client, "cr3-member@example.com")
    await _create_org(client, jwt_owner, "CR3 Org", "cr3-org")

    await _invite_and_accept(
        client, db_session, "cr3-org", jwt_owner, "cr3-admin@example.com", jwt_admin
    )
    await _invite_and_accept(
        client, db_session, "cr3-org", jwt_owner, "cr3-member@example.com", jwt_member
    )

    # Promote admin
    await client.put(
        f"/api/organisations/cr3-org/members/{uid_admin}/role",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {jwt_owner}"},
    )

    # Admin tries to change member's role — must fail with 403
    res = await client.put(
        f"/api/organisations/cr3-org/members/{uid_member}/role",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {jwt_admin}"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_change_role_owner_cannot_demote_self(client, db_session):
    """Owner cannot change their own role — returns 400."""
    jwt_owner, uid_owner = await _register(client, "cr4-owner@example.com")
    await _create_org(client, jwt_owner, "CR4 Org", "cr4-org")

    res = await client.put(
        f"/api/organisations/cr4-org/members/{uid_owner}/role",
        json={"role": "member"},
        headers={"Authorization": f"Bearer {jwt_owner}"},
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_change_role_invalid_role_returns_400(client, db_session):
    """Supplying an invalid role string returns 400."""
    jwt_owner, _ = await _register(client, "cr5-owner@example.com")
    jwt_member, uid_member = await _register(client, "cr5-member@example.com")
    await _create_org(client, jwt_owner, "CR5 Org", "cr5-org")

    await _invite_and_accept(
        client, db_session, "cr5-org", jwt_owner, "cr5-member@example.com", jwt_member
    )

    res = await client.put(
        f"/api/organisations/cr5-org/members/{uid_member}/role",
        json={"role": "superuser"},
        headers={"Authorization": f"Bearer {jwt_owner}"},
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_change_role_cannot_set_owner(client, db_session):
    """Setting role to 'owner' is not allowed and returns 400."""
    jwt_owner, _ = await _register(client, "cr6-owner@example.com")
    jwt_member, uid_member = await _register(client, "cr6-member@example.com")
    await _create_org(client, jwt_owner, "CR6 Org", "cr6-org")

    await _invite_and_accept(
        client, db_session, "cr6-org", jwt_owner, "cr6-member@example.com", jwt_member
    )

    res = await client.put(
        f"/api/organisations/cr6-org/members/{uid_member}/role",
        json={"role": "owner"},
        headers={"Authorization": f"Bearer {jwt_owner}"},
    )
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /api/organisations/{slug}/members/{user_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_member_owner_can_remove_plain_member(client, db_session):
    """Owner can remove a plain member — returns 204, member no longer listed."""
    jwt_owner, _ = await _register(client, "rm-owner@example.com")
    jwt_member, uid_member = await _register(client, "rm-member@example.com")
    await _create_org(client, jwt_owner, "RM Org", "rm-org")

    await _invite_and_accept(
        client, db_session, "rm-org", jwt_owner, "rm-member@example.com", jwt_member
    )

    res = await client.delete(
        f"/api/organisations/rm-org/members/{uid_member}",
        headers={"Authorization": f"Bearer {jwt_owner}"},
    )
    assert res.status_code == 204

    # Member no longer appears in the list
    list_res = await client.get(
        "/api/organisations/rm-org/members",
        headers={"Authorization": f"Bearer {jwt_owner}"},
    )
    ids = [m["user_id"] for m in list_res.json()]
    assert uid_member not in ids


@pytest.mark.asyncio
async def test_remove_member_admin_can_remove_plain_member(client, db_session):
    """Admin can remove a plain member."""
    jwt_owner, _ = await _register(client, "rm2-owner@example.com")
    jwt_admin, uid_admin = await _register(client, "rm2-admin@example.com")
    jwt_member, uid_member = await _register(client, "rm2-member@example.com")
    await _create_org(client, jwt_owner, "RM2 Org", "rm2-org")

    await _invite_and_accept(
        client, db_session, "rm2-org", jwt_owner, "rm2-admin@example.com", jwt_admin
    )
    await _invite_and_accept(
        client, db_session, "rm2-org", jwt_owner, "rm2-member@example.com", jwt_member
    )

    # Promote admin
    await client.put(
        f"/api/organisations/rm2-org/members/{uid_admin}/role",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {jwt_owner}"},
    )

    # Admin removes member
    res = await client.delete(
        f"/api/organisations/rm2-org/members/{uid_member}",
        headers={"Authorization": f"Bearer {jwt_admin}"},
    )
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_remove_member_plain_member_returns_403(client, db_session):
    """A plain member cannot remove anyone — returns 403."""
    jwt_owner, uid_owner = await _register(client, "rm3-owner@example.com")
    jwt_member, uid_member = await _register(client, "rm3-member@example.com")
    await _create_org(client, jwt_owner, "RM3 Org", "rm3-org")

    await _invite_and_accept(
        client, db_session, "rm3-org", jwt_owner, "rm3-member@example.com", jwt_member
    )

    res = await client.delete(
        f"/api/organisations/rm3-org/members/{uid_owner}",
        headers={"Authorization": f"Bearer {jwt_member}"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_remove_member_cannot_remove_owner(client, db_session):
    """Even the owner cannot be removed — returns 400."""
    jwt_owner, uid_owner = await _register(client, "rm4-owner@example.com")
    await _create_org(client, jwt_owner, "RM4 Org", "rm4-org")

    res = await client.delete(
        f"/api/organisations/rm4-org/members/{uid_owner}",
        headers={"Authorization": f"Bearer {jwt_owner}"},
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_remove_member_unauthenticated(client, db_session):
    """Unauthenticated DELETE returns 401 or 403."""
    res = await client.delete("/api/organisations/any-org/members/some-id")
    assert res.status_code in (401, 403)
