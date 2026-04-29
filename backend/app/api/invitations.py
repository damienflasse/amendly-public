"""
Invitation API routes.

Endpoints:
  POST /api/organisations/{slug}/invite  — send invite to an email (owner/admin only)
  GET  /api/invitations/preview          — public preview of an invitation by token (no auth)
  POST /api/invitations/accept           — accept an invite by token (any authenticated user)
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.invitation import InviteAccept, InviteCreate, InvitationPreview, InvitationResponse
from app.services.billing import BillingSyncError
from app.services.invitation import (
    accept_invite,
    create_invite,
    get_invite_preview,
    list_pending_invites,
    resend_invite,
    revoke_invite,
)
from app.utils.rate_limit import get_client_ip
from app.utils.turnstile import verify_turnstile

# Two separate routers so they can mount at different prefixes
org_router = APIRouter(prefix="/api/organisations", tags=["invitations"])
invite_router = APIRouter(prefix="/api/invitations", tags=["invitations"])


@org_router.post(
    "/{slug}/invite",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_invite(
    slug: str,
    body: InviteCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationResponse:
    """
    Invite an email address to join an organisation.

    Owner/admin only. If a pending invite already exists for the same (org, email)
    pair it is returned as-is (idempotent — no duplicate emails). If the email
    already belongs to a member of the org, 409 is returned.

    Parameters:
        slug: URL slug of the target organisation.
        body: InviteCreate request body (email).
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        InvitationResponse for the new or existing pending invitation (201 Created).

    Raises:
        HTTPException 403: If the caller is not an owner or admin.
        HTTPException 404: If the organisation is not found or the user is not a member.
        HTTPException 409: If the email is already a member of the organisation.
        HTTPException 503: If email delivery fails.
    """
    client_ip = get_client_ip(request)
    if not await verify_turnstile(
        body.turnstile_token,
        client_ip,
        context="org_invite",
        expected_action="org_invite",
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Human verification failed. Please try again.",
        )

    try:
        return await create_invite(
            db=db,
            current_user=current_user,
            slug=slug,
            email=str(body.email),
        )
    except ValueError as exc:
        msg = str(exc)
        if "already a member" in msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg) from exc
        if "Only owners" in msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg) from exc
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc


@org_router.get(
    "/{slug}/invitations",
    response_model=list[InvitationResponse],
    status_code=status.HTTP_200_OK,
)
async def get_pending_invitations(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[InvitationResponse]:
    """
    List all pending invitations for an organisation.

    Owner/admin only. Returns non-expired, non-accepted invitations ordered by
    creation date (newest first).

    Parameters:
        slug: URL slug of the target organisation.
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        List of InvitationResponse for all pending invitations.

    Raises:
        HTTPException 403: If the caller is not an owner or admin.
        HTTPException 404: If the organisation is not found or the user is not a member.
    """
    try:
        return await list_pending_invites(db=db, current_user=current_user, slug=slug)
    except ValueError as exc:
        msg = str(exc)
        if "Only owners" in msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg) from exc
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc


@org_router.delete(
    "/{slug}/invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_invitation(
    slug: str,
    invitation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Revoke (delete) a pending invitation.

    Owner/admin only. Cannot revoke an already-accepted invitation.

    Parameters:
        slug: URL slug of the target organisation.
        invitation_id: UUID of the invitation to revoke.
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        204 No Content on success.

    Raises:
        HTTPException 400: If the invitation has already been accepted.
        HTTPException 403: If the caller is not an owner or admin.
        HTTPException 404: If the org or invitation is not found.
    """
    try:
        await revoke_invite(
            db=db, current_user=current_user, slug=slug, invitation_id=invitation_id
        )
    except ValueError as exc:
        msg = str(exc)
        if "Only owners" in msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg) from exc
        if "already been accepted" in msg:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from exc
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc


@org_router.post(
    "/{slug}/invitations/{invitation_id}/resend",
    response_model=InvitationResponse,
    status_code=status.HTTP_200_OK,
)
async def post_resend_invitation(
    slug: str,
    invitation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationResponse:
    """
    Resend an invitation email, generating a fresh token and extending the expiry.

    Owner/admin only. The existing token is replaced with a new one and the
    expiry is reset to 72 hours from now.

    Parameters:
        slug: URL slug of the target organisation.
        invitation_id: UUID of the invitation to resend.
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        Updated InvitationResponse with the new expiry.

    Raises:
        HTTPException 400: If the invitation has already been accepted.
        HTTPException 403: If the caller is not an owner or admin.
        HTTPException 404: If the org or invitation is not found.
        HTTPException 503: If email delivery fails.
    """
    try:
        return await resend_invite(
            db=db, current_user=current_user, slug=slug, invitation_id=invitation_id
        )
    except ValueError as exc:
        msg = str(exc)
        if "Only owners" in msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg) from exc
        if "already been accepted" in msg:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from exc
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc


@invite_router.get(
    "/preview",
    response_model=InvitationPreview,
    status_code=status.HTTP_200_OK,
)
async def get_invitation_preview(
    token: str = Query(..., description="The invite token from the email link."),
    db: AsyncSession = Depends(get_db),
) -> InvitationPreview:
    """
    Return a public preview of an invitation — no authentication required.

    Called by the frontend accept-invitation page on mount to display the
    organisation name and invitee email before the user logs in or creates
    an account. Exposes only non-sensitive data: org name, email, expiry.

    Parameters:
        token: Invite token from the ``?token=`` query parameter.
        db: Injected async DB session.

    Returns:
        InvitationPreview with org_name, email, and expires_at.

    Raises:
        HTTPException 404: If the token is not found.
        HTTPException 400: If the invitation is expired or already accepted.
    """
    try:
        return await get_invite_preview(db=db, token=token)
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from exc


@invite_router.post(
    "/accept",
    response_model=InvitationResponse,
    status_code=status.HTTP_200_OK,
)
async def post_accept_invite(
    body: InviteAccept,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationResponse:
    """
    Accept an invitation by its token, adding the current user to the organisation.

    The token is the one embedded in the invite link sent by email. The endpoint
    validates that the token is not expired or already accepted, then creates
    a Membership row with role=member.

    Parameters:
        body: InviteAccept request body (token).
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        InvitationResponse for the accepted invitation.

    Raises:
        HTTPException 400: If the token is expired or already accepted.
        HTTPException 404: If the token is not found.
        HTTPException 409: If the current user is already a member.
    """
    client_ip = get_client_ip(request)
    if not await verify_turnstile(
        body.turnstile_token,
        client_ip,
        context="invite_accept",
        expected_action="invite_accept",
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Human verification failed. Please try again.",
        )

    try:
        return await accept_invite(db=db, current_user=current_user, token=body.token)
    except BillingSyncError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc
        if "already a member" in msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg) from exc
        if "different email address" in msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg) from exc
        # expired or already accepted
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from exc
