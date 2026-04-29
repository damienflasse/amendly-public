"""
Email service — transactional emails sent by Amendly (welcome, notifications, etc.).

All emails use table-based layouts with fully inlined CSS for maximum compatibility
across email clients (Gmail, Outlook 2016+, Apple Mail, iOS Mail).

Functions:
    send_welcome_email          — sent once when a new account is created.
    send_amendment_status_email — sent when an amendment is accepted or rejected.
"""

import logging

import resend

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Design tokens (mirrored from frontend/DESIGN.md — "The Editorial Ledger")
# ---------------------------------------------------------------------------

_C = {
    "primary":    "#515f74",   # Deep Slate — header, accents
    "secondary":  "#0053dc",   # Professional Blue — links, CTA
    "surface":    "#f7f9fb",   # Email background
    "card":       "#ffffff",   # Card background
    "low":        "#f0f4f7",   # Footer / muted areas
    "highest":    "#d9e4ea",   # Dividers, step circles
    "on_surface": "#2a3439",   # Body text
    "outline":    "#717c82",   # Secondary / muted text
    "white":      "#ffffff",
}

# ---------------------------------------------------------------------------
# Welcome email copy — one dict per supported language
# ---------------------------------------------------------------------------

_WELCOME_COPY: dict[str, dict[str, str]] = {
    "en": {
        "subject":    "Welcome to Amendly",
        "preheader":  "Your account is ready. Start managing amendments collaboratively.",
        "greeting":   "Welcome{name_part},",
        "body": (
            "Your Amendly account is active. You now have a structured workspace "
            "to manage the full amendment cycle — from the original text to the "
            "final consolidated version."
        ),
        "step1_title": "Upload a document",
        "step1_desc":  "Import your Word or plain-text document in seconds.",
        "step2_title": "Invite your team",
        "step2_desc":  "Add members to your organisation and assign roles.",
        "step3_title": "Collect &amp; consolidate",
        "step3_desc":  "Contributors submit proposals; you review, accept, and export.",
        "cta":         "Open Amendly",
        "footer": (
            "You received this email because you created an account on Amendly. "
            "If this wasn&#39;t you, you can safely ignore this message."
        ),
    },
    "fr": {
        "subject":    "Bienvenue sur Amendly",
        "preheader":  "Votre compte est prêt. Gérez vos amendements en mode collaboratif.",
        "greeting":   "Bienvenue{name_part},",
        "body": (
            "Votre compte Amendly est actif. Vous disposez désormais d&#39;un espace "
            "structuré pour piloter l&#39;intégralité du cycle des amendements — du texte "
            "initial à la version finale consolidée."
        ),
        "step1_title": "Importez un document",
        "step1_desc":  "Chargez votre fichier Word ou texte brut en quelques secondes.",
        "step2_title": "Invitez votre équipe",
        "step2_desc":  "Ajoutez des membres et attribuez des rôles.",
        "step3_title": "Collectez &amp; consolidez",
        "step3_desc":  "Les contributeurs soumettent leurs propositions&#160;; vous validez et exportez.",
        "cta":         "Ouvrir Amendly",
        "footer": (
            "Vous recevez cet e-mail parce que vous avez créé un compte sur Amendly. "
            "Si ce n&#39;est pas vous, vous pouvez ignorer ce message en toute sécurité."
        ),
    },
    "de": {
        "subject":    "Willkommen bei Amendly",
        "preheader":  "Ihr Konto ist bereit. Verwalten Sie Ihre Änderungsanträge kollaborativ.",
        "greeting":   "Willkommen{name_part},",
        "body": (
            "Ihr Amendly-Konto ist aktiv. Sie verfügen jetzt über einen strukturierten "
            "Arbeitsbereich für den gesamten Änderungsantragsprozess — vom Originaltext "
            "bis zur finalen konsolidierten Version."
        ),
        "step1_title": "Dokument hochladen",
        "step1_desc":  "Laden Sie Ihre Word- oder Textdatei in Sekunden hoch.",
        "step2_title": "Team einladen",
        "step2_desc":  "Fügen Sie Mitglieder hinzu und weisen Sie Rollen zu.",
        "step3_title": "Sammeln &amp; konsolidieren",
        "step3_desc":  "Mitwirkende reichen Vorschläge ein; Sie prüfen, akzeptieren und exportieren.",
        "cta":         "Amendly öffnen",
        "footer": (
            "Sie erhalten diese E-Mail, weil Sie ein Konto bei Amendly erstellt haben. "
            "Wenn Sie das nicht waren, können Sie diese Nachricht ignorieren."
        ),
    },
    "es": {
        "subject":    "Bienvenido a Amendly",
        "preheader":  "Tu cuenta está lista. Gestiona tus enmiendas de forma colaborativa.",
        "greeting":   "Bienvenido{name_part},",
        "body": (
            "Tu cuenta de Amendly está activa. Ahora tienes un espacio estructurado "
            "para gestionar el ciclo completo de enmiendas — desde el texto original "
            "hasta la versión final consolidada."
        ),
        "step1_title": "Sube un documento",
        "step1_desc":  "Importa tu archivo Word o de texto plano en segundos.",
        "step2_title": "Invita a tu equipo",
        "step2_desc":  "Añade miembros a tu organización y asigna roles.",
        "step3_title": "Recoge &amp; consolida",
        "step3_desc":  "Los colaboradores envían propuestas; tú las revisas, aceptas y exportas.",
        "cta":         "Abrir Amendly",
        "footer": (
            "Recibes este correo porque creaste una cuenta en Amendly. "
            "Si no fuiste tú, puedes ignorar este mensaje con total seguridad."
        ),
    },
}

_SUPPORTED_LANGS = frozenset(_WELCOME_COPY.keys())


def _resolve_lang(lang: str) -> str:
    """
    Normalise a BCP-47 language tag to one of the four supported codes.

    Parameters:
        lang: Raw language string, e.g. "fr-FR", "de", "zh-CN".

    Returns:
        One of "en", "fr", "de", "es" — defaults to "en" if no match.
    """
    code = lang.lower()[:2]
    return code if code in _SUPPORTED_LANGS else "en"


def _step_row(number: str, title: str, desc: str) -> str:
    """
    Render a single numbered step row for the welcome email.

    Parameters:
        number: Step number as a string ("1", "2", "3").
        title: Bold step title.
        desc: Supporting description.

    Returns:
        HTML string for one step row.
    """
    return f"""
    <tr>
      <td style="padding:0 0 20px 0;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td width="36" valign="top" style="padding-top:1px;">
              <div style="
                width:26px; height:26px; border-radius:50%;
                background-color:{_C['primary']}; text-align:center;
                line-height:26px; font-size:12px; font-weight:700;
                color:{_C['white']}; font-family:Arial,sans-serif;
              ">{number}</div>
            </td>
            <td valign="top" style="padding-left:10px;">
              <p style="margin:0 0 3px; font-family:Arial,sans-serif;
                        font-size:14px; font-weight:700; color:{_C['on_surface']};">
                {title}
              </p>
              <p style="margin:0; font-family:Arial,sans-serif;
                        font-size:13px; color:{_C['outline']}; line-height:1.55;">
                {desc}
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>"""


def _build_welcome_html(app_url: str, c: dict[str, str], name: str | None) -> str:
    """
    Build the branded HTML welcome email.

    Design: "The Editorial Ledger" — deep slate header, clean card, numbered steps.

    Parameters:
        app_url: Root URL of the app (e.g. "https://amendly.eu").
        c: Copy dict for the target language.
        name: User display name for personalised greeting (may be None).

    Returns:
        A complete HTML string with all styles inlined.
    """
    name_part = f" {name}" if name else ""
    greeting = c["greeting"].replace("{name_part}", name_part)

    steps = (
        _step_row("1", c["step1_title"], c["step1_desc"])
        + _step_row("2", c["step2_title"], c["step2_desc"])
        + _step_row("3", c["step3_title"], c["step3_desc"])
    )

    return f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <title>{c['subject']}</title>
</head>
<body style="margin:0; padding:0; background-color:{_C['surface']};
             font-family:Arial,sans-serif; -webkit-text-size-adjust:100%; -ms-text-size-adjust:100%;">

  <!--[if mso]><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml><![endif]-->

  <!-- Preheader — hidden preview text -->
  <div style="display:none; max-height:0; overflow:hidden; mso-hide:all; font-size:1px; color:{_C['surface']};">
    {c['preheader']}
    &zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;
  </div>

  <!-- Outer wrapper -->
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background-color:{_C['surface']}; padding:48px 16px 64px;">
    <tr>
      <td align="center">

        <!-- ============================================================
             Card — max-width 560px
        ============================================================ -->
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="max-width:560px; background-color:{_C['card']};
                      border-radius:8px;
                      box-shadow:0 4px 24px rgba(42,52,57,0.08),
                                 0 1px 4px rgba(42,52,57,0.04);">

          <!-- ── Header strip ── -->
          <tr>
            <td style="background-color:{_C['primary']}; padding:32px 40px 28px;
                       border-radius:8px 8px 0 0;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td>
                    <!-- Wordmark -->
                    <table role="presentation" cellpadding="0" cellspacing="0">
                      <tr>
                        <!-- "A" lettermark box -->
                        <td style="
                          background-color:rgba(255,255,255,0.15);
                          border-radius:6px;
                          width:36px; height:36px;
                          text-align:center; vertical-align:middle;
                          font-family:Arial,sans-serif;
                          font-size:18px; font-weight:700;
                          color:{_C['white']};
                          line-height:36px;
                          padding:0 10px;
                          mso-line-height-rule:exactly;
                        ">A</td>
                        <td style="padding-left:10px; vertical-align:middle;">
                          <span style="
                            font-family:Arial,sans-serif;
                            font-size:15px; font-weight:700;
                            color:{_C['white']};
                            letter-spacing:0.02em;
                          ">AMENDLY</span>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <tr>
                  <td style="padding-top:20px;">
                    <h1 style="
                      margin:0;
                      font-family:Arial,sans-serif;
                      font-size:26px; font-weight:700;
                      color:{_C['white']}; line-height:1.25;
                      letter-spacing:-0.01em;
                    ">{greeting}</h1>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- ── Body ── -->
          <tr>
            <td style="padding:36px 40px 0;">

              <!-- Intro paragraph -->
              <p style="
                margin:0 0 32px;
                font-family:Arial,sans-serif;
                font-size:15px; line-height:1.7;
                color:{_C['on_surface']};
              ">{c['body']}</p>

              <!-- Section label -->
              <p style="
                margin:0 0 16px;
                font-family:Arial,sans-serif;
                font-size:11px; font-weight:700;
                color:{_C['outline']};
                letter-spacing:0.1em;
                text-transform:uppercase;
              ">Getting started</p>

              <!-- Steps -->
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                     style="margin-bottom:32px;">
                <tbody>
                  {steps}
                </tbody>
              </table>

            </td>
          </tr>

          <!-- ── CTA button ── -->
          <tr>
            <td style="padding:0 40px 36px;">
              <!--[if mso]>
              <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml"
                           xmlns:w="urn:schemas-microsoft-com:office:word"
                           href="{app_url}"
                           style="height:46px;v-text-anchor:middle;width:220px;"
                           arcsize="13%" strokecolor="{_C['secondary']}"
                           fillcolor="{_C['secondary']}">
                <w:anchorlock/>
                <center style="color:{_C['white']};font-family:Arial,sans-serif;
                               font-size:14px;font-weight:700;">
                  {c['cta']}
                </center>
              </v:roundrect>
              <![endif]-->
              <!--[if !mso]><!-->
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="border-radius:6px; background-color:{_C['secondary']};">
                    <a href="{app_url}"
                       style="
                         display:inline-block;
                         padding:14px 32px;
                         font-family:Arial,sans-serif;
                         font-size:14px; font-weight:700;
                         color:{_C['white']};
                         text-decoration:none;
                         border-radius:6px;
                         letter-spacing:0.01em;
                       ">{c['cta']} &#8594;</a>
                  </td>
                </tr>
              </table>
              <!--<![endif]-->
            </td>
          </tr>

          <!-- ── Divider ── -->
          <tr>
            <td style="padding:0 40px;">
              <div style="height:1px; background-color:{_C['highest']};"></div>
            </td>
          </tr>

          <!-- ── Footer ── -->
          <tr>
            <td style="
              background-color:{_C['low']};
              padding:20px 40px 24px;
              border-radius:0 0 8px 8px;
            ">
              <p style="
                margin:0;
                font-family:Arial,sans-serif;
                font-size:12px; line-height:1.6;
                color:{_C['outline']};
              ">{c['footer']}</p>
            </td>
          </tr>

        </table>
        <!-- /Card -->

        <!-- Below-card domain label -->
        <p style="
          margin:20px 0 0;
          font-family:Arial,sans-serif;
          font-size:12px; color:{_C['outline']};
          letter-spacing:0.05em;
        ">amendly.eu</p>

      </td>
    </tr>
  </table>
</body>
</html>"""


async def send_welcome_email(
    email: str,
    name: str | None = None,
    lang: str = "en",
) -> None:
    """
    Send a welcome email to a newly created Amendly account.

    The email is localised to one of the four supported languages (en, fr, de, es).
    In development (no RESEND_API_KEY configured) the email is printed to stdout.

    Parameters:
        email: Recipient email address.
        name: User's display name — used in the personalised greeting.
        lang: BCP-47 language code (e.g. "fr", "fr-FR"). Defaults to "en".

    Side effects:
        Sends a transactional email via the Resend API, or logs to stdout in dev.
    """
    resolved = _resolve_lang(lang)
    c = _WELCOME_COPY[resolved]
    app_url = f"https://{settings.domain}"

    if not settings.resend_api_key:
        logger.info("[DEV] Welcome email for %s (lang=%s) — %s", email, resolved, app_url)
        return

    resend.api_key = settings.resend_api_key
    html = _build_welcome_html(app_url=app_url, c=c, name=name)

    try:
        resend.Emails.send(
            {
                "from": f"Amendly <{settings.resend_from_email or f'noreply@{settings.domain}'}>",
                "to": [email],
                "subject": c["subject"],
                "html": html,
            }
        )
    except Exception:
        # Welcome email failure is non-fatal — log and move on
        logger.exception("Failed to send welcome email to %s", email)
