"""
Contributor-focused endpoint tests — covers GET .../amendments/mine and the
public contribution endpoint.

Uses the same in-memory SQLite + ASGI fixture pattern as test_amendments.py.
Each test gets a fresh HTTP client backed by a rolled-back DB session.

Coverage:
  GET /api/organisations/{slug}/documents/{doc_id}/amendments/mine
      — returns only the authenticated user's own amendments
      — returns empty list for a member who has submitted nothing
      — unauthenticated caller receives 401 or 403
  POST /api/contribute/{token}
      — enforces the Redis-backed per-IP rate limit
      — bypasses Turnstile in test mode
      — rejects missing Turnstile tokens when protection is enabled
      — accepts valid Turnstile verification when protection is enabled
      — rejects invalid Turnstile verification when protection is enabled
      — enforces the plan contributor cap (new identity blocked when cap reached)
      — allows a known contributor to keep submitting after the cap is reached
"""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.api.contribute as contribute_api
from app.api.auth import _magic_link_store
from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models.invitation import Invitation
from app.models.document import Document
from app.models.organisation import Organisation, OrgPlan

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


@pytest.fixture(autouse=True)
def reset_contribution_guards():
    """Reset public contribution guard state between tests."""
    contribute_api._rate_limit_window.clear()
    contribute_api._rate_limit_redis_client = None


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


async def _open_doc(client: AsyncClient, jwt: str, slug: str, doc_id: str) -> dict:
    """
    Open a document so it can accept amendments and public contributions.

    Parameters:
        client: Test HTTP client.
        jwt: Bearer token for the caller.
        slug: Organisation slug.
        doc_id: Document UUID.

    Returns:
        Document response dict with the updated status.
    """
    res = await client.put(
        f"/api/organisations/{slug}/documents/{doc_id}/status",
        json={"status": "open"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    return res.json()


async def _generate_contributor_token(
    client: AsyncClient,
    jwt: str,
    slug: str,
    doc_id: str,
) -> str:
    """
    Create a public contributor token for a document and return it.

    Parameters:
        client: Test HTTP client.
        jwt: Bearer token for the caller.
        slug: Organisation slug.
        doc_id: Document UUID.

    Returns:
        The public contribution token returned by the API.
    """
    res = await client.post(
        f"/api/organisations/{slug}/documents/{doc_id}/contributor-token",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    return res.json()["token"]


async def _upgrade_org_plan(
    db_session: AsyncSession,
    slug: str,
    plan: OrgPlan = OrgPlan.team,
) -> None:
    """
    Directly upgrade an organisation's plan in the test DB.

    Required for tests that call _generate_contributor_token because the
    contributor-token endpoint now enforces a Team/Organisation plan gate.

    Parameters:
        db_session: Active SQLAlchemy async session for the test.
        slug:       Organisation slug to upgrade.
        plan:       Target plan (default: OrgPlan.team).
    """
    result = await db_session.execute(
        select(Organisation).where(Organisation.slug == slug)
    )
    org = result.scalar_one()
    org.plan = plan
    await db_session.flush()


class FakeRedisCounter:
    """Minimal async Redis stub for contribution rate-limit tests."""

    def __init__(self):
        self.counts: dict[str, int] = {}
        self.expirations: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        """Increment and return the current counter value for a key."""
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key: str, ttl: int) -> None:
        """Record the TTL assigned to a key."""
        self.expirations[key] = ttl


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
    slug: str,
    member_email: str,
) -> str:
    """
    Invite a new member to the organisation and return their JWT token.

    Parameters:
        client: Test HTTP client.
        db_session: Active test database session (used to read the invite token).
        owner_jwt: Bearer token for the org owner.
        slug: Organisation slug.
        member_email: Email of the user to invite.

    Returns:
        JWT access token for the newly invited member.
    """
    # Send invitation
    res = await client.post(
        f"/api/organisations/{slug}/invite",
        json={"email": member_email},
        headers={"Authorization": f"Bearer {owner_jwt}"},
    )
    assert res.status_code == 201

    # Read the invite token directly from the DB (not exposed in the API response)
    result = await db_session.execute(
        select(Invitation.token).where(Invitation.email == member_email)
    )
    invite_token = result.scalar_one()

    # Member registers, logs in, then accepts the invitation
    member_jwt = await _register_and_login(client, member_email)
    accept_res = await client.post(
        "/api/invitations/accept",
        json={"token": invite_token},
        headers={"Authorization": f"Bearer {member_jwt}"},
    )
    assert accept_res.status_code == 200
    return member_jwt


# ---------------------------------------------------------------------------
# GET .../amendments/mine
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_mine_own_amendments_only(client, db_session):
    """GET /mine returns only amendments authored by the caller.

    Two users each submit one amendment; each should only see their own.
    """
    jwt_owner = await _register_and_login(client, "mine_owner@example.com")
    await _create_org(client, jwt_owner, "mine-org-own")
    doc = await _create_doc(client, jwt_owner, "mine-org-own")
    doc_id = doc["id"]

    # Owner submits one amendment
    owner_amendment = await _create_amendment(
        client, jwt_owner, "mine-org-own", doc_id,
        original_text="Owner original", proposed_text="Owner proposed",
    )

    # Invite a member and have them submit their own amendment
    member_jwt = await _invite_member(client, db_session, jwt_owner, "mine-org-own", "mine_member@example.com")
    member_amendment = await _create_amendment(
        client, member_jwt, "mine-org-own", doc_id,
        original_text="Member original", proposed_text="Member proposed",
    )

    # Owner queries /mine — should only see their own
    res_owner = await client.get(
        f"/api/organisations/mine-org-own/documents/{doc_id}/amendments/mine",
        headers={"Authorization": f"Bearer {jwt_owner}"},
    )
    assert res_owner.status_code == 200
    owner_data = res_owner.json()
    assert owner_data["total"] == 1
    assert len(owner_data["items"]) == 1
    assert owner_data["items"][0]["id"] == owner_amendment["id"]

    # Member queries /mine — should only see their own
    res_member = await client.get(
        f"/api/organisations/mine-org-own/documents/{doc_id}/amendments/mine",
        headers={"Authorization": f"Bearer {member_jwt}"},
    )
    assert res_member.status_code == 200
    member_data = res_member.json()
    assert member_data["total"] == 1
    assert len(member_data["items"]) == 1
    assert member_data["items"][0]["id"] == member_amendment["id"]


@pytest.mark.asyncio
async def test_list_mine_empty_for_new_member(client, db_session):
    """GET /mine returns an empty list when the member has submitted nothing."""
    jwt_owner = await _register_and_login(client, "mine_empty_owner@example.com")
    await _create_org(client, jwt_owner, "mine-org-empty")
    doc = await _create_doc(client, jwt_owner, "mine-org-empty")
    doc_id = doc["id"]

    # A fresh member who has never submitted anything
    member_jwt = await _invite_member(
        client, db_session, jwt_owner, "mine-org-empty", "mine_empty_member@example.com"
    )

    res = await client.get(
        f"/api/organisations/mine-org-empty/documents/{doc_id}/amendments/mine",
        headers={"Authorization": f"Bearer {member_jwt}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_mine_unauthenticated_returns_401(client):
    """GET /mine without a bearer token returns 401 or 403."""
    res = await client.get(
        "/api/organisations/any-org/documents/any-doc-id/amendments/mine",
    )
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_public_contribution_rate_limit_blocks_after_ten_requests(client, db_session, monkeypatch):
    """POST /api/contribute/{token} returns 429 after 10 submissions from one IP."""
    monkeypatch.setattr(settings, "turnstile_secret_key", "test")
    fake_redis = FakeRedisCounter()
    monkeypatch.setattr(contribute_api, "_get_rate_limit_redis", lambda: fake_redis)

    jwt_owner = await _register_and_login(client, "public_contrib_owner_rate@example.com")
    await _create_org(client, jwt_owner, "public-contrib-org-rate")
    await _upgrade_org_plan(db_session, "public-contrib-org-rate")
    doc = await _create_doc(client, jwt_owner, "public-contrib-org-rate")
    await _open_doc(client, jwt_owner, "public-contrib-org-rate", doc["id"])
    contributor_token = await _generate_contributor_token(
        client, jwt_owner, "public-contrib-org-rate", doc["id"]
    )

    headers = {"x-forwarded-for": "198.51.100.10"}
    payload = {
        "amendment_type": "text_change",
        "section": "Article 9",
        "original_text": "Old wording",
        "proposed_text": "New wording",
        "contributor_name": "Rate Limited User",
    }

    for _ in range(contribute_api._RATE_LIMIT):
        res = await client.post(
            f"/api/contribute/{contributor_token}",
            json=payload,
            headers=headers,
        )
        assert res.status_code == 201

    blocked = await client.post(
        f"/api/contribute/{contributor_token}",
        json=payload,
        headers=headers,
    )
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "Too many submissions. Please try again later."

    redis_key = f"{contribute_api._REDIS_RATE_LIMIT_KEY_PREFIX}198.51.100.10"
    assert fake_redis.expirations[redis_key] == contribute_api._WINDOW_SECONDS
    assert fake_redis.counts[redis_key] == contribute_api._RATE_LIMIT + 1


@pytest.mark.asyncio
async def test_public_contribution_bypasses_turnstile_in_test_mode(client, db_session, monkeypatch):
    """POST /api/contribute/{token} skips Turnstile verification when secret=test."""
    monkeypatch.setattr(settings, "turnstile_secret_key", "test")

    jwt_owner = await _register_and_login(client, "public_contrib_owner@example.com")
    await _create_org(client, jwt_owner, "public-contrib-org")
    await _upgrade_org_plan(db_session, "public-contrib-org")
    doc = await _create_doc(client, jwt_owner, "public-contrib-org")
    await _open_doc(client, jwt_owner, "public-contrib-org", doc["id"])
    contributor_token = await _generate_contributor_token(
        client, jwt_owner, "public-contrib-org", doc["id"]
    )

    res = await client.post(
        f"/api/contribute/{contributor_token}",
        json={
            "amendment_type": "text_change",
            "section": "Article 1",
            "original_text": "Old wording",
            "proposed_text": "New wording",
            "contributor_name": "Public User",
            "contributor_email": "public@example.com",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["contributor_name"] == "Public User"
    assert data["author_id"] is None


@pytest.mark.asyncio
async def test_public_contribution_rejects_missing_turnstile_token_when_enabled(
    client,
    db_session,
    monkeypatch,
):
    """POST /api/contribute/{token} returns 403 when Turnstile is enabled but missing."""
    jwt_owner = await _register_and_login(client, "public_contrib_owner_missing@example.com")
    await _create_org(client, jwt_owner, "public-contrib-org-missing")
    await _upgrade_org_plan(db_session, "public-contrib-org-missing")
    doc = await _create_doc(client, jwt_owner, "public-contrib-org-missing")
    await _open_doc(client, jwt_owner, "public-contrib-org-missing", doc["id"])
    contributor_token = await _generate_contributor_token(
        client, jwt_owner, "public-contrib-org-missing", doc["id"]
    )
    monkeypatch.setattr(settings, "turnstile_secret_key", "live-secret")

    res = await client.post(
        f"/api/contribute/{contributor_token}",
        json={
            "amendment_type": "text_change",
            "section": "Article 3",
            "original_text": "Old wording",
            "proposed_text": "New wording",
            "contributor_name": "Missing Token User",
        },
    )
    assert res.status_code == 403
    assert res.json()["detail"] == "Anti-bot verification failed. Please try again."


@pytest.mark.asyncio
async def test_public_contribution_accepts_valid_turnstile(client, db_session, monkeypatch):
    """POST /api/contribute/{token} accepts a valid Turnstile response."""
    jwt_owner = await _register_and_login(client, "public_contrib_owner_valid@example.com")
    await _create_org(client, jwt_owner, "public-contrib-org-valid")
    await _upgrade_org_plan(db_session, "public-contrib-org-valid")
    doc = await _create_doc(client, jwt_owner, "public-contrib-org-valid")
    await _open_doc(client, jwt_owner, "public-contrib-org-valid", doc["id"])
    contributor_token = await _generate_contributor_token(
        client, jwt_owner, "public-contrib-org-valid", doc["id"]
    )

    monkeypatch.setattr(settings, "turnstile_secret_key", "live-secret")

    async def fake_verify_turnstile(token, remote_ip=None, *, fail_open=True, context="unknown", expected_action=None, expected_hostname=None):
        assert token == "good-token"
        assert fail_open is False
        assert context == "public_contribution"
        assert expected_action == "public_contribution"
        return True

    monkeypatch.setattr(contribute_api, "verify_turnstile", fake_verify_turnstile)

    res = await client.post(
        f"/api/contribute/{contributor_token}",
        json={
            "amendment_type": "text_change",
            "section": "Article 1",
            "original_text": "Old wording",
            "proposed_text": "New wording",
            "contributor_name": "Verified User",
            "contributor_email": "verified@example.com",
            "cf_turnstile_token": "good-token",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["contributor_name"] == "Verified User"
    assert data["author_id"] is None


@pytest.mark.asyncio
async def test_public_contribution_rejects_failed_turnstile(client, db_session, monkeypatch):
    """POST /api/contribute/{token} returns 403 when Turnstile validation fails."""
    jwt_owner = await _register_and_login(client, "public_contrib_owner_2@example.com")
    await _create_org(client, jwt_owner, "public-contrib-org-2")
    await _upgrade_org_plan(db_session, "public-contrib-org-2")
    doc = await _create_doc(client, jwt_owner, "public-contrib-org-2")
    await _open_doc(client, jwt_owner, "public-contrib-org-2", doc["id"])
    contributor_token = await _generate_contributor_token(
        client, jwt_owner, "public-contrib-org-2", doc["id"]
    )

    monkeypatch.setattr(settings, "turnstile_secret_key", "live-secret")

    async def fake_verify_turnstile(token, remote_ip=None, *, fail_open=True, context="unknown", expected_action=None, expected_hostname=None):
        assert token == "bad-token"
        assert fail_open is False
        assert context == "public_contribution"
        assert expected_action == "public_contribution"
        return False

    monkeypatch.setattr(contribute_api, "verify_turnstile", fake_verify_turnstile)

    res = await client.post(
        f"/api/contribute/{contributor_token}",
        json={
            "amendment_type": "text_change",
            "section": "Article 2",
            "original_text": "Old wording",
            "proposed_text": "New wording",
            "contributor_name": "Blocked User",
            "cf_turnstile_token": "bad-token",
        },
    )
    assert res.status_code == 403
    assert res.json()["detail"] == "Anti-bot verification failed. Please try again."


# ---------------------------------------------------------------------------
# Plan gate — contributor token generation and submission quota
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contributor_token_blocked_for_solo_plan(client):
    """POST contributor-token returns 403 when the org is on the Solo plan."""
    jwt = await _register_and_login(client, "solo_token_owner@example.com")
    await _create_org(client, jwt, "solo-contrib-org")
    doc = await _create_doc(client, jwt, "solo-contrib-org")

    res = await client.post(
        f"/api/organisations/solo-contrib-org/documents/{doc['id']}/contributor-token",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 403
    assert "Team or Organisation plan" in res.json()["detail"]


@pytest.mark.asyncio
async def test_generate_contributor_token_returns_active_status_and_expiry(client, db_session):
    """Contributor-token generation returns explicit active status and expiry metadata."""
    jwt = await _register_and_login(client, "active_link_owner@example.com")
    await _create_org(client, jwt, "active-link-org")
    await _upgrade_org_plan(db_session, "active-link-org")
    doc = await _create_doc(client, jwt, "active-link-org")
    await _open_doc(client, jwt, "active-link-org", doc["id"])

    res = await client.post(
        f"/api/organisations/active-link-org/documents/{doc['id']}/contributor-token",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "active"
    assert data["token"]
    assert data["created_at"]
    assert data["expires_at"]
    assert data["url"].endswith(f"/contribute/{data['token']}")

    doc_res = await client.get(
        f"/api/organisations/active-link-org/documents/{doc['id']}",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert doc_res.status_code == 200
    doc_data = doc_res.json()
    assert doc_data["contributor_link_status"] == "active"
    assert doc_data["contributor_token_expires_at"] == data["expires_at"]


@pytest.mark.asyncio
async def test_public_contribution_get_rejects_expired_link(
    client,
    db_session,
):
    """GET /api/contribute/{token} returns 410 once the contributor link is expired."""
    jwt = await _register_and_login(client, "expired_link_owner@example.com")
    await _create_org(client, jwt, "expired-link-org")
    await _upgrade_org_plan(db_session, "expired-link-org")
    doc = await _create_doc(client, jwt, "expired-link-org")
    await _open_doc(client, jwt, "expired-link-org", doc["id"])
    contributor_token = await _generate_contributor_token(
        client, jwt, "expired-link-org", doc["id"]
    )

    result = await db_session.execute(select(Document).where(Document.id == doc["id"]))
    stored_doc = result.scalar_one()
    stored_doc.contributor_token_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.flush()

    res = await client.get(f"/api/contribute/{contributor_token}")
    assert res.status_code == 410
    assert "has expired" in res.json()["detail"]

    doc_res = await client.get(
        f"/api/organisations/expired-link-org/documents/{doc['id']}",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert doc_res.status_code == 200
    assert doc_res.json()["contributor_link_status"] == "expired"


@pytest.mark.asyncio
async def test_public_contribution_post_rejects_expired_link(client, db_session, monkeypatch):
    """POST /api/contribute/{token} returns 410 when the contributor link is expired."""
    monkeypatch.setattr(settings, "turnstile_secret_key", "test")

    jwt = await _register_and_login(client, "expired_submit_owner@example.com")
    await _create_org(client, jwt, "expired-submit-org")
    await _upgrade_org_plan(db_session, "expired-submit-org")
    doc = await _create_doc(client, jwt, "expired-submit-org")
    await _open_doc(client, jwt, "expired-submit-org", doc["id"])
    contributor_token = await _generate_contributor_token(
        client, jwt, "expired-submit-org", doc["id"]
    )

    result = await db_session.execute(select(Document).where(Document.id == doc["id"]))
    stored_doc = result.scalar_one()
    stored_doc.contributor_token_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.flush()

    res = await client.post(
        f"/api/contribute/{contributor_token}",
        json={
            "amendment_type": "text_change",
            "section": "Article 1",
            "original_text": "Old wording",
            "proposed_text": "New wording",
            "contributor_name": "Late Contributor",
        },
    )
    assert res.status_code == 410
    assert "has expired" in res.json()["detail"]


@pytest.mark.asyncio
async def test_revoke_contributor_token_returns_revoked_status(client, db_session):
    """Revoking a contributor link returns explicit revoked state and clears expiry."""
    jwt = await _register_and_login(client, "revoked_link_owner@example.com")
    await _create_org(client, jwt, "revoked-link-org")
    await _upgrade_org_plan(db_session, "revoked-link-org")
    doc = await _create_doc(client, jwt, "revoked-link-org")
    await _open_doc(client, jwt, "revoked-link-org", doc["id"])
    await _generate_contributor_token(client, jwt, "revoked-link-org", doc["id"])

    res = await client.delete(
        f"/api/organisations/revoked-link-org/documents/{doc['id']}/contributor-token",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data == {
        "token": None,
        "created_at": None,
        "expires_at": None,
        "url": None,
        "status": "revoked",
    }

    doc_res = await client.get(
        f"/api/organisations/revoked-link-org/documents/{doc['id']}",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert doc_res.status_code == 200
    doc_data = doc_res.json()
    assert doc_data["contributor_link_status"] == "revoked"
    assert doc_data["contributor_token_expires_at"] is None


@pytest.mark.asyncio
async def test_team_plan_contributor_quota_enforced(client, db_session, monkeypatch):
    """POST /api/contribute/{token} returns 429 after 30 distinct external contributors on Team."""
    monkeypatch.setattr(settings, "turnstile_secret_key", "test")

    jwt = await _register_and_login(client, "team_quota_owner@example.com")
    await _create_org(client, jwt, "team-quota-org")
    await _upgrade_org_plan(db_session, "team-quota-org")
    doc = await _create_doc(client, jwt, "team-quota-org")
    await _open_doc(client, jwt, "team-quota-org", doc["id"])
    contributor_token = await _generate_contributor_token(
        client, jwt, "team-quota-org", doc["id"]
    )

    payload = {
        "amendment_type": "text_change",
        "section": "Article 1",
        "original_text": "Old",
        "proposed_text": "New",
    }

    # 30 accepted submissions from distinct contributors and distinct IPs.
    for i in range(30):
        res = await client.post(
            f"/api/contribute/{contributor_token}",
            json={
                **payload,
                "original_text": f"Old {i}",
                "proposed_text": f"New {i}",
                "contributor_name": f"Quota Tester {i}",
                "contributor_email": f"quota{i}@example.com",
            },
            headers={"x-forwarded-for": f"10.0.0.{i + 1}"},
        )
        assert res.status_code == 201, f"Expected 201 on submission {i}, got {res.status_code}"

    # 31st from a fresh IP — should be rejected by the document quota, not the IP limit.
    blocked = await client.post(
        f"/api/contribute/{contributor_token}",
        json={
            **payload,
            "contributor_name": "Blocked Contributor",
            "contributor_email": "blocked@example.com",
        },
        headers={"x-forwarded-for": "10.0.1.1"},
    )
    assert blocked.status_code == 429
    assert "external contributor limit (30)" in blocked.json()["detail"]


@pytest.mark.asyncio
async def test_known_contributor_can_still_submit_after_cap_reached(client, db_session, monkeypatch):
    """POST /api/contribute/{token} allows a known contributor to keep submitting once the cap is full.

    The cap counts distinct identities. A contributor whose identity is already
    in the DB does not increment the count, so they must not be blocked even
    when the document is at its limit.
    """
    monkeypatch.setattr(settings, "turnstile_secret_key", "test")

    jwt = await _register_and_login(client, "known_contrib_owner@example.com")
    await _create_org(client, jwt, "known-contrib-org")
    await _upgrade_org_plan(db_session, "known-contrib-org")
    doc = await _create_doc(client, jwt, "known-contrib-org")
    await _open_doc(client, jwt, "known-contrib-org", doc["id"])
    contributor_token = await _generate_contributor_token(
        client, jwt, "known-contrib-org", doc["id"]
    )

    base_payload = {
        "amendment_type": "text_change",
        "original_text": "Old",
        "proposed_text": "New",
    }

    # Known contributor submits first — establishes their identity in the DB.
    known_res = await client.post(
        f"/api/contribute/{contributor_token}",
        json={**base_payload, "contributor_name": "Known Person", "contributor_email": "known@example.com"},
        headers={"x-forwarded-for": "10.1.0.1"},
    )
    assert known_res.status_code == 201

    # Fill the remaining 29 slots with distinct new contributors.
    for i in range(29):
        res = await client.post(
            f"/api/contribute/{contributor_token}",
            json={**base_payload, "contributor_name": f"Filler {i}", "contributor_email": f"filler{i}@example.com"},
            headers={"x-forwarded-for": f"10.1.1.{i + 1}"},
        )
        assert res.status_code == 201, f"Filler {i} should be accepted, got {res.status_code}"

    # Cap is now full (30 distinct contributors).
    # A brand-new identity must be blocked.
    new_blocked = await client.post(
        f"/api/contribute/{contributor_token}",
        json={**base_payload, "contributor_name": "New Stranger", "contributor_email": "stranger@example.com"},
        headers={"x-forwarded-for": "10.1.2.1"},
    )
    assert new_blocked.status_code == 429

    # The known contributor submits a second amendment — must succeed.
    known_again = await client.post(
        f"/api/contribute/{contributor_token}",
        json={**base_payload, "contributor_name": "Known Person", "contributor_email": "known@example.com"},
        headers={"x-forwarded-for": "10.1.0.1"},
    )
    assert known_again.status_code == 201, (
        f"Known contributor should bypass the cap, got {known_again.status_code}: {known_again.json()}"
    )
