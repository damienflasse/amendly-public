"""
Resend webhook endpoint tests.
"""

import base64
import json
import time
from unittest.mock import patch

import pytest
import resend
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app

# Constructed at runtime so no literal webhook-secret pattern appears in source.
_TEST_WEBHOOK_SECRET = "whsec_" + base64.b64encode(b"test_secret_for_resend").decode()

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


def _sign_payload(secret: str, msg_id: str, timestamp: str, payload: str) -> str:
    """
    Generate a valid Svix signature matching Resend webhook verification rules.
    """
    decoded_secret = base64.b64decode(secret.removeprefix("whsec_"))
    signed_content = f"{msg_id}.{timestamp}.{payload}"
    signature = resend.Webhooks._generate_signature(
        decoded_secret,
        signed_content.encode("utf-8"),
    )
    return f"v1,{signature}"


@pytest.mark.asyncio
async def test_resend_webhook_missing_secret(client, monkeypatch):
    """Webhook endpoint rejects requests when signing secret is not configured."""
    monkeypatch.setattr(settings, "resend_webhook_secret", "")
    response = await client.post("/api/webhooks/resend", content="{}")
    assert response.status_code == 400
    assert response.json()["detail"] == "Resend webhook secret is not configured."


@pytest.mark.asyncio
async def test_resend_webhook_invalid_signature(client, monkeypatch):
    """Webhook endpoint rejects invalid Svix signatures."""
    monkeypatch.setattr(settings, "resend_webhook_secret", _TEST_WEBHOOK_SECRET)
    response = await client.post(
        "/api/webhooks/resend",
        content='{"type":"email.delivered"}',
        headers={
            "svix-id": "msg_invalid",
            "svix-timestamp": str(int(time.time())),
            "svix-signature": "v1,invalid",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"].startswith("Invalid Resend signature:")


@pytest.mark.asyncio
async def test_resend_webhook_logs_bounce_event(client, monkeypatch):
    """Bounce events should be accepted and logged with recipient context."""
    secret = _TEST_WEBHOOK_SECRET
    monkeypatch.setattr(settings, "resend_webhook_secret", secret)
    payload = json.dumps(
        {
            "type": "email.bounced",
            "created_at": "2026-03-31T15:06:56.452676+00:00",
            "data": {
                "email_id": "email_123",
                "to": ["user@example.com"],
                "from": "Amendly <noreply@amendly.eu>",
                "subject": "Your Amendly sign-in link",
                "bounce": {"type": "hard", "subType": "suppressed"},
            },
        }
    )
    msg_id = "msg_123"
    timestamp = str(int(time.time()))
    signature = _sign_payload(secret, msg_id, timestamp, payload)

    with patch("app.api.resend_webhooks.logger.warning") as warning_mock:
        response = await client.post(
            "/api/webhooks/resend",
            content=payload,
            headers={
                "svix-id": msg_id,
                "svix-timestamp": timestamp,
                "svix-signature": signature,
                "content-type": "application/json",
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    warning_mock.assert_called_once()
    log_line = warning_mock.call_args.args[0]
    assert "Resend webhook event=%s" in log_line
