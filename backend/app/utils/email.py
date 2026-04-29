"""
Email utility — transactional email helpers for amendment status notifications.

Follows the same branded HTML pattern as invitation emails in
app/services/invitation.py.  All rendering is done with inline CSS so the
email displays correctly in Gmail, Outlook, and Apple Mail.
"""

from __future__ import annotations

import logging

import resend

from app.core.config import settings

logger = logging.getLogger(__name__)


def _build_amendment_status_email_html(
    *,
    status: str,
    org_name: str,
    doc_title: str,
    section: str | None,
    doc_url: str,
) -> str:
    """
    Build branded HTML for an amendment accepted/rejected notification.

    Parameters:
        status: 'accepted' or 'rejected'.
        org_name: Human-readable name of the organisation.
        doc_title: Title of the document the amendment belongs to.
        section: Optional section label (None if not set).
        doc_url: Full URL to the document page.

    Returns:
        Complete HTML string for use as the Resend ``html`` field.
    """
    status_label = "accepted" if status == "accepted" else "rejected"
    status_colour = "#0d6e25" if status == "accepted" else "#b91c1c"
    status_bg = "#d1fae5" if status == "accepted" else "#fee2e2"
    headline = (
        "Your amendment was accepted"
        if status == "accepted"
        else "Your amendment was rejected"
    )
    body_text = (
        "Good news — your amendment has been <strong>accepted</strong> and will be "
        "incorporated into the consolidated document."
        if status == "accepted"
        else "Your amendment has been <strong>rejected</strong> and will not be "
        "incorporated into the consolidated document."
    )

    section_row = ""
    if section:
        section_row = f"""
              <tr>
                <td style="padding:0 0 8px;">
                  <span style="font-size:11px;font-weight:600;letter-spacing:0.08em;
                               text-transform:uppercase;color:#717c82;">Section</span><br/>
                  <span style="font-size:15px;color:#2a3439;">{section}</span>
                </td>
              </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{headline}</title>
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
                {headline}
              </h1>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:36px 40px 32px;">
              <p style="margin:0 0 24px;font-size:15px;color:#2a3439;line-height:1.6;">
                {body_text}
              </p>

              <!-- Detail pill -->
              <table role="presentation" cellpadding="0" cellspacing="0"
                     style="margin-bottom:32px;width:100%;">
                <tr>
                  <td style="background-color:#f0f4f7;border-radius:6px;padding:16px 20px;">
                    <table role="presentation" cellpadding="0" cellspacing="0" width="100%">
                      <tr>
                        <td style="padding:0 0 8px;">
                          <span style="font-size:11px;font-weight:600;letter-spacing:0.08em;
                                       text-transform:uppercase;color:#717c82;">Organisation</span><br/>
                          <span style="font-size:15px;color:#2a3439;font-weight:700;">{org_name}</span>
                        </td>
                      </tr>
                      <tr>
                        <td style="padding:0 0 8px;">
                          <span style="font-size:11px;font-weight:600;letter-spacing:0.08em;
                                       text-transform:uppercase;color:#717c82;">Document</span><br/>
                          <span style="font-size:15px;color:#2a3439;">{doc_title}</span>
                        </td>
                      </tr>{section_row}
                      <tr>
                        <td style="padding:0;">
                          <span style="font-size:11px;font-weight:600;letter-spacing:0.08em;
                                       text-transform:uppercase;color:#717c82;">Status</span><br/>
                          <span style="display:inline-block;margin-top:4px;padding:3px 12px;
                                       border-radius:4px;font-size:13px;font-weight:700;
                                       background-color:{status_bg};color:{status_colour};">
                            {status_label.upper()}
                          </span>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <!-- CTA button -->
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="border-radius:6px;background-color:#515f74;">
                    <a href="{doc_url}"
                       style="display:inline-block;padding:14px 32px;
                              font-size:14px;font-weight:600;color:#ffffff;
                              text-decoration:none;border-radius:6px;">
                      View document &rarr;
                    </a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color:#f0f4f7;padding:20px 40px;">
              <p style="margin:0;font-size:12px;color:#717c82;line-height:1.6;">
                You are receiving this email because you submitted an amendment on
                <a href="https://{settings.domain}" style="color:#0053dc;">Amendly</a>.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


async def send_amendment_status_email(
    *,
    recipient_email: str,
    status: str,
    org_name: str,
    doc_title: str,
    doc_id: str,
    org_slug: str,
    section: str | None = None,
    db=None,
) -> None:
    """
    Send a transactional email notifying an amendment author of a status change.

    Uses the 'amendment_accepted' or 'amendment_rejected' email template from
    the DB if one exists (editable by the superadmin), otherwise falls back to
    the hardcoded HTML.

    Only fires when the new status is 'accepted' or 'rejected'.
    In development (no RESEND_API_KEY), the notification is printed to stdout.
    Errors are caught and logged — a delivery failure must never abort the
    primary amendment update.

    Parameters:
        recipient_email: Email address of the amendment author.
        status: New amendment status ('accepted' or 'rejected').
        org_name: Human-readable name of the organisation.
        doc_title: Title of the document.
        doc_id: UUID of the document (used to build the link).
        org_slug: URL slug of the organisation (used to build the link).
        section: Optional section label from the amendment.
        db: Optional async DB session — used to load editable templates.

    Side effects:
        Sends a transactional email via the Resend API (or logs in dev).
    """
    if status not in ("accepted", "rejected"):
        return

    scheme = "http" if settings.domain in ("localhost", "127.0.0.1") else "https"
    doc_url = f"{scheme}://{settings.domain}/orgs/{org_slug}/documents/{doc_id}"

    section_row = ""
    if section:
        section_row = f"""
              <tr>
                <td style="padding:0 0 8px;">
                  <span style="font-size:11px;font-weight:600;letter-spacing:0.08em;
                               text-transform:uppercase;color:#717c82;">Section</span><br/>
                  <span style="font-size:15px;color:#2a3439;">{section}</span>
                </td>
              </tr>"""

    email_subject: str
    html_body: str

    if db is not None:
        try:
            from app.services.email_template import render_template  # noqa: PLC0415

            template_key = f"amendment_{status}"
            email_subject, html_body = await render_template(
                db,
                template_key,
                {
                    "org_name": org_name,
                    "doc_title": doc_title,
                    "section_row": section_row,
                    "doc_url": doc_url,
                },
            )
        except Exception:
            email_subject = ""
            html_body = ""

    if not html_body if db is not None else True:
        email_subject = f"Your amendment was {status} — {doc_title}"
        html_body = _build_amendment_status_email_html(
            status=status,
            org_name=org_name,
            doc_title=doc_title,
            section=section,
            doc_url=doc_url,
        )

    if not settings.resend_api_key:
        print(
            f"[DEV] Amendment {status} email → {recipient_email}: {email_subject} | {doc_url}"
        )
        return

    try:
        resend.api_key = settings.resend_api_key
        resend.Emails.send(
            {
                "from": f"Amendly <{settings.resend_from_email}>",
                "to": [recipient_email],
                "subject": email_subject,
                "html": html_body,
            }
        )
    except Exception:
        logger.exception(
            "Failed to send amendment status email to %s (status=%s doc=%s)",
            recipient_email,
            status,
            doc_id,
        )


def _build_amendment_submitted_email_html(
    *,
    org_name: str,
    doc_title: str,
    author_name: str,
    section: str | None,
    doc_url: str,
) -> str:
    """
    Build branded HTML for a new-amendment notification sent to org owners/admins.

    Parameters:
        org_name: Human-readable name of the organisation.
        doc_title: Title of the document.
        author_name: Display name of the member who submitted the amendment.
        section: Optional section label (None if not set).
        doc_url: Full URL to the document page.

    Returns:
        Complete HTML string for use as the Resend ``html`` field.
    """
    section_row = ""
    if section:
        section_row = f"""
              <tr>
                <td style="padding:0 0 8px;">
                  <span style="font-size:11px;font-weight:600;letter-spacing:0.08em;
                               text-transform:uppercase;color:#717c82;">Section</span><br/>
                  <span style="font-size:15px;color:#2a3439;">{section}</span>
                </td>
              </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>New amendment submitted</title>
</head>
<body style="margin:0;padding:0;background-color:#f7f9fb;font-family:'Inter',Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background-color:#f7f9fb;padding:48px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="max-width:520px;background-color:#ffffff;border-radius:6px;
                      box-shadow:0px 12px 32px rgba(42,52,57,0.06);overflow:hidden;">
          <tr>
            <td style="background-color:#515f74;padding:28px 40px;">
              <p style="margin:0;font-family:'Inter',Arial,sans-serif;
                        font-size:11px;font-weight:600;letter-spacing:0.12em;
                        text-transform:uppercase;color:#ffffff;opacity:0.7;">Amendly</p>
              <h1 style="margin:8px 0 0;font-family:Arial,sans-serif;
                         font-size:22px;font-weight:700;color:#ffffff;line-height:1.2;">
                New amendment submitted
              </h1>
            </td>
          </tr>
          <tr>
            <td style="padding:36px 40px 32px;">
              <p style="margin:0 0 24px;font-size:15px;color:#2a3439;line-height:1.6;">
                <strong>{author_name}</strong> has submitted a new amendment to
                <strong>{doc_title}</strong> in <strong>{org_name}</strong>.
              </p>
              <table role="presentation" cellpadding="0" cellspacing="0"
                     style="margin-bottom:32px;width:100%;">
                <tr>
                  <td style="background-color:#f0f4f7;border-radius:6px;padding:16px 20px;">
                    <table role="presentation" cellpadding="0" cellspacing="0" width="100%">
                      <tr>
                        <td style="padding:0 0 8px;">
                          <span style="font-size:11px;font-weight:600;letter-spacing:0.08em;
                                       text-transform:uppercase;color:#717c82;">Organisation</span><br/>
                          <span style="font-size:15px;color:#2a3439;font-weight:700;">{org_name}</span>
                        </td>
                      </tr>
                      <tr>
                        <td style="padding:0 0 8px;">
                          <span style="font-size:11px;font-weight:600;letter-spacing:0.08em;
                                       text-transform:uppercase;color:#717c82;">Document</span><br/>
                          <span style="font-size:15px;color:#2a3439;">{doc_title}</span>
                        </td>
                      </tr>{section_row}
                      <tr>
                        <td style="padding:0;">
                          <span style="font-size:11px;font-weight:600;letter-spacing:0.08em;
                                       text-transform:uppercase;color:#717c82;">Submitted by</span><br/>
                          <span style="font-size:15px;color:#2a3439;">{author_name}</span>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="border-radius:6px;background-color:#515f74;">
                    <a href="{doc_url}"
                       style="display:inline-block;padding:14px 32px;
                              font-size:14px;font-weight:600;color:#ffffff;
                              text-decoration:none;border-radius:6px;">
                      Review amendment &rarr;
                    </a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="background-color:#f0f4f7;padding:20px 40px;">
              <p style="margin:0;font-size:12px;color:#717c82;line-height:1.6;">
                You are receiving this email because you are an owner or admin of
                <a href="https://{settings.domain}" style="color:#0053dc;">Amendly</a>.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


async def send_amendment_submitted_email(
    *,
    recipient_email: str,
    org_name: str,
    doc_title: str,
    author_name: str,
    doc_id: str,
    org_slug: str,
    section: str | None = None,
) -> None:
    """
    Notify an org owner or admin that a new amendment has been submitted.

    In development (no RESEND_API_KEY), logs to stdout.
    Errors are caught and logged — delivery failure must never abort the
    primary amendment creation.

    Parameters:
        recipient_email: Email address of the owner or admin to notify.
        org_name: Human-readable name of the organisation.
        doc_title: Title of the document.
        author_name: Display name of the amendment author.
        doc_id: UUID of the document (used to build the link).
        org_slug: URL slug of the organisation (used to build the link).
        section: Optional section label from the amendment.

    Side effects:
        Sends a transactional email via the Resend API (or logs in dev).
    """
    scheme = "http" if settings.domain in ("localhost", "127.0.0.1") else "https"
    doc_url = f"{scheme}://{settings.domain}/orgs/{org_slug}/documents/{doc_id}"

    subject = f"New amendment submitted — {doc_title}"
    html_body = _build_amendment_submitted_email_html(
        org_name=org_name,
        doc_title=doc_title,
        author_name=author_name,
        section=section,
        doc_url=doc_url,
    )

    if not settings.resend_api_key:
        print(
            f"[DEV] New amendment email → {recipient_email}: {subject} | {doc_url}"
        )
        return

    try:
        resend.api_key = settings.resend_api_key
        resend.Emails.send(
            {
                "from": f"Amendly <{settings.resend_from_email}>",
                "to": [recipient_email],
                "subject": subject,
                "html": html_body,
            }
        )
    except Exception:
        logger.exception(
            "Failed to send amendment submitted email to %s (doc=%s)",
            recipient_email,
            doc_id,
        )


def _build_amendment_commented_email_html(
    *,
    org_name: str,
    doc_title: str,
    commenter_name: str,
    section: str | None,
    comment_body: str,
    doc_url: str,
) -> str:
    """
    Build branded HTML for a comment-notification email sent to the amendment author.

    Parameters:
        org_name: Human-readable name of the organisation.
        doc_title: Title of the document the amendment belongs to.
        commenter_name: Display name (or email) of the person who commented.
        section: Optional section label from the amendment (None if not set).
        comment_body: The text of the new comment (truncated for display).
        doc_url: Full URL to the document page.

    Returns:
        Complete HTML string for use as the Resend ``html`` field.
    """
    section_row = ""
    if section:
        section_row = f"""
              <tr>
                <td style="padding:0 0 8px;">
                  <span style="font-size:11px;font-weight:600;letter-spacing:0.08em;
                               text-transform:uppercase;color:#717c82;">Section</span><br/>
                  <span style="font-size:15px;color:#2a3439;">{section}</span>
                </td>
              </tr>"""

    # Truncate long comment bodies for the email preview
    preview_body = comment_body if len(comment_body) <= 300 else comment_body[:297] + "…"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>New comment on your amendment</title>
</head>
<body style="margin:0;padding:0;background-color:#f7f9fb;font-family:'Inter',Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background-color:#f7f9fb;padding:48px 16px;">
    <tr>
      <td align="center">
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
                New comment on your amendment
              </h1>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:36px 40px 32px;">
              <p style="margin:0 0 24px;font-size:15px;color:#2a3439;line-height:1.6;">
                <strong>{commenter_name}</strong> has posted a comment on your amendment
                in <strong>{doc_title}</strong>.
              </p>

              <!-- Detail pill -->
              <table role="presentation" cellpadding="0" cellspacing="0"
                     style="margin-bottom:24px;width:100%;">
                <tr>
                  <td style="background-color:#f0f4f7;border-radius:6px;padding:16px 20px;">
                    <table role="presentation" cellpadding="0" cellspacing="0" width="100%">
                      <tr>
                        <td style="padding:0 0 8px;">
                          <span style="font-size:11px;font-weight:600;letter-spacing:0.08em;
                                       text-transform:uppercase;color:#717c82;">Organisation</span><br/>
                          <span style="font-size:15px;color:#2a3439;font-weight:700;">{org_name}</span>
                        </td>
                      </tr>
                      <tr>
                        <td style="padding:0 0 8px;">
                          <span style="font-size:11px;font-weight:600;letter-spacing:0.08em;
                                       text-transform:uppercase;color:#717c82;">Document</span><br/>
                          <span style="font-size:15px;color:#2a3439;">{doc_title}</span>
                        </td>
                      </tr>{section_row}
                    </table>
                  </td>
                </tr>
              </table>

              <!-- Comment bubble -->
              <table role="presentation" cellpadding="0" cellspacing="0"
                     style="margin-bottom:32px;width:100%;">
                <tr>
                  <td style="background-color:#eef2ff;border-left:3px solid #2563eb;
                             border-radius:0 6px 6px 0;padding:14px 18px;">
                    <p style="margin:0 0 6px;font-size:11px;font-weight:600;
                               letter-spacing:0.08em;text-transform:uppercase;color:#2563eb;">
                      Comment
                    </p>
                    <p style="margin:0;font-size:14px;color:#2a3439;line-height:1.6;">
                      {preview_body}
                    </p>
                  </td>
                </tr>
              </table>

              <!-- CTA button -->
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="border-radius:6px;background-color:#515f74;">
                    <a href="{doc_url}"
                       style="display:inline-block;padding:14px 32px;
                              font-size:14px;font-weight:600;color:#ffffff;
                              text-decoration:none;border-radius:6px;">
                      View amendment &rarr;
                    </a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color:#f0f4f7;padding:20px 40px;">
              <p style="margin:0;font-size:12px;color:#717c82;line-height:1.6;">
                You are receiving this email because you submitted an amendment on
                <a href="https://{settings.domain}" style="color:#0053dc;">Amendly</a>.
                You can disable these notifications in your account settings.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


async def send_amendment_commented_email(
    *,
    recipient_email: str,
    org_name: str,
    doc_title: str,
    commenter_name: str,
    doc_id: str,
    org_slug: str,
    section: str | None = None,
    comment_body: str,
) -> None:
    """
    Notify the amendment author that a new comment has been posted on their amendment.

    Only fires when the commenter is a different user from the amendment author.
    In development (no RESEND_API_KEY), the notification is printed to stdout.
    Errors are caught and logged — a delivery failure must never abort the
    primary comment creation.

    Parameters:
        recipient_email: Email address of the amendment author.
        org_name: Human-readable name of the organisation.
        doc_title: Title of the document the amendment belongs to.
        commenter_name: Display name (or email) of the person who commented.
        doc_id: UUID of the document (used to build the link).
        org_slug: URL slug of the organisation (used to build the link).
        section: Optional section label from the amendment.
        comment_body: The text of the comment posted.

    Side effects:
        Sends a transactional email via the Resend API (or logs in dev).
    """
    scheme = "http" if settings.domain in ("localhost", "127.0.0.1") else "https"
    doc_url = f"{scheme}://{settings.domain}/orgs/{org_slug}/documents/{doc_id}"

    subject = f"New comment on your amendment — {doc_title}"
    html_body = _build_amendment_commented_email_html(
        org_name=org_name,
        doc_title=doc_title,
        commenter_name=commenter_name,
        section=section,
        comment_body=comment_body,
        doc_url=doc_url,
    )

    if not settings.resend_api_key:
        print(
            f"[DEV] Comment notification email → {recipient_email}: {subject} | {doc_url}"
        )
        return

    try:
        resend.api_key = settings.resend_api_key
        resend.Emails.send(
            {
                "from": f"Amendly <{settings.resend_from_email}>",
                "to": [recipient_email],
                "subject": subject,
                "html": html_body,
            }
        )
    except Exception:
        logger.exception(
            "Failed to send amendment commented email to %s (doc=%s)",
            recipient_email,
            doc_id,
        )
