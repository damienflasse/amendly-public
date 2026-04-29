"""
Authentication core — Amendly auth system.

Provides:
  - JWT access-token creation and verification (used for session cookies and explicit tooling Bearer tokens)
  - Magic-link token generation and email dispatch via Resend
  - OAuth state validation helpers (Google)
  - `get_current_user` FastAPI dependency — attaches the authenticated User to the request

Architecture note
-----------------
Authentication is implemented directly in the FastAPI backend.
The legacy environment variable name `BETTER_AUTH_SECRET` is still used as the
JWT signing secret to avoid breaking existing deployments.

Current primitives:
  * `PyJWT`         → JWT signing (HS256 with BETTER_AUTH_SECRET)
  * `hashlib`       → SHA-256 hashing for magic-link token storage
  * `resend`        → transactional e-mail delivery
  * `httpx`         → outbound OAuth token exchange calls

The frontend calls the `/api/auth/*` routes through `frontend/src/lib/auth.js`.
"""

import logging
import secrets
import string
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import resend
from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.utils.rate_limit import get_redis_client

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days
MAGIC_LINK_EXPIRE_MINUTES = 15             # 15-minute one-time link

_bearer_scheme = HTTPBearer(auto_error=False)
logger = logging.getLogger("uvicorn.error")
SESSION_COOKIE_NAME = "amendly_session"
TOOLING_AUTH_MODE_HEADER = "x-amendly-auth-mode"
TOOLING_AUTH_MODE_BEARER = "bearer"


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def create_access_token(
    subject: str,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a signed JWT access token.

    Parameters:
        subject: The `sub` claim — typically the user's UUID string.
        extra_claims: Optional additional claims merged into the payload.
        expires_delta: Custom expiry window; defaults to ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        A signed JWT string.
    """
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(UTC),
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.better_auth_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and verify a JWT access token.

    Parameters:
        token: Encoded JWT string.

    Returns:
        Decoded payload dict.

    Raises:
        HTTPException 401: If the token is invalid, expired, or unsigned.
    """
    try:
        payload = jwt.decode(token, settings.better_auth_secret, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ---------------------------------------------------------------------------
# Magic-link helpers
# ---------------------------------------------------------------------------

_SAFE_CHARS = string.ascii_letters + string.digits


def generate_magic_token(length: int = 48) -> str:
    """
    Generate a cryptographically secure URL-safe token for magic links.

    Parameters:
        length: Number of characters in the generated token (default 48).

    Returns:
        A URL-safe random token string.
    """
    return "".join(secrets.choice(_SAFE_CHARS) for _ in range(length))


async def send_magic_link(
    email: str, token: str, db: AsyncSession | None = None
) -> None:
    """
    Send a magic-link e-mail via Resend.

    Uses the 'magic_link' email template from the DB if one exists (editable by
    the superadmin), otherwise falls back to a simple hardcoded HTML body.

    The link embeds the one-time token as a query parameter.
    The frontend /auth/verify route reads the token and exchanges it for a session.

    Parameters:
        email: Recipient e-mail address.
        token: One-time magic-link token (plain text before storage).
        db: Optional async DB session — used to load the editable email template.
            When None, the hardcoded fallback is used.

    Side effects:
        Sends a transactional e-mail via the Resend API.

    Raises:
        HTTPException 503: If Resend API call fails (key missing or API error).
    """
    scheme = "http" if settings.domain in ("localhost", "127.0.0.1") else "https"
    magic_url = f"{scheme}://{settings.domain}/auth/verify?token={token}"

    if not settings.resend_api_key:
        print(f"[DEV] Magic link for {email}: {magic_url}")
        return

    resend.api_key = settings.resend_api_key

    subject = "Your Amendly sign-in link"
    html_body = ""

    if db is not None:
        try:
            from app.services.email_template import render_template  # noqa: PLC0415
            subject, html_body = await render_template(
                db, "magic_link", {"magic_link_url": magic_url}
            )
        except Exception as exc:
            logger.warning("Failed to render magic_link template from DB: %s", exc)

    if not html_body:
        html_body = (
            f"<p>Click the link below to sign in to Amendly. "
            f"This link expires in {MAGIC_LINK_EXPIRE_MINUTES} minutes.</p>"
            f'<p><a href="{magic_url}">Sign in to Amendly &rarr;</a></p>'
            f"<p>If you did not request this, you can safely ignore this email.</p>"
        )

    try:
        result = resend.Emails.send(
            {
                "from": f"Amendly <{settings.resend_from_email}>",
                "to": [email],
                "subject": subject,
                "html": html_body,
            }
        )
        email_id = None
        if isinstance(result, dict):
            email_id = result.get("id")
        else:
            email_id = getattr(result, "id", None)
        logger.info(
            "Magic link email queued via Resend for recipient=%s id=%s.",
            email,
            email_id or "unknown",
        )
    except Exception as exc:
        logger.exception("Magic link email delivery failed for recipient=%s.", email)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email delivery failed. Please try again.",
        ) from exc


# ---------------------------------------------------------------------------
# JWT blocklist — Redis-backed token revocation
# ---------------------------------------------------------------------------

_JWT_BLOCKLIST_PREFIX = "jwt_blocklist:"


def _get_blocklist_redis():
    """
    Return a shared redis.asyncio.Redis client for the JWT blocklist, or None.

    Uses a dedicated cache key so JWT revocation stays isolated from the other
    auth Redis use cases while still sharing the common client bootstrap path.

    Returns:
        A connected redis.asyncio.Redis instance, or None on failure.
    """
    return get_redis_client(
        "jwt_blocklist",
        logger=logger,
        unavailable_message=(
            "Redis unavailable for JWT blocklist; logout revocation will no-op."
        ),
    )


async def revoke_token(jti: str, ttl_seconds: int) -> None:
    """
    Add a JWT's JTI to the Redis blocklist with a TTL matching its remaining lifetime.

    Parameters:
        jti: The JWT ID claim (jti) to revoke.
        ttl_seconds: How long to keep the entry in Redis (should equal remaining JWT lifetime).

    Side effects:
        Writes to Redis. Silently no-ops if Redis is unavailable.
    """
    redis = _get_blocklist_redis()
    if redis is None:
        return
    try:
        await redis.setex(f"{_JWT_BLOCKLIST_PREFIX}{jti}", max(ttl_seconds, 1), "1")
    except Exception as exc:
        logger.warning("Failed to add JWT to Redis blocklist: %s", exc)


async def is_token_revoked(jti: str) -> bool:
    """
    Check whether a JWT's JTI appears in the Redis blocklist.

    Parameters:
        jti: The JWT ID claim to check.

    Returns:
        True if the token has been revoked, False if not (or if Redis is unavailable).
    """
    redis = _get_blocklist_redis()
    if redis is None:
        return False
    try:
        return bool(await redis.exists(f"{_JWT_BLOCKLIST_PREFIX}{jti}"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# FastAPI dependency — current authenticated user
# ---------------------------------------------------------------------------

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency that validates the authenticated user from the session
    cookie for normal browser flows, or from an explicitly requested Bearer
    token path used by tooling and tests.

    Parameters:
        request: Injected FastAPI Request, used to detect explicit tooling mode.
        credentials: Injected by HTTPBearer — contains the raw token string.
        db: Injected async database session.

    Returns:
        The authenticated User ORM instance.

    Raises:
        HTTPException 401: If credentials are missing, invalid, or the user
                           no longer exists in the database.
    """
    auth_mode = request.headers.get(TOOLING_AUTH_MODE_HEADER, "").strip().lower()
    if auth_mode == TOOLING_AUTH_MODE_BEARER:
        raw_token = credentials.credentials if credentials is not None else None
    else:
        raw_token = session_token
    if raw_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(raw_token)

    jti: str | None = payload.get("jti")
    if jti and await is_token_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account has been deleted",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    FastAPI dependency that enforces platform superuser access.

    Must be used after (or in place of) get_current_user.

    Parameters:
        current_user: The authenticated user, injected by get_current_user.

    Returns:
        The same User instance if they are a superuser.

    Raises:
        HTTPException 403: If the user does not have the is_superuser flag.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser access required.",
        )
    return current_user


async def ensure_superuser_seeded(db: AsyncSession) -> None:
    """
    Idempotently set is_superuser=True for the user matching SUPERUSER_EMAIL.

    Called once at application startup.  If SUPERUSER_EMAIL is empty or not
    set in the environment, this function is a no-op.

    Parameters:
        db: An async database session (caller must commit/rollback).

    Side effects:
        Updates the User row identified by settings.superuser_email in the
        database if it exists and is not already a superuser.
    """
    email = settings.superuser_email.strip()
    if not email:
        return

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        print(f"[startup] SUPERUSER_EMAIL={email!r} — user not found, skipping seed")
        return

    if not user.is_superuser:
        user.is_superuser = True
        await db.commit()
        print(f"[startup] Superuser flag set for {email!r}")
