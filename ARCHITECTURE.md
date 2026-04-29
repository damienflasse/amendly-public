# Amendly — Architecture

This document describes every directory and its purpose.

---

## Repository root

```
amendly/
├── claude.md         # Session context and workflow notes
├── backend/          # FastAPI Python application
├── frontend/         # React + Vite application
├── nginx/            # Nginx reverse-proxy config
├── docs/             # Product spec and supporting docs
├── docker-compose.yml
├── Makefile
├── .env.example
├── pytest.ini        # Repo-root pytest config for backend tests
├── README.md
└── ARCHITECTURE.md   (this file)
```

---

## backend/

FastAPI application running on Python 3.12.

```
backend/
├── app/
│   ├── main.py           # FastAPI application factory, CORS, router registration
│   ├── api/
│   │   ├── __init__.py
│   │   ├── auth.py           # Auth endpoints: magic-link, Google OAuth, /me, PATCH /me/preferences, PATCH /me/profile, POST /me/onboarding/complete, /logout, DELETE /me (GDPR erasure)
│   │   ├── organisations.py  # Org endpoints: create, list-mine, get-by-slug, patch (name+slug, owner only), delete (owner only), get-stats (active_docs/pending_amendments/member_count), list-members, change-role, remove-member, patch-notification-settings (per-org mute, any member)
│   │   ├── documents.py      # Document endpoints: create, list (paginated), get, update (title always; body draft-only), PATCH /sections (structure in draft or closed, optional title update), consolidated, review, export (single format, plan-gated), export/zip (ZIP bundle of all unlocked formats), POST/DELETE contributor-token (owner/admin — generate or revoke public link)
│   │   ├── amendments.py     # Amendment endpoints: submit, list, list-mine (GET …/mine — current user's own), get, update-status, diff, react (POST …/react — organisation plan only; toggle support/oppose), reaction-summary (GET …/reaction-summary — organisation plan only, owner/admin only)
│   │   ├── contribute.py     # Public contribution endpoints (no auth): GET /api/contribute/{token} (document preview), POST /api/contribute/{token} (anonymous amendment submission, Redis-backed rate-limited 10/IP/hour with in-memory fallback, Turnstile-protected when configured)
│   │   ├── resend_webhooks.py # Resend signed webhook receiver: POST /api/webhooks/resend; logs sent/delivered/bounced/complained email lifecycle events
│   │   ├── inbox.py          # Public contact + authenticated support endpoints: POST /api/contact (honeypot + 5/IP/hour limit), POST /api/support (auth required; forwards to internal inbox)
│   │   ├── invitations.py    # Invite endpoints: POST …/invite (org router) + GET /api/invitations/preview (no auth) + POST /api/invitations/accept
│   │   ├── billing.py        # Billing endpoints: POST /checkout (owner only), POST /portal (owner only), POST /webhook (Stripe signed)
│   │   ├── activity.py       # Activity feed: GET /api/organisations/{slug}/activity?page=N (any member; paginated, returns { items, total, page, page_size })
│   │   ├── notifications.py  # Notification center: GET /api/me/notifications?limit=N (team+ plan gated; returns { has_team_plan, items, unread_count }; items include amendment_id for deep-link anchoring; amendment_commented targeted to amendment author only), POST /api/me/notifications/read (updates notifications_last_read_at), GET /api/me/notifications/settings (global + per-org mute states)
│   │   ├── plans.py          # GET /api/plans — public, returns active plans sorted by price
│   │   ├── users.py          # GET /api/users/me/stats — orgs_count, docs_count, amendments_submitted, pending_amendments_count across all member orgs
│   │   └── admin.py          # Superuser-only admin API: plans CRUD, platform stats (+ amendments/open-docs/sparkline), org plan override (+ amendment_count/last_activity_at), email templates CRUD, prospects CRUD + POST /prospects/{id}/email
│   ├── core/
│   │   ├── config.py     # Pydantic Settings — reads all config from env vars, including Turnstile secret aliases, Resend webhook secret, and SUPPORT_INBOX_EMAIL; strips inline comments from email-address env values; ignores unrelated .env keys so backend pytest can run from repo root
│   │   ├── database.py   # SQLAlchemy async engine, session factory, Base, get_db()
│   │   └── auth.py       # JWT helpers, magic-link token gen, get_current_user dep
│   ├── models/
│   │   ├── __init__.py   # Re-exports all models (required for Alembic autogenerate)
│   │   ├── user.py       # User (id, email, name, avatar_url, plan, is_superuser, deleted_at, is_deleted, email_notifications_enabled, notifications_last_read_at, onboarding_completed)
│   │   ├── organisation.py  # Organisation (id, name, slug, plan [solo/team/organisation], stripe_customer_id)
│   │   ├── plan_config.py   # PlanConfig (plan_name, base_price_cents, included_users, extra_user_price_cents, max_active_documents, max_external_contributors, stripe_price_id, stripe_price_id_annual, features JSON, is_active, updated_at)
│   │   ├── membership.py    # Membership join table (user_id, org_id, role, notifications_muted)
│   │   ├── document.py      # Document (id, org_id, title, body, status, contributor_token [nullable VARCHAR 64 unique], contributor_token_created_at [nullable])
│   │   ├── amendment.py     # Amendment (id, doc_id, section, original_text, proposed_text, justification, status, author_id [nullable], contributor_name [nullable VARCHAR 100], contributor_email [nullable VARCHAR 254])
│   │   ├── amendment_reaction.py  # AmendmentReaction (id, user_id, amendment_id, reaction_type: support|oppose) — unique per user+amendment; cascades on user/amendment delete
│   │   ├── amendment_comment.py   # AmendmentComment (id, amendment_id, author_id, body, created_at) — threaded discussion; hard-deleted; author_id SET NULL on user delete
│   │   ├── invitation.py    # Invitation (id, org_id, email, token, created_at, expires_at, accepted_at)
│   │   ├── activity_log.py  # ActivityLog (id, org_id, user_id, doc_id, amendment_id, action, created_at)
│   │   ├── email_template.py  # EmailTemplate (id, template_key unique, subject, html_body, updated_at)
│   │   └── prospect.py      # Prospect (id, email, name, org_name, notes, status [new/contacted/demo_booked/converted/lost], created_at, updated_at)
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── organisation.py  # OrganisationCreate, OrganisationUpdate, OrganisationResponse, MembershipResponse, MemberDetail, RoleChangeRequest, OrgStatsResponse
│   │   ├── document.py      # DocumentCreate, DocumentUpdate, DocumentStatusUpdate, SectionUpdate (body required, title optional), DocumentResponse (incl. contributor_token + contributor_token_created_at), DocumentListResponse, ConsolidatedResponse, ContributorTokenResponse, DiffToken, ReviewAmendmentItem, ReviewResponse
│   │   ├── amendment.py     # AmendmentCreate, ContributorAmendmentCreate (adds contributor_name/email + validation), AmendmentStatusUpdate, AmendmentResponse (incl. author_name + author_email + contributor_name + contributor_email + comment_count), AmendmentListResponse, ReactRequest, ReactionSummaryResponse
│   │   ├── amendment_comment.py  # CommentCreate, CommentResponse, CommentListResponse
│   │   ├── invitation.py    # InviteCreate, InviteAccept, InvitationResponse
│   │   ├── billing.py       # CheckoutRequest (incl. plan_name), CheckoutResponse, PortalRequest, PortalResponse
│   │   ├── inbox.py         # ContactRequest, SupportRequest, InboxAcceptedResponse
│   │   ├── plan_config.py   # PlanConfigResponse, PlanConfigUpdate (all optional; -1 sentinel for max_active_documents / max_external_contributors)
│   │   ├── email_template.py  # EmailTemplateResponse, EmailTemplateUpdate
│   │   └── prospect.py      # ProspectCreate, ProspectUpdate, ProspectEmailRequest, ProspectResponse
│   ├── services/
│   │   ├── __init__.py
│   │   ├── organisation.py  # create_organisation, update_organisation, delete_organisation, list_organisations_for_user, get_organisation_by_slug, get_org_stats, list_members, change_member_role, remove_member
│   │   ├── document.py      # create_document (plan-based active-document cap enforced), list_documents, get_document, update_document (title always; body draft-only), update_document_sections (structure edits in draft/closed, optional title update), update_document_status, get_consolidated, get_review; logs document_created + status_changed to activity_log
│   │   ├── amendment.py     # create_amendment (sends notification to org owners/admins; skips muted members), list_amendments (includes comment_count via batch query), get_amendment, update_amendment_status (sends notification email on accepted/rejected; skips if author has notifications_muted for the org), withdraw_amendment, react_to_amendment (support/oppose with toggle semantics; organisation plan gated), get_reaction_summary (aggregated counts for all pending amendments; owner/admin + organisation plan); logs all amendment events to activity_log
│   │   ├── amendment_comment.py  # list_comments, create_comment, delete_comment (author or owner/admin); hard-delete; author resolved via eager-loaded N+1-safe query
│   │   ├── invitation.py    # create_invite (sends branded HTML email via Resend, uses DB template if set), accept_invite, get_invite_preview
│   │   ├── billing.py       # create_checkout_session (accepts plan_name; reads stripe_price_id from plan_config; embeds metadata.plan_name in Stripe session), create_portal_session, handle_stripe_event
│   │   ├── inbox.py         # send_contact_message, send_support_message; formats branded internal inbox emails via Resend and derives support tier from user/org plans
│   │   ├── activity.py      # log_activity (write helper), list_activity (read — paginated at PAGE_SIZE=20; returns { items, total, page, page_size })
│   │   ├── plan_config.py   # list_plan_configs, get_plan_config_by_name, update_plan_config, get_document_limit_for_plan, get_external_contributor_limit_for_plan
│   │   ├── email_template.py  # list_email_templates, get_email_template, upsert_email_template, reset_email_template, render_template (loads DB override or hardcoded default; substitutes {variable} placeholders)
│   │   └── prospect.py      # list_prospects, create_prospect, update_prospect, delete_prospect, send_prospect_email (Resend + note logging + auto-status advance)
│   └── utils/
│       ├── __init__.py
│       ├── diff.py          # compute_diff(original, proposed) → list[DiffToken]; word-level SequenceMatcher
│       ├── export.py        # export_docx / export_pdf / export_txt — return bytes for the export endpoint; each accepts optional `amendments` list for appendix; used by both single-format and ZIP endpoints
│       ├── email.py         # send_amendment_status_email (accepted/rejected; uses DB template if available), send_amendment_submitted_email (new amendment; notifies org owners/admins; fire-and-forget)
│       ├── docx_import.py   # docx_bytes_to_html(file_bytes) — converts uploaded .docx files to sanitised HTML for document import
│       ├── rate_limit.py    # Shared client IP extraction + Redis counter helpers used by auth and public contribution rate limiting
│       └── turnstile.py     # verify_turnstile(token, remote_ip, fail_open=True) — shared Cloudflare Turnstile verifier for auth and public contribution flows
├── migrations/
│   ├── env.py            # Alembic async migration environment
│   ├── script.py.mako    # Migration file template (includes "Reason for change")
│   └── versions/
│       ├── 0001_create_core_tables.py              # users, organisations, memberships, documents
│       ├── 0002_add_invitations_table.py            # invitations table (token, expires_at, accepted_at)
│       ├── 0003_add_stripe_customer_id.py           # stripe_customer_id on organisations (nullable, unique)
│       ├── 0004_add_withdrawn_amendment_status.py   # adds 'withdrawn' to the amendment_status PostgreSQL enum (no-op on SQLite)
│       ├── 0005_add_activity_log_table.py           # activity_log table + activity_action PostgreSQL enum
│       ├── 0006_add_user_deletion_fields.py         # GDPR erasure: adds deleted_at (DateTime) + is_deleted (Boolean) to users
│       ├── 0007_add_email_notifications_preference.py  # per-user opt-out: adds email_notifications_enabled (Boolean, default TRUE) to users
│       ├── 0008_add_superuser_and_plan_config.py       # is_superuser flag on users, plan_config table
│       ├── 0009_rename_plan_enums.py                   # rename plan enum values
│       ├── 0010_amendment_type_and_decision_reason.py  # amendment_type enum, decision_reason, nullable original/proposed text
│       ├── 0011_add_email_templates_and_prospects.py   # email_templates table (superadmin-editable templates), prospects table (sales pipeline CRM)
│       ├── 0012_add_notifications_last_read_at.py      # notifications_last_read_at (nullable DateTime) on users — tracks last time user opened in-app feed
│       ├── 0013_add_amendment_reactions.py             # amendment_reactions table (user_id, amendment_id, reaction_type: support|oppose) — unique per user+amendment
│       ├── 0014_update_plan_features_reactions.py      # backfills plan_config.features JSON to include amendment-reactions feature flags for team/organisation plans
│       ├── 0015_update_stripe_price_ids_team_org.py    # backfills stripe_price_id + stripe_price_id_annual for team and organisation plans in plan_config
│       ├── 0016_set_solo_stripe_price_id.py            # backfills stripe_price_id (monthly) for the solo plan in plan_config
│       ├── 0017_set_solo_annual_stripe_price_id.py     # backfills stripe_price_id_annual for the solo plan in plan_config
│       ├── 0018_make_amendment_author_id_nullable.py   # drops NOT NULL constraint on amendments.author_id to match the ON DELETE SET NULL FK cascade
│       ├── 0019_add_notifications_muted_to_memberships.py  # adds notifications_muted (Boolean, default false) to memberships — per-org email mute
│       ├── 0020_add_amendment_comments.py                  # amendment_comments table (id, amendment_id FK CASCADE, author_id FK SET NULL, body TEXT, created_at)
│       ├── 0023_add_external_contributor_limit_and_update_plan_defaults.py # adds plan_config.max_external_contributors; Team defaults become 20 docs / 30 external contributors; Organisation becomes the reactions tier
│       ├── 0021_add_amendment_commented_activity_action.py # adds 'amendment_commented' to activity_action enum (no-op on SQLite)
│       ├── 0022_contributor_public_link.py                 # documents: contributor_token (VARCHAR 64 nullable unique) + contributor_token_created_at; amendments: contributor_name (VARCHAR 100) + contributor_email (VARCHAR 254)
│       ├── 0024_add_user_profile_fields.py                 # users: company (VARCHAR 255 nullable) + job_position (VARCHAR 255 nullable)
│       ├── 0025_add_performance_indexes.py                 # performance: ix_amendments_doc_status (doc_id, status), ix_amendments_status (status), ix_memberships_org_role (org_id, role)
│       └── 0026_add_onboarding_completed.py               # users: add onboarding_completed BOOLEAN DEFAULT FALSE — server-side wizard completion flag
├── tests/
│   ├── test_health.py          # Smoke test for /api/health
│   ├── test_auth.py            # Auth endpoint tests (magic-link, OAuth, /me, DELETE /me GDPR erasure)
│   ├── test_organisations.py   # Organisation endpoint tests (create, list, get-by-slug)
│   ├── test_documents.py       # Document endpoint tests (create, list, get, update, access control)
│   ├── test_amendments.py      # Amendment endpoint tests (submit, list, get, status update, access control)
│   ├── test_diff.py            # Unit tests for compute_diff + integration tests for GET …/diff endpoint
│   ├── test_invitations.py     # Invite endpoint tests (create, idempotency, preview, accept, email send path mocked, 503 on Resend failure)
│   ├── test_consolidation.py   # Consolidated endpoint tests (no amends, accepted, pending/rejected ignored)
│   ├── test_export.py          # Export endpoint tests (DOCX/PDF/TXT format, access control, content correctness)
│   ├── test_billing.py             # Billing endpoint tests (checkout, portal, webhook events, solo-plan document limit)
│   ├── test_inbox.py               # Contact/support endpoint tests (honeypot, rate limit, auth gate, Resend payloads)
│   ├── test_members.py             # Member-management endpoint tests (list, change-role, remove; all access-control cases)
│   ├── test_document_status.py     # Document status endpoint tests (PUT …/status; owner/admin only; all access-control cases)
│   ├── test_withdraw_amendment.py  # Amendment withdraw endpoint tests (DELETE …/amendments/{id}; author/pending only; all access-control cases)
│   ├── test_activity.py            # Activity feed endpoint tests (GET …/activity; pagination; all action types; access control)
│   ├── test_notification_preferences.py  # PATCH /me/preferences tests + email suppression when opted out
│   ├── test_plan_config.py              # GET /api/plans, GET/PATCH /api/admin/plans, document limit enforcement, admin-modifiable limits
│   ├── test_reactions.py               # POST …/amendments/{id}/react — support, oppose, toggle off, plan gate (402 on solo), unauthenticated (401)
│   └── test_contributor.py             # GET …/amendments/mine — own amendments only, empty list for new member, unauthenticated (401)
├── alembic.ini           # Alembic configuration (URL is overridden at runtime)
├── pytest.ini            # pytest configuration
├── requirements.txt      # Pinned Python dependencies
└── Dockerfile
```

### Key conventions

- All config comes from environment variables — never hardcoded.
- `RESEND_PROSPECT_FROM_EMAIL` and `SUPPORT_INBOX_EMAIL` default to empty string — a startup warning is logged if they are unset, and they **must** be set in production for prospect outreach and support inbox routing to work.
- `STRIPE_WEBHOOK_SECRET` defaults to empty string — a startup warning is logged if unset. Stripe webhook signature verification is skipped when empty (dev only); **must** be set in production.
- Rate-limit endpoints (`/magic-link/request`, public contribution, public contact) return `Retry-After` header alongside HTTP 429 so clients know when to retry.
- Database URL is normalised to `postgresql+asyncpg://` at startup for the async driver.
- `get_db()` is a FastAPI dependency that yields an `AsyncSession` and handles commit/rollback.
- Every Alembic migration **must** include a `Reason for change:` comment in the docstring.
- `ALLOWED_ORIGINS` is stored as a comma-separated string in `.env` (`ALLOWED_ORIGINS_RAW`) and parsed at runtime via the `allowed_origins` property on `Settings`.
- Tests use an in-memory SQLite database (via `aiosqlite`) — no live Postgres needed for `pytest`.
- Backend settings ignore unrelated `.env` keys (for example frontend `VITE_*` variables) so `pytest backend/tests` works from the repo root without env parsing failures.
- `create_async_engine` skips `pool_size`/`max_overflow` for SQLite (CI) — those kwargs are only passed for PostgreSQL.
- Magic-link tokens are stored in Redis (key `magic_link:<token>`, TTL 15 min) when Redis is reachable; the module-level `_magic_link_store` dict is used as a fallback and is always kept in sync so tests can inspect it directly.
- `STRIPE_PRICE_ID` env var: when set, the billing service uses a pre-created Stripe Price instead of inline `price_data`. Leave empty in development.
- `STRIPE_PORTAL_RETURN_URL` env var: when set, the Customer Portal session uses this as the return URL. Defaults to `https://{DOMAIN}/orgs/{slug}/billing`.

---

## frontend/

React 18 application with static prerendering for public routes, bundled with Vite.

```
frontend/
├── src/
│   ├── main.jsx              # ReactDOM.createRoot entry point (client hydration)
│   ├── App.jsx               # Root component — BrowserRouter wrapping AppRoutes
│   ├── AppRoutes.jsx         # Shared route tree — used by App.jsx (client) and entry-server.jsx (SSR)
│   ├── entry-server.jsx      # SSR entry point — exports render(url) using renderToString + StaticRouter
│   ├── index.css             # Tailwind CSS directives (@tailwind base/components/utilities)
│   ├── components/
│   │   ├── ProtectedRoute.jsx    # Redirects unauthenticated users to /login; injects noindex meta tag
│   │   ├── LanguageSwitcher.jsx  # Dropdown to switch UI language (en/fr/de/es)
│   │   ├── CookieBanner.jsx      # GDPR cookie consent banner — fixed bottom strip; persists choice to localStorage key `amendly_cookie_consent`; SSR-safe
│   │   ├── NotificationBell.jsx  # In-app notification center — bell icon + unread badge + glassmorphism dropdown; polls every 60 s; plan-gated (team/organisation only); upgrade nudge for solo users; marks all read on open; clicking an amendment notification navigates to /orgs/{slug}/documents/{id}#amendment-{amendmentId} and optimistically marks that item as read
│   │   └── JsonLd.jsx            # Injects <script type="application/ld+json"> into <head>; SSR-safe (client-only)
│   ├── pages/
│   │   ├── LandingPage.jsx   # Public marketing page at "/" — hero, features, pricing, CTA, footer; JSON-LD structured data (WebSite + SoftwareApplication); fully localised via "landing" i18n namespace; all links use React <Link>
│   │   ├── PricingPage.jsx   # Dedicated pricing page at "/pricing" — Free/Pro cards, FAQ (5 items), CTA; prerendered; JSON-LD SoftwareApplication; localised via "pricing" i18n namespace; canonical + hreflang via useSeoMeta
│   │   ├── TermsPage.jsx     # Static Terms of Service at "/legal/terms" — localised via "legal" i18n namespace; no auth required
│   │   ├── PrivacyPage.jsx   # Static Privacy Policy at "/legal/privacy" — localised via "legal" i18n namespace; no auth required
│   │   ├── ContactPage.jsx   # Public contact page at "/contact" — POST /api/contact wired to real sending/error/success states; honeypot field mirrors backend anti-spam behaviour
│   │   ├── Login.jsx         # Magic-link + Google SSO login page
│   │   ├── AuthCallback.jsx  # Silent OAuth token handler (/auth/callback)
│   │   ├── Dashboard.jsx     # Authenticated dashboard — user profile + org list (org cards link to OrgDetail); illustrated welcome empty state (SVG + headline + body) when user has no orgs yet
│   │   ├── SupportPage.jsx   # Authenticated support page at "/support" — POST /api/support with sending/error/success states; derives tier badge from the highest user/org plan
│   │   ├── OrgDetail.jsx     # Org document list — /orgs/:slug; plan badge + Billing + Settings links (owner); stats pills (active docs / pending amendments / members — counter decrements on removal); Documents/Members TAB BAR (Documents tab: paginated list, client-side search+sort, inline create form, activity feed; Members tab: always-expanded member list with role badge, role selector + remove for owner, "Leave" for non-owner, pending invitations with revoke/resend for owner/admin, inline invite form; last_activity_at displayed per member when caller is owner + paid plan); notification-muted badge in headline
│   │   ├── OrgSettings.jsx   # Org settings — /orgs/:slug/settings (owner only; redirects non-owners to /orgs/:slug); editable name + slug fields with live URL preview (amendly.eu/{slug}); client-side slug validation; navigates to new slug URL after successful slug change; notification mute toggle (PATCH /api/organisations/{slug}/notification-settings; loads current state on mount; success/error feedback); danger zone: delete org (requires typing org name to unlock; navigates to /dashboard on success)
│   │   ├── Billing.jsx       # Billing management — /orgs/:slug/billing (owner only); plan display + PlanBadge; plan selector (usePlans) for upgrade checkout; live features list for paid plans; Stripe Customer Portal link
│   │   ├── AdminPricing.jsx  # Admin pricing config — /admin/pricing (superuser only); PlanConfigCard with inline edit; redirects to /dashboard on 403
│   │   ├── AdminEmailTemplates.jsx  # Admin email templates — /admin/email-templates (superuser only); edit subject + HTML body of each transactional email; live sandboxed iframe preview; "Reset to default" button; is_customised badge
│   │   ├── AdminProspects.jsx  # Admin prospect CRM — /admin/prospects (superuser only); pipeline stats cards; add/edit/delete prospects; inline status selector + notes editing; filter by status
│   │   ├── DocumentView.jsx  # Document view — /orgs/:slug/documents/:id; SPLIT-PANE layout (h-screen):
│   │   │                     #   LEFT PANE: document body (full scroll), inline edit form (owner/admin), consolidated panel;
│   │   │                     #   floating "Back to top" button (sticky bottom-right, appears after 300 px scroll);
│   │   │                     #   RIGHT PANE (420px sticky): amendment list with filters, accept/reject, reactions, pagination;
│   │   │                     #   AmendmentCard accordion: clicking ▼/▲ chevron expands/collapses inline thread panel showing full diff, reactions, decision reason (one card expanded at a time);
│   │   │                     #   Status selector (owner/admin: draft→open→closed via PUT …/status);
│   │   │                     #   Export dropdown (DOCX/PDF/TXT, owner/admin only) triggering browser download;
│   │   │                     #   Filter bar: status / type / sort — client-side, no new endpoint;
│   │   │                     #   "Withdraw" button on pending amendments (author only, window.confirm guarded);
│   │   │                     #   "View consolidated" panel showing merged text after accepted amendments;
│   │   │                     #   Bulk action toolbar (owner/admin): checkboxes on pending cards → "Accept all" / "Reject all" toolbar — parallel PATCH requests, list refresh after
│   │   ├── AcceptInvite.jsx  # /invitations/accept?token=… — fetches invite preview (no auth), shows org name + branded card; auto-accepts when authenticated, shows sign-in CTA for unauthenticated visitors; fully localised via "invite" i18n namespace
│   │   ├── AccountSettings.jsx  # /account/settings (protected) — shows user email/name; global notification toggle (PATCH /api/auth/me/preferences; loads from GET /api/me/notifications/settings; success toast + error state); per-org mute toggles (PATCH /api/organisations/{slug}/notification-settings; shown when global enabled); danger zone with GDPR "Delete my account" action guarded by window.prompt with locale-aware keyword; calls DELETE /api/auth/me, clears token, redirects to /
│   │   ├── ContributorSubmission.jsx  # /orgs/:slug/documents/:id/contribute (protected, any member) — SPLIT-PANE layout (h-screen):
│   │                         #   LEFT PANE: full scrollable document body with text-selection handler (mouseup); sticky selection banner with "Use as original text" + "Clear" actions pre-fills the originalText field;
│   │                         #   RIGHT PANE (480px): "Your pending amendments" strip above form (section + proposed snippet + Withdraw button, visible when open doc + existing pending amendments); amendment form with type toggle, section, original/proposed text, live diff preview (LCS), justification, tips + "what happens next" panels;
│   │                         #   on submission success: confirmation screen with amendment summary (type, section, diff preview or comment), "Submit another" button (resets form) + "Back to document" link
│   │   └── PublicContribution.jsx     # /contribute/:token (public, no auth) — standalone public amendment submission page for external contributors; fetches document via GET /api/contribute/{token}; shows friendly closed/error states; collects contributor name + optional email; standard amendment form (type, section, original/proposed text or general comment, justification); embeds Cloudflare Turnstile when VITE_TURNSTILE_SITE_KEY is configured; LCS word diff preview; confirmation screen on success; uses contribute.js lib
│   ├── store/
│   │   ├── authStore.js      # Zustand: { user, setUser, clearUser }
│   │   └── orgStore.js       # Zustand: { organisations, setOrganisations }
│   ├── hooks/
│   │   ├── useTranslation.js     # i18n hook — reads amendly_lang from localStorage, t(key) helper; SSR-safe
│   │   ├── useConsent.js         # GDPR consent hook — reads `amendly_cookie_consent` from localStorage; returns { accepted, declined, pending }; SSR-safe
│   │   ├── useSeoMeta.js         # SEO hook — sets document.title, canonical, meta[name=description], Open Graph, Twitter Card, hreflang, robots; SSR-safe; noindex param for protected pages
│   │   └── usePlans.js           # Fetches GET /api/plans; module-level cache deduplicates requests; exports formatPrice(cents) + formatExtraUsers(cents) helpers
│   ├── i18n/
│   │   ├── en.json           # English translations
│   │   ├── fr.json           # French translations
│   │   ├── de.json           # German translations
│   │   └── es.json           # Spanish translations
│   └── lib/
│       ├── api.js            # Shared fetch helpers — cookie-backed auth fetch, public JSON fetch, API error shaping, unauthorized event dispatch
│       ├── auth.js           # Auth client — wraps /api/auth/* endpoints; browser auth is cookie-backed only
│       ├── admin.js          # Billing + admin plan/email-template/prospect API clients
│       ├── notifications.js  # Notification center API client (GET /api/me/notifications, POST /api/me/notifications/read)
│       ├── support.js        # Contact/support client — wraps POST /api/contact and POST /api/support with shared error handling
│       ├── organisations.js  # Org + document + amendment + diff + invite + getInvitationPreview + consolidated + listMembers + changeMemberRole + removeMember + getActivity + generateContributorToken + revokeContributorToken
│       └── contribute.js     # Public contribution client (no auth) — getPublicDocument(token) + submitPublicAmendment(token, payload incl. cf_turnstile_token); used exclusively by PublicContribution.jsx
├── scripts/
│   └── prerender.js          # Post-build prerender script — renders 5 public routes to static HTML using dist/server/entry-server.js; writes dist/index.html, dist/pricing/, dist/login/, dist/legal/terms/, dist/legal/privacy/
├── public/
│   ├── robots.txt        # Crawl policy: disallow /dashboard, /account/, /orgs/; links to sitemap
│   ├── sitemap.xml       # XML sitemap: /, /login, /legal/terms, /legal/privacy
│   ├── favicon.svg       # Brand favicon — "A" letterform on #1a4bd4 background; SVG (any size)
│   ├── site.webmanifest  # PWA web manifest — name, icons, theme_color (#1a4bd4), display standalone
│   └── og-image.png      # 1200×630 Open Graph card (generated by scripts/generate_og_image.py)
├── index.html            # Vite HTML entrypoint — title, meta, OG/Twitter defaults, canonical, manifest link, favicon, font preloads
├── vite.config.js        # Vite config — dev proxy; build.target es2020; manualChunks (vendor-react, vendor-router, vendor-zustand); SSR config
├── tailwind.config.js    # Tailwind content paths and theme extensions
├── postcss.config.js     # PostCSS plugins (Tailwind + Autoprefixer)
├── package.json          # build script = client build + SSR build + prerender
├── nginx-spa.conf        # Nginx config embedded in the production container (SPA fallback + robots.txt/sitemap.xml/site.webmanifest routes + explicit .mjs JavaScript MIME for module workers)
├── Dockerfile            # Multi-stage: node:22 build → nginx:1.27 static serve
└── Dockerfile.dev        # Development image: node:22-alpine + Vite HMR; used by docker-compose.dev.yml
```

### Key conventions

- All components must respect the design tokens in `frontend/DESIGN.md` (Google Stitch export).
- The Vite dev server proxies `/api/*` to `backend:8000` so the frontend never hard-codes the API URL.
- In production, Nginx handles the `/api` → backend routing; the frontend container serves only the built static files.
- Browser auth is cookie-backed via the `amendly_session` httpOnly cookie. Frontend authenticated requests use `credentials: include`; explicit Bearer auth is reserved for tooling/tests by sending `X-Amendly-Auth-Mode: bearer`.
- Routes: `/` → LandingPage (public), `/pricing` → PricingPage (public, prerendered), `/contact` → ContactPage (public), `/legal/terms` → TermsPage (public), `/legal/privacy` → PrivacyPage (public), `/login` → Login page, `/auth/callback` → AuthCallback, `/dashboard` → Dashboard (protected), `/support` → SupportPage (protected), `/account/settings` → AccountSettings (protected), `/orgs/:slug` → OrgDetail (protected), `/orgs/:slug/billing` → Billing (protected, owner only), `/orgs/:slug/documents/:id` → DocumentView (protected), `/orgs/:slug/documents/:id/contribute` → ContributorSubmission (protected, any member), `/contribute/:token` → PublicContribution (public anonymous contributor flow), `/invitations/accept` → AcceptInvite (public; shows org name fetched from preview API; auto-accepts if authenticated, shows sign-in CTA otherwise), `/admin/pricing` → AdminPricing (protected, superuser only).
- The `ProtectedRoute` component resolves the current session via `GET /api/auth/me`; unauthenticated requests are redirected to `/login`. It also injects `<meta name="robots" content="noindex, nofollow">` so authenticated pages are never indexed.
- Zustand stores (`authStore`, `orgStore`) hold the in-memory user and organisations state across components.
- i18n: `useTranslation()` hook reads/writes `amendly_lang` from localStorage (default: `en`). Translation keys are dot-separated and namespaced by section (`nav.*`, `auth.*`, `billing.*`, `org.*`, `document.*`, `common.*`, `cookie.*`, `landing.*`, `legal.*`, `activity.*`, `invite.*`, `account.*`, `time.*`, `pricing.*`, `admin.*`, `contributor.*`). All four JSON files (`en`, `fr`, `de`, `es`) must be kept in sync; the hook falls back to English for any missing key. SSR-safe (no localStorage in Node.js).
- SEO: `useSeoMeta({ title, description, ogImage?, ogType?, noindex?, lang?, canonical? })` hook sets `document.title`, `<link rel="canonical">`, `<meta name="robots">`, Open Graph, Twitter Card, `<html lang>`, and `<link rel="alternate" hreflang>` tags. SSR-safe (no-op on server). Public pages pass `lang` + `canonical`; protected pages use `noindex: true`.
- Prerendering: `npm run build` executes three steps: (1) `vite build` — client bundle, (2) `vite build --ssr` — server bundle to `dist/server/`, (3) `node scripts/prerender.js` — injects SSR HTML into the 5 public route HTML files (`/`, `/pricing`, `/login`, `/legal/terms`, `/legal/privacy`). Crawlers receive full HTML; React hydrates on the client.
- Static files: `robots.txt`, `sitemap.xml`, `favicon.svg`, `site.webmanifest`, `og-image.png` in `public/` are copied to the build root at build time. `nginx-spa.conf` serves them with correct MIME types and 1-day cache headers.
- GDPR consent: `CookieBanner` writes `amendly_cookie_consent = "accepted" | "declined"` to localStorage. `useConsent()` reads this value and exposes `{ accepted, declined, pending }`. `AppRoutes.jsx` calls `loadPlausible()` inside a `useEffect` gated on `accepted === true`. `loadPlausible()` injects the Plausible script tag with `data-domain` set to `VITE_PLAUSIBLE_DOMAIN`; it is a no-op if the env var is unset or the script has already been injected. All localStorage hooks are SSR-safe.
- Build output: vendor chunks are split (vendor-react ~143 kB gz:46 kB, vendor-router ~22 kB gz:8 kB, vendor-zustand ~0.7 kB) for long-term browser caching. Target `es2020` eliminates legacy polyfills.

---

## nginx/

```
nginx/
├── nginx.conf         # Production template: port 80 → HTTPS redirect; port 443 → TLS + /api/ → backend, / → frontend
└── nginx.local.conf   # Local testing only: port 80 HTTP-only, no TLS; used by docker-compose.local.yml
```

Nginx sits in front of both containers and is the only service that exposes ports 80 and 443 to the host.
- Port 80 redirects all traffic to HTTPS (except the `/.well-known/acme-challenge/` path for Let's Encrypt).
- Port 443 terminates TLS using Let's Encrypt certificates mounted from `/etc/letsencrypt` on the host.
- HSTS header is set with `max-age=31536000; includeSubDomains; preload`.
- Security headers: `X-Frame-Options: SAMEORIGIN`, `X-Content-Type-Options: nosniff`, `X-XSS-Protection`.
- `nginx.conf` contains `${DOMAIN}` placeholders. The Docker Compose `command` runs `envsubst` at container
  startup to substitute them before launching nginx (the conf is mounted as `nginx.conf.template`).

---

## docker-compose.dev.yml

Development convenience file. Runs PostgreSQL, Redis, and (optionally) the Vite dev server.

| Service    | Image / Build                          | Purpose                                                         |
|------------|----------------------------------------|-----------------------------------------------------------------|
| `db`       | `postgres:16-alpine`                   | Local Postgres (port 5432)                                      |
| `redis`    | `redis:7-alpine`                       | Local Redis (port 6379)                                         |
| `frontend` | `./frontend/Dockerfile.dev`            | Vite HMR dev server (port 5173); bind-mounts host `frontend/`  |

The backend still runs on the host (`uvicorn app.main:app --reload --port 8000`).
The Vite container resolves `backend` → host machine via `extra_hosts: backend:host-gateway`.

---

## docker-compose.yml

Five services:

| Service    | Image / Build             | Purpose                                                         |
|------------|---------------------------|-----------------------------------------------------------------|
| `db`       | `postgres:16`             | Primary relational store                                        |
| `redis`    | `redis:7-alpine`          | Cache, rate limits, magic-link/OAuth state, JWT revocation      |
| `backend`  | `./backend/Dockerfile`    | FastAPI + Uvicorn (non-root user)                               |
| `frontend` | `./frontend/Dockerfile`   | Nginx serving built static files                                |
| `nginx`    | `nginx:1.27-alpine`       | Reverse proxy — only public-facing service; runs envsubst on startup |

All five services have healthchecks. Service start order: `db`+`redis` → `backend` → `frontend` → `nginx`.
`nginx` depends on both `backend` and `frontend` being healthy before it starts.
`backend` depends on both `db` and `redis` being healthy before it starts.

---

## docs/

Product specification documents (PDFs and DOCX). Not served by the application.

---

## Environment variables

All secrets and config are in `.env` (gitignored). See `.env.example` for the full list and `backend/app/core/config.py` for the canonical definition.
`SUPPORT_INBOX_EMAIL` controls the internal inbox destination for `POST /api/contact` and `POST /api/support`; if unset, the backend defaults to `hello@amendly.eu`.

---

## Session 22 additions

- `docker-compose.plausible.yml` — self-hosted Plausible Analytics stack (Postgres + ClickHouse + Plausible CE). Runs on `localhost:8001`; proxy externally via nginx on a subdomain of your choice (e.g. `stats.example.com`).
- `email_notifications_enabled` (Boolean, default TRUE) added to the `users` table via migration 0007. When FALSE the amendment service skips the accepted/rejected notification email for that author.
- `PATCH /api/auth/me/preferences` — authenticated endpoint to update notification preferences. Returns the updated `UserResponse`.
- `AccountSettings.jsx` updated with a toggle switch for notification emails (accessible `role="switch"`, animated, localised in all 4 languages).
- Production deploy guide added to `README.md` (first deploy, subsequent deploys, smoke tests, Plausible setup).
- `test_notification_preferences.py` — 7 tests covering the new endpoint and downstream email suppression behaviour.
- `feat/launch-prep` merged into `main`.

## Session 23 additions

- **Activity feed pagination** — `GET /api/organisations/{slug}/activity?page=N` now returns `{ items, total, page, page_size }` instead of a flat list. `PAGE_SIZE = 20`. `list_activity` service uses `func.count()` + `offset/limit`. `test_activity.py` updated and 4 new pagination tests added (191 tests total).
- **Frontend "Load more"** — `ActivityFeed` component in `OrgDetail.jsx` tracks `page`, `total`, and `loadingMore`. First expand fetches page 1; a "Load more" button appends subsequent pages without replacing existing entries. Total count is shown in the section header.
- **AmendmentForm auto-clear** — `AmendmentForm` in `DocumentView.jsx` resets all fields immediately on successful submission, shows a brief `✓ Amendment submitted.` flash (800 ms), then calls `onCreated`. New i18n key `document.amendment_submitted_success` added in all 4 languages.
- **Document list in-place refresh** — `handleDocCreated` in `OrgDetail.jsx` now re-fetches page 1 from the API after a document is created (instead of manually prepending), ensuring the list order and total match server state. Resets to page 1.
- **German i18n bug fixed** — `frontend/src/i18n/de.json` had two instances of German opening quote `„` followed by a literal ASCII `"` closing quote, which broke JSON parsing. Both replaced with proper German closing quote `"` (U+201C).
- `orgClient.getActivity(slug, page)` updated to pass `?page=N` query param (default 1).

## Session 24 additions

- **`frontend/Dockerfile.dev`** — lightweight `node:22-alpine` image that runs `npm run dev` with Vite HMR. Automatically runs `npm install` on first start if `node_modules` is absent. Bind-mounts the host `frontend/` directory so every file change is reflected immediately without rebuilding the image.
- **`docker-compose.dev.yml` updated** — new `frontend` service using `Dockerfile.dev`. Volume-mounts `./frontend:/app`. Resolves the `backend` hostname to the host machine via `extra_hosts: backend:host-gateway` so the Vite proxy can reach `uvicorn` running on the host. Developers can now run the full stack (Postgres + Redis + Vite) with a single command: `docker compose -f docker-compose.dev.yml up -d`.
- **`README.md` updated** — new "Local development — Docker frontend" section documents the two usage modes: (A) databases only, (B) databases + Vite in Docker. Includes first-run note about `npm install` and instructions for restarting after adding a package.

## Session 25 additions (SEO)

- **Static prerendering** — `src/entry-server.jsx` exports `render(url)` using `renderToString` + `StaticRouter`. `frontend/scripts/prerender.js` post-build script writes 4 pre-rendered HTML files: `dist/index.html`, `dist/login/`, `dist/legal/terms/`, `dist/legal/privacy/`. Crawlers receive full HTML; React hydrates on client load.
- **`src/AppRoutes.jsx`** — shared route tree extracted from `App.jsx`. Used by both `App.jsx` (BrowserRouter, client) and `entry-server.jsx` (StaticRouter, SSR prerender). All routing + analytics logic lives here.
- **SSR-safe hooks** — `useTranslation`, `useConsent`, `useSeoMeta`, `ProtectedRoute`, `CookieBanner`, `auth.js` all guard `localStorage` / `document` / `window` access with `typeof window !== 'undefined'` checks so they run safely in Node.js during prerendering.
- **`useSeoMeta` enriched** — new parameters: `noindex` (injects `noindex, nofollow` on protected pages), `lang` (updates `<html lang>` + `og:locale` + `<link rel="alternate" hreflang>` for all 4 locales), `canonical` (upserts `<link rel="canonical">` with clean path — no query string).
- **`ProtectedRoute` noindex** — all authenticated routes inject `<meta name="robots" content="noindex, nofollow">` as belt-and-suspenders protection against accidental indexing.
- **JSON-LD structured data** — `src/components/JsonLd.jsx` injects `<script type="application/ld+json">` into `<head>`. `LandingPage` emits two blocks: `WebSite` (Sitelinks signal) + `SoftwareApplication` with Free/Pro pricing offers.
- **Favicon + PWA manifest** — `public/favicon.svg` (brand "A" on `#1a4bd4`); `public/site.webmanifest` (PWA manifest with `theme_color`, `display: standalone`, icons). `nginx-spa.conf` serves the manifest with `application/manifest+json` MIME type.
- **`index.html` enriched** — added `og:image:width/height/alt`, `twitter:image:alt`, `twitter:site`, `<meta name="author">`, `<meta name="theme-color">`, `<meta name="apple-mobile-web-app-*">`, `<link rel="manifest">`.
- **Vite build optimised** — `build.target: 'es2020'`; `manualChunks` splits vendor code into `vendor-react`, `vendor-router`, `vendor-zustand` for long-term browser caching; `assetsInlineLimit: 8192` reduces HTTP requests.
- **`package.json` build pipeline** — `npm run build` = `vite build` + `vite build --ssr` + `node scripts/prerender.js`. Added `build:client`, `build:ssr`, `prerender` scripts for granular control.

Previous session 25 deploy additions:
- **`scripts/deploy.sh`** — automated VPS deployment script.
- **`scripts/deploy_local.sh`** — local production-stack test script.
- **`docker-compose.local.yml`** — Docker Compose TLS-free override for local testing.
- **`nginx/nginx.local.conf`** — HTTP-only nginx config for local testing.

## scripts/

```
scripts/
├── deploy.sh              # Production deploy → your-server.example.com (rsync + docker compose)
├── deploy_local.sh        # Local production-stack test (docker-compose.yml + docker-compose.local.yml)
├── setup-vps-nginx.sh     # One-time VPS host-nginx setup: installs nginx+certbot, provisions TLS for amendly.eu
└── generate_og_image.py   # Generates frontend/public/og-image.png (1200×630 OG card)
```

**`deploy.sh`** — run from the project root:
```bash
./scripts/deploy.sh              # full deploy
./scripts/deploy.sh --dry-run    # preview commands
./scripts/deploy.sh --skip-rsync # re-deploy .env only
```

**`deploy_local.sh`** — run from the project root:
```bash
./scripts/deploy_local.sh          # build and start
./scripts/deploy_local.sh --down   # stop and clean up
./scripts/deploy_local.sh --no-build --logs  # quick restart with log tail
```

**`setup-vps-nginx.sh`** — run once on the VPS as root:
```bash
sudo bash scripts/setup-vps-nginx.sh [--domain=amendly.eu] [--email=hello@amendly.eu] [--dry-run]
```
Installs host nginx + certbot, deploys `nginx/nginx.vps-host.conf`, issues a Let's Encrypt certificate,
and provides instructions to restart the Amendly stack on host port 8081 using `docker-compose.vps.yml`.

**`generate_og_image.py`** — run with:
`source backend/.venv/bin/activate && python scripts/generate_og_image.py`
Uses `Pillow` (already in `backend/requirements.txt`). Regenerate if the brand design changes.

## Session 27 additions (admin pricing interface + dynamic plan config)

### Backend

- **Migration 0008** (`migrations/versions/0008_add_superuser_and_plan_config.py`) — adds `is_superuser BOOLEAN NOT NULL DEFAULT FALSE` to `users`; creates `plan_config` table (plan_name, base_price_cents, included_users, extra_user_price_cents, max_active_documents, stripe_price_id, stripe_price_id_annual, features JSON, is_active, updated_at); seeds Solo/Team/Organisation rows.
- **Migration 0023** (`migrations/versions/0023_add_external_contributor_limit_and_update_plan_defaults.py`) — adds `max_external_contributors` to `plan_config`; Team defaults become 20 active docs / 30 external contributors; Organisation gains CSV/JSON exports and becomes the only reactions tier.
- **Migration 0009** (`migrations/versions/0009_rename_plan_enums.py`) — renames PostgreSQL enum values: `free→solo`, `pro→team`, `enterprise→organisation` for both `org_plan` and `user_plan` types. SQLite guard: no-op when `dialect.name != "postgresql"`.
- **`app/models/plan_config.py`** (new) — `PlanConfig` SQLAlchemy model mapped to `plan_config` table; `features` stored as JSON TEXT; includes configurable document and external-contributor caps.
- **`app/models/organisation.py`** — `OrgPlan` enum now `solo/team/organisation`; default `OrgPlan.solo`.
- **`app/models/user.py`** — `UserPlan` enum now `solo/team/organisation`; added `is_superuser: Mapped[bool]` field.
- **`app/core/config.py`** — added `superuser_email: str = ""` setting.
- **`app/core/auth.py`** — added `require_superuser` FastAPI dependency (raises HTTP 403 for non-superusers); added `ensure_superuser_seeded(db)` async startup function.
- **`app/schemas/plan_config.py`** (new) — `PlanConfigResponse` and `PlanConfigUpdate` (all optional fields; `-1` sentinel → `NULL` for `max_active_documents` / `max_external_contributors`).
- **`app/schemas/billing.py`** — added `plan_name: str = "solo"` to `CheckoutRequest`.
- **`app/services/plan_config.py`** (new) — `list_plan_configs`, `get_plan_config_by_name`, `update_plan_config`, `get_document_limit_for_plan`, `get_external_contributor_limit_for_plan`.
- **`app/services/document.py`** — removed hardcoded `FREE_TIER_DOCUMENT_LIMIT`; document limit now read dynamically from `plan_config` via `get_document_limit_for_plan`.
- **`app/services/billing.py`** — removed hardcoded limits; `create_checkout_session` accepts `plan_name`, reads `stripe_price_id`/`base_price_cents` from `plan_config`, embeds `metadata.plan_name` in Stripe session; webhook handler reads `plan_name` from metadata.
- **`app/api/admin.py`** (new) — `GET /api/admin/plans` + `PATCH /api/admin/plans/{plan_name}` (superuser only).
- **`app/api/plans.py`** (new) — `GET /api/plans` (public, active plans only).
- **`app/main.py`** — registers `admin_router` + `plans_router`; startup event calls `ensure_superuser_seeded`.
- **`tests/test_plan_config.py`** (new) — 12 tests covering public endpoint, admin auth, plan update, sentinel -1, 404, and dynamic document limit enforcement.
- **`tests/test_billing.py`** — updated: enum values `free→solo`, `pro→team`; seeded `plan_config` rows for checkout tests.

### Frontend

- **`src/hooks/usePlans.js`** (new) — `usePlans()` hook; module-level cache to deduplicate requests. Exports `formatPrice(cents)` and `formatExtraUsers(cents)` helpers.
- **`src/pages/AdminPricing.jsx`** (new) — `/admin/pricing` (protected, superuser only); `PlanConfigCard` with inline edit mode for all plan fields; redirects to `/dashboard` on 403.
- **`src/lib/organisations.js`** — added `planClient` (`getPlans`, `adminListPlans`, `adminUpdatePlan`); `billingClient.createCheckoutSession` now accepts `planName` parameter.
- **`src/AppRoutes.jsx`** — added `/admin/pricing` route.
- **`src/pages/PricingPage.jsx`** — rewritten to use `usePlans()`: dynamic pricing cards, skeleton loading, JSON-LD built from live plan data.
- **`src/pages/LandingPage.jsx`** — pricing section now uses `usePlans()`: dynamic cards from API, skeleton loading while fetching, JSON-LD offers built from live plan data.
- **`src/pages/Billing.jsx`** — uses `usePlans()`: upgrade section shows live plan selector (radio buttons) so the user picks a plan before checkout; paid plan section shows live features from `plan_config`.
- **i18n files** (`en`, `fr`, `de`, `es`) — added `admin` namespace (`pricing_title`, `pricing_subtitle`, `no_plans`).
- **`.env.example`** — added `SUPERUSER_EMAIL=` variable.

### Key invariants

- All pricing (prices, features, limits) is now sourced from `plan_config` at runtime. No hardcoded plan data in application code.
- `SUPERUSER_EMAIL` env var: if set, the named user is upserted to `is_superuser=True` on every startup. Safe to rotate; setting it to empty disables the feature.
- Public `GET /api/plans` returns only `is_active=True` plans, sorted by price ascending.
- Admin `PATCH /api/admin/plans/{name}` supports partial updates; `-1` maps to `NULL` (unlimited) for `max_active_documents`.

## Session 28 additions (prerender fix, robots.txt, annual billing toggle)

### Frontend

- **`frontend/public/robots.txt`** — added `Disallow: /admin/` so the superuser pricing config page is never crawled.
- **`frontend/src/hooks/usePlans.js`** — SSR-safe prerender fix:
  - Added `STATIC_PLANS` constant matching the `plan_config` table seeds (migration 0008). Returned immediately during SSR (no `window`) so prerendered HTML at `/pricing` and `/` contains real pricing content instead of empty skeleton placeholders.
  - Added `annualMonthlyEquivalent(cents)` helper — returns the monthly-equivalent price when billing annually (10 months paid for 12; 2 months free).
  - Added `formatAnnualTotal(cents)` helper — formats the total annual charge (e.g. `€90 / year`).
- **`src/pages/LandingPage.jsx`** — annual billing toggle:
  - New local `BillingToggle` component (accessible `role="switch"`, animated pill, savings badge).
  - `PricingCard` extended with `annualMonthlyPrice`, `annualTotal`, and `annual` props.
  - Toggle state (`annual`) controls which price and total are displayed on each card.
  - Uses `annualMonthlyEquivalent` + `formatAnnualTotal` from `usePlans`.
- **`src/pages/PricingPage.jsx`** — same `BillingToggle` + extended `PricingCard` as `LandingPage`.
- **i18n** (`en`, `fr`, `de`, `es`) — added 3 new keys to both `landing` and `pricing` namespaces:
  - `billing_monthly`, `billing_annual`, `billing_annual_savings`

### No backend changes — 202 tests still passing.

---

## Session 29 additions (annual billing on Billing page)

### Backend

- **`app/schemas/billing.py`** — added `annual: bool = False` field to `CheckoutRequest`. When `True`, the checkout endpoint routes to the annual Stripe price.
- **`app/api/billing.py`** — passes `annual=body.annual` through to `create_checkout_session`.
- **`app/services/billing.py`** — `create_checkout_session` accepts new `annual: bool = False` parameter:
  - When `annual=True` and `plan_config.stripe_price_id_annual` is set, that price ID is used.
  - When `annual=True` and no annual price ID is configured, inline `price_data` is built with `interval: year` and `unit_amount = base_price_cents * 10` (2 months free).
  - Embeds `billing_period: "annual" | "monthly"` in Stripe session metadata.
  - Monthly path unchanged: prefers `stripe_price_id`, then global `STRIPE_PRICE_ID` env var, then inline monthly `price_data`.

### Frontend

- **`src/pages/Billing.jsx`** — annual billing toggle on the upgrade section:
  - New local `BillingToggle` component (identical design to LandingPage/PricingPage: accessible `role="switch"`, animated pill, savings badge).
  - `annual` state (`useState(false)`) added to the Billing component.
  - Toggle placed inline with the "Upgrade your plan" heading.
  - Each plan radio shows the annual-equivalent monthly price and annual total when the toggle is active.
  - `handleUpgrade` passes `annual` as the fifth argument to `billingClient.createCheckoutSession`.
- **`src/lib/organisations.js`** — `billingClient.createCheckoutSession` accepts new `annual = false` parameter and sends it as `annual` in the JSON body.
- **i18n** (`en`, `fr`, `de`, `es`) — added 3 new keys to the `billing` namespace:
  - `billing_monthly`, `billing_annual`, `billing_annual_savings`
  (These keys already existed in `landing` and `pricing` namespaces from session 28.)

### 202 tests still passing (no new test files needed — backend change is an additive param with `False` default).

---

## Session 32 additions (DocumentView simplification + deploy)

### Frontend

- **`src/pages/DocumentView.jsx`** — inline amendment submission removed:
  - `AmendmentForm` component (≈190 lines) deleted from `DocumentView.jsx`. All contributor submissions now go through the dedicated `ContributorSubmission` page.
  - `showAmendForm` state and `handleAmendmentCreated` handler removed.
  - "+ Propose amendment" `<button>` replaced with a React Router `<Link>` to `/orgs/:slug/documents/:id/contribute`. Styled identically (primary button). Hidden when `doc.status === 'closed'`.
  - Empty-amendments fallback no longer conditioned on `!showAmendForm` (always shown when list is empty).
  - Reuses existing `document.propose_amendment` i18n key — no translation changes required.
- **`feat/session-31` and `feat/session-32` merged to `main`** and deployed to production VPS.

### Backend — migration fixes

Three root bugs fixed to support a fresh-database deploy (new volume after `docker compose down`):

1. **Migration 0001** — `sa.Enum(..., create_type=False)` in `op.create_table()` columns was not preventing SQLAlchemy's asyncpg ORM event hook from re-creating the type; replaced with `postgresql.ENUM(name=..., create_type=False)` from `sqlalchemy.dialects.postgresql`. Enum pre-creation now uses PL/pgSQL `DO $$ BEGIN ... EXCEPTION WHEN duplicate_object THEN NULL; END $$` blocks instead of `Enum.create(checkfirst=True)`.
2. **Migration 0001** — `amendments` table and `amendment_status` enum were missing from 0001, causing migration 0004 (`ALTER TYPE amendment_status ADD VALUE`) to fail with "type does not exist" on a fresh DB.
3. **Migration 0005** — same `sa.Enum` ORM event hook issue; fixed with the same `postgresql.ENUM` + PL/pgSQL approach.

### Production VPS status
- All 5 Docker containers healthy (db, redis, backend, frontend, nginx).
- All 9 migrations applied to a fresh PostgreSQL volume.
- Nginx running in HTTP-only mode (`docker-compose.local.yml` override) — TLS via Let's Encrypt not yet provisioned on this VPS.
- Port 80 conflict note: `otherapp-nginx-1` (separate service on the same VPS) was temporarily stopped to allow Amendly nginx to bind to port 80. Consider provisioning a dedicated VPS or host-level nginx as reverse proxy for both services.

### 202 tests still passing.

---

## Session 31 additions (ContributorSubmission page)

### Frontend

- **`src/pages/ContributorSubmission.jsx`** — rewritten from stub to a fully wired amendment submission form:
  - Route changed from `/contributor/submit` to `/orgs/:slug/documents/:id/contribute` (consistent with existing routing patterns; reads both params from React Router).
  - Fetches the document on mount via `orgClient.getDocument(slug, docId)` to display the title and body as submission context.
  - Shows a "closed" banner and disables the form when `doc.status === 'closed'`.
  - Collects `section` (optional), `original_text` (required), `proposed_text` (required), `justification` (optional) — exactly matching the backend `AmendmentCreate` schema.
  - **Live diff preview**: client-side LCS word-differ (`computeClientDiff`) renders inline tokens using the canonical diff colour tokens (`#dbe1ff`/`#003798` for additions, strikethrough `#717c82` for deletions). No extra API call needed.
  - On submit calls `orgClient.createAmendment(slug, docId, payload)`.
  - On success shows a 1.5 s success flash then navigates to `/orgs/:slug/documents/:id`.
  - Breadcrumb nav: Dashboard → org slug → document title → Submit amendment.
  - Sidebar: Submission Tips card + "What happens next" card (both fully localised).
  - JSDoc on all components and helper functions; fully localised via new `contributor` i18n namespace.
- **`src/AppRoutes.jsx`** — route updated from `/contributor/submit` to `/orgs/:slug/documents/:id/contribute`.
- **i18n** (`en`, `fr`, `de`, `es`) — added `contributor` namespace (20 keys each): `breadcrumb`, `context_label`, `original_doc_label`, `diff_label`, `diff_hint`, `diff_placeholder`, `tips_title`, `tip_1/2/3_title`, `tip_1/2/3_body`, `next_title`, `next_1/2/3`, `back_to_document`, `success`.

### No backend changes — 202 tests still passing.

---

## Session 30 additions (prerender validation + branch merge + deploy)

- **Prerender validation** — `npm run build` confirmed `dist/pricing/index.html` contains real plan prices (`€9`, `€29`, `€99`) with no skeleton or loading states. Both `/pricing` and `/` prerender correctly from `STATIC_PLANS` in `usePlans.js` (SSR path, no backend needed at build time).
- **Backend container rebuilt** — `docker compose up -d --build backend` required to mount the new session-27 files (`admin.py`, `plans.py`, `plan_config.py`, etc.) into the running container. 202 tests confirmed after rebuild.
- **Sessions 24–27 committed** — all previously untracked files (admin API, plan_config model/service/schema, migrations 0008–0009, AdminPricing page, Dockerfile.dev, deploy scripts, docker-compose.local.yml, nginx.local.conf, docs/marketing/) committed on `feat/session-28`.
- **Merged into `main`** — `feat/session-28` merged via fast-forward and deployed to VPS.
- **iCloud duplicate files** (filenames containing ` 2`) left untracked and excluded from all commits — they are older versions created by iCloud sync conflict resolution.

---

## Session 26 additions (launch finalisation)

- **`/pricing` page** — `src/pages/PricingPage.jsx` — dedicated public page with Free/Pro pricing cards, 5-item FAQ, and CTA. Prerendered (added to `scripts/prerender.js`). JSON-LD `SoftwareApplication` structured data. Fully localised via new `pricing` namespace in all 4 i18n files (`en`, `fr`, `de`, `es`). `useSeoMeta` provides unique `<title>`, `<meta description>`, canonical, hreflang, and `og:locale`.
- **`AppRoutes.jsx` updated** — new `<Route path="/pricing" element={<PricingPage />} />` registered alongside the other public routes.
- **`sitemap.xml` updated** — `/pricing` added with `priority=0.9` (below `/` at 1.0, above `/login` at 0.7).
- **`LandingPage.jsx` footer fixed** — `<a href="/legal/terms">` and `<a href="/legal/privacy">` converted to `<Link to="…">` so navigation does not trigger a full page reload. Pricing link added to the Product column.
- **Lighthouse CI** — `.github/workflows/ci.yml` gets a new `lighthouse` job (runs after `frontend-lint`). Builds the full production bundle, serves it with `http-server`, and runs `@lhci/cli` against 5 public URLs. Thresholds: Accessibility ≥ 90 (error), SEO ≥ 90 (error), Performance ≥ 80 (warn), Best Practices ≥ 90 (warn). Results uploaded to LHCI temporary public storage.
- **Google Search Console placeholder** — `frontend/public/google-site-verification.html` with step-by-step instructions for replacing it with the real file downloaded from GSC when the property is registered.
- **Dockerfile build pipeline confirmed** — `npm run build` in `frontend/Dockerfile` already executes all three steps (client + SSR + prerender). No change needed.

---

## Session 33 additions (deploy hardening + VPS TLS architecture)

### deploy.sh — iCloud exclude

- **`scripts/deploy.sh`** — added `--exclude='* 2.*'` to the rsync call. Prevents iCloud sync-conflict duplicate files (filenames containing ` 2`, e.g. `"activity 2.py"`) from being transferred to the VPS and breaking Alembic migration detection.

### VPS TLS / nginx conflict — Option B (host-level nginx)

The root cause: both Amendly and OtherApp compete for port 80 on the same Hetzner VPS. The chosen solution is a **host-level nginx** that owns ports 80 and 443, terminates TLS, and reverse-proxies to each app on its own internal port.

Three new files implement this:

- **`nginx/nginx.vps-host.conf`** — Host nginx virtual-host config for `amendly.eu`.
  - HTTP → HTTPS redirect (with ACME challenge pass-through for certbot).
  - HTTPS → `http://127.0.0.1:8081` (Amendly Docker nginx).
  - Security headers: HSTS, X-Frame-Options, X-Content-Type-Options, X-XSS-Protection.
  - Installed at `/etc/nginx/sites-available/amendly.eu.conf` on the VPS.

- **`docker-compose.vps.yml`** — Docker Compose overlay for the VPS.
  - Overrides the Amendly nginx service to bind host port `8081:80` (instead of `80:80` / `443:443`).
  - Used with: `docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d --build`
  - The Amendly Docker nginx no longer terminates TLS — that is handled by the host nginx.

- **`scripts/setup-vps-nginx.sh`** — One-time setup script (run as root on VPS).
  - Installs `nginx` and `certbot` + `python3-certbot-nginx` via apt.
  - Deploys `nginx.vps-host.conf` to `/etc/nginx/sites-available/`.
  - Issues a Let's Encrypt certificate for `amendly.eu` and `www.amendly.eu`.
  - Adds the WebSocket upgrade map to `/etc/nginx/nginx.conf` if absent.
  - Supports `--domain`, `--email`, and `--dry-run` flags.

### VPS migration sequence

```
# On the VPS (as root):
cd /opt/amendly

# 1. Stop the Amendly stack to free port 80
docker compose down

# 2. Run the host nginx setup (provisions TLS + certbot)
sudo bash scripts/setup-vps-nginx.sh

# 3. Restart the Amendly stack on port 8081
docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d --build

# 4. Smoke test
curl -s https://amendly.eu/api/health
```

### Stripe end-to-end test checklist (deferred from session 32)

The following steps should be executed manually once the VPS has TLS:

1. Set `SUPERUSER_EMAIL=<your email>` in VPS `.env` and redeploy.
2. Log into `/admin/pricing` — enter real Stripe test-mode Price IDs (monthly + annual) for each plan and save.
3. Navigate to `/orgs/:slug/billing` as org owner — test checkout for monthly and annual paths.
4. On a local machine, run `stripe listen --forward-to localhost:8000/api/billing/webhook` (Stripe CLI) and repeat checkout to verify the webhook fires.
5. Confirm `org.plan` is set correctly in the DB after `checkout.session.completed`.
6. Trigger `customer.subscription.deleted` via Stripe dashboard — confirm `org.plan` reverts to `solo`.

### 202 tests still passing (no backend changes this session).

---

## Session 34 additions (deploy.sh --vps flag + operational guides)

### scripts/deploy.sh — `--vps` flag

- **New `--vps` flag** — when passed, `COMPOSE_CMD` is set to
  `docker compose -f docker-compose.yml -f docker-compose.vps.yml` so the
  Amendly nginx container binds to host port `8081` (host nginx owns 80/443).
  Without `--vps` the script uses plain `docker compose` (original behaviour).
- **Smoke test** — when `--vps` is active the smoke test runs locally on the
  developer machine: `curl -sf https://amendly.eu/api/health`. Without `--vps`
  it SSH-tunnels to check `http://localhost/api/health` on the VPS as before.
- **Summary** — prints `https://amendly.eu` as the app URL when `--vps` is set;
  `http://<REMOTE_HOST>` otherwise.

**Updated usage:**
```bash
./scripts/deploy.sh                          # plain deploy (port 80)
./scripts/deploy.sh --vps                    # VPS with host nginx (port 8081)
./scripts/deploy.sh --vps --skip-migrations  # re-deploy code only
./scripts/deploy.sh --dry-run --vps          # preview VPS deploy commands
```

### VPS TLS migration — manual steps (completed on VPS)

The following one-time operations are performed on the Hetzner VPS as root:

```bash
cd /opt/amendly

# 1. Stop the Amendly stack (frees port 80 for host nginx)
docker compose down

# 2. Run the host nginx setup (installs nginx + certbot, issues TLS cert)
sudo bash scripts/setup-vps-nginx.sh

# 3. Start the Amendly stack on port 8081
docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d --build

# 4. Smoke test
curl -s https://amendly.eu/api/health
# Expected: {"status":"ok"}
```

After this the deploy script is called with `--vps` for all future deploys.

### Stripe end-to-end testing — manual steps

Prerequisites: VPS has TLS, `SUPERUSER_EMAIL` is set in VPS `.env`.

1. Log into `https://amendly.eu/admin/pricing`
2. Enter real Stripe **test-mode** Price IDs (monthly + annual) for each plan and save.
3. Navigate to `/orgs/:slug/billing` as org owner.
4. Test monthly checkout: select a paid plan, click Upgrade, complete with Stripe test card `4242 4242 4242 4242`.
5. Test annual checkout: toggle the billing period switch, click Upgrade, complete.
6. Verify `org.plan` changed in the DB:
   ```bash
   ssh root@your-server.example.com \
     "cd /opt/amendly && docker compose exec db psql -U amendly -c \
      \"SELECT name, plan FROM organisations;\""
   ```
7. Webhook verification (local machine with Stripe CLI):
   ```bash
   stripe listen --forward-to localhost:8000/api/billing/webhook
   # In a separate terminal: re-run a checkout, watch the CLI output
   ```
8. Cancel the subscription via Stripe Dashboard → confirm `org.plan` reverts to `solo`.

### No backend or test changes — 202 tests still passing.

---

## Session 36 additions (VPS TLS provisioning)

### Infrastructure

- **VPS TLS live** — DNS confirmed propagated (`amendly.eu` → `YOUR_SERVER_IP`). Let's Encrypt
  certificate issued for `amendly.eu` and `www.amendly.eu` via `certbot --nginx`.
  Certificate expires 2026-06-21; auto-renewal managed by certbot systemd timer.

- **Host nginx installed** — nginx 1.24 installed on the Hetzner VPS host OS.
  Config at `/etc/nginx/sites-available/amendly.eu.conf` (deployed by `setup-vps-nginx.sh`).
  Handles port 80 → HTTPS redirect and port 443 → `http://localhost:8081` proxy.
  HSTS, X-Frame-Options, X-Content-Type-Options, X-XSS-Protection headers set.

- **`nginx/nginx.vps.conf`** (new) — HTTP-only internal router for the Docker nginx container
  in VPS mode. Proxies `/api/` → `backend:8000` and `/` → `frontend:80`. No TLS,
  no `${DOMAIN}` placeholders. Used by the VPS overlay volume mount.

- **`docker-compose.vps.yml`** — fixed: now overrides `volumes` to mount `nginx.vps.conf`
  as the active `/etc/nginx/nginx.conf`, and overrides `command` to run nginx directly
  (no envsubst). The `!reset` tag approach was dropped; instead the base `docker-compose.yml`
  was updated to have no `ports` on the nginx service (ports live in overlays only).

- **`docker-compose.yml`** — removed hardcoded `ports: ["80:80", "443:443"]` from the nginx
  service. Ports are now entirely in overlay files:
  - `docker-compose.prod.yml` — classic self-hosted TLS (ports 80/443)
  - `docker-compose.vps.yml` — host-nginx mode (port 8081 only)

- **`docker-compose.prod.yml`** (new) — provides `ports: ["80:80", "443:443"]` for the nginx
  service when running in classic self-hosted TLS mode (no host nginx).

### VPS status (session 36)

- All 5 Docker containers healthy (db, redis, backend, frontend, nginx) on port 8081.
- Host nginx is live on ports 80 and 443. TLS working locally on VPS.
- **Hetzner Cloud Firewall must allow TCP port 443 inbound** — currently blocked at the
  cloud-network level (not the OS firewall). Configurable in Hetzner Cloud Console.
  Port 80 is already open. Once 443 is opened, `https://amendly.eu/api/health` will respond.

### Frontend companion changes (committed in session 36)

- **`src/components/Logo.jsx`** (new) — brand SVG logo component. Used by `PublicHeader`
  and `PublicFooter` instead of plain text.
- **`src/components/HeroDashboardIllustration.jsx`** (new) — self-contained SVG/JSX
  illustration for the landing page hero section; replaces Google-hosted image URL.
- **`src/pages/LandingPage.jsx`** — "How it works" steps now use local `/images/*.png`
  instead of Google-hosted URLs; hero uses `HeroDashboardIllustration`.
- **`frontend/public/images/`** — added `how_it_works_step_{1,2,3}.png` (local assets).
- **`frontend/DESIGN.md`** — section 8 added: Amendly colour palette from Gemini Canvas.

### No backend or test changes — 202 tests still passing.

---

## Session 37 additions (Billing page bugfix + Stripe E2E runbook)

### Frontend

- **`src/pages/Billing.jsx`** — bugfix: removed `'solo'` from the `isPaid` array.
  Solo is the default free-tier plan. The bug caused solo-plan orgs to display
  the manage-subscription UI (Customer Portal link) instead of the upgrade UI
  (plan selector + checkout CTA). The fix ensures solo-plan orgs always see the
  upgrade flow. No other code changes required.

### Stripe E2E operational runbook (manual steps — no code changes needed)

All billing code (checkout, portal, webhook) was fully implemented in sessions
27–29. This session documents the manual steps to complete the E2E test:

1. **Open Hetzner Cloud Firewall port 443** in Cloud Console → Firewalls → Inbound rules.
   Verify: `curl -sf https://amendly.eu/api/health` → `{"status":"ok","version":"0.1.0"}`

2. **Set `SUPERUSER_EMAIL`** in VPS `.env`, redeploy `.env` only:
   ```bash
   ./scripts/deploy.sh --vps --skip-rsync --skip-migrations
   ```

3. **Enter real Stripe test Price IDs** at `https://amendly.eu/admin/pricing`:
   - Create products in Stripe Dashboard (test mode) for Team and Organisation plans.
   - Copy monthly + annual Price IDs and save via the admin UI.

4. **Test checkout flows** at `/orgs/:slug/billing`:
   - Monthly: select Team, toggle off annual, click Upgrade, use card `4242 4242 4242 4242`.
   - Annual: toggle annual on, click Upgrade.
   - Verify in DB: `SELECT name, plan FROM organisations;`

5. **Set `STRIPE_WEBHOOK_SECRET`** in VPS `.env`:
   - Add webhook endpoint in Stripe Dashboard: `https://amendly.eu/api/billing/webhook`
   - Events: `checkout.session.completed`, `customer.subscription.deleted`
   - Copy signing secret (`whsec_…`) to `.env`, redeploy `.env`.
   - Test: `stripe listen --forward-to https://amendly.eu/api/billing/webhook`

6. **Test subscription cancellation**:
   - Cancel in Stripe Dashboard → confirm org plan reverts to `solo` in DB.

### Post-launch tasks (to do after Stripe E2E)

- **Google Search Console**: register `https://amendly.eu`, verify via HTML file
  (`frontend/public/google-site-verification.html` placeholder already exists),
  submit `https://amendly.eu/sitemap.xml`.
- **Plausible analytics**: set `VITE_PLAUSIBLE_DOMAIN=amendly.eu` in VPS `.env`,
  redeploy. Analytics activates only after user accepts GDPR cookie consent.

### 202 tests still passing (no backend changes).

---

## Session 35 additions (landing page refresh + annual-first billing)

### Frontend

- **`src/components/PublicHeader.jsx`** (new) — shared sticky header for all public pages.
  Glass-morphism style (`bg-white/80 backdrop-blur-md`). Desktop nav links (Features, How It Works, Pricing, Contact). Language switcher + Sign In + Get Started CTAs. Uses `amendly-blue` design token.
- **`src/components/PublicFooter.jsx`** (new) — shared footer for all public pages.
  5-column grid (brand + socials, Product, Company, Resources, Legal). All links are React Router `<Link>` — no full-page reloads.
- **`src/pages/LandingPage.jsx`** — hero section redesigned with `PublicHeader` / `PublicFooter`. Old inline `<header>` and `<footer>` removed. Annual billing toggle now defaults to `true` (annual-first, per GTM recommendation).
- **`src/pages/PricingPage.jsx`** — inline header/footer replaced with `PublicHeader` / `PublicFooter`. Annual toggle defaults to `true`.
- **`src/pages/TermsPage.jsx`** — inline minimal header/footer replaced with `PublicHeader` / `PublicFooter`.
- **`src/pages/PrivacyPage.jsx`** — inline minimal header/footer replaced with `PublicHeader` / `PublicFooter`.
- **`src/pages/Billing.jsx`** — annual billing toggle now defaults to `true` (annual-first).
- **`tailwind.config.js`** — added `amendly-blue` (`#2563eb`), `amendly-dark` (`#1e293b`), `amendly-gray` (`#64748b`) colour tokens; added `dot-pattern` background image utility (`radial-gradient`).
- **`src/index.css`** — added `.bg-dots` (20px background-size) and `.hero-gradient` utility classes used by the landing hero section.

### Annual-first billing rationale

GTM doc (section 18) explicitly states: *"Annual billing should be presented as the default on the pricing page, with monthly as the alternative. Reduces churn and improves cash flow."* All three billing surfaces (`LandingPage`, `PricingPage`, `Billing`) now default to `annual = true`.

### VPS status (session 35)

- DNS for `amendly.eu` not yet pointed to VPS (IP: `2a01:4f9:c011:9ce2::1`). TLS provisioning is blocked on DNS.
- Docker stack healthy on VPS (all 5 containers), serving HTTP on port 80.
- `docker-compose.vps.yml` not yet on VPS — will be transferred on next `./scripts/deploy.sh --vps`.
- `setup-vps-nginx.sh` not yet run on VPS.
- Full TLS + Stripe E2E checklist deferred to next session once DNS propagates.

### No backend or test changes — 202 tests still passing.

## Session 42 additions (rich text, amendment types, decision reasons, email redesign)

### Backend

- **`app/models/amendment.py`** — new `AmendmentType` enum (`text_change | general_comment`); `amendment_type` column (NOT NULL, default `text_change`); `original_text` and `proposed_text` made nullable; new `decision_reason` column (nullable Text).
- **`app/schemas/amendment.py`** — `AmendmentCreate` gains `amendment_type` + model-level validator (requires `original_text`/`proposed_text` for `text_change`; requires `justification` for `general_comment`); `AmendmentStatusUpdate` gains optional `decision_reason`; `AmendmentResponse` exposes both new fields.
- **`app/services/amendment.py`** — `_format_amendment` serialises `amendment_type` and `decision_reason`; `create_amendment` sets `amendment_type`; `update_amendment_status` persists `decision_reason`.
- **`app/api/amendments.py`** — diff endpoint returns empty tokens for `general_comment` amendments (no original/proposed text to diff).
- **`app/services/email.py`** — welcome email fully redesigned: "The Editorial Ledger" branded header (Primary Deep Slate + "A" lettermark), personalised greeting using `name` parameter, numbered steps with filled circle markers, Professional Blue CTA button, VML Outlook fallback, `amendly.eu` below-card label.
- **`migrations/versions/0010_amendment_type_and_decision_reason.py`** — adds `amendment_type` enum column, makes `original_text`/`proposed_text` nullable, adds `decision_reason` column.  PostgreSQL uses native `ENUM`; SQLite uses `batch_alter_table` + `VARCHAR`.

### Frontend

- **`package.json`** — added `@tiptap/react ^2.11.5`, `@tiptap/pm ^2.11.5`, `@tiptap/starter-kit ^2.11.5`, `dompurify ^3.2.4`.
- **`src/components/RichTextEditor.jsx`** (new) — TipTap-based WYSIWYG editor with Editorial Ledger styling. Toolbar: Bold, Italic, H2, H3, Bullet list, Ordered list, Blockquote.  SSR-safe (returns `null` until editor hydrates).
- **`src/lib/sanitize.js`** (new) — `sanitizeHtml(html)` strips dangerous tags before `dangerouslySetInnerHTML`. Browser: DOMPurify (lazy-loaded). SSR fallback: strips all tags with regex.
- **`src/pages/DocumentView.jsx`**:
  - Body display detects HTML content (starts with `<`) → renders via `dangerouslySetInnerHTML` with Tailwind arbitrary-value prose classes; falls back to `<pre>` for legacy plain-text bodies.
  - `EditDocumentForm` body textarea replaced with `RichTextEditor`.
  - `ConsolidatedPanel` body renderer upgraded to same HTML/plain-text dual rendering.
  - `AmendmentCard` handles `general_comment` type (shows comment body instead of diff; skips diff API call). Inline decision-confirmation panel replaces one-click accept/reject: textarea for optional decision reason, confirm + cancel buttons.
  - `handleAmendmentStatus` passes `decisionReason` to `orgClient.updateAmendmentStatus`.
- **`src/pages/ContributorSubmission.jsx`** — type toggle (text_change / general_comment); conditional field rendering; `amendment_type` passed in submission payload; separate validation path for each type.
- **`src/lib/organisations.js`** — `updateAmendmentStatus` accepts and forwards optional `decisionReason` in request body.
- **`src/i18n/{en,fr,de,es}.json`** — 14 new keys: `body_placeholder`, `amendment_type_label`, `type_text_change`, `type_general_comment`, `comment_label`, `comment_placeholder`, `comment_required`, `decision_reason_placeholder`, `decision_reason_block_label`, `confirm_accept`, `confirm_reject`.

## Session 42b additions (DOCX import)

### Backend

- **`app/utils/docx_import.py`** (new) — `docx_bytes_to_html(file_bytes) → str` converts a `.docx` file to clean HTML. Mapping: `Heading 1 → <h2>`, `Heading 2/3 → <h3>`, `List Bullet → <ul><li>`, `List Number → <ol><li>`, all others → `<p>`. Inline formatting: bold → `<strong>`, italic → `<em>`. 10 MB size guard. Falls back gracefully on unrecognised styles.
- **`app/api/documents.py`** — new `POST /api/organisations/{slug}/documents/extract-docx` endpoint (`multipart/form-data`). Returns `{ html: string, char_count: int }`. Gated on org membership (any role). Does NOT save the document — the caller handles persistence via the existing `PUT /{doc_id}` endpoint.

### Frontend

- **`src/lib/organisations.js`** — `orgClient.extractDocx(slug, file)` sends the File as `FormData` (no `Content-Type` header — browser sets boundary automatically).
- **`src/pages/DocumentView.jsx`** — `EditDocumentForm` gains an "Import .docx" button above the TipTap editor. Clicking opens a native file picker (`.docx` filter). On selection, calls `orgClient.extractDocx()`, loads the returned HTML into TipTap. Import errors shown inline. Existing body is replaced (with TipTap's undo history intact).
- **`src/i18n/{en,fr,de,es}.json`** — 2 new keys: `import_docx`, `importing_docx`.

## Session 85b additions (PDF import hardening)

### Backend

- **`app/utils/pdf_import.py`** (new) — `pdf_bytes_to_html(file_bytes) -> str` extracts basic text from uploaded PDFs with `pypdf`, converts blank-line-separated blocks into `<p>` tags, and inserts `<hr>` between pages. 25 MB size guard.
- **`app/api/documents.py`** — new `POST /api/organisations/{slug}/documents/extract-pdf` endpoint (`multipart/form-data`). Returns `{ html: string, char_count: int }`. Gated on org membership (any role). Does NOT save the document.

### Frontend

- **`src/lib/organisations.js`** — added `orgClient.extractPdf(slug, file)` mirroring the existing DOCX extraction flow.
- **`src/pages/DocumentView.jsx`** and **`src/pages/OrgDetail.jsx`** — PDF import now uses the backend extraction endpoint instead of `pdf.js` in the browser, avoiding worker/MIME/runtime compatibility failures on client devices.
- **`src/pages/OrgDetail.jsx`** — the `New document` action in the Documents tab is now a primary CTA button instead of a low-contrast text link.

## Session 90 additions (document import audit — security, UX, quality, robustness)

### Backend

- **`app/utils/pdf_import.py`** — `MAX_BYTES` harmonised to 10 MB (was 25 MB). `PdfImportResult` gains `warnings: list[str]`. Table detection via `page.extract_tables()` adds `"tables_ignored"` warning when tables are present. `_looks_like_title()` relaxed: max length 200 chars, max 20 words, capitalisation condition removed (too fragile for French).
- **`app/utils/docx_import.py`** — `docx_bytes_to_html()` now returns `DocxImportResult(html, warnings)` instead of a bare string. Table detection via `doc.tables` adds `"tables_ignored"` warning. `_runs_to_html()` now accepts a `Paragraph` object and iterates XML children to emit `<a href="…">` hyperlinks for supported schemes (http/https/mailto). New `_detect_indent_level()` helper returns a zero-based nesting level from `w:ilvl` or left-indent; list items carry `data-level` attributes. Error messages standardised to French ("Fichier trop volumineux. Taille maximale : 10 Mo.").
- **`app/api/documents.py`** — Both extract endpoints now: (1) validate magic bytes (`%PDF` / `PK`) and return 400 with a clear message on mismatch; (2) emit structured `logger.info("document_import", extra={…})` logs with org slug, user ID, file size, char count, and warnings; (3) expose `warnings: list[str]` in `ExtractDocxResponse` and `ExtractPdfResponse`.

### Frontend

- **`src/lib/sanitize.js`** — DOMPurify switched from dynamic async import to static import, eliminating the race condition where `sanitizeHtml()` could be called before DOMPurify loaded. `initDOMPurify()` kept as a no-op for backward compatibility. `a` added to `ALLOWED_TAGS`; `href`, `target`, `rel` added to `ALLOWED_ATTR`.
- **`src/lib/documentImport.js`** — `fetch` replaced by `XMLHttpRequest` to support `upload.progress` events. `extractDocxFile()` and `extractPdfFile()` accept an optional `{ onProgress }` callback (percent 0–100, then `'processing'`).
- **`src/pages/DocumentView.jsx`** — `EditDocumentForm` gains: (a) client-side file validation (size > 10 MB, wrong MIME/extension) before upload; (b) `window.confirm` overwrite guard when body is non-empty; (c) a thin `h-1` progress bar with indeterminate animation during backend processing; (d) a 6-second auto-dismissing post-import toast showing section count, character count, and table warnings.
- **`src/index.css`** — `@keyframes progress-slide` for indeterminate progress bar; CSS rules for `li[data-level]` to visually indent nested imported list items.
- **`src/i18n/{en,fr,de,es}.json`** — 11 new keys: `import_overwrite_confirm`, `import_error_too_large`, `import_error_format_pdf`, `import_error_format_docx`, `import_processing`, `import_success`, `import_sections`, `import_chars`, `import_tables_ignored`.
- **`src/main.jsx`** — `initDOMPurify()` call removed (no longer needed with static import).

## Session 57 additions (spam protection + i18n fixes)

### Backend (`app/api/auth.py`, `app/core/config.py`)

- **Rate limiting** — Redis-backed counter applied to `POST /api/auth/magic-link/request`: 5 req/min per IP (`_RL_IP_MAX`), 3 req/10min per email (`_RL_EMAIL_MAX`). Limits are hardcoded constants in `app/api/auth.py` (not env-var configurable).
- **Cloudflare Turnstile verification** — shared helper in `backend/app/utils/turnstile.py` verifies challenge tokens against `https://challenges.cloudflare.com/turnstile/v0/siteverify`, validates the expected `action`, and rejects hostname mismatches against `DOMAIN` / `ALLOWED_ORIGINS_RAW`. In production the helper defaults to fail-closed on upstream errors; in development/tests it still fail-opens unless a caller overrides it. Enforcement is standardised across magic-link login, waitlist, invitations, and public contribution. Verification is skipped when the secret is unset or explicitly set to `test`.
- **Disposable email blocklist** — a hardcoded set of disposable email domains is checked at magic-link request time; requests from those domains receive a 422.
- New env vars: `TURNSTILE_SECRET_KEY` (preferred server-side Turnstile secret) and legacy alias `CLOUDFLARE_TURNSTILE_SECRET`.

### Frontend (`frontend/src/pages/Login.jsx`, `frontend/src/lib/auth.js`)

- **Turnstile widgets** — `Login.jsx`, `LandingPage.jsx` waitlist forms, invitation acceptance/invite flows, and `PublicContribution.jsx` embed Turnstile when `VITE_TURNSTILE_SITE_KEY` is set and the hostname is not local. Each flow sends a fixed action string (`auth_magic_link`, `waitlist`, `org_invite`, `invite_accept`, `public_contribution`) that the backend verifies.
- **Route-level lazy loading** — authenticated/dashboard routes in `src/AppRoutes.jsx` are loaded with `React.lazy`, keeping private workspace code out of the landing/login/public-route bundle path.
- **Docker build wiring** — `frontend/Dockerfile` and the `frontend` service in `docker-compose.yml` forward `VITE_TURNSTILE_SITE_KEY` as a build arg so the production bundle contains the Turnstile site key.
- New env var: `VITE_TURNSTILE_SITE_KEY`.

### Nginx (`nginx/nginx.conf`)

- Real IP resolution from `CF-Connecting-IP` header — Cloudflare IPv4 and IPv6 ranges are declared with `set_real_ip_from`; `real_ip_header CF-Connecting-IP` ensures rate-limiting uses the visitor IP rather than the Cloudflare proxy IP.

### i18n

- **FR** — added 3 missing `billing` keys: `plan_solo_desc`, `plan_team_desc`, `plan_org_desc`.
- **DE / ES** — added 25 missing keys: 3 `billing.plan_*_desc`, 15 `org.upgrade_*`, 7 `invite.upgrade_*`.

---

## Session 58 additions (review mode validation + Turnstile E2E audit)

### Validation (no code changes — all features confirmed working)

- **Turnstile E2E** — `Login.jsx` renders the Cloudflare Turnstile widget when `VITE_TURNSTILE_SITE_KEY` is set and the hostname is not local; the resolved token is passed as `turnstile_token` in the POST body; `auth.js:requestMagicLink` passes it as `turnstile_token`; backend verifies via CF API when `CLOUDFLARE_TURNSTILE_SECRET` is set; bypasses silently on `localhost` / `127.0.0.1`. Flow is complete and correct.
- **Review mode** — `GET /api/organisations/{slug}/documents/{id}/review` returns `ReviewResponse` (title, full_diff_tokens, count_*, accepted_amendments with per-amendment diff_tokens). `ReviewView.jsx` is registered at `/orgs/:slug/documents/:id/review`, fetches role + review in parallel, renders stats bar, full-document diff, accepted amendment accordion, and export panel (owner/admin only). Navigation link from `DocumentView.jsx` confirmed. All 16 review i18n keys confirmed present in EN/FR/DE/ES.
- **Export** — `orgClient.exportDocument(slug, docId, format)` fetches `GET …/export?format=…` with the cookie-backed authenticated request helper and triggers browser download. Backend enforces owner/admin plus plan-based format gating; generates DOCX/PDF/TXT/CSV/JSON from consolidated body depending on the plan.

### Documentation fixes

- **ARCHITECTURE.md Session 57 typos corrected**: env var name is `CLOUDFLARE_TURNSTILE_SECRET` (not `CLOUDFLARE_TURNSTILE_SECRET_KEY`); rate limits are hardcoded constants, not env-var configurable.
- `.env.example` was already correct.

---

## Session 59 additions (split-pane UX — DocumentView + ContributorSubmission)

### Frontend

- **`src/pages/DocumentView.jsx`** — layout redesigned from single-column `max-w-3xl` to a full-viewport split-pane (`h-screen flex flex-col`):
  - Left pane (`flex-1 overflow-y-auto`): document header, body (rich text / pre), inline edit form, consolidated panel. Independent scroll.
  - Right pane (`w-[420px] bg-surface-container-low overflow-y-auto`): amendment list with all controls (filters, sort, reaction summary, accept/reject, pagination). Permanently visible alongside the document regardless of document length.
  - No backend changes. No new API calls.

- **`src/pages/ContributorSubmission.jsx`** — layout redesigned from stacked grid to full-viewport split-pane:
  - Breadcrumb moves to a `shrink-0` top bar.
  - Left pane (`flex-1 overflow-y-auto`): full scrollable document body with `cursor-text select-text`. `onMouseUp` handler captures `window.getSelection()` when the selection is within `docBodyRef`. A sticky banner appears showing the truncated selection text with two actions: "Use as original text" (fills `originalText` field, clears selection) and "Clear".
  - Right pane (`w-[480px] bg-surface-container-low overflow-y-auto`): amendment form (type toggle, section, original/proposed text, live diff preview, justification) + tips + what-happens-next panels.
  - Imports added: `useRef` from React, `sanitizeHtml` from `../lib/sanitize` (for rich-text document rendering in left pane).
  - `originalText` field gains a "Clear" button when pre-filled.
  - New i18n keys (`select_hint`, `selection_label`, `use_selection`, `clear_selection`) added to EN/FR/DE/ES. `anchor_not_found` message updated to reference "left" instead of "above".

---

## Session 59 bug-fixes (contributor submission polish)

### Bugs fixed

- **Anchor check broken for HTML documents** — the client-side guard `doc.body.includes(originalText)` compared plain-text selection against raw HTML markup, always failing for rich-text documents. Fixed in `ContributorSubmission.jsx`: skip the `includes()` check when `doc.body.trimStart().startsWith('<')`. Matching fix applied in `backend/app/services/amendment.py` (same `lstrip().startswith('<')` guard) so the backend no longer rejects valid text-change amendments on HTML documents.

- **Selection banner shown for `general_comment` type** — `handleTextSelection` fired regardless of `amendmentType`, showing the "Use as original text" banner even when submitting a general comment (where `original_text` is irrelevant). Fixed with an early-return guard: `if (amendmentType !== 'text_change') return`.

- **Stale selection not cleared on type switch** — switching the toggle to `general_comment` while a selection was pending left the banner visible. Fixed in the `general_comment` toggle `onClick`: clears `selectedText` state and `window.getSelection()`.

- **422 error message garbled** — FastAPI 422 responses carry `detail` as an array of objects; `new Error(array)` coerced to `[object Object]`. Fixed in `handleSubmit` catch block: if `err.detail` is an array, join the `msg` fields with `'; '` for a readable error string.

## Session 77 additions (member invitation improvements + document status workflow)

No backend changes — all existing endpoints were already correct.

### Frontend

- **`src/pages/DocumentView.jsx`** — `StatusSelector` (dropdown with all 3 statuses) replaced by `StatusToggle`:
  - Shows `DocStatusBadge` + a contextual action button for owner/admin.
  - Button label: "Open for amendments" (draft → open), "Close for amendments" (open → closed), "Reopen" (closed → open).
  - Members still see `DocStatusBadge` only (no change).
  - Component still calls `orgClient.updateDocumentStatus` (PUT …/status) under the hood.

- **`src/pages/ContributorSubmission.jsx`** — closed-document handling improved:
  - When `doc.status === 'closed'` and no confirmation screen is active, the right pane shows a friendly full-height message (lock icon + `contributor.doc_closed_title` + `contributor.doc_closed_body` + back link) instead of the disabled form.
  - The `{!confirmedAmendment && (` form conditional now guards on `!isClosed` as well.

- **`src/i18n/{en,fr,de,es}.json`** — new keys added in all 4 languages:
  - `document.close_for_amendments`, `document.reopen`, `document.open_for_amendments`
  - `document.draft_banner_hint` updated to reference the button label instead of the old dropdown.
  - `contributor.doc_closed_title`, `contributor.doc_closed_body`

### Already implemented (confirmed, no changes)

- **`src/pages/OrgDetail.jsx`** — `MembersPanel` already fetches pending invitations (owner/admin only) and renders each with Revoke and Resend action buttons (`orgClient.revokeInvitation` / `orgClient.resendInvitation`). Confirmed present since session 62.

## Session 78 additions (bulk amendment actions + activity CSV export + invitation email polish)

### Backend

- **`app/api/amendments.py`** — new endpoint `PATCH /api/organisations/{slug}/documents/{doc_id}/amendments/bulk-status`: accepts `{ amendment_ids: [], status: "accepted"|"rejected", decision_reason?: string }` and applies the status change to all listed amendments in one request (owner/admin only).

### Frontend

- **`src/pages/DocumentView.jsx`** — `handleBulkAction` now calls the single bulk endpoint instead of N individual calls. Reduces network traffic for bulk accept/reject flows.

- **`src/pages/OrgDetail.jsx`** — "Export CSV" button added to the activity tab (owner/admin only). Calls `GET /api/organisations/{slug}/activity/export` which returns the full activity log as `text/csv`. `ActivityFeed` now accepts a `userRole` prop.

- **`src/i18n/{en,fr,de,es}.json`** — new key `activity.export` added in all 4 languages.

- **Invitation email** — CTA button colour updated from `#515f74` to `#2563EB` (amendly-blue) for stronger visual hierarchy.

## Session 79 additions (amendment search + contributor UX + pending stat shortcut)

### Backend

- **`app/schemas/document.py`** — `DocumentResponse` gains `pending_count: int = 0` field.
- **`app/services/document.py`** — `list_documents` uses a correlated scalar subquery to populate `pending_count` per document row. `_format_doc` accepts an optional `pending_count` parameter.

### Frontend

- **`src/pages/DocumentView.jsx`** — amendment search filter extended to include `section` and `author_name`/`author_email` in addition to `original_text`, `proposed_text`, `justification`.

- **`src/pages/ContributorSubmission.jsx`** — post-submit confirmation screen updated: uses `contributor.amendment_submitted_success` as a compact status label above the title; "Back to document" link replaced by "View all amendments →" (`contributor.view_all_amendments`).

- **`src/pages/OrgDetail.jsx`** — "N pending" stats badge converted to a `<button>`. On click: switches to Documents tab, scrolls to the first document with `pending_count > 0`, or shows an inline toast (`org.stats_no_pending_docs`) if none exists. `useRef` added for per-row element references. `handlePendingStatClick` function added.

- **`src/i18n/{en,fr,de,es}.json`** — new keys added in all 4 languages:
  - `contributor.view_all_amendments`
  - `org.stats_no_pending_docs`

## Session 83 additions (comment notifications)

### Backend

- **`app/models/activity_log.py`** — `ActivityAction` enum gains `amendment_commented` value; docstring updated.
- **`app/utils/email.py`** — two new functions:
  - `_build_amendment_commented_email_html(...)` — branded HTML template with comment preview bubble (blue left-border, truncated to 300 chars) and CTA button.
  - `send_amendment_commented_email(...)` — dispatches the email via Resend (or logs to stdout in dev); errors are caught and logged without aborting the comment creation.
- **`app/services/amendment_comment.py`** — `create_comment` extended:
  - Calls `log_activity(... action=ActivityAction.amendment_commented)` before commit.
  - After commit, loads the amendment author; if the author is a different user, has `email_notifications_enabled=True`, and has not muted the org (`notifications_muted=False` on their `Membership`), calls `send_amendment_commented_email`. All errors in the notification path are silently logged so they cannot abort the comment.
- **`migrations/versions/0021_add_amendment_commented_activity_action.py`** — adds `amendment_commented` to the `activity_action` PostgreSQL enum via `ALTER TYPE … ADD VALUE IF NOT EXISTS`; no-op on SQLite (VARCHAR column).

## Session 84 additions (notification centre — amendment_commented)

### Backend

- **`app/api/notifications.py`** — `GET /api/me/notifications` now includes `amendment_commented` activity entries with targeted delivery: a subquery joins `activity_log` to `amendments` and only returns comment notifications where `amendments.author_id == current_user.id`. All other action types remain org-wide. New imports: `ActivityAction`, `Amendment`, `exists`, `or_`.

### Frontend

- **`NotificationBell.jsx`** — `actionColour()` gains `amendment_commented → 'bg-secondary-container'` (indigo tint, distinct from submitted/accepted/rejected).

### i18n

- All 4 language files (`en`, `fr`, `de`, `es`) gain `notifications.action_amendment_commented` with a personalised label ("X commented on your amendment in {doc}").


## Session 89 additions (onboarding wizard — post-signup flow)

### Backend

- **`app/models/user.py`** — added `onboarding_completed: Mapped[bool]` (default `False`, server_default `"false"`). Docstring updated.
- **`app/api/auth.py`** — `UserResponse` gains `onboarding_completed: bool = False`. New endpoint `POST /api/auth/me/onboarding/complete` — sets `onboarding_completed = True` and returns the updated `UserResponse`.
- **`migrations/versions/0026_add_onboarding_completed.py`** — adds `onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE` to `users`. Existing users receive `FALSE` and will see the wizard on next login.

### Frontend

- **`src/components/OnboardingWizard.jsx`** — complete rewrite. New 3-step flow:
  1. **Profile** — name (required), company, job_position → `PATCH /api/auth/me/profile`
  2. **Create org** — name + slug → `POST /api/organisations` (automatically skipped if user already has orgs)
  3. **Invite colleague** — email → `POST /api/organisations/:slug/invite` (optional, skippable; skipped automatically if no org is available)
  - Trigger: now uses `!user.onboarding_completed` (server-side flag) instead of localStorage key.
  - At end of any path: calls `POST /api/auth/me/onboarding/complete` so the flag is set server-side.
  - Props changed: `organisations` (list), `onClose`, `onOrgCreated`, `onUserUpdated`, `t`.
  - Removed exports `shouldShowOnboarding` / `markOnboardingDone` (localStorage-based helpers, no longer needed).
- **`src/pages/Dashboard.jsx`** — wizard trigger changed from `orgs.length === 0 && shouldShowOnboarding()` to `!me.onboarding_completed`. Passes `organisations`, `onUserUpdated` props to wizard. Removed `shouldShowOnboarding`/`markOnboardingDone` imports.
- **`src/lib/auth.js`** — new `authClient.completeOnboarding()` → `POST /api/auth/me/onboarding/complete`.

### i18n

- All 4 language files (`en`, `fr`, `de`, `es`) — `onboarding` section fully refreshed:
  - Replaced Welcome-screen keys with profile-form keys (`step1_name_label`, `step1_company_label`, `step1_job_label`, etc.).
  - Replaced success-screen `step3_*` keys with invite-step keys (`step3_email_label`, `step3_cta`, `step3_sent_title`, `step3_sent_desc`).
  - New shared keys: `skip`, `done_cta`.
  - `common.saving` and `common.sending` added to all 4 files.
