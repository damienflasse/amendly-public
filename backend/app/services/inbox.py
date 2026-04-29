"""
Inbox service for public contact messages and authenticated support requests.
"""

from __future__ import annotations

import logging
from html import escape

import resend

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.membership import Membership
from app.models.organisation import Organisation
from app.models.user import User
from app.schemas.inbox import ContactRequest, SupportRequest

logger = logging.getLogger(__name__)

_PLAN_RANK = {
    "free": 0,
    "solo": 1,
    "team": 2,
    "pro": 2,
    "organisation": 3,
}

_CATEGORY_LABELS = {
    "billing": "Billing",
    "account": "Account & login",
    "documents": "Documents & amendments",
    "export": "Export",
    "other": "Other",
}


def _enum_value(value: object) -> str:
    """Return the plain string value of an enum-like value."""
    return value.value if hasattr(value, "value") else str(value)


def _support_tier_for_plan(plan: str) -> str:
    """Map a plan name to the support tier label used in metadata."""
    rank = _PLAN_RANK.get(plan, 0)
    if rank >= 2:
        return "priority"
    if rank == 1:
        return "standard"
    return "community"


def _html_paragraphs(text: str) -> str:
    """Convert user-supplied plain text into escaped HTML paragraphs."""
    return "<br />".join(escape(line) for line in text.splitlines()) or escape(text)


def _render_metadata_rows(rows: list[tuple[str, str]]) -> str:
    """Render metadata rows as a simple HTML table."""
    rendered = []
    for label, value in rows:
        rendered.append(
            "<tr>"
            f"<td style=\"padding:8px 12px;font-weight:600;color:#2a3439;"
            f"border-bottom:1px solid #d9e4ea;vertical-align:top;\">{escape(label)}</td>"
            f"<td style=\"padding:8px 12px;color:#2a3439;border-bottom:1px solid #d9e4ea;\">{escape(value)}</td>"
            "</tr>"
        )
    return "".join(rendered)


def _wrap_email_html(title: str, intro: str, rows: list[tuple[str, str]], message_html: str) -> str:
    """Build a compact branded HTML email for inbox-style notifications."""
    metadata_rows = _render_metadata_rows(rows)
    return f"""<!DOCTYPE html>
<html lang="en">
  <body style="margin:0;padding:24px;background:#f7f9fb;font-family:Arial,sans-serif;color:#2a3439;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:680px;margin:0 auto;background:#ffffff;border-radius:12px;border:1px solid #d9e4ea;">
      <tr>
        <td style="padding:24px 28px;background:#515f74;color:#ffffff;border-radius:12px 12px 0 0;">
          <div style="font-size:12px;letter-spacing:0.08em;text-transform:uppercase;opacity:0.8;">Amendly inbox</div>
          <h1 style="margin:8px 0 0;font-size:24px;line-height:1.3;">{escape(title)}</h1>
        </td>
      </tr>
      <tr>
        <td style="padding:24px 28px 12px;">
          <p style="margin:0 0 20px;font-size:15px;line-height:1.7;color:#515f74;">{escape(intro)}</p>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;background:#f7f9fb;border-radius:8px;overflow:hidden;">
            {metadata_rows}
          </table>
        </td>
      </tr>
      <tr>
        <td style="padding:12px 28px 28px;">
          <div style="font-size:12px;letter-spacing:0.08em;text-transform:uppercase;color:#717c82;margin-bottom:10px;">Message</div>
          <div style="padding:18px 20px;background:#ffffff;border:1px solid #d9e4ea;border-radius:8px;font-size:15px;line-height:1.7;color:#2a3439;">
            {message_html}
          </div>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def _deliver_team_email(*, subject: str, reply_to: str, html: str, text_preview: str) -> None:
    """Send an internal team email via Resend, or log it in development."""
    if not settings.resend_api_key:
        print(
            "=== Amendly inbox message ===\n"
            f"Inbox: {settings.support_inbox_email}\n"
            f"Reply-To: {reply_to}\n"
            f"Subject: {subject}\n\n"
            f"{text_preview}\n"
        )
        return

    resend.api_key = settings.resend_api_key
    try:
        resend.Emails.send(
            {
                "from": f"Amendly <{settings.resend_from_email}>",
                "to": [settings.support_inbox_email],
                "reply_to": [reply_to],
                "subject": subject,
                "html": html,
            }
        )
    except Exception as exc:
        logger.error("Failed to deliver inbox email '%s': %s", subject, exc)
        raise RuntimeError("Email delivery failed.") from exc


async def _build_support_context(db: AsyncSession, current_user: User) -> dict[str, object]:
    """Resolve support metadata for the authenticated user."""
    result = await db.execute(
        select(Organisation.name, Organisation.plan)
        .join(Membership, Membership.org_id == Organisation.id)
        .where(Membership.user_id == current_user.id)
        .order_by(Organisation.created_at)
    )
    org_rows = result.all()
    organisations = [
        {
            "name": name,
            "plan": _enum_value(plan),
        }
        for name, plan in org_rows
    ]

    highest_plan = _enum_value(current_user.plan) if current_user.plan is not None else "free"
    for org in organisations:
        if _PLAN_RANK.get(org["plan"], 0) > _PLAN_RANK.get(highest_plan, 0):
            highest_plan = org["plan"]

    return {
        "highest_plan": highest_plan,
        "support_tier": _support_tier_for_plan(highest_plan),
        "organisations": organisations,
    }


async def send_contact_message(payload: ContactRequest) -> None:
    """Send a public contact message to the Amendly inbox."""
    sender_name = f"{payload.first_name} {payload.last_name}".strip()
    subject = f"[Contact] {sender_name}"
    metadata = [
        ("From", sender_name),
        ("Email", payload.email),
    ]
    html = _wrap_email_html(
        title="New contact message",
        intro="A visitor submitted the public contact form.",
        rows=metadata,
        message_html=_html_paragraphs(payload.message),
    )
    _deliver_team_email(
        subject=subject,
        reply_to=payload.email,
        html=html,
        text_preview=f"From: {sender_name} <{payload.email}>\n\n{payload.message}",
    )


async def send_support_message(
    db: AsyncSession,
    *,
    current_user: User,
    payload: SupportRequest,
) -> None:
    """Send an authenticated support request to the Amendly inbox."""
    context = await _build_support_context(db, current_user)
    sender_name = current_user.name or current_user.email
    tier = str(context["support_tier"])
    highest_plan = str(context["highest_plan"])
    organisations = context["organisations"]
    org_summary = (
        ", ".join(f"{org['name']} ({org['plan']})" for org in organisations)
        if organisations
        else "No organisations"
    )
    category_label = _CATEGORY_LABELS.get(payload.category.value, payload.category.value)
    subject = f"[Support][{tier}][{payload.category.value}] {payload.subject}"
    metadata = [
        ("User", sender_name),
        ("Email", current_user.email),
        ("Tier", tier),
        ("Highest plan", highest_plan),
        ("Category", category_label),
        ("Subject", payload.subject),
        ("Organisations", org_summary),
    ]
    html = _wrap_email_html(
        title="New support request",
        intro="An authenticated user submitted a support request from the dashboard.",
        rows=metadata,
        message_html=_html_paragraphs(payload.message),
    )
    _deliver_team_email(
        subject=subject,
        reply_to=current_user.email,
        html=html,
        text_preview=(
            f"User: {sender_name} <{current_user.email}>\n"
            f"Tier: {tier}\n"
            f"Plan: {highest_plan}\n"
            f"Category: {category_label}\n"
            f"Organisations: {org_summary}\n\n"
            f"{payload.message}"
        ),
    )
