"""
Turnstile utility tests.
"""

import logging

import pytest

from app.core.config import settings
from app.utils import turnstile as turnstile_utils


class _FakeResponse:
    """Minimal httpx-like response stub for Turnstile utility tests."""

    def __init__(self, payload: dict, status_code: int = 200):
        """Initialise the fake JSON payload and HTTP status code."""
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def raise_for_status(self) -> None:
        """Mimic a successful HTTP response."""
        return None

    def json(self) -> dict:
        """Return the fake JSON payload."""
        return self._payload


class _FakeAsyncClient:
    """Minimal async client stub that returns a pre-baked response."""

    def __init__(self, response: _FakeResponse):
        """Store the response object that should be returned from post()."""
        self._response = response

    async def __aenter__(self):
        """Enter the async context manager."""
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Exit the async context manager without suppressing exceptions."""
        return False

    async def post(self, url: str, data: dict[str, str]):
        """Return the pre-baked response."""
        return self._response


@pytest.mark.asyncio
async def test_verify_turnstile_logs_cloudflare_rejection(monkeypatch, caplog):
    """Cloudflare rejection details should be logged for production diagnosis."""
    monkeypatch.setattr(settings, "turnstile_secret_key", "live-secret")
    monkeypatch.setattr(settings, "domain", "amendly.eu")
    response = _FakeResponse(
        {
            "success": False,
            "hostname": "amendly.eu",
            "action": "login",
            "cdata": "magic-link",
            "error-codes": ["invalid-input-response", "timeout-or-duplicate"],
        }
    )
    monkeypatch.setattr(
        turnstile_utils.httpx,
        "AsyncClient",
        lambda timeout=5: _FakeAsyncClient(response),
    )

    with caplog.at_level(logging.WARNING):
        result = await turnstile_utils.verify_turnstile(
            "bad-token",
            "203.0.113.10",
            context="auth_magic_link",
        )

    assert result is False
    assert "context=auth_magic_link" in caplog.text
    assert "hostname=amendly.eu" in caplog.text
    assert "invalid-input-response,timeout-or-duplicate" in caplog.text


@pytest.mark.asyncio
async def test_verify_turnstile_rejects_action_mismatch(monkeypatch, caplog):
    """A successful Turnstile response must still match the expected action."""
    monkeypatch.setattr(settings, "turnstile_secret_key", "live-secret")
    monkeypatch.setattr(settings, "domain", "amendly.eu")
    monkeypatch.setattr(settings, "allowed_origins_raw", "https://app.amendly.eu")
    response = _FakeResponse(
        {
            "success": True,
            "hostname": "app.amendly.eu",
            "action": "waitlist",
            "error-codes": [],
        }
    )
    monkeypatch.setattr(
        turnstile_utils.httpx,
        "AsyncClient",
        lambda timeout=5: _FakeAsyncClient(response),
    )

    with caplog.at_level(logging.WARNING):
        result = await turnstile_utils.verify_turnstile(
            "token",
            "203.0.113.10",
            context="auth_magic_link",
            expected_action="auth_magic_link",
        )

    assert result is False
    assert "Turnstile action mismatch" in caplog.text


@pytest.mark.asyncio
async def test_verify_turnstile_fails_closed_on_network_error_in_production(monkeypatch):
    """Production verification defaults to fail-closed on upstream failures."""
    monkeypatch.setattr(settings, "turnstile_secret_key", "live-secret")
    monkeypatch.setattr(settings, "environment", "production")

    class _BrokenAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, data: dict[str, str]):
            raise RuntimeError("network down")

    monkeypatch.setattr(
        turnstile_utils.httpx,
        "AsyncClient",
        lambda timeout=5: _BrokenAsyncClient(),
    )

    result = await turnstile_utils.verify_turnstile(
        "token",
        "203.0.113.10",
        context="waitlist",
        expected_action="waitlist",
    )

    assert result is False
