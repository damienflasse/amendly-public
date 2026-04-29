"""
Organisation service — business logic for creating and querying organisations.

All database interaction goes through this service so that the API routes
remain thin and testable in isolation.
"""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.activity_log import ActivityLog
from app.models.amendment import Amendment, AmendmentStatus
from app.models.document import Document, DocumentStatus
from app.models.membership import MemberRole, Membership
from app.models.organisation import Organisation
from app.models.user import User
from app.schemas.organisation import MemberDetail, MembershipResponse, OrgStatsResponse, OrganisationCreate, OrganisationResponse, OrganisationUpdate, RoleChangeRequest


def _format_org(org: Organisation) -> OrganisationResponse:
    """
    Convert an Organisation ORM instance to an OrganisationResponse schema.

    Parameters:
        org: SQLAlchemy Organisation instance.

    Returns:
        OrganisationResponse with ISO-8601 created_at string.
    """
    return OrganisationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        plan=org.plan.value,
        created_at=org.created_at.isoformat(),
    )


async def create_organisation(
    db: AsyncSession,
    current_user: User,
    payload: OrganisationCreate,
) -> OrganisationResponse:
    """
    Create a new organisation and add the creator as owner.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user who is creating the organisation.
        payload: Validated OrganisationCreate request body.

    Returns:
        OrganisationResponse for the newly created organisation.

    Raises:
        ValueError: If the slug is already taken by another organisation.
    """
    org = Organisation(name=payload.name, slug=payload.slug)
    db.add(org)

    try:
        await db.flush()  # Populate org.id before creating membership
    except IntegrityError:
        await db.rollback()
        raise ValueError(f"Slug '{payload.slug}' is already taken.")

    membership = Membership(user_id=current_user.id, org_id=org.id, role=MemberRole.owner)
    db.add(membership)
    await db.flush()

    return _format_org(org)


async def update_organisation(
    db: AsyncSession,
    current_user: User,
    slug: str,
    payload: OrganisationUpdate,
) -> OrganisationResponse:
    """
    Update an organisation's name and/or slug.

    Only the owner may call this endpoint.  If the slug is changed, the new
    slug must not already be taken by another organisation.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user performing the update (must be owner).
        slug: Current URL slug of the target organisation.
        payload: OrganisationUpdate with optional name and/or slug fields.

    Returns:
        OrganisationResponse for the updated organisation.

    Raises:
        ValueError: If the org is not found, the caller is not the owner, or
                    the new slug is already taken.
        PermissionError: If the caller is not the organisation owner.
    """
    # Resolve org
    org_result = await db.execute(
        select(Organisation).where(Organisation.slug == slug)
    )
    org = org_result.scalar_one_or_none()
    if org is None:
        raise ValueError(f"Organisation '{slug}' not found.")

    # Verify caller is the owner
    caller_result = await db.execute(
        select(Membership).where(
            (Membership.org_id == org.id) & (Membership.user_id == current_user.id)
        )
    )
    caller = caller_result.scalar_one_or_none()
    if caller is None:
        raise ValueError(f"Organisation '{slug}' not found.")  # no disclosure
    if caller.role != MemberRole.owner:
        raise PermissionError("Only the organisation owner can update organisation settings.")

    if payload.name is not None:
        org.name = payload.name
    if payload.slug is not None and payload.slug != org.slug:
        org.slug = payload.slug

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise ValueError(f"Slug '{payload.slug}' is already taken.")

    return _format_org(org)


async def delete_organisation(
    db: AsyncSession,
    current_user: User,
    slug: str,
) -> None:
    """
    Permanently delete an organisation and all associated data.

    Only the owner may call this endpoint.  The cascade on the Organisation
    model handles deletion of memberships, documents, and invitations.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user performing the deletion (must be owner).
        slug: URL slug of the organisation to delete.

    Returns:
        None (204 No Content in the route).

    Raises:
        ValueError: If the org is not found.
        PermissionError: If the caller is not the organisation owner.
    """
    org_result = await db.execute(
        select(Organisation).where(Organisation.slug == slug)
    )
    org = org_result.scalar_one_or_none()
    if org is None:
        raise ValueError(f"Organisation '{slug}' not found.")

    caller_result = await db.execute(
        select(Membership).where(
            (Membership.org_id == org.id) & (Membership.user_id == current_user.id)
        )
    )
    caller = caller_result.scalar_one_or_none()
    if caller is None:
        raise ValueError(f"Organisation '{slug}' not found.")  # no disclosure
    if caller.role != MemberRole.owner:
        raise PermissionError("Only the organisation owner can delete the organisation.")

    await db.delete(org)
    await db.flush()


async def list_organisations_for_user(
    db: AsyncSession,
    current_user: User,
) -> list[MembershipResponse]:
    """
    Return all organisations the current user belongs to, with their role.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user whose memberships to fetch.

    Returns:
        List of MembershipResponse objects (org details + role).
    """
    result = await db.execute(
        select(Membership)
        .options(selectinload(Membership.organisation))
        .where(Membership.user_id == current_user.id)
        .order_by(Membership.created_at)
    )
    memberships = result.scalars().all()

    return [
        MembershipResponse(
            id=m.organisation.id,
            name=m.organisation.name,
            slug=m.organisation.slug,
            plan=m.organisation.plan.value,
            created_at=m.organisation.created_at.isoformat(),
            role=m.role.value,
        )
        for m in memberships
    ]


async def list_members(
    db: AsyncSession,
    current_user: User,
    slug: str,
) -> list[MemberDetail]:
    """
    Return all members of an organisation.

    The caller must be a member of the organisation (any role).  Returns one
    MemberDetail record per membership row, joined with the corresponding user
    to expose email and display name.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user requesting the list.
        slug: URL slug of the target organisation.

    Returns:
        List of MemberDetail objects sorted by membership creation date.

    Raises:
        ValueError: If the org does not exist or the caller is not a member
                    (both map to 404 in the route to avoid disclosure).
    """
    # Verify membership and resolve org_id in one query
    org_result = await db.execute(
        select(Organisation)
        .join(
            Membership,
            (Membership.org_id == Organisation.id) & (Membership.user_id == current_user.id),
        )
        .where(Organisation.slug == slug)
    )
    org = org_result.scalar_one_or_none()
    if org is None:
        raise ValueError(f"Organisation '{slug}' not found or you are not a member.")

    result = await db.execute(
        select(Membership)
        .options(selectinload(Membership.user))
        .where(Membership.org_id == org.id)
        .order_by(Membership.created_at)
    )
    memberships = result.scalars().all()

    # Build a map of user_id → most recent activity timestamp for this org.
    # One aggregate query avoids N+1 per member.
    activity_result = await db.execute(
        select(ActivityLog.user_id, func.max(ActivityLog.created_at).label("last_activity"))
        .where(ActivityLog.org_id == org.id)
        .group_by(ActivityLog.user_id)
    )
    activity_map = {row.user_id: row.last_activity for row in activity_result}

    return [
        MemberDetail(
            user_id=m.user_id,
            email=m.user.email,
            name=m.user.name,
            role=m.role.value,
            joined_at=m.created_at.isoformat(),
            last_activity_at=(
                activity_map[m.user_id].isoformat()
                if m.user_id in activity_map and activity_map[m.user_id] is not None
                else None
            ),
        )
        for m in memberships
    ]


async def change_member_role(
    db: AsyncSession,
    current_user: User,
    slug: str,
    target_user_id: str,
    payload: RoleChangeRequest,
) -> MemberDetail:
    """
    Change the role of an organisation member.

    Only the owner may call this endpoint.  The owner cannot demote themselves.
    Only 'admin' and 'member' are valid target roles (owner cannot be set).

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user performing the change (must be owner).
        slug: URL slug of the target organisation.
        target_user_id: ID of the user whose role is to be changed.
        payload: RoleChangeRequest containing the desired new role.

    Returns:
        MemberDetail for the updated membership.

    Raises:
        ValueError: If the org/member is not found, the caller is not the owner,
                    the caller tries to demote themselves, or the role is invalid.
    """
    allowed_roles = {MemberRole.admin, MemberRole.member}
    try:
        new_role = MemberRole(payload.role)
    except ValueError:
        raise ValueError(f"Invalid role '{payload.role}'. Must be 'admin' or 'member'.")
    if new_role not in allowed_roles:
        raise ValueError("Cannot set role to 'owner' via API.")

    # Resolve org and verify caller is the owner
    org_result = await db.execute(
        select(Organisation)
        .where(Organisation.slug == slug)
    )
    org = org_result.scalar_one_or_none()
    if org is None:
        raise ValueError(f"Organisation '{slug}' not found.")

    caller_membership_result = await db.execute(
        select(Membership).where(
            (Membership.org_id == org.id) & (Membership.user_id == current_user.id)
        )
    )
    caller_membership = caller_membership_result.scalar_one_or_none()
    if caller_membership is None:
        raise ValueError(f"Organisation '{slug}' not found.")  # no disclosure
    if caller_membership.role != MemberRole.owner:
        raise PermissionError("Only the organisation owner can change member roles.")

    if target_user_id == current_user.id:
        raise ValueError("The owner cannot change their own role.")

    # Fetch the target membership (joined with user for the response)
    target_result = await db.execute(
        select(Membership)
        .options(selectinload(Membership.user))
        .where(
            (Membership.org_id == org.id) & (Membership.user_id == target_user_id)
        )
    )
    target = target_result.scalar_one_or_none()
    if target is None:
        raise ValueError(f"User '{target_user_id}' is not a member of this organisation.")

    target.role = new_role
    await db.flush()

    return MemberDetail(
        user_id=target.user_id,
        email=target.user.email,
        name=target.user.name,
        role=target.role.value,
        joined_at=target.created_at.isoformat(),
        last_activity_at=None,  # Not fetched on role change — client retains previous value
    )


async def remove_member(
    db: AsyncSession,
    current_user: User,
    slug: str,
    target_user_id: str,
) -> None:
    """
    Remove a member from an organisation.

    Requires owner or admin role.  The org owner cannot be removed.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user performing the removal.
        slug: URL slug of the target organisation.
        target_user_id: ID of the user to remove.

    Returns:
        None (204 No Content in the route).

    Raises:
        ValueError: If the org/member is not found or the target is the owner.
        PermissionError: If the caller is a plain member (not owner or admin).
    """
    # Resolve org
    org_result = await db.execute(
        select(Organisation).where(Organisation.slug == slug)
    )
    org = org_result.scalar_one_or_none()
    if org is None:
        raise ValueError(f"Organisation '{slug}' not found.")

    # Verify caller is a member and has at least admin role
    caller_result = await db.execute(
        select(Membership).where(
            (Membership.org_id == org.id) & (Membership.user_id == current_user.id)
        )
    )
    caller = caller_result.scalar_one_or_none()
    if caller is None:
        raise ValueError(f"Organisation '{slug}' not found.")  # no disclosure
    if caller.role not in (MemberRole.owner, MemberRole.admin):
        raise PermissionError("Only owner or admin can remove members.")

    # Fetch the target membership
    target_result = await db.execute(
        select(Membership).where(
            (Membership.org_id == org.id) & (Membership.user_id == target_user_id)
        )
    )
    target = target_result.scalar_one_or_none()
    if target is None:
        raise ValueError(f"User '{target_user_id}' is not a member of this organisation.")
    if target.role == MemberRole.owner:
        raise ValueError("The organisation owner cannot be removed.")

    from app.services.billing import sync_subscription_seat_quantity  # noqa: PLC0415

    async with db.begin_nested():
        await db.delete(target)
        await db.flush()

        await sync_subscription_seat_quantity(
            db=db,
            org_id=org.id,
            strict=True,
            require_license_grant=False,
        )


async def get_organisation_by_slug(
    db: AsyncSession,
    current_user: User,
    slug: str,
) -> OrganisationResponse:
    """
    Fetch a single organisation by slug, enforcing membership.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user requesting the org.
        slug: URL slug of the target organisation.

    Returns:
        OrganisationResponse for the matching organisation.

    Raises:
        ValueError: If the org does not exist or the user is not a member
                    (both map to 404 in the route to avoid disclosure).
    """
    # Verify the user is a member before returning the org
    result = await db.execute(
        select(Organisation)
        .join(
            Membership,
            (Membership.org_id == Organisation.id) & (Membership.user_id == current_user.id),
        )
        .where(Organisation.slug == slug)
    )
    org = result.scalar_one_or_none()
    if org is None:
        raise ValueError(f"Organisation '{slug}' not found or you are not a member.")

    return _format_org(org)


async def get_org_stats(
    db: AsyncSession,
    current_user: User,
    slug: str,
) -> OrgStatsResponse:
    """
    Return activity counters for an organisation dashboard.

    Counts: open documents, pending amendments across all org documents,
    and total members.  Membership is verified before any query.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user requesting the stats.
        slug: URL slug of the target organisation.

    Returns:
        OrgStatsResponse with active_docs, pending_amendments, member_count.

    Raises:
        ValueError: If the org does not exist or the user is not a member.
    """
    # Verify membership first
    result = await db.execute(
        select(Organisation)
        .join(
            Membership,
            (Membership.org_id == Organisation.id) & (Membership.user_id == current_user.id),
        )
        .where(Organisation.slug == slug)
    )
    org = result.scalar_one_or_none()
    if org is None:
        raise ValueError(f"Organisation '{slug}' not found or you are not a member.")

    # Active documents (status = open)
    active_docs_result = await db.execute(
        select(func.count(Document.id))
        .where(Document.org_id == org.id, Document.status == DocumentStatus.open)
    )
    active_docs = active_docs_result.scalar_one()

    # Pending amendments across all org documents
    pending_amendments_result = await db.execute(
        select(func.count(Amendment.id))
        .join(Document, Amendment.doc_id == Document.id)
        .where(Document.org_id == org.id, Amendment.status == AmendmentStatus.pending)
    )
    pending_amendments = pending_amendments_result.scalar_one()

    # Member count
    member_count_result = await db.execute(
        select(func.count(Membership.user_id)).where(Membership.org_id == org.id)
    )
    member_count = member_count_result.scalar_one()

    return OrgStatsResponse(
        active_docs=active_docs,
        pending_amendments=pending_amendments,
        member_count=member_count,
    )
