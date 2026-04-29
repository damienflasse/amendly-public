"""
EmailTemplate service — CRUD for superadmin-editable email templates.

Templates are stored in the DB as HTML with {variable} placeholders.
At send time, callers call render_template(key, variables) which:
  1. Loads the template from the DB (if it exists).
  2. Falls back to the hardcoded default (if no DB row exists).
  3. Substitutes {variable} placeholders using the supplied dict.

Default template keys and their placeholders:
  invite              — {org_name}, {invite_url}
  amendment_accepted  — {org_name}, {doc_title}, {section_row}, {doc_url}
  amendment_rejected  — {org_name}, {doc_title}, {section_row}, {doc_url}
  magic_link          — {magic_link_url}
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_template import EmailTemplate
from app.schemas.email_template import EmailTemplateResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default template definitions
# ---------------------------------------------------------------------------

_DEFAULT_SUBJECTS: dict[str, str] = {
    "invite": "You've been invited to join {org_name} on Amendly",
    "amendment_accepted": "Your amendment was accepted — {doc_title}",
    "amendment_rejected": "Your amendment was rejected — {doc_title}",
    "magic_link": "Your Amendly sign-in link",
    # Prospect outreach sequence — FR
    "prospect_intro": "Gérer les amendements de {org_name} — il y a mieux",
    "prospect_relance_1": "{nom}, comment gérez-vous vos amendements ?",
    "prospect_relance_2": "Ce qu'Amendly change concrètement pour {org_name}",
    "prospect_relance_3": "Je referme le dossier, {nom}",
    # Prospect outreach sequence — EN
    "prospect_intro_en": "Managing {org_name}'s amendments — there's a better way",
    "prospect_relance_1_en": "{nom}, how are you currently handling amendments?",
    "prospect_relance_2_en": "What Amendly changes concretely for {org_name}",
    "prospect_relance_3_en": "Closing the file, {nom}",
}

_DEFAULT_BODIES: dict[str, str] = {
    "invite": """\
<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <title>Invitation to join {org_name}</title>
</head>
<body style="margin:0;padding:0;background-color:#f7f9fb;font-family:Arial,sans-serif;
             -webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;">
  <!-- Preheader -->
  <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;color:#f7f9fb;">
    You have been invited to join {org_name} on Amendly.
    &zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;
  </div>
  <!-- Outer wrapper -->
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background-color:#f7f9fb;padding:48px 16px 64px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="max-width:560px;background-color:#ffffff;border-radius:8px;
                      box-shadow:0 4px 24px rgba(42,52,57,0.08),0 1px 4px rgba(42,52,57,0.04);">
          <!-- Header strip -->
          <tr>
            <td style="background-color:#515f74;padding:32px 40px 28px;border-radius:8px 8px 0 0;">
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background-color:rgba(255,255,255,0.15);border-radius:6px;
                             width:36px;height:36px;text-align:center;vertical-align:middle;
                             font-family:Arial,sans-serif;font-size:18px;font-weight:700;
                             color:#ffffff;line-height:36px;padding:0 10px;
                             mso-line-height-rule:exactly;">A</td>
                  <td style="padding-left:10px;vertical-align:middle;">
                    <span style="font-family:Arial,sans-serif;font-size:15px;font-weight:700;
                                 color:#ffffff;letter-spacing:0.02em;">AMENDLY</span>
                  </td>
                </tr>
              </table>
              <h1 style="margin:20px 0 0;font-family:Arial,sans-serif;font-size:24px;
                         font-weight:700;color:#ffffff;line-height:1.25;letter-spacing:-0.01em;">
                You&rsquo;ve been invited
              </h1>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:36px 40px 32px;">
              <p style="margin:0 0 28px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.7;">
                Great news! You have been invited to collaborate on
                <strong style="color:#515f74;">{org_name}</strong>
                — the organisation is using Amendly to manage its amendment process
                collaboratively.
              </p>
              <!-- Org card -->
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                     style="margin-bottom:32px;">
                <tr>
                  <td style="background-color:#f0f4f7;border-radius:6px;padding:18px 20px;">
                    <p style="margin:0;font-family:Arial,sans-serif;font-size:11px;
                               font-weight:700;letter-spacing:0.1em;text-transform:uppercase;
                               color:#717c82;">Organisation</p>
                    <p style="margin:6px 0 0;font-family:Arial,sans-serif;font-size:17px;
                               font-weight:700;color:#2a3439;">{org_name}</p>
                  </td>
                </tr>
              </table>
              <!-- CTA -->
              <!--[if mso]>
              <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml"
                           xmlns:w="urn:schemas-microsoft-com:office:word"
                           href="{invite_url}"
                           style="height:46px;v-text-anchor:middle;width:220px;"
                           arcsize="13%" strokecolor="#0053dc" fillcolor="#0053dc">
                <w:anchorlock/>
                <center style="color:#ffffff;font-family:Arial,sans-serif;
                               font-size:14px;font-weight:700;">
                  Accept invitation
                </center>
              </v:roundrect>
              <![endif]-->
              <!--[if !mso]><!-->
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="border-radius:6px;background-color:#0053dc;">
                    <a href="{invite_url}"
                       style="display:inline-block;padding:14px 32px;font-family:Arial,sans-serif;
                              font-size:14px;font-weight:700;color:#ffffff;
                              text-decoration:none;border-radius:6px;letter-spacing:0.01em;">
                      Accept invitation &#8594;
                    </a>
                  </td>
                </tr>
              </table>
              <!--<![endif]-->
            </td>
          </tr>
          <!-- Divider -->
          <tr>
            <td style="padding:0 40px;">
              <div style="height:1px;background-color:#d9e4ea;"></div>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background-color:#f0f4f7;padding:20px 40px 24px;
                       border-radius:0 0 8px 8px;">
              <p style="margin:0;font-family:Arial,sans-serif;font-size:12px;
                        color:#717c82;line-height:1.6;">
                This invitation expires in 72 hours. If you did not expect this invitation,
                you can safely ignore this email.
              </p>
            </td>
          </tr>
        </table>
        <p style="margin:20px 0 0;font-family:Arial,sans-serif;font-size:12px;
                  color:#717c82;letter-spacing:0.05em;">amendly.eu</p>
      </td>
    </tr>
  </table>
</body>
</html>""",

    "amendment_accepted": """\
<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <title>Your amendment was accepted</title>
</head>
<body style="margin:0;padding:0;background-color:#f7f9fb;font-family:Arial,sans-serif;
             -webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;">
  <!-- Preheader -->
  <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;color:#f7f9fb;">
    Good news — your amendment on {doc_title} has been accepted.
    &zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;
  </div>
  <!-- Outer wrapper -->
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background-color:#f7f9fb;padding:48px 16px 64px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="max-width:560px;background-color:#ffffff;border-radius:8px;
                      box-shadow:0 4px 24px rgba(42,52,57,0.08),0 1px 4px rgba(42,52,57,0.04);">
          <!-- Header strip -->
          <tr>
            <td style="background-color:#515f74;padding:32px 40px 28px;border-radius:8px 8px 0 0;">
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background-color:rgba(255,255,255,0.15);border-radius:6px;
                             width:36px;height:36px;text-align:center;vertical-align:middle;
                             font-family:Arial,sans-serif;font-size:18px;font-weight:700;
                             color:#ffffff;line-height:36px;padding:0 10px;
                             mso-line-height-rule:exactly;">A</td>
                  <td style="padding-left:10px;vertical-align:middle;">
                    <span style="font-family:Arial,sans-serif;font-size:15px;font-weight:700;
                                 color:#ffffff;letter-spacing:0.02em;">AMENDLY</span>
                  </td>
                </tr>
              </table>
              <h1 style="margin:20px 0 0;font-family:Arial,sans-serif;font-size:24px;
                         font-weight:700;color:#ffffff;line-height:1.25;letter-spacing:-0.01em;">
                Amendment accepted ✓
              </h1>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:36px 40px 32px;">
              <p style="margin:0 0 28px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.7;">
                Great news — your amendment has been <strong>accepted</strong> and will be
                incorporated into the final consolidated document.
              </p>
              <!-- Detail card -->
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                     style="margin-bottom:32px;">
                <tr>
                  <td style="background-color:#f0f4f7;border-radius:6px;padding:20px;">
                    <table role="presentation" cellpadding="0" cellspacing="0" width="100%">
                      <tr>
                        <td style="padding:0 0 14px;">
                          <span style="font-family:Arial,sans-serif;font-size:11px;font-weight:700;
                                       letter-spacing:0.1em;text-transform:uppercase;color:#717c82;">
                            Organisation</span><br/>
                          <span style="font-family:Arial,sans-serif;font-size:15px;font-weight:700;
                                       color:#2a3439;">{org_name}</span>
                        </td>
                      </tr>
                      <tr>
                        <td style="padding:0 0 14px;border-top:1px solid #d9e4ea;padding-top:14px;">
                          <span style="font-family:Arial,sans-serif;font-size:11px;font-weight:700;
                                       letter-spacing:0.1em;text-transform:uppercase;color:#717c82;">
                            Document</span><br/>
                          <span style="font-family:Arial,sans-serif;font-size:15px;
                                       color:#2a3439;">{doc_title}</span>
                        </td>
                      </tr>
                      {section_row}
                      <tr>
                        <td style="border-top:1px solid #d9e4ea;padding-top:14px;">
                          <span style="font-family:Arial,sans-serif;font-size:11px;font-weight:700;
                                       letter-spacing:0.1em;text-transform:uppercase;color:#717c82;">
                            Status</span><br/>
                          <span style="display:inline-block;margin-top:6px;padding:4px 14px;
                                       border-radius:20px;font-family:Arial,sans-serif;
                                       font-size:13px;font-weight:700;
                                       background-color:#d1fae5;color:#0d6e25;
                                       letter-spacing:0.04em;text-transform:uppercase;">
                            &#10003; Accepted
                          </span>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
              <!-- CTA -->
              <!--[if mso]>
              <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml"
                           xmlns:w="urn:schemas-microsoft-com:office:word"
                           href="{doc_url}"
                           style="height:46px;v-text-anchor:middle;width:200px;"
                           arcsize="13%" strokecolor="#0053dc" fillcolor="#0053dc">
                <w:anchorlock/>
                <center style="color:#ffffff;font-family:Arial,sans-serif;
                               font-size:14px;font-weight:700;">View document</center>
              </v:roundrect>
              <![endif]-->
              <!--[if !mso]><!-->
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="border-radius:6px;background-color:#0053dc;">
                    <a href="{doc_url}"
                       style="display:inline-block;padding:14px 32px;font-family:Arial,sans-serif;
                              font-size:14px;font-weight:700;color:#ffffff;
                              text-decoration:none;border-radius:6px;letter-spacing:0.01em;">
                      View document &#8594;
                    </a>
                  </td>
                </tr>
              </table>
              <!--<![endif]-->
            </td>
          </tr>
          <!-- Divider -->
          <tr>
            <td style="padding:0 40px;">
              <div style="height:1px;background-color:#d9e4ea;"></div>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background-color:#f0f4f7;padding:20px 40px 24px;
                       border-radius:0 0 8px 8px;">
              <p style="margin:0;font-family:Arial,sans-serif;font-size:12px;
                        color:#717c82;line-height:1.6;">
                You are receiving this email because you submitted an amendment on Amendly.
              </p>
            </td>
          </tr>
        </table>
        <p style="margin:20px 0 0;font-family:Arial,sans-serif;font-size:12px;
                  color:#717c82;letter-spacing:0.05em;">amendly.eu</p>
      </td>
    </tr>
  </table>
</body>
</html>""",

    "amendment_rejected": """\
<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <title>Your amendment was not accepted</title>
</head>
<body style="margin:0;padding:0;background-color:#f7f9fb;font-family:Arial,sans-serif;
             -webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;">
  <!-- Preheader -->
  <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;color:#f7f9fb;">
    An update on your amendment for {doc_title}.
    &zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;
  </div>
  <!-- Outer wrapper -->
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background-color:#f7f9fb;padding:48px 16px 64px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="max-width:560px;background-color:#ffffff;border-radius:8px;
                      box-shadow:0 4px 24px rgba(42,52,57,0.08),0 1px 4px rgba(42,52,57,0.04);">
          <!-- Header strip -->
          <tr>
            <td style="background-color:#515f74;padding:32px 40px 28px;border-radius:8px 8px 0 0;">
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background-color:rgba(255,255,255,0.15);border-radius:6px;
                             width:36px;height:36px;text-align:center;vertical-align:middle;
                             font-family:Arial,sans-serif;font-size:18px;font-weight:700;
                             color:#ffffff;line-height:36px;padding:0 10px;
                             mso-line-height-rule:exactly;">A</td>
                  <td style="padding-left:10px;vertical-align:middle;">
                    <span style="font-family:Arial,sans-serif;font-size:15px;font-weight:700;
                                 color:#ffffff;letter-spacing:0.02em;">AMENDLY</span>
                  </td>
                </tr>
              </table>
              <h1 style="margin:20px 0 0;font-family:Arial,sans-serif;font-size:24px;
                         font-weight:700;color:#ffffff;line-height:1.25;letter-spacing:-0.01em;">
                Amendment not accepted
              </h1>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:36px 40px 32px;">
              <p style="margin:0 0 28px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.7;">
                Thank you for your contribution. After review, your amendment has
                <strong>not been accepted</strong> for this document. You can view the
                document to see the final consolidated version.
              </p>
              <!-- Detail card -->
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                     style="margin-bottom:32px;">
                <tr>
                  <td style="background-color:#f0f4f7;border-radius:6px;padding:20px;">
                    <table role="presentation" cellpadding="0" cellspacing="0" width="100%">
                      <tr>
                        <td style="padding:0 0 14px;">
                          <span style="font-family:Arial,sans-serif;font-size:11px;font-weight:700;
                                       letter-spacing:0.1em;text-transform:uppercase;color:#717c82;">
                            Organisation</span><br/>
                          <span style="font-family:Arial,sans-serif;font-size:15px;font-weight:700;
                                       color:#2a3439;">{org_name}</span>
                        </td>
                      </tr>
                      <tr>
                        <td style="padding:0 0 14px;border-top:1px solid #d9e4ea;padding-top:14px;">
                          <span style="font-family:Arial,sans-serif;font-size:11px;font-weight:700;
                                       letter-spacing:0.1em;text-transform:uppercase;color:#717c82;">
                            Document</span><br/>
                          <span style="font-family:Arial,sans-serif;font-size:15px;
                                       color:#2a3439;">{doc_title}</span>
                        </td>
                      </tr>
                      {section_row}
                      <tr>
                        <td style="border-top:1px solid #d9e4ea;padding-top:14px;">
                          <span style="font-family:Arial,sans-serif;font-size:11px;font-weight:700;
                                       letter-spacing:0.1em;text-transform:uppercase;color:#717c82;">
                            Status</span><br/>
                          <span style="display:inline-block;margin-top:6px;padding:4px 14px;
                                       border-radius:20px;font-family:Arial,sans-serif;
                                       font-size:13px;font-weight:700;
                                       background-color:#fee2e2;color:#b91c1c;
                                       letter-spacing:0.04em;text-transform:uppercase;">
                            Not accepted
                          </span>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
              <!-- CTA -->
              <!--[if mso]>
              <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml"
                           xmlns:w="urn:schemas-microsoft-com:office:word"
                           href="{doc_url}"
                           style="height:46px;v-text-anchor:middle;width:200px;"
                           arcsize="13%" strokecolor="#515f74" fillcolor="#515f74">
                <w:anchorlock/>
                <center style="color:#ffffff;font-family:Arial,sans-serif;
                               font-size:14px;font-weight:700;">View document</center>
              </v:roundrect>
              <![endif]-->
              <!--[if !mso]><!-->
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="border-radius:6px;background-color:#515f74;">
                    <a href="{doc_url}"
                       style="display:inline-block;padding:14px 32px;font-family:Arial,sans-serif;
                              font-size:14px;font-weight:700;color:#ffffff;
                              text-decoration:none;border-radius:6px;letter-spacing:0.01em;">
                      View document &#8594;
                    </a>
                  </td>
                </tr>
              </table>
              <!--<![endif]-->
            </td>
          </tr>
          <!-- Divider -->
          <tr>
            <td style="padding:0 40px;">
              <div style="height:1px;background-color:#d9e4ea;"></div>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background-color:#f0f4f7;padding:20px 40px 24px;
                       border-radius:0 0 8px 8px;">
              <p style="margin:0;font-family:Arial,sans-serif;font-size:12px;
                        color:#717c82;line-height:1.6;">
                You are receiving this email because you submitted an amendment on Amendly.
              </p>
            </td>
          </tr>
        </table>
        <p style="margin:20px 0 0;font-family:Arial,sans-serif;font-size:12px;
                  color:#717c82;letter-spacing:0.05em;">amendly.eu</p>
      </td>
    </tr>
  </table>
</body>
</html>""",

    # ------------------------------------------------------------------
    # Prospect outreach sequence — sent from RESEND_PROSPECT_FROM_EMAIL
    # Placeholders: {nom}, {org_name}
    # ------------------------------------------------------------------
    "prospect_intro": """\
<!DOCTYPE html>
<html lang="fr" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <title>Amendly &#8212; prise de contact</title>
</head>
<body style="margin:0;padding:0;background-color:#f7f9fb;font-family:Arial,sans-serif;
             -webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;">
  <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;color:#f7f9fb;">
    G&eacute;rer les amendements de {org_name} sans chaos de fichiers.
    &zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;
  </div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background-color:#f7f9fb;padding:48px 16px 64px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="max-width:560px;background-color:#ffffff;border-radius:8px;
                      box-shadow:0 4px 24px rgba(42,52,57,0.08),0 1px 4px rgba(42,52,57,0.04);">
          <!-- Header -->
          <tr>
            <td style="background-color:#515f74;padding:24px 40px;border-radius:8px 8px 0 0;">
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background-color:rgba(255,255,255,0.15);border-radius:6px;
                             width:36px;height:36px;text-align:center;vertical-align:middle;
                             font-family:Arial,sans-serif;font-size:18px;font-weight:700;
                             color:#ffffff;line-height:36px;padding:0 10px;
                             mso-line-height-rule:exactly;">A</td>
                  <td style="padding-left:10px;vertical-align:middle;">
                    <span style="font-family:Arial,sans-serif;font-size:15px;font-weight:700;
                                 color:#ffffff;letter-spacing:0.02em;">AMENDLY</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:36px 40px 32px;">
              <p style="margin:0 0 20px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Bonjour {nom},
              </p>
              <p style="margin:0 0 20px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Je me permets de vous contacter car <strong style="color:#515f74;">{org_name}</strong>
                travaille probablement sur des textes collectifs &#8212; statuts, r&eacute;solutions,
                motions &#8212; qui doivent &ecirc;tre amend&eacute;s et vot&eacute;s en assembl&eacute;e.
              </p>
              <p style="margin:0 0 20px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                La plupart des organisations g&egrave;rent &ccedil;a &agrave; coups d&rsquo;emails,
                de fichiers Word qui circulent et de tableaux de suivi. C&rsquo;est chronophage,
                source d&rsquo;erreurs, et difficile &agrave; tra&ccedil;er.
              </p>
              <p style="margin:0 0 24px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                <strong style="color:#515f74;">Amendly</strong> est une plateforme d&eacute;di&eacute;e
                &agrave; ce workflow&nbsp;: chaque contributeur soumet ses amendements directement
                sur le texte, les responsables les acceptent ou les rejettent, et le document final
                consolid&eacute; est export&eacute; en un clic.
              </p>
              <!-- Benefit list -->
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                     style="margin-bottom:28px;">
                <tr>
                  <td style="background-color:#f0f4f7;border-radius:6px;padding:18px 20px;
                             border-left:3px solid #515f74;">
                    <p style="margin:0 0 8px;font-family:Arial,sans-serif;font-size:14px;
                               color:#2a3439;line-height:1.7;">
                      &#10003;&nbsp; Fini les allers-retours par email
                    </p>
                    <p style="margin:0 0 8px;font-family:Arial,sans-serif;font-size:14px;
                               color:#2a3439;line-height:1.7;">
                      &#10003;&nbsp; Un statut clair pour chaque amendement
                    </p>
                    <p style="margin:0;font-family:Arial,sans-serif;font-size:14px;
                               color:#2a3439;line-height:1.7;">
                      &#10003;&nbsp; Export Word ou PDF du texte final en un clic
                    </p>
                  </td>
                </tr>
              </table>
              <p style="margin:0 0 28px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Si c&rsquo;est un sujet qui vous parle, je serais heureux d&rsquo;en discuter
                15 minutes &agrave; votre convenance. R&eacute;pondez simplement &agrave; cet email.
              </p>
              <p style="margin:0;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Bien &agrave; vous,<br/>
                  <strong>{sender_name}</strong><br/>
                <span style="color:#717c82;font-size:13px;">Fondateur &#8212; Amendly</span>
              </p>
            </td>
          </tr>
          <!-- Divider -->
          <tr>
            <td style="padding:0 40px;">
              <div style="height:1px;background-color:#d9e4ea;"></div>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background-color:#f0f4f7;padding:20px 40px 24px;border-radius:0 0 8px 8px;">
              <p style="margin:0;font-family:Arial,sans-serif;font-size:12px;
                        color:#717c82;line-height:1.6;">
                Amendly &#8212; gestion collaborative des amendements &bull;
                <a href="https://amendly.eu" style="color:#515f74;text-decoration:none;">amendly.eu</a>
              </p>
            </td>
          </tr>
        </table>
        <p style="margin:20px 0 0;font-family:Arial,sans-serif;font-size:12px;
                  color:#717c82;letter-spacing:0.05em;">amendly.eu</p>
      </td>
    </tr>
  </table>
</body>
</html>""",

    "prospect_relance_1": """\
<!DOCTYPE html>
<html lang="fr" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <title>Amendly &#8212; relance</title>
</head>
<body style="margin:0;padding:0;background-color:#f7f9fb;font-family:Arial,sans-serif;
             -webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;">
  <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;color:#f7f9fb;">
    Comment {org_name} g&egrave;re-t-elle ses amendements avant une assembl&eacute;e ?
    &zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;
  </div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background-color:#f7f9fb;padding:48px 16px 64px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="max-width:560px;background-color:#ffffff;border-radius:8px;
                      box-shadow:0 4px 24px rgba(42,52,57,0.08),0 1px 4px rgba(42,52,57,0.04);">
          <!-- Header -->
          <tr>
            <td style="background-color:#515f74;padding:24px 40px;border-radius:8px 8px 0 0;">
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background-color:rgba(255,255,255,0.15);border-radius:6px;
                             width:36px;height:36px;text-align:center;vertical-align:middle;
                             font-family:Arial,sans-serif;font-size:18px;font-weight:700;
                             color:#ffffff;line-height:36px;padding:0 10px;
                             mso-line-height-rule:exactly;">A</td>
                  <td style="padding-left:10px;vertical-align:middle;">
                    <span style="font-family:Arial,sans-serif;font-size:15px;font-weight:700;
                                 color:#ffffff;letter-spacing:0.02em;">AMENDLY</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:36px 40px 32px;">
              <p style="margin:0 0 20px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Bonjour {nom},
              </p>
              <p style="margin:0 0 20px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Je vous ai &eacute;crit il y a quelques jours au sujet d&rsquo;Amendly.
                Le timing n&rsquo;&eacute;tait peut-&ecirc;tre pas id&eacute;al &mdash;
                je me permets une relance courte.
              </p>
              <p style="margin:0 0 20px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Une question directe&nbsp;: comment <strong style="color:#515f74;">{org_name}</strong>
                g&egrave;re-t-elle aujourd&rsquo;hui le d&eacute;p&ocirc;t et le traitement
                des amendements avant une assembl&eacute;e g&eacute;n&eacute;rale ou un
                congr&egrave;s&nbsp;?
              </p>
              <p style="margin:0 0 20px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                C&rsquo;est souvent le moment o&ugrave; les emails s&rsquo;accumulent,
                les versions de fichiers se multiplient et les responsables perdent
                le fil de ce qui a &eacute;t&eacute; accept&eacute; ou non.
                Amendly r&eacute;sout exactement &ccedil;a.
              </p>
              <p style="margin:0 0 28px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Si vous avez 15 minutes cette semaine, je serais ravi de vous montrer
                comment la plateforme fonctionne. R&eacute;pondez simplement &agrave; cet email.
              </p>
              <p style="margin:0;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Bien &agrave; vous,<br/>
                  <strong>{sender_name}</strong><br/>
                <span style="color:#717c82;font-size:13px;">Fondateur &#8212; Amendly</span>
              </p>
            </td>
          </tr>
          <!-- Divider -->
          <tr>
            <td style="padding:0 40px;">
              <div style="height:1px;background-color:#d9e4ea;"></div>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background-color:#f0f4f7;padding:20px 40px 24px;border-radius:0 0 8px 8px;">
              <p style="margin:0;font-family:Arial,sans-serif;font-size:12px;
                        color:#717c82;line-height:1.6;">
                Amendly &#8212; gestion collaborative des amendements &bull;
                <a href="https://amendly.eu" style="color:#515f74;text-decoration:none;">amendly.eu</a>
              </p>
            </td>
          </tr>
        </table>
        <p style="margin:20px 0 0;font-family:Arial,sans-serif;font-size:12px;
                  color:#717c82;letter-spacing:0.05em;">amendly.eu</p>
      </td>
    </tr>
  </table>
</body>
</html>""",

    "prospect_relance_2": """\
<!DOCTYPE html>
<html lang="fr" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <title>Amendly &#8212; ce que vous gagneriez</title>
</head>
<body style="margin:0;padding:0;background-color:#f7f9fb;font-family:Arial,sans-serif;
             -webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;">
  <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;color:#f7f9fb;">
    Concr&egrave;tement, voici ce qu&rsquo;Amendly change pour {org_name}.
    &zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;
  </div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background-color:#f7f9fb;padding:48px 16px 64px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="max-width:560px;background-color:#ffffff;border-radius:8px;
                      box-shadow:0 4px 24px rgba(42,52,57,0.08),0 1px 4px rgba(42,52,57,0.04);">
          <!-- Header -->
          <tr>
            <td style="background-color:#515f74;padding:24px 40px;border-radius:8px 8px 0 0;">
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background-color:rgba(255,255,255,0.15);border-radius:6px;
                             width:36px;height:36px;text-align:center;vertical-align:middle;
                             font-family:Arial,sans-serif;font-size:18px;font-weight:700;
                             color:#ffffff;line-height:36px;padding:0 10px;
                             mso-line-height-rule:exactly;">A</td>
                  <td style="padding-left:10px;vertical-align:middle;">
                    <span style="font-family:Arial,sans-serif;font-size:15px;font-weight:700;
                                 color:#ffffff;letter-spacing:0.02em;">AMENDLY</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:36px 40px 32px;">
              <p style="margin:0 0 20px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Bonjour {nom},
              </p>
              <p style="margin:0 0 20px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Derni&egrave;re relance de ma part &mdash; promis, je serai bref.
              </p>
              <p style="margin:0 0 16px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Concr&egrave;tement, voici ce qu&rsquo;Amendly apporte &agrave; une organisation
                comme <strong style="color:#515f74;">{org_name}</strong>&nbsp;:
              </p>
              <!-- Benefit list -->
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                     style="margin-bottom:28px;">
                <tr>
                  <td style="background-color:#f0f4f7;border-radius:6px;padding:20px 20px 12px;">
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="padding:0 0 10px;vertical-align:top;width:20px;">
                          <span style="font-family:Arial,sans-serif;font-size:14px;
                                       color:#515f74;font-weight:700;">&#10003;</span>
                        </td>
                        <td style="padding:0 0 10px;">
                          <span style="font-family:Arial,sans-serif;font-size:14px;
                                       color:#2a3439;line-height:1.6;">
                            <strong>Plus d&rsquo;emails qui s&rsquo;accumulent</strong> &mdash;
                            les amendements sont d&eacute;pos&eacute;s directement sur la plateforme
                          </span>
                        </td>
                      </tr>
                      <tr>
                        <td style="padding:0 0 10px;vertical-align:top;width:20px;">
                          <span style="font-family:Arial,sans-serif;font-size:14px;
                                       color:#515f74;font-weight:700;">&#10003;</span>
                        </td>
                        <td style="padding:0 0 10px;">
                          <span style="font-family:Arial,sans-serif;font-size:14px;
                                       color:#2a3439;line-height:1.6;">
                            <strong>Un statut clair</strong> pour chaque proposition&nbsp;:
                            en attente, accept&eacute;, rejet&eacute;, retir&eacute;
                          </span>
                        </td>
                      </tr>
                      <tr>
                        <td style="padding:0 0 10px;vertical-align:top;width:20px;">
                          <span style="font-family:Arial,sans-serif;font-size:14px;
                                       color:#515f74;font-weight:700;">&#10003;</span>
                        </td>
                        <td style="padding:0 0 10px;">
                          <span style="font-family:Arial,sans-serif;font-size:14px;
                                       color:#2a3439;line-height:1.6;">
                            <strong>Une vue diff</strong> qui montre exactement
                            ce qui change dans le texte
                          </span>
                        </td>
                      </tr>
                      <tr>
                        <td style="padding:0 0 10px;vertical-align:top;width:20px;">
                          <span style="font-family:Arial,sans-serif;font-size:14px;
                                       color:#515f74;font-weight:700;">&#10003;</span>
                        </td>
                        <td style="padding:0 0 10px;">
                          <span style="font-family:Arial,sans-serif;font-size:14px;
                                       color:#2a3439;line-height:1.6;">
                            <strong>Export en un clic</strong> (Word, PDF) avec
                            tous les amendements accept&eacute;s int&eacute;gr&eacute;s
                          </span>
                        </td>
                      </tr>
                      <tr>
                        <td style="padding:0;vertical-align:top;width:20px;">
                          <span style="font-family:Arial,sans-serif;font-size:14px;
                                       color:#515f74;font-weight:700;">&#10003;</span>
                        </td>
                        <td style="padding:0;">
                          <span style="font-family:Arial,sans-serif;font-size:14px;
                                       color:#2a3439;line-height:1.6;">
                            <strong>Un historique complet</strong> pour chaque
                            d&eacute;cision &mdash; tra&ccedil;abilit&eacute; totale
                          </span>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
              <p style="margin:0 0 28px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Si l&rsquo;une de ces probl&eacute;matiques vous concerne,
                je suis disponible pour un appel cette semaine.
                R&eacute;pondez simplement &agrave; cet email.
              </p>
              <p style="margin:0;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Bien &agrave; vous,<br/>
                  <strong>{sender_name}</strong><br/>
                <span style="color:#717c82;font-size:13px;">Fondateur &#8212; Amendly</span>
              </p>
            </td>
          </tr>
          <!-- Divider -->
          <tr>
            <td style="padding:0 40px;">
              <div style="height:1px;background-color:#d9e4ea;"></div>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background-color:#f0f4f7;padding:20px 40px 24px;border-radius:0 0 8px 8px;">
              <p style="margin:0;font-family:Arial,sans-serif;font-size:12px;
                        color:#717c82;line-height:1.6;">
                Amendly &#8212; gestion collaborative des amendements &bull;
                <a href="https://amendly.eu" style="color:#515f74;text-decoration:none;">amendly.eu</a>
              </p>
            </td>
          </tr>
        </table>
        <p style="margin:20px 0 0;font-family:Arial,sans-serif;font-size:12px;
                  color:#717c82;letter-spacing:0.05em;">amendly.eu</p>
      </td>
    </tr>
  </table>
</body>
</html>""",

    "prospect_relance_3": """\
<!DOCTYPE html>
<html lang="fr" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <title>Amendly &#8212; derni&egrave;re relance</title>
</head>
<body style="margin:0;padding:0;background-color:#f7f9fb;font-family:Arial,sans-serif;
             -webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;">
  <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;color:#f7f9fb;">
    Je referme le dossier &mdash; mais la porte reste ouverte.
    &zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;
  </div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background-color:#f7f9fb;padding:48px 16px 64px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="max-width:560px;background-color:#ffffff;border-radius:8px;
                      box-shadow:0 4px 24px rgba(42,52,57,0.08),0 1px 4px rgba(42,52,57,0.04);">
          <!-- Header -->
          <tr>
            <td style="background-color:#515f74;padding:24px 40px;border-radius:8px 8px 0 0;">
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background-color:rgba(255,255,255,0.15);border-radius:6px;
                             width:36px;height:36px;text-align:center;vertical-align:middle;
                             font-family:Arial,sans-serif;font-size:18px;font-weight:700;
                             color:#ffffff;line-height:36px;padding:0 10px;
                             mso-line-height-rule:exactly;">A</td>
                  <td style="padding-left:10px;vertical-align:middle;">
                    <span style="font-family:Arial,sans-serif;font-size:15px;font-weight:700;
                                 color:#ffffff;letter-spacing:0.02em;">AMENDLY</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:36px 40px 32px;">
              <p style="margin:0 0 20px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Bonjour {nom},
              </p>
              <p style="margin:0 0 20px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Je ne veux pas vous importuner davantage.
              </p>
              <p style="margin:0 0 20px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Si la gestion des amendements n&rsquo;est pas une priorit&eacute; pour
                <strong style="color:#515f74;">{org_name}</strong> en ce moment,
                c&rsquo;est tout &agrave; fait compr&eacute;hensible.
                Je referme le dossier de mon c&ocirc;t&eacute;.
              </p>
              <p style="margin:0 0 28px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Si la situation &eacute;volue &mdash; avant une prochaine assembl&eacute;e
                g&eacute;n&eacute;rale, un congr&egrave;s, ou une r&eacute;vision de statuts
                &mdash; n&rsquo;h&eacute;sitez pas &agrave; revenir vers moi.
              </p>
              <p style="margin:0;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Bonne continuation,<br/>
                  <strong>{sender_name}</strong><br/>
                <span style="color:#717c82;font-size:13px;">Fondateur &#8212; Amendly</span>
              </p>
            </td>
          </tr>
          <!-- Divider -->
          <tr>
            <td style="padding:0 40px;">
              <div style="height:1px;background-color:#d9e4ea;"></div>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background-color:#f0f4f7;padding:20px 40px 24px;border-radius:0 0 8px 8px;">
              <p style="margin:0;font-family:Arial,sans-serif;font-size:12px;
                        color:#717c82;line-height:1.6;">
                Amendly &#8212; gestion collaborative des amendements &bull;
                <a href="https://amendly.eu" style="color:#515f74;text-decoration:none;">amendly.eu</a>
              </p>
            </td>
          </tr>
        </table>
        <p style="margin:20px 0 0;font-family:Arial,sans-serif;font-size:12px;
                  color:#717c82;letter-spacing:0.05em;">amendly.eu</p>
      </td>
    </tr>
  </table>
</body>
</html>""",

    "magic_link": """\
<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <title>Your Amendly sign-in link</title>
</head>
<body style="margin:0;padding:0;background-color:#f7f9fb;font-family:Arial,sans-serif;
             -webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;">
  <!-- Preheader -->
  <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;color:#f7f9fb;">
    Your Amendly sign-in link — expires in 15 minutes.
    &zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;
  </div>
  <!-- Outer wrapper -->
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background-color:#f7f9fb;padding:48px 16px 64px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="max-width:560px;background-color:#ffffff;border-radius:8px;
                      box-shadow:0 4px 24px rgba(42,52,57,0.08),0 1px 4px rgba(42,52,57,0.04);">
          <!-- Header strip -->
          <tr>
            <td style="background-color:#515f74;padding:32px 40px 28px;border-radius:8px 8px 0 0;">
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background-color:rgba(255,255,255,0.15);border-radius:6px;
                             width:36px;height:36px;text-align:center;vertical-align:middle;
                             font-family:Arial,sans-serif;font-size:18px;font-weight:700;
                             color:#ffffff;line-height:36px;padding:0 10px;
                             mso-line-height-rule:exactly;">A</td>
                  <td style="padding-left:10px;vertical-align:middle;">
                    <span style="font-family:Arial,sans-serif;font-size:15px;font-weight:700;
                                 color:#ffffff;letter-spacing:0.02em;">AMENDLY</span>
                  </td>
                </tr>
              </table>
              <h1 style="margin:20px 0 0;font-family:Arial,sans-serif;font-size:24px;
                         font-weight:700;color:#ffffff;line-height:1.25;letter-spacing:-0.01em;">
                Sign in to Amendly
              </h1>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:36px 40px 32px;">
              <p style="margin:0 0 8px;font-family:Arial,sans-serif;font-size:11px;
                        font-weight:700;letter-spacing:0.1em;text-transform:uppercase;
                        color:#717c82;">One-time sign-in link</p>
              <p style="margin:0 0 32px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.7;">
                Click the button below to sign in to your Amendly account.
                This link expires in <strong>15 minutes</strong> and can only be used once.
              </p>
              <!-- CTA -->
              <!--[if mso]>
              <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml"
                           xmlns:w="urn:schemas-microsoft-com:office:word"
                           href="{magic_link_url}"
                           style="height:46px;v-text-anchor:middle;width:180px;"
                           arcsize="13%" strokecolor="#0053dc" fillcolor="#0053dc">
                <w:anchorlock/>
                <center style="color:#ffffff;font-family:Arial,sans-serif;
                               font-size:14px;font-weight:700;">Sign in</center>
              </v:roundrect>
              <![endif]-->
              <!--[if !mso]><!-->
              <table role="presentation" cellpadding="0" cellspacing="0"
                     style="margin-bottom:32px;">
                <tr>
                  <td style="border-radius:6px;background-color:#0053dc;">
                    <a href="{magic_link_url}"
                       style="display:inline-block;padding:14px 40px;font-family:Arial,sans-serif;
                              font-size:14px;font-weight:700;color:#ffffff;
                              text-decoration:none;border-radius:6px;letter-spacing:0.01em;">
                      Sign in to Amendly &#8594;
                    </a>
                  </td>
                </tr>
              </table>
              <!--<![endif]-->
              <!-- Fallback link -->
              <p style="margin:0;font-family:Arial,sans-serif;font-size:13px;
                        color:#717c82;line-height:1.6;">
                If the button doesn&rsquo;t work, copy and paste this link into your browser:
              </p>
              <p style="margin:6px 0 0;font-family:Arial,sans-serif;font-size:12px;
                        color:#0053dc;word-break:break-all;">{magic_link_url}</p>
            </td>
          </tr>
          <!-- Divider -->
          <tr>
            <td style="padding:0 40px;">
              <div style="height:1px;background-color:#d9e4ea;"></div>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background-color:#f0f4f7;padding:20px 40px 24px;
                       border-radius:0 0 8px 8px;">
              <p style="margin:0;font-family:Arial,sans-serif;font-size:12px;
                        color:#717c82;line-height:1.6;">
                If you did not request this sign-in link, you can safely ignore this email.
                Your account has not been affected.
              </p>
            </td>
          </tr>
        </table>
        <p style="margin:20px 0 0;font-family:Arial,sans-serif;font-size:12px;
                  color:#717c82;letter-spacing:0.05em;">amendly.eu</p>
      </td>
    </tr>
  </table>
</body>
</html>""",

    # ------------------------------------------------------------------
    # Prospect outreach sequence — EN
    # Placeholders: {nom}, {org_name}
    # ------------------------------------------------------------------
    "prospect_intro_en": """\
<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <title>Amendly &#8212; introduction</title>
</head>
<body style="margin:0;padding:0;background-color:#f7f9fb;font-family:Arial,sans-serif;
             -webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;">
  <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;color:#f7f9fb;">
    Managing {org_name}&rsquo;s amendments without the chaos.
    &zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;
  </div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background-color:#f7f9fb;padding:48px 16px 64px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="max-width:560px;background-color:#ffffff;border-radius:8px;
                      box-shadow:0 4px 24px rgba(42,52,57,0.08),0 1px 4px rgba(42,52,57,0.04);">
          <!-- Header -->
          <tr>
            <td style="background-color:#515f74;padding:24px 40px;border-radius:8px 8px 0 0;">
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background-color:rgba(255,255,255,0.15);border-radius:6px;
                             width:36px;height:36px;text-align:center;vertical-align:middle;
                             font-family:Arial,sans-serif;font-size:18px;font-weight:700;
                             color:#ffffff;line-height:36px;padding:0 10px;
                             mso-line-height-rule:exactly;">A</td>
                  <td style="padding-left:10px;vertical-align:middle;">
                    <span style="font-family:Arial,sans-serif;font-size:15px;font-weight:700;
                                 color:#ffffff;letter-spacing:0.02em;">AMENDLY</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:36px 40px 32px;">
              <p style="margin:0 0 20px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Hello {nom},
              </p>
              <p style="margin:0 0 20px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                I&rsquo;m reaching out because <strong style="color:#515f74;">{org_name}</strong>
                likely works on collective texts &#8212; bylaws, resolutions, motions &#8212;
                that need to be amended and voted on in assembly.
              </p>
              <p style="margin:0 0 20px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Most organisations manage this through email chains, circulating Word files,
                and tracking spreadsheets. It&rsquo;s time-consuming, error-prone, and
                nearly impossible to audit afterwards.
              </p>
              <p style="margin:0 0 24px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                <strong style="color:#515f74;">Amendly</strong> is a platform built for
                exactly this workflow: contributors submit amendments directly on the text,
                administrators accept or reject them, and the final consolidated document
                is exported in one click.
              </p>
              <!-- Benefit list -->
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                     style="margin-bottom:28px;">
                <tr>
                  <td style="background-color:#f0f4f7;border-radius:6px;padding:18px 20px;
                             border-left:3px solid #515f74;">
                    <p style="margin:0 0 8px;font-family:Arial,sans-serif;font-size:14px;
                               color:#2a3439;line-height:1.7;">
                      &#10003;&nbsp; No more back-and-forth emails
                    </p>
                    <p style="margin:0 0 8px;font-family:Arial,sans-serif;font-size:14px;
                               color:#2a3439;line-height:1.7;">
                      &#10003;&nbsp; A clear status for every amendment
                    </p>
                    <p style="margin:0;font-family:Arial,sans-serif;font-size:14px;
                               color:#2a3439;line-height:1.7;">
                      &#10003;&nbsp; One-click Word or PDF export of the final text
                    </p>
                  </td>
                </tr>
              </table>
              <p style="margin:0 0 28px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                If this resonates, I&rsquo;d be happy to chat for 15 minutes at your
                convenience &#8212; just reply to this email.
              </p>
              <p style="margin:0;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Best regards,<br/>
                  <strong>{sender_name}</strong><br/>
                <span style="color:#717c82;font-size:13px;">Founder &#8212; Amendly</span>
              </p>
            </td>
          </tr>
          <!-- Divider -->
          <tr>
            <td style="padding:0 40px;">
              <div style="height:1px;background-color:#d9e4ea;"></div>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background-color:#f0f4f7;padding:20px 40px 24px;border-radius:0 0 8px 8px;">
              <p style="margin:0;font-family:Arial,sans-serif;font-size:12px;
                        color:#717c82;line-height:1.6;">
                Amendly &#8212; collaborative amendment management &bull;
                <a href="https://amendly.eu" style="color:#515f74;text-decoration:none;">amendly.eu</a>
              </p>
            </td>
          </tr>
        </table>
        <p style="margin:20px 0 0;font-family:Arial,sans-serif;font-size:12px;
                  color:#717c82;letter-spacing:0.05em;">amendly.eu</p>
      </td>
    </tr>
  </table>
</body>
</html>""",

    "prospect_relance_1_en": """\
<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <title>Amendly &#8212; follow-up</title>
</head>
<body style="margin:0;padding:0;background-color:#f7f9fb;font-family:Arial,sans-serif;
             -webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;">
  <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;color:#f7f9fb;">
    How does {org_name} currently handle its amendment process?
    &zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;
  </div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background-color:#f7f9fb;padding:48px 16px 64px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="max-width:560px;background-color:#ffffff;border-radius:8px;
                      box-shadow:0 4px 24px rgba(42,52,57,0.08),0 1px 4px rgba(42,52,57,0.04);">
          <!-- Header -->
          <tr>
            <td style="background-color:#515f74;padding:24px 40px;border-radius:8px 8px 0 0;">
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background-color:rgba(255,255,255,0.15);border-radius:6px;
                             width:36px;height:36px;text-align:center;vertical-align:middle;
                             font-family:Arial,sans-serif;font-size:18px;font-weight:700;
                             color:#ffffff;line-height:36px;padding:0 10px;
                             mso-line-height-rule:exactly;">A</td>
                  <td style="padding-left:10px;vertical-align:middle;">
                    <span style="font-family:Arial,sans-serif;font-size:15px;font-weight:700;
                                 color:#ffffff;letter-spacing:0.02em;">AMENDLY</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:36px 40px 32px;">
              <p style="margin:0 0 20px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Hello {nom},
              </p>
              <p style="margin:0 0 20px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                I sent you a note about Amendly last week &#8212; I wanted to follow up
                with a simple question: how does <strong style="color:#515f74;">{org_name}</strong>
                currently manage its amendment process?
              </p>
              <p style="margin:0 0 20px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Whether it&rsquo;s an annual general meeting, a congress, or a working group
                session, the coordination overhead is almost always underestimated &#8212;
                collecting submissions, tracking versions, communicating decisions back to contributors.
              </p>
              <p style="margin:0 0 28px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                If you&rsquo;re still managing it via email and Word documents, I&rsquo;d love
                to show you what a structured workflow looks like in practice.
                It typically saves hours of preparation time.
              </p>
              <p style="margin:0;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Happy to exchange a few words if you&rsquo;re open to it.<br/><br/>
                  <strong>{sender_name}</strong><br/>
                <span style="color:#717c82;font-size:13px;">Founder &#8212; Amendly</span>
              </p>
            </td>
          </tr>
          <!-- Divider -->
          <tr>
            <td style="padding:0 40px;">
              <div style="height:1px;background-color:#d9e4ea;"></div>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background-color:#f0f4f7;padding:20px 40px 24px;border-radius:0 0 8px 8px;">
              <p style="margin:0;font-family:Arial,sans-serif;font-size:12px;
                        color:#717c82;line-height:1.6;">
                Amendly &#8212; collaborative amendment management &bull;
                <a href="https://amendly.eu" style="color:#515f74;text-decoration:none;">amendly.eu</a>
              </p>
            </td>
          </tr>
        </table>
        <p style="margin:20px 0 0;font-family:Arial,sans-serif;font-size:12px;
                  color:#717c82;letter-spacing:0.05em;">amendly.eu</p>
      </td>
    </tr>
  </table>
</body>
</html>""",

    "prospect_relance_2_en": """\
<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <title>Amendly &#8212; what changes concretely</title>
</head>
<body style="margin:0;padding:0;background-color:#f7f9fb;font-family:Arial,sans-serif;
             -webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;">
  <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;color:#f7f9fb;">
    What organisations like {org_name} gain when they switch to Amendly.
    &zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;
  </div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background-color:#f7f9fb;padding:48px 16px 64px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="max-width:560px;background-color:#ffffff;border-radius:8px;
                      box-shadow:0 4px 24px rgba(42,52,57,0.08),0 1px 4px rgba(42,52,57,0.04);">
          <!-- Header -->
          <tr>
            <td style="background-color:#515f74;padding:24px 40px;border-radius:8px 8px 0 0;">
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background-color:rgba(255,255,255,0.15);border-radius:6px;
                             width:36px;height:36px;text-align:center;vertical-align:middle;
                             font-family:Arial,sans-serif;font-size:18px;font-weight:700;
                             color:#ffffff;line-height:36px;padding:0 10px;
                             mso-line-height-rule:exactly;">A</td>
                  <td style="padding-left:10px;vertical-align:middle;">
                    <span style="font-family:Arial,sans-serif;font-size:15px;font-weight:700;
                                 color:#ffffff;letter-spacing:0.02em;">AMENDLY</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:36px 40px 32px;">
              <p style="margin:0 0 20px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Hello {nom},
              </p>
              <p style="margin:0 0 20px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                One last follow-up before I let you get on with your work.
              </p>
              <p style="margin:0 0 20px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Here&rsquo;s what organisations like
                <strong style="color:#515f74;">{org_name}</strong>
                typically gain when they move their amendment process to Amendly:
              </p>
              <!-- Benefit blocks -->
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                     style="margin-bottom:28px;">
                <tr>
                  <td style="background-color:#f0f4f7;border-radius:6px;padding:18px 20px;
                             border-left:3px solid #515f74;">
                    <p style="margin:0 0 12px;font-family:Arial,sans-serif;font-size:14px;
                               color:#2a3439;line-height:1.75;">
                      <strong style="color:#515f74;">&#8594;&nbsp; No more email submissions.</strong><br/>
                      Contributors submit directly on the platform, with their reasoning attached &#8212;
                      no version confusion, no missing attachments.
                    </p>
                    <p style="margin:0 0 12px;font-family:Arial,sans-serif;font-size:14px;
                               color:#2a3439;line-height:1.75;">
                      <strong style="color:#515f74;">&#8594;&nbsp; Everything in one place.</strong><br/>
                      Administrators review, accept, reject, or consolidate amendments
                      with a single click &#8212; no spreadsheet required.
                    </p>
                    <p style="margin:0;font-family:Arial,sans-serif;font-size:14px;
                               color:#2a3439;line-height:1.75;">
                      <strong style="color:#515f74;">&#8594;&nbsp; Instant final document.</strong><br/>
                      The consolidated text is generated automatically &#8212;
                      ready to export as Word or PDF, no manual copy-pasting.
                    </p>
                  </td>
                </tr>
              </table>
              <p style="margin:0 0 28px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                The result: less back-and-forth, fewer errors, and a clean audit trail
                for every decision taken.
              </p>
              <p style="margin:0;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                If this sounds useful, I&rsquo;m available for a short demo this week &#8212;
                just let me know.<br/><br/>
                  <strong>{sender_name}</strong><br/>
                <span style="color:#717c82;font-size:13px;">Founder &#8212; Amendly</span>
              </p>
            </td>
          </tr>
          <!-- Divider -->
          <tr>
            <td style="padding:0 40px;">
              <div style="height:1px;background-color:#d9e4ea;"></div>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background-color:#f0f4f7;padding:20px 40px 24px;border-radius:0 0 8px 8px;">
              <p style="margin:0;font-family:Arial,sans-serif;font-size:12px;
                        color:#717c82;line-height:1.6;">
                Amendly &#8212; collaborative amendment management &bull;
                <a href="https://amendly.eu" style="color:#515f74;text-decoration:none;">amendly.eu</a>
              </p>
            </td>
          </tr>
        </table>
        <p style="margin:20px 0 0;font-family:Arial,sans-serif;font-size:12px;
                  color:#717c82;letter-spacing:0.05em;">amendly.eu</p>
      </td>
    </tr>
  </table>
</body>
</html>""",

    "prospect_relance_3_en": """\
<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <title>Amendly &#8212; closing the file</title>
</head>
<body style="margin:0;padding:0;background-color:#f7f9fb;font-family:Arial,sans-serif;
             -webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;">
  <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;color:#f7f9fb;">
    No pressure &#8212; the door stays open.
    &zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;
  </div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background-color:#f7f9fb;padding:48px 16px 64px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="max-width:560px;background-color:#ffffff;border-radius:8px;
                      box-shadow:0 4px 24px rgba(42,52,57,0.08),0 1px 4px rgba(42,52,57,0.04);">
          <!-- Header -->
          <tr>
            <td style="background-color:#515f74;padding:24px 40px;border-radius:8px 8px 0 0;">
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background-color:rgba(255,255,255,0.15);border-radius:6px;
                             width:36px;height:36px;text-align:center;vertical-align:middle;
                             font-family:Arial,sans-serif;font-size:18px;font-weight:700;
                             color:#ffffff;line-height:36px;padding:0 10px;
                             mso-line-height-rule:exactly;">A</td>
                  <td style="padding-left:10px;vertical-align:middle;">
                    <span style="font-family:Arial,sans-serif;font-size:15px;font-weight:700;
                                 color:#ffffff;letter-spacing:0.02em;">AMENDLY</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:36px 40px 32px;">
              <p style="margin:0 0 20px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                Hello {nom},
              </p>
              <p style="margin:0 0 20px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                I&rsquo;ve tried to reach you a few times about Amendly without success &#8212;
                I&rsquo;ll assume the timing simply isn&rsquo;t right.
              </p>
              <p style="margin:0 0 20px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                I&rsquo;m closing this outreach for now, but if the question of managing
                collective texts comes up again for
                <strong style="color:#515f74;">{org_name}</strong>,
                feel free to reach out at any time &#8212; at
                <a href="mailto:{contact_email}" style="color:#515f74;text-decoration:none;">{contact_email}</a>
                or at
                <a href="https://amendly.eu" style="color:#515f74;text-decoration:none;">amendly.eu</a>.
              </p>
              <p style="margin:0 0 28px;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                I wish you and {org_name} all the best.
              </p>
              <p style="margin:0;font-family:Arial,sans-serif;font-size:15px;
                        color:#2a3439;line-height:1.75;">
                  <strong>{sender_name}</strong><br/>
                <span style="color:#717c82;font-size:13px;">Founder &#8212; Amendly</span>
              </p>
            </td>
          </tr>
          <!-- Divider -->
          <tr>
            <td style="padding:0 40px;">
              <div style="height:1px;background-color:#d9e4ea;"></div>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background-color:#f0f4f7;padding:20px 40px 24px;border-radius:0 0 8px 8px;">
              <p style="margin:0;font-family:Arial,sans-serif;font-size:12px;
                        color:#717c82;line-height:1.6;">
                Amendly &#8212; collaborative amendment management &bull;
                <a href="https://amendly.eu" style="color:#515f74;text-decoration:none;">amendly.eu</a>
              </p>
            </td>
          </tr>
        </table>
        <p style="margin:20px 0 0;font-family:Arial,sans-serif;font-size:12px;
                  color:#717c82;letter-spacing:0.05em;">amendly.eu</p>
      </td>
    </tr>
  </table>
</body>
</html>""",
}

# Human-readable description of placeholders per template key
TEMPLATE_VARIABLES: dict[str, list[str]] = {
    "invite": ["{org_name}", "{invite_url}"],
    "amendment_accepted": ["{org_name}", "{doc_title}", "{section_row}", "{doc_url}"],
    "amendment_rejected": ["{org_name}", "{doc_title}", "{section_row}", "{doc_url}"],
    "magic_link": ["{magic_link_url}"],
    "prospect_intro": ["{nom}", "{org_name}"],
    "prospect_relance_1": ["{nom}", "{org_name}"],
    "prospect_relance_2": ["{nom}", "{org_name}"],
    "prospect_relance_3": ["{nom}", "{org_name}"],
    "prospect_intro_en": ["{nom}", "{org_name}"],
    "prospect_relance_1_en": ["{nom}", "{org_name}"],
    "prospect_relance_2_en": ["{nom}", "{org_name}"],
    "prospect_relance_3_en": ["{nom}", "{org_name}"],
}

ALL_KEYS = list(_DEFAULT_SUBJECTS.keys())


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------


def _row_to_schema(tmpl: EmailTemplate) -> EmailTemplateResponse:
    """Convert an ORM EmailTemplate to its response schema."""
    return EmailTemplateResponse(
        template_key=tmpl.template_key,
        subject=tmpl.subject,
        html_body=tmpl.html_body,
        variables=TEMPLATE_VARIABLES.get(tmpl.template_key, []),
        updated_at=tmpl.updated_at.isoformat(),
        is_customised=True,
    )


def _default_schema(key: str) -> EmailTemplateResponse:
    """Return the default (hardcoded) template as a schema object."""
    return EmailTemplateResponse(
        template_key=key,
        subject=_DEFAULT_SUBJECTS[key],
        html_body=_DEFAULT_BODIES[key],
        variables=TEMPLATE_VARIABLES.get(key, []),
        updated_at=None,
        is_customised=False,
    )


async def list_email_templates(db: AsyncSession) -> list[EmailTemplateResponse]:
    """
    Return all template definitions, merging DB overrides with defaults.

    For each known template key, returns the DB row if one exists, otherwise
    returns the hardcoded default.

    Parameters:
        db: Async SQLAlchemy session.

    Returns:
        List of EmailTemplateResponse, one per template key.
    """
    result = await db.execute(select(EmailTemplate))
    rows = {row.template_key: row for row in result.scalars().all()}

    return [
        _row_to_schema(rows[key]) if key in rows else _default_schema(key)
        for key in ALL_KEYS
    ]


async def get_email_template(
    db: AsyncSession, key: str
) -> EmailTemplateResponse | None:
    """
    Return the template for the given key (DB override or default).

    Parameters:
        db: Async SQLAlchemy session.
        key: Template key (e.g. 'invite').

    Returns:
        EmailTemplateResponse, or None if the key is unknown.
    """
    if key not in ALL_KEYS:
        return None
    result = await db.execute(
        select(EmailTemplate).where(EmailTemplate.template_key == key)
    )
    row = result.scalar_one_or_none()
    return _row_to_schema(row) if row else _default_schema(key)


async def upsert_email_template(
    db: AsyncSession, key: str, subject: str, html_body: str
) -> EmailTemplateResponse:
    """
    Create or update the DB template for the given key.

    Parameters:
        db: Async SQLAlchemy session.
        key: Template key — must be one of ALL_KEYS.
        subject: New subject line (may contain {placeholders}).
        html_body: New HTML body (may contain {placeholders}).

    Returns:
        Updated EmailTemplateResponse.

    Raises:
        ValueError: If the key is not a known template key.
    """
    if key not in ALL_KEYS:
        raise ValueError(f"Unknown template key: {key!r}")

    result = await db.execute(
        select(EmailTemplate).where(EmailTemplate.template_key == key)
    )
    row = result.scalar_one_or_none()

    if row is None:
        row = EmailTemplate(template_key=key, subject=subject, html_body=html_body)
        db.add(row)
    else:
        row.subject = subject
        row.html_body = html_body

    await db.commit()
    await db.refresh(row)
    return _row_to_schema(row)


async def reset_email_template(db: AsyncSession, key: str) -> EmailTemplateResponse:
    """
    Delete any DB override for the given key, reverting to the hardcoded default.

    Parameters:
        db: Async SQLAlchemy session.
        key: Template key to reset.

    Returns:
        The default EmailTemplateResponse.

    Raises:
        ValueError: If the key is not a known template key.
    """
    if key not in ALL_KEYS:
        raise ValueError(f"Unknown template key: {key!r}")

    result = await db.execute(
        select(EmailTemplate).where(EmailTemplate.template_key == key)
    )
    row = result.scalar_one_or_none()
    if row is not None:
        await db.delete(row)
        await db.commit()
    return _default_schema(key)


async def render_template(
    db: AsyncSession, key: str, variables: dict[str, str]
) -> tuple[str, str]:
    """
    Render a template by substituting {variable} placeholders.

    Parameters:
        db: Async SQLAlchemy session.
        key: Template key (e.g. 'invite').
        variables: Dict mapping placeholder names to their values.

    Returns:
        Tuple of (rendered_subject, rendered_html_body).
        Returns the hardcoded default if no DB template exists.
    """
    tmpl = await get_email_template(db, key)
    if tmpl is None:
        logger.warning("Unknown template key %r — returning empty strings", key)
        return ("", "")

    try:
        rendered_subject = tmpl.subject.format_map(variables)
        rendered_body = tmpl.html_body.format_map(variables)
    except KeyError as exc:
        logger.warning(
            "Missing placeholder %s in template %r — falling back to raw template",
            exc,
            key,
        )
        rendered_subject = tmpl.subject
        rendered_body = tmpl.html_body

    return rendered_subject, rendered_body
