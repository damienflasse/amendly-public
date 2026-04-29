"""
Inbound message endpoint tests for /api/contact and /api/support.
"""

from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.api.inbox as inbox_api
from app.api.auth import _magic_link_store
from app.core.database import Base, get_db
from app.main import app
from app.models.organisation import Organisation, OrgPlan

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


@pytest.fixture(autouse=True)
def reset_contact_rate_limits():
    """Reset public contact rate-limit state between tests."""
    inbox_api._contact_rate_limit_window.clear()
    inbox_api._contact_rate_limit_redis_client = None


async def _register_and_login(client: AsyncClient, email: str) -> str:
    """Register a new user via magic link and return the JWT access token."""
    await client.post("/api/auth/magic-link/request", json={"email": email})
    token = next(t for t, v in _magic_link_store.items() if v["email"] == email)
    res = await client.post("/api/auth/magic-link/verify", json={"token": token})
    return res.json()["access_token"]


async def _create_org(client: AsyncClient, jwt: str, slug: str) -> dict:
    """Create an organisation and return its response dict."""
    res = await client.post(
        "/api/organisations",
        json={"name": f"Org {slug}", "slug": slug},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 201
    return res.json()


async def _upgrade_to_team(db_session: AsyncSession, slug: str) -> None:
    """Upgrade an organisation's plan to 'team' directly in the database."""
    result = await db_session.execute(
        select(Organisation).where(Organisation.slug == slug)
    )
    org = result.scalar_one()
    org.plan = OrgPlan.team
    await db_session.flush()


@pytest.mark.asyncio
async def test_contact_sends_email_via_resend(client, monkeypatch):
    """Public contact submissions are forwarded to the configured inbox."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "resend_api_key", "re_test_key")
    monkeypatch.setattr(settings, "support_inbox_email", "hello@amendly.eu")
    send_mock = MagicMock(return_value={"id": "email-id-123"})

    with patch("app.services.inbox.resend.Emails.send", send_mock):
        res = await client.post(
            "/api/contact",
            json={
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane@example.com",
                "message": "I would like a product demo.",
            },
        )

    assert res.status_code == 200
    assert res.json() == {"ok": True}
    assert send_mock.call_count == 1
    call_kwargs = send_mock.call_args[0][0]
    assert call_kwargs["to"] == ["hello@amendly.eu"]
    assert call_kwargs["reply_to"] == ["jane@example.com"]
    assert call_kwargs["subject"] == "[Contact] Jane Doe"
    assert "I would like a product demo." in call_kwargs["html"]


@pytest.mark.asyncio
async def test_contact_honeypot_skips_delivery(client, monkeypatch):
    """Filled honeypot fields are accepted but do not trigger email delivery."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "resend_api_key", "re_test_key")
    send_mock = MagicMock(return_value={"id": "email-id-123"})

    with patch("app.services.inbox.resend.Emails.send", send_mock):
        res = await client.post(
            "/api/contact",
            json={
                "first_name": "Bot",
                "last_name": "Trap",
                "email": "bot@example.com",
                "message": "Spam",
                "website": "https://spam.example.com",
            },
        )

    assert res.status_code == 200
    assert res.json() == {"ok": True}
    assert send_mock.call_count == 0


@pytest.mark.asyncio
async def test_contact_rate_limit_returns_429(client, monkeypatch):
    """Public contact submissions are capped per IP address."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "resend_api_key", "re_test_key")
    send_mock = MagicMock(return_value={"id": "email-id-123"})

    with patch("app.services.inbox.resend.Emails.send", send_mock):
        for index in range(inbox_api._CONTACT_RATE_LIMIT):
            res = await client.post(
                "/api/contact",
                json={
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "email": f"jane{index}@example.com",
                    "message": "Need help with pricing.",
                },
            )
            assert res.status_code == 200

        blocked = await client.post(
            "/api/contact",
            json={
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "blocked@example.com",
                "message": "Need help with pricing.",
            },
        )

    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "Too many contact requests. Please try again later."


@pytest.mark.asyncio
async def test_support_requires_authentication(client):
    """The support endpoint is restricted to authenticated users."""
    res = await client.post(
        "/api/support",
        json={
            "category": "billing",
            "subject": "Invoice question",
            "message": "Can you clarify the seat count on my invoice?",
        },
    )
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_support_sends_email_with_priority_metadata(client, db_session, monkeypatch):
    """Authenticated support submissions include the resolved tier metadata."""
    from app.core.config import settings

    jwt = await _register_and_login(client, "support-user@example.com")
    await _create_org(client, jwt, "support-tier-org")
    await _upgrade_to_team(db_session, "support-tier-org")

    monkeypatch.setattr(settings, "resend_api_key", "re_test_key")
    monkeypatch.setattr(settings, "support_inbox_email", "hello@amendly.eu")
    send_mock = MagicMock(return_value={"id": "email-id-123"})

    with patch("app.services.inbox.resend.Emails.send", send_mock):
        res = await client.post(
            "/api/support",
            json={
                "category": "billing",
                "subject": "Seat billing mismatch",
                "message": "The number of billed seats looks wrong after inviting a member.",
            },
            headers={"Authorization": f"Bearer {jwt}"},
        )

    assert res.status_code == 200
    assert res.json() == {"ok": True}
    assert send_mock.call_count == 1
    call_kwargs = send_mock.call_args[0][0]
    assert call_kwargs["to"] == ["hello@amendly.eu"]
    assert call_kwargs["reply_to"] == ["support-user@example.com"]
    assert call_kwargs["subject"] == "[Support][priority][billing] Seat billing mismatch"
    assert "support-tier-org" in call_kwargs["html"]
    assert "priority" in call_kwargs["html"]
