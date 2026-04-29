# Amendly — Architecture

This document describes every directory and its purpose.

---

## Repository root

```
amendly/
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
`SUPPORT_INBOX_EMAIL` controls the internal inbox destination for `POST /api/contact` and `POST /api/support`; must be set in production.

---
