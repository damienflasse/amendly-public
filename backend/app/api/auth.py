"""
Authentication API routes.

These endpoints back the custom frontend auth client in
`frontend/src/lib/auth.js`.

Endpoints:
  POST   /api/auth/magic-link/request  — request a magic-link email
  POST   /api/auth/magic-link/verify   — exchange a magic-link token for a JWT
  GET    /api/auth/oauth/{provider}    — initiate Google OAuth flow
  GET    /api/auth/oauth/callback      — handle OAuth provider callback
  POST   /api/auth/logout              — invalidate the session (client-side only for JWT)
  GET    /api/auth/me                  — return the current authenticated user
  PATCH  /api/auth/me/preferences      — update notification preferences
  DELETE /api/auth/me                  — GDPR right to erasure: anonymise the account
"""

import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.core.auth import (
    MAGIC_LINK_EXPIRE_MINUTES,
    SESSION_COOKIE_NAME,
    TOOLING_AUTH_MODE_BEARER,
    TOOLING_AUTH_MODE_HEADER,
    create_access_token,
    generate_magic_token,
    get_current_user,
    revoke_token,
    send_magic_link,
)
from app.core.config import settings
from app.core.database import get_db
from app.models.membership import MemberRole, Membership
from app.models.organisation import Organisation
from app.models.user import User, UserPlan
from app.services.email import send_welcome_email
from app.utils.rate_limit import check_redis_rate_limit, get_client_ip, get_redis_client
from app.utils.turnstile import verify_turnstile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Pydantic schemas (kept local because they are only used by auth routes)
# ---------------------------------------------------------------------------


class MagicLinkRequest(BaseModel):
    """Body for POST /api/auth/magic-link/request."""

    email: EmailStr
    turnstile_token: str | None = None


class MagicLinkVerify(BaseModel):
    """Body for POST /api/auth/magic-link/verify."""

    token: str


class TokenResponse(BaseModel):
    """Response containing a signed JWT access token."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Public user fields returned by /api/auth/me."""

    id: str
    email: str
    name: str | None
    company: str | None = None
    job_position: str | None = None
    avatar_url: str | None
    plan: str
    email_notifications_enabled: bool = True
    onboarding_completed: bool = False
    is_superuser: bool = False

    model_config = {"from_attributes": True}


class UserPreferencesUpdate(BaseModel):
    """Body for PATCH /api/auth/me/preferences."""

    email_notifications_enabled: bool


class UserProfileUpdate(BaseModel):
    """Body for PATCH /api/auth/me/profile."""

    name: str | None = None
    company: str | None = None
    job_position: str | None = None
    avatar_url: str | None = None

    @field_validator("avatar_url")
    @classmethod
    def validate_avatar_url(cls, v: str | None) -> str | None:
        """Reject non-https URLs to prevent javascript: / data: URI injection."""
        if v is not None and not v.startswith("https://"):
            raise ValueError("avatar_url must be an https:// URL")
        return v


def _session_cookie_secure(request: Request) -> bool:
    """Return True when the session cookie must be marked Secure.

    X-Forwarded-Proto is only trusted when settings.trust_proxy_headers is
    True, which should be enabled only when the backend is exclusively
    reachable through a trusted reverse-proxy (nginx, Cloudflare).  Without
    that guard an attacker reaching the backend directly could send
    X-Forwarded-Proto: http to force Secure=False on the session cookie.
    """
    if settings.trust_proxy_headers:
        forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
        if forwarded_proto:
            return forwarded_proto == "https"
    if request.url.scheme == "https":
        return True
    return settings.domain not in {"localhost", "127.0.0.1"}


def _set_session_cookie(response: Response, request: Request, token: str) -> None:
    """Attach the signed JWT to an httpOnly cookie."""
    max_age = 60 * 60 * 24 * 7
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=max_age,
        expires=max_age,
        httponly=True,
        secure=_session_cookie_secure(request),
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response, request: Request) -> None:
    """Delete the auth session cookie."""
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=_session_cookie_secure(request),
        samesite="lax",
        path="/",
    )


def _extract_request_token(request: Request) -> str | None:
    """Return the current auth token from the browser cookie or explicit tooling header."""
    cookie_token = request.cookies.get(SESSION_COOKIE_NAME)
    if cookie_token:
        return cookie_token

    auth_mode = request.headers.get(TOOLING_AUTH_MODE_HEADER, "").strip().lower()
    if auth_mode != TOOLING_AUTH_MODE_BEARER:
        return None

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.removeprefix("Bearer ").strip() or None
    return None


# ---------------------------------------------------------------------------
# Magic-link store — Redis-backed with in-memory fallback
# ---------------------------------------------------------------------------
# The in-memory dict is the authoritative fallback when Redis is unavailable
# (e.g. during tests or local dev without Redis).  Tests can import
# _magic_link_store directly to inspect tokens without going through Redis.
# Maps token → {"email": str, "expires_at": ISO-8601 string}
_magic_link_store: dict[str, dict] = {}

# Lazy Redis client — initialised once on first use; None if unavailable.
_redis_client = None


def _get_redis():
    """
    Return a shared redis.asyncio.Redis client, or None if Redis is unavailable.

    Attempts to connect using REDIS_URL from settings.  Connection errors are
    caught and logged; the caller should fall back to _magic_link_store.

    Returns:
        A connected redis.asyncio.Redis instance, or None on failure.
    """
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    _redis_client = get_redis_client(
        "auth",
        logger=logger,
        unavailable_message="Redis unavailable — magic-link store will use in-memory fallback.",
    )
    return _redis_client


_REDIS_KEY_PREFIX = "magic_link:"
_REDIS_TTL_SECONDS = MAGIC_LINK_EXPIRE_MINUTES * 60


def _hash_magic_token(token: str) -> str:
    """Return the SHA-256 hex digest of a magic-link token.

    The raw token is sent to the user by email; only its hash is stored in
    Redis so that a Redis dump cannot be replayed directly to authenticate.
    """
    return hashlib.sha256(token.encode()).hexdigest()


async def _store_magic_link(token: str, email: str, expires_at: datetime) -> None:
    """
    Persist a magic-link token to Redis (preferred) or the in-memory dict.

    Parameters:
        token: The one-time token string (raw, as sent to the user by email).
        email: The email address associated with the token.
        expires_at: UTC datetime when the token expires.

    Side effects:
        Writes to Redis (keyed by SHA-256 hash of token) with TTL, or to
        _magic_link_store (keyed by raw token) on Redis failure.
    """
    record = {"email": email, "expires_at": expires_at.isoformat()}
    redis = _get_redis()
    if redis is not None:
        try:
            await redis.setex(
                f"{_REDIS_KEY_PREFIX}{_hash_magic_token(token)}",
                _REDIS_TTL_SECONDS,
                json.dumps(record),
            )
            # Mirror in the local dict (raw token) so tests can inspect it
            _magic_link_store[token] = {"email": email, "expires_at": expires_at}
            return
        except Exception:
            logger.warning("Redis write failed — falling back to in-memory store.")
    _magic_link_store[token] = {"email": email, "expires_at": expires_at}


async def _pop_magic_link(token: str) -> dict | None:
    """
    Consume (read and delete) a magic-link token from Redis or the in-memory dict.

    Parameters:
        token: The one-time token to look up and delete (raw, as sent by email).

    Returns:
        A dict with keys "email" (str) and "expires_at" (datetime), or None if
        the token does not exist or has already been consumed.
    """
    redis = _get_redis()
    if redis is not None:
        try:
            key = f"{_REDIS_KEY_PREFIX}{_hash_magic_token(token)}"
            raw = await redis.get(key)
            if raw is not None:
                await redis.delete(key)
                _magic_link_store.pop(token, None)
                data = json.loads(raw)
                return {
                    "email": data["email"],
                    "expires_at": datetime.fromisoformat(data["expires_at"]),
                }
            # Not in Redis — check in-memory (handles race or Redis restart)
        except Exception:
            logger.warning("Redis read failed — falling back to in-memory store.")
    return _magic_link_store.pop(token, None)


# ---------------------------------------------------------------------------
# Magic-link endpoints
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Disposable / throwaway email domain blocklist
# ---------------------------------------------------------------------------

_DISPOSABLE_DOMAINS: frozenset[str] = frozenset({
    "mailinator.com", "guerrillamail.com", "guerrillamail.net", "guerrillamail.org",
    "guerrillamailblock.com", "guerrillamail.biz", "guerrillamail.de", "guerrillamail.info",
    "grr.la", "spam4.me", "yopmail.com", "yopmail.fr", "cool.fr.nf",
    "jetable.fr.nf", "nospam.ze.tc", "nomail.xl.cx", "mega.zik.dj", "speed.1s.fr",
    "courriel.fr.nf", "moncourrier.fr.nf", "monemail.fr.nf", "monmail.fr.nf",
    "trashmail.com", "trashmail.me", "trashmail.net", "trashmail.at", "trashmail.io",
    "trashmail.org", "trashmail.xyz", "trashmailer.com", "tempr.email", "dispostable.com",
    "mailnull.com", "spamgourmet.com", "spamgourmet.net", "spamgourmet.org",
    "10minutemail.com", "10minutemail.net", "10minutemail.org", "10minutemail.de",
    "minutemail.com", "throwam.com", "throwam.net", "throwam.org", "getnada.com", "getairmail.com",
    "fakeinbox.com", "filzmail.com", "discard.email", "discardmail.com", "discardmail.de",
    "spamhereplease.com", "spamhere.eu", "maildrop.cc", "mailnesia.com",
    "sharklasers.com", "spam.la", "spoofmail.de", "tempinbox.com", "tempinbox.co.uk",
    "tempemail.net", "tempsky.com",
    "mohmal.com", "mohmal.im", "mohmal.in", "mohmal.tech",
    "nwldx.com", "spamfree24.org", "spamfree24.de", "spamfree24.info",
    "spamfree24.biz", "spamfree24.eu", "spamfree24.net", "spamfree24.com",
})


def _is_disposable_email(email: str) -> bool:
    """Return True if the email's domain is on the throwaway-email blocklist."""
    try:
        domain = email.rsplit("@", 1)[1].lower()
    except IndexError:
        return False
    return domain in _DISPOSABLE_DOMAINS


# ---------------------------------------------------------------------------
# Rate limiting helpers
# ---------------------------------------------------------------------------

_RL_IP_KEY = "rl:magic:ip:"
_RL_EMAIL_KEY = "rl:magic:email:"
_RL_IP_MAX = 5        # max requests per IP per minute
_RL_IP_TTL = 60
_RL_EMAIL_MAX = 3     # max requests per email per 10 minutes
_RL_EMAIL_TTL = 600


async def _check_rate_limit(key: str, max_count: int, ttl_seconds: int) -> bool:
    """
    Increment a Redis counter and return True if under the limit.

    Uses INCR + EXPIRE so the TTL is only set on first access.
    Falls back to True (allow) if Redis is unavailable.

    Parameters:
        key: Redis key for the counter.
        max_count: Maximum number of requests allowed in the window.
        ttl_seconds: TTL for the key on first creation.

    Returns:
        True if the request is allowed, False if rate-limited.
    """
    allowed = await check_redis_rate_limit(
        _get_redis(),
        key,
        max_count=max_count,
        ttl_seconds=ttl_seconds,
    )
    if allowed is None:
        return True
    return allowed


@router.post("/magic-link/request", status_code=status.HTTP_202_ACCEPTED)
async def request_magic_link(
    request: Request, body: MagicLinkRequest, db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Request a magic-link login email.

    Generates a one-time token, stores it with a 15-minute expiry in Redis
    (or the in-memory fallback when Redis is unavailable), and sends an email
    via Resend (or prints to console in dev mode).

    Rate-limited: max 5 requests per IP per minute and max 3 per email per
    10 minutes to prevent Denial-of-Wallet abuse via the Resend API.

    Parameters:
        request: FastAPI Request — used to extract the client IP.
        body: JSON body containing the user's email address.
        db: Injected async DB session — used to load the editable email template.

    Returns:
        202 Accepted with a generic message (do not reveal whether the
        email exists to prevent user enumeration).

    Raises:
        HTTPException 429: If the IP or email rate limit is exceeded.
    """
    # Behind Cloudflare → Nginx the real visitor IP is in CF-Connecting-IP.
    # Fall back to X-Real-IP (set by nginx real_ip module) then to the socket peer.
    client_ip = get_client_ip(request)
    if not await _check_rate_limit(f"{_RL_IP_KEY}{client_ip}", _RL_IP_MAX, _RL_IP_TTL):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": str(_RL_IP_TTL)},
        )
    if not await _check_rate_limit(f"{_RL_EMAIL_KEY}{body.email.lower()}", _RL_EMAIL_MAX, _RL_EMAIL_TTL):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": str(_RL_EMAIL_TTL)},
        )

    # Turnstile challenge — only enforced when a Turnstile secret is set.
    if settings.turnstile_secret_key:
        if not await verify_turnstile(
            body.turnstile_token,
            client_ip,
            context="auth_magic_link",
            expected_action="auth_magic_link",
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Human verification failed. Please try again.",
            )

    # Reject throwaway email domains.
    if _is_disposable_email(body.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please use a permanent email address.",
        )

    token = generate_magic_token()
    expires_at = datetime.now(UTC) + timedelta(minutes=MAGIC_LINK_EXPIRE_MINUTES)
    await _store_magic_link(token, body.email, expires_at)

    await send_magic_link(email=body.email, token=token, db=db)

    return {"message": "If that address is registered, a login link is on its way."}


@router.post("/magic-link/verify", response_model=TokenResponse)
async def verify_magic_link(
    request: Request,
    response: Response,
    body: MagicLinkVerify,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Verify a magic-link token and return a JWT access token.

    Looks up and atomically deletes the token from Redis (or the in-memory
    fallback), validates expiry, upserts the User row, then returns a signed JWT.

    Parameters:
        body: JSON body containing the one-time magic-link token.
        db: Injected async DB session.

    Returns:
        A TokenResponse with a signed JWT.

    Raises:
        HTTPException 400: If the token is invalid or expired.
    """
    record = await _pop_magic_link(body.token)
    if record is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")

    if datetime.now(UTC) > record["expires_at"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token has expired")

    email: str = record["email"]

    # Upsert: create user on first login
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    is_new = user is None
    if is_new:
        user = User(email=email, plan=UserPlan.solo)
        db.add(user)
        await db.flush()  # populate user.id before creating token

    if is_new:
        lang = request.headers.get("accept-language", "en")[:2]
        await send_welcome_email(email=email, lang=lang)

    access_token = create_access_token(subject=user.id)
    _set_session_cookie(response, request, access_token)
    return TokenResponse(access_token=access_token)


# ---------------------------------------------------------------------------
# OAuth endpoints (Google)
# ---------------------------------------------------------------------------

_OAUTH_CONFIGS: dict[str, dict] = {
    "google": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
        "scope": "openid email profile",
        "client_id_key": "google_client_id",
        "client_secret_key": "google_client_secret",
    },
}

# In-memory fallback for OAuth state (used when Redis is unavailable)
_oauth_state_store: dict[str, str] = {}

_OAUTH_STATE_KEY = "oauth_state:"
_OAUTH_STATE_TTL = 600  # 10 minutes — long enough for slow OAuth flows


def _oauth_callback_url() -> str:
    """Return the OAuth callback URL, using http for localhost and https elsewhere."""
    scheme = "http" if settings.domain in ("localhost", "127.0.0.1") else "https"
    return f"{scheme}://{settings.domain}/api/auth/oauth/callback"


async def _store_oauth_state(state: str, provider: str) -> None:
    """
    Persist an OAuth CSRF state nonce to Redis (preferred) or in-memory fallback.

    Parameters:
        state: The random nonce generated for this OAuth flow.
        provider: The OAuth provider name (currently only "google").

    Side effects:
        Writes to Redis with a 10-minute TTL, or to _oauth_state_store on failure.
    """
    redis = _get_redis()
    if redis is not None:
        try:
            await redis.setex(f"{_OAUTH_STATE_KEY}{state}", _OAUTH_STATE_TTL, provider)
            _oauth_state_store[state] = provider  # mirror for local inspection
            return
        except Exception:
            logger.warning("Redis write failed for OAuth state — using in-memory fallback.")
    _oauth_state_store[state] = provider


async def _pop_oauth_state(state: str) -> str | None:
    """
    Consume (read and delete) an OAuth CSRF state nonce from Redis or in-memory.

    Parameters:
        state: The nonce to look up and delete.

    Returns:
        The provider name if the state exists, or None if not found / already consumed.
    """
    redis = _get_redis()
    if redis is not None:
        try:
            key = f"{_OAUTH_STATE_KEY}{state}"
            provider = await redis.get(key)
            if provider is not None:
                await redis.delete(key)
                _oauth_state_store.pop(state, None)
                return provider
        except Exception:
            logger.warning("Redis read failed for OAuth state — falling back to in-memory.")
    return _oauth_state_store.pop(state, None)


@router.get("/oauth/callback")
async def oauth_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """
    Handle the OAuth provider callback after user grants consent.

    Validates the state nonce, exchanges the authorisation code for an access
    token, fetches the user's profile, upserts the User row, issues a JWT,
    and redirects to the frontend after setting an httpOnly session cookie.

    Parameters:
        code: Authorisation code from the OAuth provider.
        state: CSRF state nonce that must match the one we issued.
        db: Injected async DB session.

    Returns:
        302 redirect to the frontend /auth/callback route.

    Raises:
        HTTPException 400: If state is invalid or token exchange fails.
    """
    import httpx

    provider = await _pop_oauth_state(state)
    if provider is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")

    cfg = _OAUTH_CONFIGS[provider]
    client_id = getattr(settings, cfg["client_id_key"])
    client_secret = getattr(settings, cfg["client_secret_key"])
    callback_url = _oauth_callback_url()

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            cfg["token_url"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": callback_url,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
        if token_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OAuth token exchange failed",
            )
        tokens = token_response.json()
        provider_access_token = tokens.get("access_token")

        # Fetch user profile
        userinfo_response = await client.get(
            cfg["userinfo_url"],
            headers={"Authorization": f"Bearer {provider_access_token}"},
        )
        if userinfo_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch user profile from OAuth provider",
            )
        profile = userinfo_response.json()

    # Normalise profile fields across providers
    email: str | None = profile.get("email") or profile.get("mail")
    name: str | None = profile.get("name") or profile.get("displayName")
    raw_avatar: str | None = profile.get("picture")
    # Only accept https:// URLs — same rule as UserProfileUpdate.validate_avatar_url
    avatar_url: str | None = raw_avatar if (raw_avatar and raw_avatar.startswith("https://")) else None

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth provider did not return an email address.",
        )

    # Upsert user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    is_new = user is None
    if is_new:
        user = User(email=email, name=name, avatar_url=avatar_url, plan=UserPlan.solo)
        db.add(user)
        await db.flush()
    else:
        if name and not user.name:
            user.name = name
        if avatar_url and not user.avatar_url:
            user.avatar_url = avatar_url

    if is_new:
        await send_welcome_email(email=email, name=name, lang="en")

    access_token = create_access_token(subject=user.id)
    frontend_url = settings.allowed_origins[0] if settings.allowed_origins else f"http://{settings.domain}"
    response = RedirectResponse(
        url=f"{frontend_url}/auth/callback",
        status_code=status.HTTP_302_FOUND,
    )
    _set_session_cookie(response, request, access_token)
    return response


@router.get("/oauth/{provider}")
async def oauth_redirect(provider: str) -> RedirectResponse:
    """
    Initiate an OAuth 2.0 authorisation-code flow.

    Generates a random state nonce, stores it, and redirects the browser
    to the provider's authorisation endpoint.

    Parameters:
        provider: "google".

    Returns:
        302 redirect to the provider's auth page.

    Raises:
        HTTPException 400: If the provider name is not supported.
    """
    if provider not in _OAUTH_CONFIGS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown provider: {provider}")

    cfg = _OAUTH_CONFIGS[provider]
    client_id = getattr(settings, cfg["client_id_key"])
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{provider} OAuth is not configured on this server.",
        )

    state = generate_magic_token(32)
    await _store_oauth_state(state, provider)

    callback_url = _oauth_callback_url()
    auth_url = (
        f"{cfg['auth_url']}"
        f"?client_id={client_id}"
        f"&redirect_uri={callback_url}"
        f"&response_type=code"
        f"&scope={cfg['scope'].replace(' ', '+')}"
        f"&state={state}"
    )
    return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)


# ---------------------------------------------------------------------------
# Session / me endpoints
# ---------------------------------------------------------------------------



@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response) -> None:
    """
    Log the current user out by revoking their JWT in the Redis blocklist.

    Extracts the current token from the session cookie or Authorization header, decodes it to
    read the JTI and expiry, then stores the JTI in Redis with a TTL equal to
    the token's remaining lifetime.  Subsequent requests with the same token
    will be rejected by get_current_user.

    Falls back gracefully (no error) if the token is missing, malformed, or
    Redis is unavailable — the client should discard the token regardless.
    """
    raw_token = _extract_request_token(request)
    if raw_token is None:
        _clear_session_cookie(response, request)
        return None
    try:
        import jwt as _jwt  # noqa: PLC0415
        payload = _jwt.decode(
            raw_token, settings.better_auth_secret, algorithms=["HS256"]
        )
        jti: str | None = payload.get("jti")
        exp: int | None = payload.get("exp")
        if jti and exp:
            remaining = exp - int(datetime.now(UTC).timestamp())
            await revoke_token(jti, remaining)
    except Exception as exc:
        logger.warning("Token decoding or revocation failed during logout: %s", exc)

    _clear_session_cookie(response, request)
    return None


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """
    Return the profile of the currently authenticated user.

    Parameters:
        current_user: Injected via the get_current_user dependency.

    Returns:
        UserResponse with the user's id, email, name, avatar, plan, and
        email_notifications_enabled preference.
    """
    return UserResponse.model_validate(current_user)


# ---------------------------------------------------------------------------
# Notification preferences — PATCH /api/auth/me/preferences
# ---------------------------------------------------------------------------


@router.patch("/me/preferences", response_model=UserResponse)
async def update_preferences(
    body: UserPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Update notification preferences for the authenticated user.

    Currently supports toggling amendment status email notifications.
    Setting email_notifications_enabled to False suppresses the
    accepted/rejected emails sent when an admin acts on an amendment
    authored by this user.

    Parameters:
        body: JSON body with email_notifications_enabled (bool).
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        Updated UserResponse reflecting the new preference.
    """
    current_user.email_notifications_enabled = body.email_notifications_enabled
    await db.flush()
    return UserResponse.model_validate(current_user)


# ---------------------------------------------------------------------------
# Profile update — PATCH /api/auth/me/profile
# ---------------------------------------------------------------------------


@router.patch("/me/profile", response_model=UserResponse)
async def update_profile(
    body: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Update the authenticated user's profile information.

    Parameters:
        body: JSON body with name, company, job_position, and avatar_url.
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        Updated UserResponse reflecting the new profile fields.
    """
    if body.name is not None:
        current_user.name = body.name
    if body.company is not None:
        current_user.company = body.company
    if body.job_position is not None:
        current_user.job_position = body.job_position
    if body.avatar_url is not None:
        current_user.avatar_url = body.avatar_url

    await db.flush()
    return UserResponse.model_validate(current_user)


# ---------------------------------------------------------------------------
# Onboarding completion — POST /api/auth/me/onboarding/complete
# ---------------------------------------------------------------------------


@router.post("/me/onboarding/complete", response_model=UserResponse)
async def complete_onboarding(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Mark the authenticated user's onboarding wizard as completed.

    Called by the frontend when the user finishes (or dismisses) the
    post-signup onboarding wizard.  Setting this flag server-side ensures the
    wizard is shown only once per account regardless of device or browser.

    Parameters:
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        Updated UserResponse with onboarding_completed = True.
    """
    current_user.onboarding_completed = True
    await db.flush()
    return UserResponse.model_validate(current_user)


# ---------------------------------------------------------------------------
# GDPR right to erasure — DELETE /api/auth/me
# ---------------------------------------------------------------------------


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Anonymise and soft-delete the authenticated user's account (GDPR Article 17).

    Steps:
      1. For every organisation where the user is the sole owner, find any other
         admin to promote to owner. If no admin exists, promote the first non-owner
         member. If the user is the only member, leave the org ownerless (no other
         member is affected).
      2. Remove the user from all organisations where they are NOT the sole owner
         (i.e., their memberships are deleted).
      3. Overwrite personally identifiable fields on the User row:
           email   → "deleted-<user_id>@deleted.invalid"
           name    → None
           avatar_url → None
      4. Set is_deleted = True and deleted_at = now().

    The user row is retained so that foreign-key references (amendments, activity
    log) remain intact.  The anonymised email placeholder is guaranteed unique
    because it embeds the user's UUID.

    Parameters:
        current_user: The authenticated user requesting erasure.
        db: Injected async DB session.

    Returns:
        204 No Content on success.
    """
    user_id = current_user.id

    # ------------------------------------------------------------------
    # Step 1 & 2 — resolve ownership transfers, then remove memberships
    # ------------------------------------------------------------------

    # Load all memberships for this user, together with their organisation
    memberships_result = await db.execute(
        select(Membership).where(Membership.user_id == user_id)
    )
    memberships = memberships_result.scalars().all()

    for m in memberships:
        if m.role == MemberRole.owner:
            # Count how many OTHER owners exist in this org
            other_owners_result = await db.execute(
                select(func.count()).select_from(Membership).where(
                    (Membership.org_id == m.org_id)
                    & (Membership.user_id != user_id)
                    & (Membership.role == MemberRole.owner)
                )
            )
            other_owner_count = other_owners_result.scalar_one()

            if other_owner_count == 0:
                # This user is the sole owner — find a successor
                # Prefer admin, then any remaining member
                successor_result = await db.execute(
                    select(Membership)
                    .where(
                        (Membership.org_id == m.org_id)
                        & (Membership.user_id != user_id)
                    )
                    .order_by(
                        # admins first (admin < member alphabetically in enum order)
                        Membership.role,
                        Membership.created_at,
                    )
                    .limit(1)
                )
                successor = successor_result.scalar_one_or_none()
                if successor is not None:
                    successor.role = MemberRole.owner
                    await db.flush()
                # If successor is None there are no other members — org is left
                # without an owner (it will be unreachable, which is acceptable).

        # Delete this user's membership row
        await db.delete(m)

    await db.flush()

    # ------------------------------------------------------------------
    # Step 2b — revoke all contributor tokens on documents authored inside
    # organisations where this user was a member (prevents orphaned public links).
    # ------------------------------------------------------------------
    org_ids = [m.org_id for m in memberships]
    if org_ids:
        docs_result = await db.execute(
            select(Document).where(
                Document.org_id.in_(org_ids),
                Document.contributor_token.is_not(None),
            )
        )
        for doc in docs_result.scalars().all():
            doc.contributor_token = None
            doc.contributor_token_created_at = None
            doc.contributor_token_expires_at = None
        await db.flush()

    # ------------------------------------------------------------------
    # Step 3 & 4 — anonymise PII and mark the account as deleted
    # ------------------------------------------------------------------
    current_user.email = f"deleted-{user_id}@deleted.invalid"
    current_user.name = None
    current_user.company = None
    current_user.job_position = None
    current_user.avatar_url = None
    current_user.is_deleted = True
    current_user.deleted_at = datetime.now(UTC)

    await db.flush()
    _clear_session_cookie(response, request)
    logger.info("User %s account anonymised (GDPR erasure).", user_id)
    return None
