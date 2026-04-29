"""
Invitation endpoint tests.

Covers:
  - POST /api/organisations/{slug}/invite (create invite, idempotency, access control)
  - GET  /api/invitations/preview        (public preview by token)
  - POST /api/invitations/accept         (accept invite, error cases)
  - Email send path via Resend (mocked)

Uses the same in-memory SQLite + ASGI fixture pattern as other test modules.
Each test gets a fresh HTTP client backed by a rolled-back DB session.
"""

from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.auth import _magic_link_store
import app.api.invitations as invitations_api
from app.core.config import settings
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
    """Register via magic-link and return the JWT access token."""
    await client.post("/api/auth/magic-link/request", json={"email": email})
    token = next(t for t, v in _magic_link_store.items() if v["email"] == email)
    res = await client.post("/api/auth/magic-link/verify", json={"token": token})
    client.cookies.clear()
    return res.json()["access_token"]


async def _create_org(client: AsyncClient, jwt: str, slug: str) -> dict:
    """Helper to create an org and return the response JSON."""
    res = await client.post(
        "/api/organisations",
        json={"name": slug.replace("-", " ").title(), "slug": slug},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 201
    return res.json()


async def _get_invite_token(db_session: AsyncSession, email: str) -> str | None:
    """Retrieve the invite token for a given email from the test DB session."""
    result = await db_session.execute(
        select(Invitation.token).where(Invitation.email == email)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# POST /api/organisations/{slug}/invite
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invite_by_owner_success(client):
    """Owner can invite an email address; response includes the invitation id."""
    jwt = await _register_and_login(client, "invite-owner@example.com")
    await _create_org(client, jwt, "invite-org-1")

    res = await client.post(
        "/api/organisations/invite-org-1/invite",
        json={"email": "invitee@example.com"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "invitee@example.com"
    assert data["org_id"] is not None
    assert data["accepted_at"] is None
    assert "expires_at" in data


@pytest.mark.asyncio
async def test_invite_idempotent(client):
    """Sending a second invite for the same email returns the existing pending invite."""
    jwt = await _register_and_login(client, "invite-idem@example.com")
    await _create_org(client, jwt, "invite-org-2")

    res1 = await client.post(
        "/api/organisations/invite-org-2/invite",
        json={"email": "dup@example.com"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    res2 = await client.post(
        "/api/organisations/invite-org-2/invite",
        json={"email": "dup@example.com"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res1.status_code == 201
    assert res2.status_code == 201
    # Same token → same invitation id
    assert res1.json()["id"] == res2.json()["id"]


@pytest.mark.asyncio
async def test_invite_member_not_in_org_gets_404(client):
    """A user who is not a member of the org gets 404 (not 403) when inviting."""
    owner_jwt = await _register_and_login(client, "invite-admin@example.com")
    outsider_jwt = await _register_and_login(client, "invite-outsider@example.com")
    await _create_org(client, owner_jwt, "invite-org-3")

    # Outsider is not in invite-org-3 → should get 404
    res = await client.post(
        "/api/organisations/invite-org-3/invite",
        json={"email": "another@example.com"},
        headers={"Authorization": f"Bearer {outsider_jwt}"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_invite_already_member_returns_409(client):
    """Inviting an email that already belongs to a member returns 409."""
    jwt = await _register_and_login(client, "invite-409@example.com")
    await _create_org(client, jwt, "invite-org-4")

    # The owner is already a member — invite their own email
    res = await client.post(
        "/api/organisations/invite-org-4/invite",
        json={"email": "invite-409@example.com"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_invite_unauthenticated_returns_401(client):
    """Calling invite without a token returns 401."""
    res = await client.post(
        "/api/organisations/some-org/invite",
        json={"email": "anon@example.com"},
    )
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_invite_invalid_email_returns_422(client):
    """Submitting a malformed email returns 422 validation error."""
    jwt = await _register_and_login(client, "invite-val@example.com")
    await _create_org(client, jwt, "invite-org-5")

    res = await client.post(
        "/api/organisations/invite-org-5/invite",
        json={"email": "not-an-email"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_invite_rejects_failed_turnstile(client, monkeypatch):
    """Invite creation returns 403 when Turnstile validation fails."""
    jwt = await _register_and_login(client, "invite-turnstile-owner@example.com")
    await _create_org(client, jwt, "invite-turnstile-org")
    monkeypatch.setattr(settings, "turnstile_secret_key", "live-secret")

    async def fake_verify_turnstile(token, remote_ip=None, *, fail_open=True, context="unknown", expected_action=None, expected_hostname=None):
        assert token == "bad-token"
        assert remote_ip == "203.0.113.9"
        assert fail_open is True
        assert context == "org_invite"
        assert expected_action == "org_invite"
        return False

    monkeypatch.setattr(invitations_api, "verify_turnstile", fake_verify_turnstile)

    res = await client.post(
        "/api/organisations/invite-turnstile-org/invite",
        json={"email": "invitee@example.com", "turnstile_token": "bad-token"},
        headers={
            "Authorization": f"Bearer {jwt}",
            "cf-connecting-ip": "203.0.113.9",
        },
    )
    assert res.status_code == 403
    assert res.json()["detail"] == "Human verification failed. Please try again."


@pytest.mark.asyncio
async def test_invite_accepts_valid_turnstile(client, monkeypatch):
    """Invite creation succeeds when Turnstile validation passes."""
    jwt = await _register_and_login(client, "invite-turnstile-ok-owner@example.com")
    await _create_org(client, jwt, "invite-turnstile-ok-org")
    monkeypatch.setattr(settings, "turnstile_secret_key", "live-secret")

    async def fake_verify_turnstile(token, remote_ip=None, *, fail_open=True, context="unknown", expected_action=None, expected_hostname=None):
        assert token == "good-token"
        assert remote_ip == "198.51.100.14"
        assert fail_open is True
        assert context == "org_invite"
        assert expected_action == "org_invite"
        return True

    monkeypatch.setattr(invitations_api, "verify_turnstile", fake_verify_turnstile)

    res = await client.post(
        "/api/organisations/invite-turnstile-ok-org/invite",
        json={"email": "invitee@example.com", "turnstile_token": "good-token"},
        headers={
            "Authorization": f"Bearer {jwt}",
            "cf-connecting-ip": "198.51.100.14",
        },
    )
    assert res.status_code == 201


# ---------------------------------------------------------------------------
# POST /api/invitations/accept
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_accept_invite_success(client, db_session):
    """An invited user can accept an invite and becomes a member."""
    owner_jwt = await _register_and_login(client, "accept-owner@example.com")
    invitee_jwt = await _register_and_login(client, "accept-invitee@example.com")
    await _create_org(client, owner_jwt, "accept-org-1")

    # Create invite
    invite_res = await client.post(
        "/api/organisations/accept-org-1/invite",
        json={"email": "accept-invitee@example.com"},
        headers={"Authorization": f"Bearer {owner_jwt}"},
    )
    assert invite_res.status_code == 201

    # Retrieve the token directly from the shared test DB session
    token = await _get_invite_token(db_session, "accept-invitee@example.com")
    assert token is not None, "Invite token not found in test DB"

    # Accept the invite
    accept_res = await client.post(
        "/api/invitations/accept",
        json={"token": token},
        headers={"Authorization": f"Bearer {invitee_jwt}"},
    )
    assert accept_res.status_code == 200
    data = accept_res.json()
    assert data["accepted_at"] is not None

    # Verify the invitee now appears in the org
    me_res = await client.get(
        "/api/organisations/me",
        headers={"Authorization": f"Bearer {invitee_jwt}"},
    )
    assert me_res.status_code == 200
    org_slugs = [o["slug"] for o in me_res.json()]
    assert "accept-org-1" in org_slugs


@pytest.mark.asyncio
async def test_accept_invite_invalid_token_returns_404(client):
    """Accepting with a non-existent token returns 404."""
    jwt = await _register_and_login(client, "accept-404@example.com")

    res = await client.post(
        "/api/invitations/accept",
        json={"token": "totallyinvalidtoken123456"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_accept_invite_already_member_returns_409(client, db_session):
    """A user who is already a member gets 409 when accepting an invite."""
    owner_jwt = await _register_and_login(client, "alreadymember-owner@example.com")
    await _create_org(client, owner_jwt, "accept-org-2")

    # Invite a fresh email address
    invite_res = await client.post(
        "/api/organisations/accept-org-2/invite",
        json={"email": "fresh-user@example.com"},
        headers={"Authorization": f"Bearer {owner_jwt}"},
    )
    assert invite_res.status_code == 201

    # Retrieve the token from the shared test DB session
    token = await _get_invite_token(db_session, "fresh-user@example.com")
    assert token is not None, "Invite token not found in test DB"

    # The owner (already a member) tries to accept the fresh-user invite
    res = await client.post(
        "/api/invitations/accept",
        json={"token": token},
        headers={"Authorization": f"Bearer {owner_jwt}"},
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_accept_invite_rejects_failed_turnstile(client, db_session, monkeypatch):
    """Invite acceptance returns 403 when Turnstile validation fails."""
    owner_jwt = await _register_and_login(client, "accept-turnstile-owner@example.com")
    invitee_jwt = await _register_and_login(client, "accept-turnstile-user@example.com")
    await _create_org(client, owner_jwt, "accept-turnstile-org")
    invite_res = await client.post(
        "/api/organisations/accept-turnstile-org/invite",
        json={"email": "accept-turnstile-user@example.com"},
        headers={"Authorization": f"Bearer {owner_jwt}"},
    )
    assert invite_res.status_code == 201
    token = await _get_invite_token(db_session, "accept-turnstile-user@example.com")
    assert token is not None
    monkeypatch.setattr(settings, "turnstile_secret_key", "live-secret")

    async def fake_verify_turnstile(token_value, remote_ip=None, *, fail_open=True, context="unknown", expected_action=None, expected_hostname=None):
        assert token_value == "bad-token"
        assert remote_ip == "198.51.100.25"
        assert fail_open is True
        assert context == "invite_accept"
        assert expected_action == "invite_accept"
        return False

    monkeypatch.setattr(invitations_api, "verify_turnstile", fake_verify_turnstile)

    res = await client.post(
        "/api/invitations/accept",
        json={"token": token, "turnstile_token": "bad-token"},
        headers={
            "Authorization": f"Bearer {invitee_jwt}",
            "cf-connecting-ip": "198.51.100.25",
        },
    )
    assert res.status_code == 403
    assert res.json()["detail"] == "Human verification failed. Please try again."


@pytest.mark.asyncio
async def test_accept_invite_accepts_valid_turnstile(client, db_session, monkeypatch):
    """Invite acceptance succeeds when Turnstile validation passes."""
    owner_jwt = await _register_and_login(client, "accept-turnstile-ok-owner@example.com")
    invitee_jwt = await _register_and_login(client, "accept-turnstile-ok-user@example.com")
    await _create_org(client, owner_jwt, "accept-turnstile-ok-org")
    invite_res = await client.post(
        "/api/organisations/accept-turnstile-ok-org/invite",
        json={"email": "accept-turnstile-ok-user@example.com"},
        headers={"Authorization": f"Bearer {owner_jwt}"},
    )
    assert invite_res.status_code == 201
    token = await _get_invite_token(db_session, "accept-turnstile-ok-user@example.com")
    assert token is not None
    monkeypatch.setattr(settings, "turnstile_secret_key", "live-secret")

    async def fake_verify_turnstile(token_value, remote_ip=None, *, fail_open=True, context="unknown", expected_action=None, expected_hostname=None):
        assert token_value == "good-token"
        assert remote_ip == "203.0.113.44"
        assert fail_open is True
        assert context == "invite_accept"
        assert expected_action == "invite_accept"
        return True

    monkeypatch.setattr(invitations_api, "verify_turnstile", fake_verify_turnstile)

    res = await client.post(
        "/api/invitations/accept",
        json={"token": token, "turnstile_token": "good-token"},
        headers={
            "Authorization": f"Bearer {invitee_jwt}",
            "cf-connecting-ip": "203.0.113.44",
        },
    )
    assert res.status_code == 200
    assert res.json()["accepted_at"] is not None


# ---------------------------------------------------------------------------
# GET /api/invitations/preview
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preview_returns_org_name(client, db_session):
    """GET /preview returns org_name, email, expires_at for a valid token."""
    owner_jwt = await _register_and_login(client, "preview-owner@example.com")
    await _create_org(client, owner_jwt, "preview-org-1")

    await client.post(
        "/api/organisations/preview-org-1/invite",
        json={"email": "preview-invitee@example.com"},
        headers={"Authorization": f"Bearer {owner_jwt}"},
    )

    token = await _get_invite_token(db_session, "preview-invitee@example.com")
    assert token is not None

    res = await client.get(f"/api/invitations/preview?token={token}")
    assert res.status_code == 200
    data = res.json()
    assert data["org_name"] == "Preview Org 1"
    assert data["email"] == "preview-invitee@example.com"
    assert "expires_at" in data


@pytest.mark.asyncio
async def test_preview_unknown_token_returns_404(client):
    """GET /preview with a non-existent token returns 404."""
    res = await client.get("/api/invitations/preview?token=doesnotexist123456")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_preview_no_auth_required(client, db_session):
    """GET /preview is callable without an Authorization header."""
    owner_jwt = await _register_and_login(client, "preview-noauth@example.com")
    await _create_org(client, owner_jwt, "preview-org-2")

    await client.post(
        "/api/organisations/preview-org-2/invite",
        json={"email": "noauth-invitee@example.com"},
        headers={"Authorization": f"Bearer {owner_jwt}"},
    )

    token = await _get_invite_token(db_session, "noauth-invitee@example.com")
    # Call WITHOUT any Authorization header
    res = await client.get(f"/api/invitations/preview?token={token}")
    assert res.status_code == 200


# ---------------------------------------------------------------------------
# Email send path — Resend mock
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invite_sends_email_via_resend(client, monkeypatch):
    """When RESEND_API_KEY is set, resend.Emails.send is called with the invite HTML."""
    # Register the owner before patching so the magic-link email goes through the
    # dev-mode code path (resend_api_key is still empty at that point).
    jwt = await _register_and_login(client, "email-send@example.com")
    await _create_org(client, jwt, "email-send-org")

    # Now patch the settings to simulate a configured Resend key.
    # We patch only the invitation service's reference so the auth module
    # (magic-link) is not affected.
    from app.core.config import settings
    monkeypatch.setattr(settings, "resend_api_key", "re_test_key")
    monkeypatch.setattr(settings, "domain", "amendly.eu")

    send_mock = MagicMock(return_value={"id": "email-id-123"})

    with patch("app.services.invitation.resend.Emails.send", send_mock):
        res = await client.post(
            "/api/organisations/email-send-org/invite",
            json={"email": "recipient@example.com"},
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert res.status_code == 201

    # Verify Resend was called exactly once for the invitation email
    assert send_mock.call_count == 1
    call_kwargs = send_mock.call_args[0][0]  # first positional arg (the dict)

    assert call_kwargs["to"] == ["recipient@example.com"]
    assert "Email Send Org" in call_kwargs["subject"]
    # HTML email should contain the branded accept link
    assert "https://amendly.eu/invitations/accept?token=" in call_kwargs["html"]
    # HTML should contain the rich template markers
    assert "Email Send Org" in call_kwargs["html"]
    assert "Accept invitation" in call_kwargs["html"]


@pytest.mark.asyncio
async def test_invite_logs_url_in_dev_mode(client, monkeypatch, capsys):
    """When RESEND_API_KEY is empty, the invite URL is printed to stdout (dev mode)."""
    # Register first (resend_api_key is empty by default — dev mode)
    jwt = await _register_and_login(client, "dev-email@example.com")
    await _create_org(client, jwt, "dev-email-org")

    from app.core.config import settings
    monkeypatch.setattr(settings, "resend_api_key", "")
    monkeypatch.setattr(settings, "domain", "localhost")

    res = await client.post(
        "/api/organisations/dev-email-org/invite",
        json={"email": "dev-recipient@example.com"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 201

    captured = capsys.readouterr()
    assert "localhost/invitations/accept?token=" in captured.out
    assert "dev-recipient@example.com" in captured.out


@pytest.mark.asyncio
async def test_invite_email_failure_returns_503(client, monkeypatch):
    """When Resend raises an exception the endpoint returns 503."""
    # Register before patching so magic-link flow is unaffected
    jwt = await _register_and_login(client, "email-fail@example.com")
    await _create_org(client, jwt, "email-fail-org")

    from app.core.config import settings
    monkeypatch.setattr(settings, "resend_api_key", "re_test_key")

    with patch("app.services.invitation.resend.Emails.send", side_effect=Exception("Network error")):
        res = await client.post(
            "/api/organisations/email-fail-org/invite",
            json={"email": "fail-recipient@example.com"},
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert res.status_code == 503
