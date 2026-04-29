"""
Organisation API routes.

Endpoints:
  POST   /api/organisations                                   — create an org; auto-adds creator as owner
  GET    /api/organisations/me                                — list the caller's orgs with their role
  GET    /api/organisations/{slug}                            — fetch one org (must be a member)
  PATCH  /api/organisations/{slug}                            — update name and/or slug (owner only)
  DELETE /api/organisations/{slug}                            — delete the org and all its data (owner only)
  GET    /api/organisations/{slug}/stats                      — activity counters (active docs, pending amendments, members)
  GET    /api/organisations/{slug}/members                    — list all members (any member)
  PUT    /api/organisations/{slug}/members/{user_id}/role     — change a member's role (owner only)
  DELETE /api/organisations/{slug}/members/{user_id}          — remove a member (owner or admin)
  PATCH  /api/organisations/{slug}/notification-settings      — toggle per-org email mute for the caller
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.membership import Membership
from app.models.organisation import Organisation
from app.models.user import User
from app.schemas.organisation import (
    MemberDetail,
    MembershipResponse,
    OrgStatsResponse,
    OrganisationCreate,
    OrganisationResponse,
    OrganisationUpdate,
    RoleChangeRequest,
)
from app.services.billing import BillingSyncError
from app.services.organisation import (
    change_member_role,
    create_organisation,
    delete_organisation,
    get_org_stats,
    get_organisation_by_slug,
    list_members,
    list_organisations_for_user,
    remove_member,
    update_organisation,
)

router = APIRouter(prefix="/api/organisations", tags=["organisations"])


@router.post("", response_model=OrganisationResponse, status_code=status.HTTP_201_CREATED)
async def post_organisation(
    body: OrganisationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganisationResponse:
    """
    Create a new organisation.

    The authenticated user is automatically added as the owner in the
    memberships table. Slugs must be globally unique — a 409 is returned
    if the slug is already taken.

    Parameters:
        body: OrganisationCreate request body (name + slug).
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        OrganisationResponse for the newly created organisation (201 Created).

    Raises:
        HTTPException 422: If name or slug validation fails.
        HTTPException 409: If the slug already exists.
    """
    try:
        return await create_organisation(db=db, current_user=current_user, payload=body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/me", response_model=list[MembershipResponse])
async def get_my_organisations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MembershipResponse]:
    """
    List all organisations the current user belongs to, with their role.

    Parameters:
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        List of MembershipResponse objects sorted by membership creation date.
    """
    return await list_organisations_for_user(db=db, current_user=current_user)


@router.get("/{slug}/members", response_model=list[MemberDetail])
async def get_members(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MemberDetail]:
    """
    List all members of an organisation.

    Any authenticated member of the organisation may call this endpoint.
    Returns 404 both when the org does not exist and when the caller is not
    a member, to avoid disclosing the existence of private organisations.

    Parameters:
        slug: URL slug of the target organisation.
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        List of MemberDetail objects (user_id, email, name, role, joined_at).

    Raises:
        HTTPException 404: If the org is not found or the user is not a member.
    """
    try:
        return await list_members(db=db, current_user=current_user, slug=slug)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/{slug}/members/{user_id}/role", response_model=MemberDetail)
async def put_member_role(
    slug: str,
    user_id: str,
    body: RoleChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MemberDetail:
    """
    Change the role of an organisation member.

    Only the organisation owner may call this endpoint.
    Valid target roles are 'admin' and 'member'. The owner role cannot be
    assigned via the API, and an owner cannot demote themselves.

    Parameters:
        slug: URL slug of the target organisation.
        user_id: ID of the user whose role is being changed.
        body: RoleChangeRequest with the desired role ('admin' or 'member').
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        Updated MemberDetail for the affected membership.

    Raises:
        HTTPException 400: If the role value is invalid or the owner tries to
                           demote themselves.
        HTTPException 403: If the caller is not the organisation owner.
        HTTPException 404: If the org or target user is not found.
    """
    try:
        return await change_member_role(
            db=db,
            current_user=current_user,
            slug=slug,
            target_user_id=user_id,
            payload=body,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower() or "not a member" in detail.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc


@router.delete("/{slug}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_member(
    slug: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Remove a member from an organisation.

    Requires owner or admin role.  The organisation owner cannot be removed.

    Parameters:
        slug: URL slug of the target organisation.
        user_id: ID of the user to remove.
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        204 No Content on success.

    Raises:
        HTTPException 400: If the caller tries to remove the owner.
        HTTPException 403: If the caller is a plain member.
        HTTPException 404: If the org or target user is not found.
    """
    try:
        await remove_member(
            db=db,
            current_user=current_user,
            slug=slug,
            target_user_id=user_id,
        )
    except BillingSyncError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower() or "not a member" in detail.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc


@router.get("/{slug}", response_model=OrganisationResponse)
async def get_organisation(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganisationResponse:
    """
    Fetch a single organisation by slug.

    Returns 404 both when the org does not exist and when the user is not a
    member, to avoid disclosing the existence of private organisations.

    Parameters:
        slug: URL slug of the target organisation.
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        OrganisationResponse for the matching organisation.

    Raises:
        HTTPException 404: If the org is not found or the user is not a member.
    """
    try:
        return await get_organisation_by_slug(db=db, current_user=current_user, slug=slug)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/{slug}", response_model=OrganisationResponse)
async def patch_organisation(
    slug: str,
    body: OrganisationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganisationResponse:
    """
    Update an organisation's name and/or slug.

    Only the organisation owner may call this endpoint.  If the slug is
    changed, the new slug must not be taken by another organisation.

    Parameters:
        slug: Current URL slug of the target organisation.
        body: OrganisationUpdate with optional name and/or slug fields.
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        OrganisationResponse with the updated fields.

    Raises:
        HTTPException 403: If the caller is not the organisation owner.
        HTTPException 404: If the org is not found or the user is not a member.
        HTTPException 409: If the new slug is already taken.
        HTTPException 422: If validation fails (bad slug format, empty name, etc.).
    """
    try:
        return await update_organisation(
            db=db, current_user=current_user, slug=slug, payload=body
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        detail = str(exc)
        if "already taken" in detail:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_org(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Permanently delete an organisation and all associated data.

    Only the organisation owner may call this endpoint.  All memberships,
    documents, amendments, and invitations are deleted via cascade.

    Parameters:
        slug: URL slug of the organisation to delete.
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        204 No Content on success.

    Raises:
        HTTPException 403: If the caller is not the organisation owner.
        HTTPException 404: If the org is not found or the user is not a member.
    """
    try:
        await delete_organisation(db=db, current_user=current_user, slug=slug)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{slug}/stats", response_model=OrgStatsResponse)
async def get_organisation_stats(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrgStatsResponse:
    """
    Return activity counters for an organisation's dashboard.

    Returns active document count, pending amendment count, and total member
    count.  Requires the caller to be a member of the organisation.

    Parameters:
        slug: URL slug of the target organisation.
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        OrgStatsResponse with active_docs, pending_amendments, member_count.

    Raises:
        HTTPException 404: If the org is not found or the user is not a member.
    """
    try:
        return await get_org_stats(db=db, current_user=current_user, slug=slug)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Per-org notification settings
# ---------------------------------------------------------------------------


class OrgNotificationSettingsUpdate(BaseModel):
    """Body for PATCH /api/organisations/{slug}/notification-settings."""

    notifications_muted: bool


@router.patch("/{slug}/notification-settings")
async def patch_org_notification_settings(
    slug: str,
    body: OrgNotificationSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Toggle per-organisation email notification mute for the authenticated user.

    Any member of the organisation can call this endpoint to mute or unmute
    email notifications for that specific org without affecting the global
    email_notifications_enabled preference or other org memberships.

    Parameters:
        slug: URL slug of the target organisation.
        body: OrgNotificationSettingsUpdate with notifications_muted bool.
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        Dict: { "notifications_muted": <bool> }

    Raises:
        HTTPException 404: If the org is not found or the caller is not a member.
    """
    # Verify membership in one JOIN query (also confirms the org exists)
    membership_result = await db.execute(
        select(Membership)
        .join(Organisation, Organisation.id == Membership.org_id)
        .where(Organisation.slug == slug, Membership.user_id == current_user.id)
    )
    membership = membership_result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found.")

    await db.execute(
        update(Membership)
        .where(Membership.org_id == membership.org_id, Membership.user_id == current_user.id)
        .values(notifications_muted=body.notifications_muted)
    )

    return {"notifications_muted": body.notifications_muted}
