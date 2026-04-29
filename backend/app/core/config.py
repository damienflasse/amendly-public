from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # Treat comma-separated env vars as lists instead of trying JSON parse
        env_ignore_empty=True,
    )

    # Database
    database_url: str

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Auth
    better_auth_secret: str = ""

    # OAuth — Google
    google_client_id: str = ""
    google_client_secret: str = ""


    # Email
    resend_api_key: str = ""
    resend_from_email: str = ""
    # Sender for prospect/outreach emails — must be set via RESEND_PROSPECT_FROM_EMAIL env var
    resend_prospect_from_email: str = ""
    resend_webhook_secret: str = ""
    # Internal support inbox — must be set via SUPPORT_INBOX_EMAIL env var
    support_inbox_email: str = ""

    # Sender display name — used in prospect outreach emails (e.g. "Alice - Amendly")
    sender_name: str = ""

    # Payments
    stripe_secret_key: str = ""
    # Webhook signature verification — leave empty to skip (dev only); must be set in production
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""  # Pre-created Stripe Price ID for production (overrides inline price_data)
    stripe_portal_return_url: str = ""  # URL the Customer Portal redirects back to after the session

    # Cloudflare Turnstile
    turnstile_secret_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "TURNSTILE_SECRET_KEY",
            "CLOUDFLARE_TURNSTILE_SECRET",
        ),
    )
    contributor_link_expire_days: int = 30

    # Platform superuser
    superuser_email: str = ""  # When set, this user is granted is_superuser=True on startup

    # Proxy / TLS
    # Set to True only when the backend sits behind a trusted reverse-proxy
    # (nginx, Cloudflare) that sets X-Forwarded-Proto. When False (default),
    # the X-Forwarded-Proto header is ignored — an attacker reaching the
    # backend directly cannot force Secure=False on the session cookie.
    trust_proxy_headers: bool = False

    # App
    environment: str = "development"
    domain: str = "localhost"
    # Stored as a comma-separated string in .env, e.g. "http://localhost:5173,https://app.amendly.eu"
    allowed_origins_raw: str = "http://localhost:5173"

    @property
    def allowed_origins(self) -> list[str]:
        """Parse comma-separated ALLOWED_ORIGINS_RAW env var into a list."""
        return [o.strip() for o in self.allowed_origins_raw.split(",") if o.strip()]

    @property
    def cloudflare_turnstile_secret(self) -> str:
        """Backward-compatible alias for older Turnstile config references."""
        return self.turnstile_secret_key

    @property
    def is_production(self) -> bool:
        """Return True when runtime configuration targets production."""
        return self.environment == "production"

    @field_validator(
        "environment",
        "resend_from_email",
        "resend_prospect_from_email",
        "support_inbox_email",
        mode="before",
    )
    @classmethod
    def strip_inline_env_comments(cls, value: str) -> str:
        """
        Remove trailing inline shell-style comments from email env values.

        `.env` files in this repo sometimes carry explanatory comments on the
        same line as the value. Pydantic may preserve those comments as part of
        the string, which is unsafe for email addresses passed to upstream APIs.
        """
        if not isinstance(value, str):
            return value
        return value.split(" #", 1)[0].strip()

    @model_validator(mode="after")
    def validate_production_security_requirements(self) -> "Settings":
        """
        Reject insecure production configurations at startup.

        Production must not boot with an empty JWT signing secret because that
        would make every access token forgeable.
        """
        if self.is_production and not self.better_auth_secret:
            raise ValueError(
                "BETTER_AUTH_SECRET must be set when ENVIRONMENT=production."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
