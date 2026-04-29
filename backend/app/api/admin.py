"""
Admin API — platform superuser endpoints for plan configuration and dashboard.

Endpoints:
  GET  /api/admin/plans                         — list all plan configs (superuser only)
  PATCH /api/admin/plans/{name}                 — partially update a plan config (superuser only)
  GET  /api/admin/stats                         — platform overview stats (superuser only)
  GET  /api/admin/organisations                 — all orgs with metrics (superuser only)
  PATCH /api/admin/organisations/{id}/plan      — override an org's plan (superuser only)
  GET  /api/admin/users                         — list all users with filters (superuser only)
  PATCH /api/admin/users/{id}                   — override user plan / expiry (superuser only)
  GET  /api/admin/email-templates               — list all email templates (superuser only)
  GET  /api/admin/email-templates/{key}         — get a single email template (superuser only)
  PATCH /api/admin/email-templates/{key}        — upsert an email template (superuser only)
  DELETE /api/admin/email-templates/{key}       — reset template to default (superuser only)
  GET  /api/admin/prospects                     — list all prospects (superuser only)
  POST /api/admin/prospects                     — create a prospect (superuser only)
  PATCH /api/admin/prospects/{id}               — update a prospect (superuser only)
  DELETE /api/admin/prospects/{id}              — delete a prospect (superuser only)
  POST /api/admin/prospects/{id}/email          — send an email to a prospect (superuser only)

All endpoints require the is_superuser flag on the authenticated user.
Non-superusers receive HTTP 403.  Unauthenticated requests receive HTTP 401.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_superuser


def _http_error(exc: ValueError) -> HTTPException:
    msg = str(exc)
    code = status.HTTP_404_NOT_FOUND if "not found" in msg.lower() else status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=code, detail=msg)
from app.core.database import get_db
from app.models.user import User
from app.schemas.admin import AdminOrgPlanUpdate, AdminOrgResponse, AdminStatsResponse, AdminUserResponse, AdminUserUpdate
from app.schemas.email_template import EmailTemplateResponse, EmailTemplateUpdate
from app.schemas.plan_config import PlanConfigResponse, PlanConfigUpdate
from app.schemas.prospect import ProspectCreate, ProspectEmailRequest, ProspectResponse, ProspectUpdate
from app.services.admin import get_platform_stats, list_all_organisations, list_all_users, update_org_plan, update_user
from app.services.email_template import (
    list_email_templates,
    get_email_template,
    upsert_email_template,
    reset_email_template,
)
from app.services.plan_config import list_plan_configs, update_plan_config
from app.services.prospect import (
    list_prospects,
    create_prospect,
    update_prospect,
    delete_prospect,
    send_prospect_email,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get(
    "/plans",
    response_model=list[PlanConfigResponse],
    summary="List all plan configurations (superuser)",
)
async def admin_list_plans(
    current_user: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
) -> list[PlanConfigResponse]:
    """
    Return all plan configurations (active and inactive), sorted by price.

    Requires the authenticated user to have is_superuser = TRUE.

    Parameters:
        current_user: Injected by require_superuser (HTTP 403 if not superuser).
        db: Injected async DB session.

    Returns:
        List of all PlanConfigResponse objects.
    """
    return await list_plan_configs(db, active_only=False)


@router.patch(
    "/plans/{plan_name}",
    response_model=PlanConfigResponse,
    summary="Update a plan configuration (superuser)",
)
async def admin_update_plan(
    plan_name: str,
    body: PlanConfigUpdate,
    current_user: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
) -> PlanConfigResponse:
    """
    Partially update a plan configuration.

    All body fields are optional; only non-None fields are written.
    Sending max_active_documents = -1 sets it to NULL (unlimited).

    Parameters:
        plan_name: URL path parameter — 'solo', 'team', or 'organisation'.
        body: PlanConfigUpdate with optional fields to change.
        current_user: Injected by require_superuser (HTTP 403 if not superuser).
        db: Injected async DB session.

    Returns:
        Updated PlanConfigResponse.

    Raises:
        HTTPException 404: If no plan with the given name exists.
    """
    try:
        return await update_plan_config(db, plan_name, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/stats",
    response_model=AdminStatsResponse,
    summary="Platform overview statistics (superuser)",
)
async def admin_get_stats(
    current_user: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
) -> AdminStatsResponse:
    """
    Return aggregated platform-level statistics.

    Includes total org/user counts, breakdown by plan, and an estimated
    monthly recurring revenue (MRR) computed from plan_config prices.

    Parameters:
        current_user: Injected by require_superuser (HTTP 403 if not superuser).
        db: Injected async DB session.

    Returns:
        AdminStatsResponse with total_orgs, total_users, orgs_by_plan, estimated_mrr_cents.
    """
    return await get_platform_stats(db)


@router.get(
    "/organisations",
    response_model=list[AdminOrgResponse],
    summary="List all organisations (superuser)",
)
async def admin_list_organisations(
    current_user: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
) -> list[AdminOrgResponse]:
    """
    Return all organisations enriched with member and document counts.

    Results are ordered newest-first.

    Parameters:
        current_user: Injected by require_superuser (HTTP 403 if not superuser).
        db: Injected async DB session.

    Returns:
        List of AdminOrgResponse objects.
    """
    return await list_all_organisations(db)


@router.patch(
    "/organisations/{org_id}/plan",
    response_model=AdminOrgResponse,
    summary="Override an organisation's billing plan (superuser)",
)
async def admin_update_org_plan(
    org_id: str,
    body: AdminOrgPlanUpdate,
    current_user: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
) -> AdminOrgResponse:
    """
    Override the billing plan of an organisation (extension or revocation).

    This is a direct database override and does not interact with Stripe.
    Use for manual corrections, trial extensions, or plan revocations.

    Parameters:
        org_id: UUID of the organisation to update.
        body: AdminOrgPlanUpdate with the new plan ('solo' | 'team' | 'organisation').
        current_user: Injected by require_superuser (HTTP 403 if not superuser).
        db: Injected async DB session.

    Returns:
        Updated AdminOrgResponse.

    Raises:
        HTTPException 400: If the plan value is invalid.
        HTTPException 404: If the organisation is not found.
    """
    try:
        return await update_org_plan(db, org_id=org_id, new_plan=body.plan)
    except ValueError as exc:
        raise _http_error(exc) from exc


# ---------------------------------------------------------------------------
# User management endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/users",
    response_model=list[AdminUserResponse],
    summary="List all users (superuser)",
)
async def admin_list_users(
    search: str | None = Query(default=None, description="Filter by email or name substring"),
    plan: str | None = Query(default=None, description="Filter by plan: solo | team | organisation"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted accounts"),
    current_user: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
) -> list[AdminUserResponse]:
    """
    Return all users with org membership info, optionally filtered.

    Parameters:
        search: Case-insensitive substring match on email or name.
        plan: Exact plan filter ('solo', 'team', 'organisation').
        include_deleted: When True, include soft-deleted / anonymised accounts.
        current_user: Injected by require_superuser (HTTP 403 if not superuser).
        db: Injected async DB session.

    Returns:
        List of AdminUserResponse objects ordered newest-first.
    """
    try:
        return await list_all_users(db, search=search, plan=plan, include_deleted=include_deleted)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.patch(
    "/users/{user_id}",
    response_model=AdminUserResponse,
    summary="Update a user's plan or expiry (superuser)",
)
async def admin_update_user(
    user_id: str,
    body: AdminUserUpdate,
    current_user: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
) -> AdminUserResponse:
    """
    Override a user's plan and/or plan_expires_at (for gifts or compensation).

    All body fields are optional; only non-None fields are written.
    Send plan_expires_at as an ISO-8601 string to set an expiry, or as an
    empty string / null JSON to clear it.

    Parameters:
        user_id: UUID of the user to update.
        body: AdminUserUpdate with optional plan and plan_expires_at.
        current_user: Injected by require_superuser (HTTP 403 if not superuser).
        db: Injected async DB session.

    Returns:
        Updated AdminUserResponse.

    Raises:
        HTTPException 400: If the plan value is invalid.
        HTTPException 404: If the user is not found.
    """
    kwargs: dict = {}
    if body.plan is not None:
        kwargs["plan"] = body.plan
    if body.plan_expires_at is not None:
        # Empty string means "clear expiry"
        kwargs["plan_expires_at"] = None if body.plan_expires_at == "" else body.plan_expires_at
    else:
        kwargs["plan_expires_at"] = ...  # sentinel: leave unchanged

    try:
        return await update_user(db, user_id, **kwargs)
    except ValueError as exc:
        raise _http_error(exc) from exc


# ---------------------------------------------------------------------------
# Email template endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/email-templates",
    response_model=list[EmailTemplateResponse],
    summary="List all email templates (superuser)",
)
async def admin_list_email_templates(
    current_user: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
) -> list[EmailTemplateResponse]:
    """
    Return all known email templates, merging DB overrides with defaults.

    Parameters:
        current_user: Injected by require_superuser (HTTP 403 if not superuser).
        db: Injected async DB session.

    Returns:
        List of EmailTemplateResponse (one per template key).
    """
    return await list_email_templates(db)


@router.get(
    "/email-templates/{template_key}",
    response_model=EmailTemplateResponse,
    summary="Get a single email template (superuser)",
)
async def admin_get_email_template(
    template_key: str,
    current_user: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
) -> EmailTemplateResponse:
    """
    Return the template for the given key (DB override or default).

    Parameters:
        template_key: e.g. 'invite', 'amendment_accepted'.
        current_user: Injected by require_superuser (HTTP 403 if not superuser).
        db: Injected async DB session.

    Returns:
        EmailTemplateResponse.

    Raises:
        HTTPException 404: If the template key is unknown.
    """
    tmpl = await get_email_template(db, template_key)
    if tmpl is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown template key: {template_key!r}",
        )
    return tmpl


@router.patch(
    "/email-templates/{template_key}",
    response_model=EmailTemplateResponse,
    summary="Upsert an email template (superuser)",
)
async def admin_upsert_email_template(
    template_key: str,
    body: EmailTemplateUpdate,
    current_user: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
) -> EmailTemplateResponse:
    """
    Create or update the DB override for the given template key.

    Parameters:
        template_key: e.g. 'invite', 'magic_link'.
        body: EmailTemplateUpdate with subject and html_body.
        current_user: Injected by require_superuser (HTTP 403 if not superuser).
        db: Injected async DB session.

    Returns:
        Updated EmailTemplateResponse with is_customised = True.

    Raises:
        HTTPException 404: If the template key is unknown.
    """
    try:
        return await upsert_email_template(db, template_key, body.subject, body.html_body)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.delete(
    "/email-templates/{template_key}",
    response_model=EmailTemplateResponse,
    summary="Reset an email template to its default (superuser)",
)
async def admin_reset_email_template(
    template_key: str,
    current_user: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
) -> EmailTemplateResponse:
    """
    Delete any DB override, reverting the template to the hardcoded default.

    Parameters:
        template_key: e.g. 'invite'.
        current_user: Injected by require_superuser (HTTP 403 if not superuser).
        db: Injected async DB session.

    Returns:
        The default EmailTemplateResponse with is_customised = False.

    Raises:
        HTTPException 404: If the template key is unknown.
    """
    try:
        return await reset_email_template(db, template_key)
    except ValueError as exc:
        raise _http_error(exc) from exc


# ---------------------------------------------------------------------------
# Prospect endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/prospects",
    response_model=list[ProspectResponse],
    summary="List all prospects (superuser)",
)
async def admin_list_prospects(
    current_user: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
) -> list[ProspectResponse]:
    """
    Return all prospects ordered newest-first.

    Parameters:
        current_user: Injected by require_superuser (HTTP 403 if not superuser).
        db: Injected async DB session.

    Returns:
        List of ProspectResponse objects.
    """
    return await list_prospects(db)


@router.post(
    "/prospects",
    response_model=ProspectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new prospect (superuser)",
)
async def admin_create_prospect(
    body: ProspectCreate,
    current_user: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
) -> ProspectResponse:
    """
    Create a new sales prospect.

    Parameters:
        body: ProspectCreate with required email and optional fields.
        current_user: Injected by require_superuser (HTTP 403 if not superuser).
        db: Injected async DB session.

    Returns:
        Newly created ProspectResponse (HTTP 201).
    """
    return await create_prospect(db, body)


@router.patch(
    "/prospects/{prospect_id}",
    response_model=ProspectResponse,
    summary="Update a prospect (superuser)",
)
async def admin_update_prospect(
    prospect_id: str,
    body: ProspectUpdate,
    current_user: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
) -> ProspectResponse:
    """
    Partially update an existing prospect (status, notes, contact details).

    Parameters:
        prospect_id: UUID of the prospect.
        body: ProspectUpdate with optional fields.
        current_user: Injected by require_superuser (HTTP 403 if not superuser).
        db: Injected async DB session.

    Returns:
        Updated ProspectResponse.

    Raises:
        HTTPException 400: If the status value is invalid.
        HTTPException 404: If the prospect is not found.
    """
    try:
        return await update_prospect(db, prospect_id, body)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.delete(
    "/prospects/{prospect_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a prospect (superuser)",
)
async def admin_delete_prospect(
    prospect_id: str,
    current_user: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Permanently delete a prospect row.

    Parameters:
        prospect_id: UUID of the prospect to delete.
        current_user: Injected by require_superuser (HTTP 403 if not superuser).
        db: Injected async DB session.

    Returns:
        HTTP 204 No Content.

    Raises:
        HTTPException 404: If the prospect is not found.
    """
    try:
        await delete_prospect(db, prospect_id)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.post(
    "/prospects/{prospect_id}/email",
    response_model=ProspectResponse,
    summary="Send an email to a prospect (superuser)",
)
async def admin_send_prospect_email(
    prospect_id: str,
    body: ProspectEmailRequest,
    current_user: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
) -> ProspectResponse:
    """
    Send a transactional email to a prospect and log it in their notes.

    Either supply template_key to use a stored email template (with {nom}
    and {org_name} placeholders substituted from the prospect's data), or
    supply both subject and html_body for a free-form email.

    Side effects:
      - The email is sent immediately via Resend.
      - A log line (timestamp + subject) is appended to prospect.notes.
      - If the prospect status is 'new', it is advanced to 'contacted'.

    Parameters:
        prospect_id: UUID of the prospect to email.
        body: ProspectEmailRequest — template_key OR subject + html_body.
        current_user: Injected by require_superuser (HTTP 403 if not superuser).
        db: Injected async DB session.

    Returns:
        Updated ProspectResponse.

    Raises:
        HTTPException 400: If validation fails (missing fields or unknown template key).
        HTTPException 404: If the prospect is not found.
        HTTPException 502: If the Resend API call fails.
    """
    try:
        return await send_prospect_email(db, prospect_id, body)
    except ValueError as exc:
        raise _http_error(exc) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
