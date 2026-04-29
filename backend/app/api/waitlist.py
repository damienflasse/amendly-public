"""
Waitlist API — pre-launch email capture endpoints.

Endpoints:
  POST /api/waitlist              — public; register an email on the waitlist
  GET  /api/admin/waitlist        — superuser only; list all waitlist entries
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_superuser
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.waitlist import WaitlistCreate, WaitlistResponse
from app.services.waitlist import create_waitlist_entry, list_waitlist_entries
from app.utils.turnstile import verify_turnstile

# Public router — no auth required
public_router = APIRouter(prefix="/api/waitlist", tags=["waitlist"])

# Admin router — reuses the existing /api/admin prefix namespace
admin_router = APIRouter(prefix="/api/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Public endpoint
# ---------------------------------------------------------------------------


@public_router.post(
    "",
    response_model=WaitlistResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Join the waitlist (public)",
)
async def join_waitlist(
    payload: WaitlistCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> WaitlistResponse:
    """
    Register an email address on the pre-launch waitlist.

    Turnstile is enforced when TURNSTILE_SECRET_KEY is set in the environment.
    In development (secret unset or set to "test") the check is bypassed.

    Parameters:
        payload: WaitlistCreate with the visitor's email, optional source tag,
                 and optional Turnstile token.
        request: FastAPI request (used to forward client IP to Cloudflare).
        db:      Injected async DB session.

    Returns:
        WaitlistResponse for the new entry (HTTP 201).

    Raises:
        HTTPException 403: If the Turnstile challenge fails.
        HTTPException 409: If the email is already registered.
    """
    if settings.turnstile_secret_key:
        client_ip = request.headers.get("CF-Connecting-IP") or (
            request.client.host if request.client else None
        )
        if not await verify_turnstile(
            payload.turnstile_token,
            remote_ip=client_ip,
            context="waitlist",
            expected_action="waitlist",
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bot check failed. Please try again.",
            )

    try:
        return await create_waitlist_entry(db, payload)
    except ValueError as exc:
        if str(exc) == "already_registered":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is already on the waitlist.",
            ) from exc
        raise


# ---------------------------------------------------------------------------
# Admin endpoint
# ---------------------------------------------------------------------------


@admin_router.get(
    "/waitlist",
    response_model=list[WaitlistResponse],
    summary="List all waitlist entries (superuser)",
)
async def admin_list_waitlist(
    current_user: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
) -> list[WaitlistResponse]:
    """
    Return all waitlist entries ordered by signup date (newest first).

    Parameters:
        current_user: Injected by require_superuser (HTTP 403 if not superuser).
        db:           Injected async DB session.

    Returns:
        List of WaitlistResponse.
    """
    return await list_waitlist_entries(db)
