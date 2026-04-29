"""
Notification preferences endpoint tests.

Covers PATCH /api/auth/me/preferences and the downstream behaviour that
amendment status emails are suppressed when email_notifications_enabled=False.

Uses the same in-memory SQLite pattern as the other test modules — no live
Postgres or Redis is needed.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app

# ---------------------------------------------------------------------------
# In-memory SQLite test database fixtures (mirrors test_auth.py pattern)
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


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
# Helper: register a user and return (jwt, email)
# ---------------------------------------------------------------------------

async def _register_user(client, email: str) -> str:
    """Register a user via magic-link flow and return the JWT."""
    from app.api.auth import _magic_link_store

    res = await client.post("/api/auth/magic-link/request", json={"email": email})
    assert res.status_code == 202

    token = next(t for t, v in _magic_link_store.items() if v["email"] == email)
    res = await client.post("/api/auth/magic-link/verify", json={"token": token})
    assert res.status_code == 200
    return res.json()["access_token"]


# ---------------------------------------------------------------------------
# PATCH /api/auth/me/preferences — unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preferences_unauthenticated(client):
    """PATCH /api/auth/me/preferences without a token should return 401."""
    res = await client.patch(
        "/api/auth/me/preferences",
        json={"email_notifications_enabled": False},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_preferences_default_is_true(client):
    """
    A freshly registered user should have email_notifications_enabled=True
    as returned by GET /api/auth/me.
    """
    jwt = await _register_user(client, "default-prefs@example.com")
    headers = {"Authorization": f"Bearer {jwt}"}
    res = await client.get("/api/auth/me", headers=headers)
    assert res.status_code == 200
    assert res.json()["email_notifications_enabled"] is True


@pytest.mark.asyncio
async def test_disable_notifications(client):
    """
    PATCH /api/auth/me/preferences with email_notifications_enabled=False
    should return 200 with the updated value.
    """
    jwt = await _register_user(client, "opt-out@example.com")
    headers = {"Authorization": f"Bearer {jwt}"}

    res = await client.patch(
        "/api/auth/me/preferences",
        json={"email_notifications_enabled": False},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["email_notifications_enabled"] is False

    # Verify GET /me reflects the change
    res = await client.get("/api/auth/me", headers=headers)
    assert res.status_code == 200
    assert res.json()["email_notifications_enabled"] is False


@pytest.mark.asyncio
async def test_reenable_notifications(client):
    """
    Toggling email_notifications_enabled from False back to True should persist.
    """
    jwt = await _register_user(client, "re-enable@example.com")
    headers = {"Authorization": f"Bearer {jwt}"}

    # Disable first
    res = await client.patch(
        "/api/auth/me/preferences",
        json={"email_notifications_enabled": False},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["email_notifications_enabled"] is False

    # Re-enable
    res = await client.patch(
        "/api/auth/me/preferences",
        json={"email_notifications_enabled": True},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["email_notifications_enabled"] is True


@pytest.mark.asyncio
async def test_preferences_missing_field(client):
    """PATCH with an empty body should return 422 (field is required)."""
    jwt = await _register_user(client, "bad-prefs@example.com")
    headers = {"Authorization": f"Bearer {jwt}"}

    res = await client.patch(
        "/api/auth/me/preferences",
        json={},
        headers=headers,
    )
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# Downstream behaviour: email suppressed when opted out
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_email_suppressed_when_opted_out(client):
    """
    When a user has email_notifications_enabled=False, update_amendment_status
    must NOT call send_amendment_status_email even if the amendment is accepted.

    The amendment acceptance flow is exercised indirectly through the service
    layer; we patch send_amendment_status_email and verify it is NOT called.
    """
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.amendment import Amendment, AmendmentStatus
    from app.models.document import Document
    from app.models.membership import MemberRole, Membership
    from app.models.organisation import Organisation
    from app.models.user import User
    from app.services.amendment import update_amendment_status
    from app.schemas.amendment import AmendmentStatusUpdate

    # Build minimal DB state directly (bypassing HTTP for speed)
    # We need the db_session fixture — access it via the app override
    async def _get_session():
        """Pull the test session from the current dependency override."""
        return app.dependency_overrides[get_db]

    # Use the db_session fixture indirectly by calling the service layer with
    # a real session sourced via the fixture.  We need a separate fixture access
    # — instead, use the HTTP layer to set up state then call the service.

    # 1. Register author (opted-out) and admin via magic-link
    author_jwt = await _register_user(client, "opted-out-author@example.com")
    admin_jwt = await _register_user(client, "opted-out-admin@example.com")

    # 2. Admin creates an org
    res = await client.post(
        "/api/organisations",
        json={"name": "Test Org Prefs", "slug": "test-org-prefs"},
        headers={"Authorization": f"Bearer {admin_jwt}"},
    )
    assert res.status_code == 201

    # 3. Invite and add the author as a member (via the invite API)
    res = await client.post(
        "/api/organisations/test-org-prefs/invite",
        json={"email": "opted-out-author@example.com"},
        headers={"Authorization": f"Bearer {admin_jwt}"},
    )
    assert res.status_code in (200, 201)

    # Fetch the invitation token and accept it
    from sqlalchemy import select as sa_select
    from app.models.invitation import Invitation

    # We need a DB session — retrieve it from the dependency override
    db_gen = app.dependency_overrides[get_db]()
    db: AsyncSession = await db_gen.__anext__()

    inv_result = await db.execute(
        sa_select(Invitation)
        .where(Invitation.email == "opted-out-author@example.com")
        .order_by(Invitation.created_at.desc())
        .limit(1)
    )
    inv = inv_result.scalar_one_or_none()
    assert inv is not None, "Invitation not created"
    inv_token = inv.token

    await db_gen.aclose()

    res = await client.post(
        "/api/invitations/accept",
        json={"token": inv_token},
        headers={"Authorization": f"Bearer {author_jwt}"},
    )
    assert res.status_code == 200

    # 4. Author opts out of email notifications
    res = await client.patch(
        "/api/auth/me/preferences",
        json={"email_notifications_enabled": False},
        headers={"Authorization": f"Bearer {author_jwt}"},
    )
    assert res.status_code == 200

    # 5. Create a document
    res = await client.post(
        "/api/organisations/test-org-prefs/documents",
        json={"title": "Test Doc Prefs", "body": "Original text."},
        headers={"Authorization": f"Bearer {admin_jwt}"},
    )
    assert res.status_code == 201
    doc_id = res.json()["id"]

    # 6. Author submits an amendment
    res = await client.post(
        f"/api/organisations/test-org-prefs/documents/{doc_id}/amendments",
        json={
            "original_text": "Original text.",
            "proposed_text": "Updated text.",
        },
        headers={"Authorization": f"Bearer {author_jwt}"},
    )
    assert res.status_code == 201
    amendment_id = res.json()["id"]

    # 7. Admin accepts the amendment — email must NOT be sent
    with patch(
        "app.services.amendment.send_amendment_status_email",
        new_callable=AsyncMock,
    ) as mock_email:
        res = await client.put(
            f"/api/organisations/test-org-prefs/documents/{doc_id}/amendments/{amendment_id}/status",
            json={"status": "accepted"},
            headers={"Authorization": f"Bearer {admin_jwt}"},
        )
        assert res.status_code == 200
        mock_email.assert_not_called()


@pytest.mark.asyncio
async def test_email_sent_when_opted_in(client):
    """
    When a user has email_notifications_enabled=True (default), accepting an
    amendment MUST call send_amendment_status_email.
    """
    author_jwt = await _register_user(client, "opted-in-author@example.com")
    admin_jwt = await _register_user(client, "opted-in-admin@example.com")

    res = await client.post(
        "/api/organisations",
        json={"name": "Test Org Prefs2", "slug": "test-org-prefs2"},
        headers={"Authorization": f"Bearer {admin_jwt}"},
    )
    assert res.status_code == 201

    # Invite author
    res = await client.post(
        "/api/organisations/test-org-prefs2/invite",
        json={"email": "opted-in-author@example.com"},
        headers={"Authorization": f"Bearer {admin_jwt}"},
    )
    assert res.status_code in (200, 201)

    from sqlalchemy import select as sa_select
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.invitation import Invitation

    db_gen = app.dependency_overrides[get_db]()
    db: AsyncSession = await db_gen.__anext__()
    inv_result = await db.execute(
        sa_select(Invitation)
        .where(Invitation.email == "opted-in-author@example.com")
        .order_by(Invitation.created_at.desc())
        .limit(1)
    )
    inv = inv_result.scalar_one_or_none()
    assert inv is not None
    inv_token = inv.token
    await db_gen.aclose()

    res = await client.post(
        "/api/invitations/accept",
        json={"token": inv_token},
        headers={"Authorization": f"Bearer {author_jwt}"},
    )
    assert res.status_code == 200

    # Author does NOT opt out — default is True
    res = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {author_jwt}"})
    assert res.json()["email_notifications_enabled"] is True

    # Create doc and amendment
    res = await client.post(
        "/api/organisations/test-org-prefs2/documents",
        json={"title": "Test Doc Prefs2", "body": "Original text."},
        headers={"Authorization": f"Bearer {admin_jwt}"},
    )
    assert res.status_code == 201
    doc_id = res.json()["id"]

    res = await client.post(
        f"/api/organisations/test-org-prefs2/documents/{doc_id}/amendments",
        json={
            "original_text": "Original text.",
            "proposed_text": "Revised text.",
        },
        headers={"Authorization": f"Bearer {author_jwt}"},
    )
    assert res.status_code == 201
    amendment_id = res.json()["id"]

    # Accept amendment — email MUST be attempted
    with patch(
        "app.services.amendment.send_amendment_status_email",
        new_callable=AsyncMock,
    ) as mock_email:
        res = await client.put(
            f"/api/organisations/test-org-prefs2/documents/{doc_id}/amendments/{amendment_id}/status",
            json={"status": "accepted"},
            headers={"Authorization": f"Bearer {admin_jwt}"},
        )
        assert res.status_code == 200
        mock_email.assert_called_once()


# ---------------------------------------------------------------------------
# Per-org mute suppression
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_status_email_suppressed_when_org_muted(client):
    """
    When an author has notifications_muted=True for the amendment's org,
    update_amendment_status must NOT call send_amendment_status_email even
    if the amendment is accepted and email_notifications_enabled is True.
    """
    author_jwt = await _register_user(client, "muted-author@example.com")
    admin_jwt = await _register_user(client, "muted-admin@example.com")

    # Admin creates org
    res = await client.post(
        "/api/organisations",
        json={"name": "Muted Org Status", "slug": "muted-org-status"},
        headers={"Authorization": f"Bearer {admin_jwt}"},
    )
    assert res.status_code == 201

    # Invite author
    res = await client.post(
        "/api/organisations/muted-org-status/invite",
        json={"email": "muted-author@example.com"},
        headers={"Authorization": f"Bearer {admin_jwt}"},
    )
    assert res.status_code in (200, 201)

    from sqlalchemy import select as sa_select
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.invitation import Invitation

    db_gen = app.dependency_overrides[get_db]()
    db: AsyncSession = await db_gen.__anext__()
    inv_result = await db.execute(
        sa_select(Invitation)
        .where(Invitation.email == "muted-author@example.com")
        .order_by(Invitation.created_at.desc())
        .limit(1)
    )
    inv = inv_result.scalar_one_or_none()
    assert inv is not None
    inv_token = inv.token
    await db_gen.aclose()

    res = await client.post(
        "/api/invitations/accept",
        json={"token": inv_token},
        headers={"Authorization": f"Bearer {author_jwt}"},
    )
    assert res.status_code == 200

    # Author mutes notifications for this org (global pref stays enabled)
    res = await client.patch(
        "/api/organisations/muted-org-status/notification-settings",
        json={"notifications_muted": True},
        headers={"Authorization": f"Bearer {author_jwt}"},
    )
    assert res.status_code == 200
    assert res.json()["notifications_muted"] is True

    # Confirm global email_notifications_enabled is still True
    res = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {author_jwt}"})
    assert res.json()["email_notifications_enabled"] is True

    # Create doc and amendment
    res = await client.post(
        "/api/organisations/muted-org-status/documents",
        json={"title": "Doc Muted Status", "body": "Original text."},
        headers={"Authorization": f"Bearer {admin_jwt}"},
    )
    assert res.status_code == 201
    doc_id = res.json()["id"]

    res = await client.post(
        f"/api/organisations/muted-org-status/documents/{doc_id}/amendments",
        json={"original_text": "Original text.", "proposed_text": "Changed text."},
        headers={"Authorization": f"Bearer {author_jwt}"},
    )
    assert res.status_code == 201
    amendment_id = res.json()["id"]

    # Accept amendment — status email must NOT be sent
    with patch(
        "app.services.amendment.send_amendment_status_email",
        new_callable=AsyncMock,
    ) as mock_email:
        res = await client.put(
            f"/api/organisations/muted-org-status/documents/{doc_id}/amendments/{amendment_id}/status",
            json={"status": "accepted"},
            headers={"Authorization": f"Bearer {admin_jwt}"},
        )
        assert res.status_code == 200
        mock_email.assert_not_called()


@pytest.mark.asyncio
async def test_submitted_email_suppressed_when_org_muted(client):
    """
    When an admin has notifications_muted=True for the org, submitting an
    amendment must NOT call send_amendment_submitted_email for that admin,
    even if email_notifications_enabled is True.
    """
    contributor_jwt = await _register_user(client, "contributor-mute@example.com")
    admin_jwt = await _register_user(client, "admin-mute@example.com")

    # Admin creates org
    res = await client.post(
        "/api/organisations",
        json={"name": "Muted Org Submit", "slug": "muted-org-submit"},
        headers={"Authorization": f"Bearer {admin_jwt}"},
    )
    assert res.status_code == 201

    # Invite contributor
    res = await client.post(
        "/api/organisations/muted-org-submit/invite",
        json={"email": "contributor-mute@example.com"},
        headers={"Authorization": f"Bearer {admin_jwt}"},
    )
    assert res.status_code in (200, 201)

    from sqlalchemy import select as sa_select
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.invitation import Invitation

    db_gen = app.dependency_overrides[get_db]()
    db: AsyncSession = await db_gen.__anext__()
    inv_result = await db.execute(
        sa_select(Invitation)
        .where(Invitation.email == "contributor-mute@example.com")
        .order_by(Invitation.created_at.desc())
        .limit(1)
    )
    inv = inv_result.scalar_one_or_none()
    assert inv is not None
    inv_token = inv.token
    await db_gen.aclose()

    res = await client.post(
        "/api/invitations/accept",
        json={"token": inv_token},
        headers={"Authorization": f"Bearer {contributor_jwt}"},
    )
    assert res.status_code == 200

    # Admin mutes notifications for this org
    res = await client.patch(
        "/api/organisations/muted-org-submit/notification-settings",
        json={"notifications_muted": True},
        headers={"Authorization": f"Bearer {admin_jwt}"},
    )
    assert res.status_code == 200
    assert res.json()["notifications_muted"] is True

    # Create doc
    res = await client.post(
        "/api/organisations/muted-org-submit/documents",
        json={"title": "Doc Submit Muted", "body": "Some text."},
        headers={"Authorization": f"Bearer {admin_jwt}"},
    )
    assert res.status_code == 201
    doc_id = res.json()["id"]

    # Contributor submits amendment — submitted email must NOT be sent to the muted admin
    with patch(
        "app.services.amendment.send_amendment_submitted_email",
        new_callable=AsyncMock,
    ) as mock_email:
        res = await client.post(
            f"/api/organisations/muted-org-submit/documents/{doc_id}/amendments",
            json={"original_text": "Some text.", "proposed_text": "Better text."},
            headers={"Authorization": f"Bearer {contributor_jwt}"},
        )
        assert res.status_code == 201
        mock_email.assert_not_called()
