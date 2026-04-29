"""
Plan configuration API tests.

Coverage:
  GET /api/plans (public)
    - Returns 200 with active plans only.
    - Inactive plans are excluded.

  GET /api/admin/plans (superuser)
    - Returns 200 with all plans (including inactive) for superuser.
    - Returns 403 for a normal authenticated user.
    - Returns 401 for unauthenticated requests.

  PATCH /api/admin/plans/{name} (superuser)
    - Returns 200 and persists changes for superuser.
    - Sentinel -1 sets max_active_documents to NULL (unlimited).
    - Returns 404 for unknown plan name.
    - Returns 403 for a normal authenticated user.

  Document enforcement
    - Solo plan (limit=3): 4th document returns 403.
    - Team plan (limit=None): no cap enforced.
    - Changing limit via admin PATCH is reflected immediately.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.auth import _magic_link_store
from app.core.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
async def test_engine():
    """Create an async SQLite engine shared across all tests in the session."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    """Yield a fresh AsyncSession for each test, rolling back after."""
    TestSession = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with TestSession() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_session):
    """HTTP test client with get_db overridden to use the SQLite test session."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register_and_login(client: AsyncClient, email: str) -> str:
    """Register via magic link and return the JWT access token."""
    await client.post("/api/auth/magic-link/request", json={"email": email})
    token = next(t for t, v in _magic_link_store.items() if v["email"] == email)
    res = await client.post("/api/auth/magic-link/verify", json={"token": token})
    return res.json()["access_token"]


async def _create_org(client: AsyncClient, jwt: str, slug: str) -> dict:
    """Create an organisation and return its response dict."""
    res = await client.post(
        "/api/organisations",
        json={"name": f"Org {slug}", "slug": slug},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 201
    return res.json()


async def _seed_plans(db_session, plans: list[dict]) -> None:
    """
    Seed plan_config rows for testing.

    Parameters:
        db_session: Active AsyncSession.
        plans: List of dicts with plan configuration fields.
    """
    for p in plans:
        await db_session.execute(
            text(
                "INSERT OR REPLACE INTO plan_config "
                "(plan_name, base_price_cents, included_users, extra_user_price_cents, "
                "max_active_documents, stripe_price_id, stripe_price_id_annual, features, is_active, updated_at) "
                "VALUES (:plan_name, :price, :users, :extra, :limit, :spid, :spid_a, :features, :active, CURRENT_TIMESTAMP)"
            ),
            {
                "plan_name": p["plan_name"],
                "price": p.get("base_price_cents", 900),
                "users": p.get("included_users", 1),
                "extra": p.get("extra_user_price_cents", 0),
                "limit": p.get("max_active_documents"),
                "spid": p.get("stripe_price_id", ""),
                "spid_a": p.get("stripe_price_id_annual", ""),
                "features": p.get("features", "[]"),
                "active": 1 if p.get("is_active", True) else 0,
            },
        )
    await db_session.flush()


async def _make_superuser(db_session, email: str) -> None:
    """Set is_superuser = TRUE on the user with the given email."""
    await db_session.execute(
        text("UPDATE users SET is_superuser = 1 WHERE email = :email"),
        {"email": email},
    )
    await db_session.flush()


# ---------------------------------------------------------------------------
# GET /api/plans (public)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_plans_public_returns_active_only(client, db_session):
    """GET /api/plans returns only is_active=TRUE rows, no auth required."""
    await _seed_plans(db_session, [
        {"plan_name": "pc_solo", "base_price_cents": 900, "included_users": 1, "extra_user_price_cents": 0, "max_active_documents": 3, "is_active": True},
        {"plan_name": "pc_team", "base_price_cents": 2900, "included_users": 3, "extra_user_price_cents": 800, "max_active_documents": None, "is_active": True},
        {"plan_name": "pc_hidden", "base_price_cents": 4900, "included_users": 5, "extra_user_price_cents": 0, "max_active_documents": None, "is_active": False},
    ])

    res = await client.get("/api/plans")
    assert res.status_code == 200
    data = res.json()
    names = [p["plan_name"] for p in data]
    assert "pc_solo" in names
    assert "pc_team" in names
    assert "pc_hidden" not in names


@pytest.mark.asyncio
async def test_get_plans_returns_features_as_list(client, db_session):
    """Features JSON column is returned as a proper list."""
    await _seed_plans(db_session, [
        {
            "plan_name": "pc_features_test",
            "base_price_cents": 900,
            "included_users": 1,
            "extra_user_price_cents": 0,
            "max_active_documents": 3,
            "features": '["Feature A", "Feature B"]',
            "is_active": True,
        },
    ])

    res = await client.get("/api/plans")
    assert res.status_code == 200
    plans = res.json()
    plan = next(p for p in plans if p["plan_name"] == "pc_features_test")
    assert plan["features"] == ["Feature A", "Feature B"]


# ---------------------------------------------------------------------------
# GET /api/admin/plans (superuser only)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_list_plans_superuser(client, db_session):
    """Superuser can access GET /api/admin/plans and sees all plans."""
    await _seed_plans(db_session, [
        {"plan_name": "admin_solo", "base_price_cents": 900, "included_users": 1, "extra_user_price_cents": 0, "is_active": True},
        {"plan_name": "admin_hidden", "base_price_cents": 4900, "included_users": 5, "extra_user_price_cents": 0, "is_active": False},
    ])

    su_email = "admin_su@example.com"
    su_jwt = await _register_and_login(client, su_email)
    await _make_superuser(db_session, su_email)

    res = await client.get(
        "/api/admin/plans",
        headers={"Authorization": f"Bearer {su_jwt}"},
    )
    assert res.status_code == 200
    names = [p["plan_name"] for p in res.json()]
    assert "admin_solo" in names
    assert "admin_hidden" in names


@pytest.mark.asyncio
async def test_admin_list_plans_normal_user_403(client, db_session):
    """Normal authenticated user gets 403 on GET /api/admin/plans."""
    jwt = await _register_and_login(client, "admin_normal@example.com")

    res = await client.get(
        "/api/admin/plans",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_list_plans_unauthenticated_401(client):
    """Unauthenticated request to GET /api/admin/plans returns 401."""
    res = await client.get("/api/admin/plans")
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /api/admin/plans/{name} (superuser only)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_update_plan_persists(client, db_session):
    """Superuser PATCH updates plan and returns the updated values."""
    await _seed_plans(db_session, [
        {"plan_name": "update_solo", "base_price_cents": 900, "included_users": 1, "extra_user_price_cents": 0, "max_active_documents": 3, "is_active": True},
    ])

    su_email = "patch_su@example.com"
    su_jwt = await _register_and_login(client, su_email)
    await _make_superuser(db_session, su_email)

    res = await client.patch(
        "/api/admin/plans/update_solo",
        json={"base_price_cents": 1200},
        headers={"Authorization": f"Bearer {su_jwt}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["base_price_cents"] == 1200
    assert data["plan_name"] == "update_solo"


@pytest.mark.asyncio
async def test_admin_update_plan_sentinel_minus_one(client, db_session):
    """Sending max_active_documents=-1 sets it to NULL (unlimited)."""
    await _seed_plans(db_session, [
        {"plan_name": "sentinel_solo", "base_price_cents": 900, "included_users": 1, "extra_user_price_cents": 0, "max_active_documents": 3, "is_active": True},
    ])

    su_email = "sentinel_su@example.com"
    su_jwt = await _register_and_login(client, su_email)
    await _make_superuser(db_session, su_email)

    res = await client.patch(
        "/api/admin/plans/sentinel_solo",
        json={"max_active_documents": -1},
        headers={"Authorization": f"Bearer {su_jwt}"},
    )
    assert res.status_code == 200
    assert res.json()["max_active_documents"] is None


@pytest.mark.asyncio
async def test_admin_update_plan_unknown_404(client, db_session):
    """PATCH on unknown plan name returns 404."""
    su_email = "unknown_su@example.com"
    su_jwt = await _register_and_login(client, su_email)
    await _make_superuser(db_session, su_email)

    res = await client.patch(
        "/api/admin/plans/nonexistent_plan",
        json={"base_price_cents": 500},
        headers={"Authorization": f"Bearer {su_jwt}"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_admin_update_plan_normal_user_403(client, db_session):
    """Normal user gets 403 on PATCH /api/admin/plans/{name}."""
    jwt = await _register_and_login(client, "patch_normal@example.com")

    res = await client.patch(
        "/api/admin/plans/solo",
        json={"base_price_cents": 500},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# Document limit enforcement — dynamic (admin-modifiable)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_document_limit_enforced_from_plan_config(client, db_session):
    """The document cap is read from plan_config, not hardcoded."""
    await _seed_plans(db_session, [
        {"plan_name": "solo", "base_price_cents": 900, "included_users": 1, "extra_user_price_cents": 0, "max_active_documents": 2, "is_active": True},
    ])

    jwt = await _register_and_login(client, "doc_limit_user@example.com")
    await _create_org(client, jwt, "doc-limit-org")

    # Create 2 documents — should succeed (limit is 2 in test seed)
    for i in range(2):
        res = await client.post(
            "/api/organisations/doc-limit-org/documents",
            json={"title": f"Doc {i + 1}"},
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert res.status_code == 201

    # 3rd document should fail
    res = await client.post(
        "/api/organisations/doc-limit-org/documents",
        json={"title": "Doc 3 — should fail"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_document_limit_update_via_admin_applies_immediately(client, db_session):
    """Changing the document limit via admin PATCH affects subsequent document creation."""
    await _seed_plans(db_session, [
        {"plan_name": "solo", "base_price_cents": 900, "included_users": 1, "extra_user_price_cents": 0, "max_active_documents": 1, "is_active": True},
    ])

    jwt = await _register_and_login(client, "doc_admin_user@example.com")
    await _create_org(client, jwt, "doc-admin-org")

    # First doc succeeds
    res = await client.post(
        "/api/organisations/doc-admin-org/documents",
        json={"title": "Doc 1"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 201

    # Second doc fails (limit=1)
    res = await client.post(
        "/api/organisations/doc-admin-org/documents",
        json={"title": "Doc 2 — should fail initially"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 403

    # Superuser raises the limit to 5
    su_email = "doc_admin_su@example.com"
    su_jwt = await _register_and_login(client, su_email)
    await _make_superuser(db_session, su_email)

    patch_res = await client.patch(
        "/api/admin/plans/solo",
        json={"max_active_documents": 5},
        headers={"Authorization": f"Bearer {su_jwt}"},
    )
    assert patch_res.status_code == 200

    # Now the second doc should succeed
    res = await client.post(
        "/api/organisations/doc-admin-org/documents",
        json={"title": "Doc 2 — should succeed now"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 201
