"""
Invitation service — business logic for creating and accepting organisation invitations.

Flow:
  1. Owner or admin calls create_invite(slug, email).
     - Verifies the caller has owner/admin role.
     - If the email belongs to an existing user who is already a member → 409.
     - If a pending (non-expired, non-accepted) invite already exists → returns it
       (idempotent: no duplicate spam).
     - Otherwise creates a new Invitation row and emails the invite link.

  2. Any user calls accept_invite(token).
     - Looks up the invitation by token.
     - Validates it is not expired and not already accepted.
     - If the current user is already a member → 409.
     - Creates a Membership row with role=member and stamps accepted_at.
"""

import secrets
import string
from datetime import UTC, datetime, timedelta

import resend
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.invitation import Invitation
from app.models.membership import MemberRole, Membership
from app.models.organisation import Organisation
from app.models.user import User
from app.schemas.invitation import InvitationPreview, InvitationResponse

INVITE_EXPIRE_HOURS = 72  # Invites are valid for 3 days

_SAFE_CHARS = string.ascii_letters + string.digits


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _generate_invite_token(length: int = 48) -> str:
    """
    Generate a cryptographically secure URL-safe token for invite links.

    Parameters:
        length: Number of characters in the generated token (default 48).

    Returns:
        A URL-safe random token string.
    """
    return "".join(secrets.choice(_SAFE_CHARS) for _ in range(length))


def _format_invitation(inv: Invitation) -> InvitationResponse:
    """
    Convert an Invitation ORM instance to an InvitationResponse schema.

    Parameters:
        inv: SQLAlchemy Invitation instance.

    Returns:
        InvitationResponse with ISO-8601 datetime strings.
    """
    return InvitationResponse(
        id=inv.id,
        org_id=inv.org_id,
        email=inv.email,
        created_at=inv.created_at.isoformat(),
        expires_at=inv.expires_at.isoformat(),
        accepted_at=inv.accepted_at.isoformat() if inv.accepted_at else None,
    )


async def _require_owner_or_admin(
    db: AsyncSession,
    current_user: User,
    slug: str,
) -> Organisation:
    """
    Fetch an organisation by slug and verify the caller is an owner or admin.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user making the request.
        slug: URL slug of the target organisation.

    Returns:
        The Organisation ORM instance.

    Raises:
        ValueError: If the org is not found, user is not a member,
                    or user does not have owner/admin role.
    """
    result = await db.execute(
        select(Organisation, Membership)
        .join(
            Membership,
            (Membership.org_id == Organisation.id) & (Membership.user_id == current_user.id),
        )
        .where(Organisation.slug == slug)
    )
    row = result.one_or_none()
    if row is None:
        raise ValueError(f"Organisation '{slug}' not found or you are not a member.")
    org, membership = row
    if membership.role not in (MemberRole.owner, MemberRole.admin):
        raise ValueError("Only owners and admins can invite members.")
    return org


def _build_invite_email_html(invite_url: str, org_name: str) -> str:
    """
    Build a branded HTML invite email body with inline CSS.

    No external resources are referenced — all styles are inlined so the email
    renders correctly in all major clients (Gmail, Outlook, Apple Mail).

    Parameters:
        invite_url: The full accept-invitation URL including the token.
        org_name: Human-readable name of the organisation.

    Returns:
        A complete HTML string suitable for use as the ``html`` field of a
        Resend email payload.
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Invitation to join {org_name}</title>
</head>
<body style="margin:0;padding:0;background-color:#f7f9fb;font-family:'Inter',Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background-color:#f7f9fb;padding:48px 16px;">
    <tr>
      <td align="center">
        <!-- Card -->
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="max-width:520px;background-color:#ffffff;border-radius:6px;
                      box-shadow:0px 12px 32px rgba(42,52,57,0.06);overflow:hidden;">

          <!-- Header strip -->
          <tr>
            <td style="background-color:#515f74;padding:28px 40px;">
              <p style="margin:0;font-family:'Inter',Arial,sans-serif;
                        font-size:11px;font-weight:600;letter-spacing:0.12em;
                        text-transform:uppercase;color:#ffffff;opacity:0.7;">
                Amendly
              </p>
              <h1 style="margin:8px 0 0;font-family:Arial,sans-serif;
                         font-size:22px;font-weight:700;color:#ffffff;line-height:1.2;">
                You&rsquo;ve been invited
              </h1>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:36px 40px 32px;">
              <p style="margin:0 0 24px;font-size:15px;color:#2a3439;line-height:1.6;">
                You have been invited to join
                <strong style="color:#515f74;">{org_name}</strong>
                on Amendly — the collaborative amendment management platform.
              </p>

              <!-- Org pill -->
              <table role="presentation" cellpadding="0" cellspacing="0"
                     style="margin-bottom:32px;">
                <tr>
                  <td style="background-color:#f0f4f7;border-radius:6px;
                              padding:14px 20px;">
                    <p style="margin:0;font-size:11px;font-weight:600;
                               letter-spacing:0.08em;text-transform:uppercase;
                               color:#717c82;">Organisation</p>
                    <p style="margin:4px 0 0;font-size:16px;font-weight:700;
                               color:#2a3439;">{org_name}</p>
                  </td>
                </tr>
              </table>

              <!-- CTA button -->
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="border-radius:6px;background-color:#2563EB;">
                    <a href="{invite_url}"
                       style="display:inline-block;padding:14px 32px;
                              font-size:14px;font-weight:600;color:#ffffff;
                              text-decoration:none;border-radius:6px;">
                      Accept invitation &rarr;
                    </a>
                  </td>
                </tr>
              </table>

              <p style="margin:28px 0 0;font-size:13px;color:#717c82;line-height:1.5;">
                This invitation expires in
                <strong>{INVITE_EXPIRE_HOURS}&nbsp;hours</strong>.
                If you cannot click the button above, copy and paste this link into
                your browser:
              </p>
              <p style="margin:8px 0 0;font-size:12px;color:#0053dc;word-break:break-all;">
                {invite_url}
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color:#f0f4f7;padding:20px 40px;">
              <p style="margin:0;font-size:12px;color:#717c82;line-height:1.6;">
                If you were not expecting this invitation, you can safely ignore
                this email. Your email address will not be added to any
                organisation without your explicit consent.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


async def _send_invite_email(
    db: AsyncSession, email: str, token: str, org_name: str
) -> None:
    """
    Send an organisation invite email via Resend.

    Uses the 'invite' email template from the DB if one exists (editable by the
    superadmin), otherwise falls back to the hardcoded HTML.

    The link embeds the one-time token as a query parameter pointing to the
    frontend /invitations/accept route. In development (no RESEND_API_KEY set),
    the invite URL is printed to stdout instead of sending a real email.

    Parameters:
        db: Async SQLAlchemy session — used to load the editable email template.
        email: Recipient email address.
        token: One-time invite token (plain text).
        org_name: Human-readable name of the organisation.

    Side effects:
        Sends a transactional email via the Resend API (or logs the URL in dev).

    Raises:
        HTTPException 503: If the Resend API call fails.
    """
    scheme = "http" if settings.domain in ("localhost", "127.0.0.1") else "https"
    invite_url = f"{scheme}://{settings.domain}/invitations/accept?token={token}"

    if not settings.resend_api_key:
        print(f"[DEV] Invite link for {email} → {org_name}: {invite_url}")
        return

    resend.api_key = settings.resend_api_key

    from app.services.email_template import render_template  # noqa: PLC0415

    subject, html = await render_template(
        db, "invite", {"org_name": org_name, "invite_url": invite_url}
    )
    if not html:
        subject = f"You've been invited to join {org_name} on Amendly"
        html = _build_invite_email_html(invite_url=invite_url, org_name=org_name)

    try:
        resend.Emails.send(
            {
                "from": f"Amendly <{settings.resend_from_email}>",
                "to": [email],
                "subject": subject,
                "html": html,
            }
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email delivery failed. Please try again.",
        ) from exc


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


async def create_invite(
    db: AsyncSession,
    current_user: User,
    slug: str,
    email: str,
) -> InvitationResponse:
    """
    Create (or return an existing pending) invitation for an email address.

    Owner/admin only. If the email already belongs to a member of the org,
    raises ValueError (→ 409). If a pending non-expired invite already exists
    for this (org, email) pair, returns it without re-sending (idempotent).
    Otherwise creates a new Invitation and sends the invite email.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user creating the invite (must be owner/admin).
        slug: URL slug of the target organisation.
        email: Email address of the invitee.

    Returns:
        InvitationResponse for the new or existing pending invitation.

    Raises:
        ValueError: If the org is not found, caller lacks permission,
                    or the email is already a member of the org.
        HTTPException 503: If email delivery fails.
    """
    org = await _require_owner_or_admin(db, current_user, slug)

    # Check: is the email already a member?
    existing_member_result = await db.execute(
        select(User).where(User.email == email)
    )
    invited_user = existing_member_result.scalar_one_or_none()

    if invited_user:
        mem_check = await db.execute(
            select(Membership).where(
                Membership.user_id == invited_user.id,
                Membership.org_id == org.id,
            )
        )
        if mem_check.scalar_one_or_none() is not None:
            raise ValueError(f"{email} is already a member of this organisation.")

    now = datetime.now(UTC)

    # Idempotency: return existing pending invite if one exists and is not expired
    existing_invite_result = await db.execute(
        select(Invitation).where(
            Invitation.org_id == org.id,
            Invitation.email == email,
            Invitation.accepted_at.is_(None),
            Invitation.expires_at > now,
        )
    )
    existing_invite = existing_invite_result.scalar_one_or_none()
    if existing_invite is not None:
        return _format_invitation(existing_invite)

    # Create a fresh invitation
    token = _generate_invite_token()
    expires_at = now + timedelta(hours=INVITE_EXPIRE_HOURS)

    invitation = Invitation(
        org_id=org.id,
        email=email,
        token=token,
        expires_at=expires_at,
    )
    db.add(invitation)
    await db.flush()

    # Send the invite email (dev: prints to stdout)
    await _send_invite_email(db=db, email=email, token=token, org_name=org.name)

    return _format_invitation(invitation)


async def accept_invite(
    db: AsyncSession,
    current_user: User,
    token: str,
) -> InvitationResponse:
    """
    Accept an invitation by token, creating a Membership for the current user.

    Validates the token is valid, not expired, and not already accepted.
    If the user is already a member of the target org, raises ValueError (→ 409).
    On success, creates a Membership row with role=member and stamps accepted_at.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user accepting the invite.
        token: The invite token from the URL query parameter.

    Returns:
        InvitationResponse for the accepted invitation.

    Raises:
        ValueError: If the token is not found, expired, already accepted,
                    the current user's email does not match the invited email,
                    or the user is already a member of the org.
    """
    now = datetime.now(UTC)

    result = await db.execute(
        select(Invitation).where(Invitation.token == token)
    )
    invitation = result.scalar_one_or_none()

    if invitation is None:
        raise ValueError("Invitation not found.")
    if invitation.accepted_at is not None:
        raise ValueError("This invitation has already been accepted.")
    if invitation.expires_at.replace(tzinfo=UTC) < now:
        raise ValueError("This invitation has expired.")

    # Check for existing membership
    mem_check = await db.execute(
        select(Membership).where(
            Membership.user_id == current_user.id,
            Membership.org_id == invitation.org_id,
        )
    )
    if mem_check.scalar_one_or_none() is not None:
        raise ValueError("You are already a member of this organisation.")

    # Enforce nominal binding: only the invited email may accept
    if current_user.email.lower() != invitation.email.lower():
        raise ValueError("This invitation was sent to a different email address.")

    from app.services.billing import sync_subscription_seat_quantity  # noqa: PLC0415

    async with db.begin_nested():
        membership = Membership(
            user_id=current_user.id,
            org_id=invitation.org_id,
            role=MemberRole.member,
        )
        db.add(membership)

        invitation.accepted_at = now
        await db.flush()

        await sync_subscription_seat_quantity(
            db=db,
            org_id=invitation.org_id,
            strict=True,
            require_license_grant=True,
        )

    return _format_invitation(invitation)


async def list_pending_invites(
    db: AsyncSession,
    current_user: User,
    slug: str,
) -> list[InvitationResponse]:
    """
    List all pending (non-expired, non-accepted) invitations for an organisation.

    Owner/admin only.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user requesting the list (must be owner/admin).
        slug: URL slug of the target organisation.

    Returns:
        List of InvitationResponse for all pending invitations.

    Raises:
        ValueError: If the org is not found or caller lacks permission.
    """
    org = await _require_owner_or_admin(db, current_user, slug)
    now = datetime.now(UTC)

    result = await db.execute(
        select(Invitation).where(
            Invitation.org_id == org.id,
            Invitation.accepted_at.is_(None),
            Invitation.expires_at > now,
        ).order_by(Invitation.created_at.desc())
    )
    return [_format_invitation(inv) for inv in result.scalars().all()]


async def revoke_invite(
    db: AsyncSession,
    current_user: User,
    slug: str,
    invitation_id: str,
) -> None:
    """
    Revoke (delete) a pending invitation.

    Owner/admin only. Only pending (non-accepted) invitations can be revoked.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user revoking the invite (must be owner/admin).
        slug: URL slug of the target organisation.
        invitation_id: UUID of the invitation to revoke.

    Side effects:
        Deletes the Invitation row from the database.

    Raises:
        ValueError: If the org is not found, caller lacks permission,
                    the invitation is not found, or it has already been accepted.
    """
    org = await _require_owner_or_admin(db, current_user, slug)

    result = await db.execute(
        select(Invitation).where(
            Invitation.id == invitation_id,
            Invitation.org_id == org.id,
        )
    )
    invitation = result.scalar_one_or_none()

    if invitation is None:
        raise ValueError("Invitation not found.")
    if invitation.accepted_at is not None:
        raise ValueError("Cannot revoke an invitation that has already been accepted.")

    await db.delete(invitation)
    await db.flush()


async def resend_invite(
    db: AsyncSession,
    current_user: User,
    slug: str,
    invitation_id: str,
) -> InvitationResponse:
    """
    Resend an invitation email, refreshing the token and expiry.

    Owner/admin only. Generates a new token and resets the expiry to 72 hours
    from now, then re-sends the invite email.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user resending the invite (must be owner/admin).
        slug: URL slug of the target organisation.
        invitation_id: UUID of the invitation to resend.

    Returns:
        Updated InvitationResponse with the new token's expiry.

    Raises:
        ValueError: If the org is not found, caller lacks permission,
                    or the invitation is not found or already accepted.
        HTTPException 503: If email delivery fails.
    """
    org = await _require_owner_or_admin(db, current_user, slug)

    result = await db.execute(
        select(Invitation).where(
            Invitation.id == invitation_id,
            Invitation.org_id == org.id,
        )
    )
    invitation = result.scalar_one_or_none()

    if invitation is None:
        raise ValueError("Invitation not found.")
    if invitation.accepted_at is not None:
        raise ValueError("Cannot resend an invitation that has already been accepted.")

    now = datetime.now(UTC)
    invitation.token = _generate_invite_token()
    invitation.expires_at = now + timedelta(hours=INVITE_EXPIRE_HOURS)
    await db.flush()

    await _send_invite_email(db=db, email=invitation.email, token=invitation.token, org_name=org.name)

    return _format_invitation(invitation)


async def get_invite_preview(
    db: AsyncSession,
    token: str,
) -> InvitationPreview:
    """
    Return a public preview of an invitation for the accept-invitation page.

    This endpoint is intentionally unauthenticated — it is called before the
    invitee may have an account — so it exposes only the minimum information
    needed to render the UI: the organisation name, the invitee email, and
    the expiry timestamp.

    Parameters:
        db: Async SQLAlchemy session.
        token: The invite token from the URL query parameter.

    Returns:
        InvitationPreview with org_name, email, and expires_at.

    Raises:
        ValueError: If the token is not found, already accepted, or expired.
    """
    now = datetime.now(UTC)

    result = await db.execute(
        select(Invitation, Organisation)
        .join(Organisation, Organisation.id == Invitation.org_id)
        .where(Invitation.token == token)
    )
    row = result.one_or_none()

    if row is None:
        raise ValueError("Invitation not found.")

    invitation, org = row

    if invitation.accepted_at is not None:
        raise ValueError("This invitation has already been accepted.")
    if invitation.expires_at.replace(tzinfo=UTC) < now:
        raise ValueError("This invitation has expired.")

    return InvitationPreview(
        org_name=org.name,
        email=invitation.email,
        expires_at=invitation.expires_at.isoformat(),
    )
