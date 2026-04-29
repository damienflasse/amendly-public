"""
Cloudflare Turnstile helpers shared by public and authenticated endpoints.
"""

import logging
from collections.abc import Sequence
from urllib.parse import urlparse

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def _expected_hostnames() -> set[str]:
    hostnames = {settings.domain.lower()}
    for origin in settings.allowed_origins:
        parsed = urlparse(origin)
        if parsed.hostname:
            hostnames.add(parsed.hostname.lower())
    return {hostname for hostname in hostnames if hostname}


async def verify_turnstile(
    token: str | None,
    remote_ip: str | None = None,
    *,
    fail_open: bool | None = None,
    context: str = "unknown",
    expected_action: str | None = None,
    expected_hostname: str | Sequence[str] | None = None,
) -> bool:
    """
    Validate a Cloudflare Turnstile token against the siteverify API.

    Parameters:
        token: Visitor token returned by the Turnstile widget.
        remote_ip: Optional client IP forwarded to Cloudflare.
        fail_open: When True, network or API errors allow the request through.
            Defaults to fail-closed in production and fail-open elsewhere.
        context: Short label describing which endpoint triggered verification.
        expected_action: Expected Turnstile action string for this flow.
        expected_hostname: Allowed hostname or hostnames for the Turnstile response.

    Returns:
        True when verification succeeds, when the secret is unset or set to
        "test" (dev/CI bypass), or when fail_open=True and the request fails.
        False when a configured Turnstile check fails or the token is missing.
    """
    secret = settings.turnstile_secret_key
    if fail_open is None:
        fail_open = not settings.is_production
    if not secret or secret == "test":
        return True
    if not token:
        logger.warning("Turnstile token missing for context=%s.", context)
        return False

    payload: dict[str, str] = {"secret": secret, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(_TURNSTILE_VERIFY_URL, data=payload)
            response.raise_for_status()
            data = response.json()
            success = bool(data.get("success"))
            if not success:
                error_codes = data.get("error-codes")
                if not isinstance(error_codes, Sequence) or isinstance(error_codes, str):
                    error_codes = []
                logger.warning(
                    "Turnstile verification rejected for context=%s hostname=%s action=%s cdata=%s errors=%s.",
                    context,
                    data.get("hostname"),
                    data.get("action"),
                    data.get("cdata"),
                    ",".join(str(code) for code in error_codes) or "none",
                )
                return False

            hostname = (data.get("hostname") or "").strip().lower()
            valid_hostnames: set[str]
            if expected_hostname is None:
                valid_hostnames = _expected_hostnames()
            elif isinstance(expected_hostname, str):
                valid_hostnames = {expected_hostname.strip().lower()}
            else:
                valid_hostnames = {item.strip().lower() for item in expected_hostname if item and item.strip()}

            if valid_hostnames and hostname not in valid_hostnames:
                logger.warning(
                    "Turnstile hostname mismatch for context=%s hostname=%s expected=%s.",
                    context,
                    hostname or "missing",
                    ",".join(sorted(valid_hostnames)),
                )
                return False

            action = (data.get("action") or "").strip()
            if expected_action and action != expected_action:
                logger.warning(
                    "Turnstile action mismatch for context=%s action=%s expected=%s hostname=%s.",
                    context,
                    action or "missing",
                    expected_action,
                    hostname or "missing",
                )
                return False

            return True
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Turnstile verification HTTP error for context=%s status=%s body=%s.",
            context,
            exc.response.status_code,
            exc.response.text[:200],
        )
        return fail_open
    except Exception:
        logger.warning(
            "Turnstile verification request failed for context=%s.",
            context,
            exc_info=True,
        )
        return fail_open
