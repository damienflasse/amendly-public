import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.activity import router as activity_router
from app.api.amendment_comments import router as amendment_comments_router
from app.api.notifications import router as notifications_router
from app.api.waitlist import public_router as waitlist_router, admin_router as waitlist_admin_router
from app.api.admin import router as admin_router
from app.api.amendments import router as amendments_router, doc_router as amendments_doc_router
from app.api.auth import router as auth_router
from app.api.billing import router as billing_router
from app.api.contribute import router as contribute_router
from app.api.documents import router as documents_router
from app.api.invitations import invite_router, org_router as invite_org_router
from app.api.inbox import router as inbox_router
from app.api.organisations import router as organisations_router
from app.api.plans import router as plans_router
from app.api.resend_webhooks import router as resend_webhooks_router
from app.api.users import router as users_router
from app.core.auth import ensure_superuser_seeded
from app.core.config import settings
from app.core.database import AsyncSessionLocal


_logger = logging.getLogger(__name__)


async def _seed_superuser() -> None:
    """
    Apply the SUPERUSER_EMAIL bootstrap once during application startup.

    Side effects:
        Opens a database session and updates the matching user row when needed.
    """
    async with AsyncSessionLocal() as db:
        await ensure_superuser_seeded(db)


def _log_startup_configuration_warnings() -> None:
    """
    Emit operational warnings for optional-but-important runtime settings.

    Side effects:
        Writes warning and critical messages to the application logger.
    """
    if not settings.better_auth_secret:
        _logger.critical(
            "BETTER_AUTH_SECRET is not set — JWT signing uses an empty secret. "
            "All tokens are trivially forgeable. Set this in production immediately."
        )
    if not settings.stripe_webhook_secret:
        _logger.warning(
            "STRIPE_WEBHOOK_SECRET is not set — Stripe webhook signature "
            "verification is disabled. Set this in production."
        )
    if not settings.resend_prospect_from_email:
        _logger.warning(
            "RESEND_PROSPECT_FROM_EMAIL is not set — prospect outreach emails "
            "will use an empty sender address."
        )
    if not settings.support_inbox_email:
        _logger.warning(
            "SUPPORT_INBOX_EMAIL is not set — contact/support messages will "
            "have no recipient inbox configured."
        )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """
    Run one-time startup tasks and keep them out of deprecated event hooks.

    Side effects:
        Seeds the configured superuser and logs missing production settings.
    """
    await _seed_superuser()
    _log_startup_configuration_warnings()
    yield


app = FastAPI(
    title="Amendly API",
    version="0.1.0",
    docs_url=None if settings.is_production else "/api/docs",
    redoc_url=None if settings.is_production else "/api/redoc",
    openapi_url=None if settings.is_production else "/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "Accept-Language",
        # Amendly tooling auth (API keys / CLI)
        "X-Amendly-Auth-Mode",
        # Stripe webhook signature
        "Stripe-Signature",
        # Resend/Svix webhook signatures
        "Svix-Id",
        "Svix-Timestamp",
        "Svix-Signature",
    ],
)

# Feature routers
app.include_router(auth_router)
app.include_router(organisations_router)
app.include_router(documents_router)
app.include_router(contribute_router)
app.include_router(amendments_router)
app.include_router(amendments_doc_router)
app.include_router(amendment_comments_router)
app.include_router(invite_org_router)
app.include_router(invite_router)
app.include_router(inbox_router)
app.include_router(billing_router)
app.include_router(resend_webhooks_router)
app.include_router(activity_router)
app.include_router(plans_router)
app.include_router(admin_router)
app.include_router(users_router)
app.include_router(notifications_router)
app.include_router(waitlist_router)
app.include_router(waitlist_admin_router)


@app.get("/api/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Return a minimal health payload for smoke checks and monitoring."""
    return {"status": "ok", "version": "0.1.0"}
