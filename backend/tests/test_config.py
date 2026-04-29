"""
Configuration tests for backend settings loading.
"""

import pytest

from app.core.config import Settings


def test_settings_ignore_unrelated_env_vars_in_env_file(tmp_path, monkeypatch):
    """
    Settings should load from a repo-root .env file that includes frontend-only keys.

    In containerised environments (e.g. Docker Compose) the real DATABASE_URL and
    related variables are already injected as OS environment variables, which would
    normally take precedence over a .env file in pydantic-settings.  We therefore
    temporarily remove them so the test can assert on the values from the file.

    Parameters:
        tmp_path: pytest temporary directory fixture used to create a throwaway env file.
        monkeypatch: pytest fixture used to temporarily clear OS environment variables.

    Side effects:
        Writes a temporary .env file to disk.
    """
    # Clear variables that Docker Compose injects so the test .env file wins.
    for var in ("DATABASE_URL", "REDIS_URL", "ALLOWED_ORIGINS_RAW", "ENVIRONMENT"):
        monkeypatch.delenv(var, raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "DATABASE_URL=sqlite+aiosqlite:///:memory:",
                "REDIS_URL=redis://localhost:6379",
                "ALLOWED_ORIGINS_RAW=http://localhost:5173,http://127.0.0.1:5173",
                "ENVIRONMENT=development",
                "VITE_PLAUSIBLE_DOMAIN=amendly.eu",
                "VITE_TURNSTILE_SITE_KEY=site-key",
            ]
        ),
        encoding="utf-8",
    )

    parsed = Settings(_env_file=env_file)

    assert parsed.database_url == "sqlite+aiosqlite:///:memory:"
    assert parsed.redis_url == "redis://localhost:6379"
    assert parsed.allowed_origins == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def test_settings_require_jwt_secret_in_production(tmp_path, monkeypatch):
    """Production settings must fail fast when the JWT secret is empty."""
    for var in ("DATABASE_URL", "REDIS_URL", "ALLOWED_ORIGINS_RAW", "ENVIRONMENT", "BETTER_AUTH_SECRET"):
        monkeypatch.delenv(var, raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "DATABASE_URL=sqlite+aiosqlite:///:memory:",
                "REDIS_URL=redis://localhost:6379",
                "ALLOWED_ORIGINS_RAW=https://amendly.eu",
                "ENVIRONMENT=production",
                "BETTER_AUTH_SECRET=",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="BETTER_AUTH_SECRET must be set"):
        Settings(_env_file=env_file)
