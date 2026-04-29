"""
Billing endpoint and service tests.

Uses the same in-memory SQLite + ASGI fixture pattern as other test modules.
Stripe API calls are mocked with unittest.mock.patch so no network calls occur.

Coverage:
  POST /api/billing/checkout
    - Owner gets checkout URL (200).
    - Non-owner member gets 403.
    - Non-member gets 404.
    - Unauthenticated request gets 401.
    - Stripe not configured → 400.

  POST /api/billing/portal
    - Owner with existing Stripe customer gets portal URL (200).
    - Owner without Stripe customer gets 400 (no subscription yet).
    - Non-owner member gets 403.
    - Non-member gets 404.
    - Unauthenticated request gets 401/403.
    - Stripe not configured → 400.

  POST /api/billing/webhook
    - checkout.session.completed upgrades org plan to 'team'.
    - customer.subscription.deleted downgrades org plan to 'solo'.
    - Invalid signature → 400.
    - Missing webhook secret → 400.
    - Unknown event type → 200 {"status": "ok"} (ignored silently).

  Document creation plan-based limit
    - 4th document creation on a solo-plan org (limit=3) returns 403.
    - Team-plan org (unlimited) can create more than 3 documents.
"""

from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
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
    """
    Register a new user via magic link and return the JWT access token.

    Parameters:
        client: Test HTTP client.
        email: Email address for the test user.

    Returns:
        JWT access token string.
    """
    await client.post("/api/auth/magic-link/request", json={"email": email})
    token = next(t for t, v in _magic_link_store.items() if v["email"] == email)
    res = await client.post("/api/auth/magic-link/verify", json={"token": token})
    return res.json()["access_token"]


async def _create_org(client: AsyncClient, jwt: str, slug: str) -> dict:
    """
    Create an organisation and return its response dict.

    Parameters:
        client: Test HTTP client.
        jwt: Bearer token for the creating user.
        slug: Unique slug for the organisation.

    Returns:
        Organisation response dict from the API.
    """
    res = await client.post(
        "/api/organisations",
        json={"name": f"Org {slug}", "slug": slug},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 201
    return res.json()


async def _add_member(client: AsyncClient, owner_jwt: str, slug: str, member_email: str) -> str:
    """
    Invite and accept a member, returning their JWT.

    Parameters:
        client: Test HTTP client.
        owner_jwt: Bearer token for the org owner.
        slug: Organisation slug.
        member_email: Email of the member to invite.

    Returns:
        JWT access token for the new member.
    """
    from sqlalchemy import select
    from app.models.invitation import Invitation

    # Invite
    await client.post(
        f"/api/organisations/{slug}/invite",
        json={"email": member_email},
        headers={"Authorization": f"Bearer {owner_jwt}"},
    )
    # Register member
    member_jwt = await _register_and_login(client, member_email)
    # Retrieve invite token directly from the test DB session
    invite_token = None
    async for session in app.dependency_overrides[get_db]():
        result = await session.execute(
            select(Invitation.token).where(Invitation.email == member_email)
        )
        invite_token = result.scalar_one()
        break
    await client.post(
        "/api/invitations/accept",
        json={"token": invite_token},
        headers={"Authorization": f"Bearer {member_jwt}"},
    )
    return member_jwt


async def _seed_plan_config(db_session, plan_name: str, limit: int | None) -> None:
    """
    Seed a plan_config row for use in document-limit tests.

    Parameters:
        db_session: Active AsyncSession.
        plan_name: Plan name ('solo', 'team', 'organisation').
        limit: max_active_documents value (None = unlimited).
    """
    await db_session.execute(
        text(
            "INSERT OR REPLACE INTO plan_config "
            "(plan_name, base_price_cents, included_users, extra_user_price_cents, "
            "max_active_documents, stripe_price_id, stripe_price_id_annual, features, is_active, updated_at) "
            "VALUES (:plan_name, :price, :users, :extra, :limit, '', '', '[]', 1, CURRENT_TIMESTAMP)"
        ),
        {
            "plan_name": plan_name,
            "price": 900,
            "users": 1,
            "extra": 0,
            "limit": limit,
        },
    )
    await db_session.flush()


async def _get_invite_token(db_session: AsyncSession, email: str) -> str:
    """Retrieve the pending invite token for an email from the test DB session."""
    from app.models.invitation import Invitation

    result = await db_session.execute(
        select(Invitation.token)
        .where(Invitation.email == email, Invitation.accepted_at.is_(None))
        .order_by(Invitation.created_at.desc())
        .limit(1)
    )
    token = result.scalar_one_or_none()
    assert token is not None, f"No pending invite found for {email}"
    return token


# ---------------------------------------------------------------------------
# POST /api/billing/checkout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checkout_owner_success(client, db_session):
    """Owner gets a checkout URL (200) — Stripe call is mocked."""
    await _seed_plan_config(db_session, "solo", None)  # no doc limit needed for billing test
    jwt = await _register_and_login(client, "billingowner@example.com")
    await _create_org(client, jwt, "billing-owner-org")

    fake_session = MagicMock()
    fake_session.url = "https://checkout.stripe.com/pay/fake_session_id"
    fake_customer = MagicMock()
    fake_customer.id = "cus_testfake"

    with (
        patch("app.services.billing.settings") as mock_settings,
        patch("stripe.Customer.create", return_value=fake_customer),
        patch("stripe.checkout.Session.create", return_value=fake_session),
    ):
        mock_settings.stripe_secret_key = "sk_test_fake"
        mock_settings.stripe_webhook_secret = "whsec_fake"
        mock_settings.stripe_price_id = ""

        res = await client.post(
            "/api/billing/checkout",
            json={
                "slug": "billing-owner-org",
                "success_url": "http://localhost:5173/billing?success=1",
                "cancel_url": "http://localhost:5173/billing?cancel=1",
                "plan_name": "solo",
            },
            headers={"Authorization": f"Bearer {jwt}"},
        )

    assert res.status_code == 200
    data = res.json()
    assert "checkout_url" in data
    assert data["checkout_url"] == "https://checkout.stripe.com/pay/fake_session_id"


@pytest.mark.asyncio
async def test_checkout_team_uses_member_quantity_for_tiered_price(client, db_session):
    """Team checkout sends the current membership count as the Stripe quantity."""
    await db_session.execute(
        text(
            "INSERT OR REPLACE INTO plan_config "
            "(plan_name, base_price_cents, included_users, extra_user_price_cents, "
            "max_active_documents, stripe_price_id, stripe_price_id_annual, features, is_active, updated_at) "
            "VALUES ('team', 2900, 3, 800, NULL, 'price_team_monthly', 'price_team_annual', '[]', 1, CURRENT_TIMESTAMP)"
        )
    )
    await db_session.flush()

    owner_jwt = await _register_and_login(client, "team_billing_owner@example.com")
    await _create_org(client, owner_jwt, "team-billing-org")
    await _register_and_login(client, "team_billing_member@example.com")
    await _add_member(client, owner_jwt, "team-billing-org", "team_billing_member@example.com")

    fake_session = MagicMock()
    fake_session.url = "https://checkout.stripe.com/pay/team_session"
    fake_customer = MagicMock()
    fake_customer.id = "cus_team_checkout"

    with (
        patch("app.services.billing.settings") as mock_settings,
        patch("stripe.Customer.create", return_value=fake_customer),
        patch("stripe.checkout.Session.create", return_value=fake_session) as mock_checkout,
    ):
        mock_settings.stripe_secret_key = "sk_test_fake"
        mock_settings.stripe_webhook_secret = "whsec_fake"
        mock_settings.stripe_price_id = ""

        res = await client.post(
            "/api/billing/checkout",
            json={
                "slug": "team-billing-org",
                "success_url": "http://localhost:5173/billing?success=1",
                "cancel_url": "http://localhost:5173/billing?cancel=1",
                "plan_name": "team",
            },
            headers={"Authorization": f"Bearer {owner_jwt}"},
        )

    assert res.status_code == 200
    assert mock_checkout.call_args.kwargs["line_items"] == [
        {"price": "price_team_monthly", "quantity": 2}
    ]


@pytest.mark.asyncio
async def test_checkout_non_member_returns_404(client):
    """Non-member gets 404 on checkout."""
    jwt_owner = await _register_and_login(client, "co_owner@example.com")
    await _create_org(client, jwt_owner, "co-nm-org")

    jwt_outsider = await _register_and_login(client, "co_outsider@example.com")

    with patch("app.services.billing.settings") as mock_settings:
        mock_settings.stripe_secret_key = "sk_test_fake"

        res = await client.post(
            "/api/billing/checkout",
            json={
                "slug": "co-nm-org",
                "success_url": "http://localhost:5173/s",
                "cancel_url": "http://localhost:5173/c",
            },
            headers={"Authorization": f"Bearer {jwt_outsider}"},
        )

    assert res.status_code == 404


@pytest.mark.asyncio
async def test_checkout_unauthenticated(client):
    """Unauthenticated checkout request returns 401 or 403."""
    res = await client.post(
        "/api/billing/checkout",
        json={
            "slug": "some-org",
            "success_url": "http://localhost:5173/s",
            "cancel_url": "http://localhost:5173/c",
        },
    )
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_checkout_stripe_not_configured(client):
    """Returns 400 when Stripe secret key is missing."""
    jwt = await _register_and_login(client, "billingnk@example.com")
    await _create_org(client, jwt, "billing-nk-org")

    with patch("app.services.billing.settings") as mock_settings:
        mock_settings.stripe_secret_key = ""

        res = await client.post(
            "/api/billing/checkout",
            json={
                "slug": "billing-nk-org",
                "success_url": "http://localhost:5173/s",
                "cancel_url": "http://localhost:5173/c",
            },
            headers={"Authorization": f"Bearer {jwt}"},
        )

    assert res.status_code == 400
    assert "not configured" in res.json()["detail"].lower()


# ---------------------------------------------------------------------------
# POST /api/billing/webhook
# ---------------------------------------------------------------------------


def _build_mock_event(event_type: str, data: dict, event_id: str | None = None) -> dict:
    """
    Build a minimal Stripe event dict for testing.

    Parameters:
        event_type: Stripe event type string.
        data: The event data object.
        event_id: Optional Stripe event ID (defaults to a deterministic value
                  derived from event_type so each call gets a unique ID).

    Returns:
        A dict matching the structure stripe.Webhook.construct_event returns.
    """
    import uuid
    return {
        "id": event_id or f"evt_test_{uuid.uuid4().hex[:12]}",
        "type": event_type,
        "data": {"object": data},
    }


@pytest.mark.asyncio
async def test_webhook_checkout_completed_upgrades_plan(client, db_session):
    """checkout.session.completed sets org.plan to 'team' (from metadata)."""
    jwt = await _register_and_login(client, "wh_owner@example.com")
    await _create_org(client, jwt, "wh-upgrade-org")

    fake_event = _build_mock_event(
        "checkout.session.completed",
        {"customer": "cus_wh_test_001", "metadata": {"plan_name": "team"}},
    )

    with (
        patch("app.core.config.settings") as mock_cfg,
        patch("app.api.billing.settings") as mock_api_settings,
        patch("stripe.Webhook.construct_event", return_value=fake_event),
    ):
        mock_cfg.stripe_secret_key = "sk_test_fake"
        mock_cfg.stripe_webhook_secret = "whsec_fake"
        mock_api_settings.stripe_secret_key = "sk_test_fake"
        mock_api_settings.stripe_webhook_secret = "whsec_fake"

        # Set stripe_customer_id on the org so the webhook can find it
        from sqlalchemy import select
        from app.models.organisation import Organisation
        async for session in app.dependency_overrides[get_db]():
            result = await session.execute(
                select(Organisation).where(Organisation.slug == "wh-upgrade-org")
            )
            org = result.scalar_one()
            org.stripe_customer_id = "cus_wh_test_001"
            await session.flush()
            break

        res = await client.post(
            "/api/billing/webhook",
            content=b'{"type":"checkout.session.completed"}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )

    assert res.status_code == 200

    # Verify plan was upgraded to 'team'
    async for session in app.dependency_overrides[get_db]():
        result = await session.execute(
            select(Organisation).where(Organisation.slug == "wh-upgrade-org")
        )
        org = result.scalar_one()
        assert org.plan.value == "team"
        break


@pytest.mark.asyncio
async def test_webhook_subscription_deleted_downgrades_plan(client):
    """customer.subscription.deleted sets org.plan back to 'solo'."""
    from sqlalchemy import select
    from app.models.organisation import Organisation, OrgPlan

    jwt = await _register_and_login(client, "wh_down_owner@example.com")
    await _create_org(client, jwt, "wh-downgrade-org")

    # Set org to team + set stripe_customer_id
    async for session in app.dependency_overrides[get_db]():
        result = await session.execute(
            select(Organisation).where(Organisation.slug == "wh-downgrade-org")
        )
        org = result.scalar_one()
        org.stripe_customer_id = "cus_wh_test_002"
        org.plan = OrgPlan.team
        await session.flush()
        break

    fake_event = _build_mock_event(
        "customer.subscription.deleted",
        {"customer": "cus_wh_test_002"},
    )

    with (
        patch("app.api.billing.settings") as mock_api_settings,
        patch("stripe.Webhook.construct_event", return_value=fake_event),
    ):
        mock_api_settings.stripe_secret_key = "sk_test_fake"
        mock_api_settings.stripe_webhook_secret = "whsec_fake"

        res = await client.post(
            "/api/billing/webhook",
            content=b'{"type":"customer.subscription.deleted"}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )

    assert res.status_code == 200

    # Verify plan was downgraded to 'solo'
    async for session in app.dependency_overrides[get_db]():
        result = await session.execute(
            select(Organisation).where(Organisation.slug == "wh-downgrade-org")
        )
        org = result.scalar_one()
        assert org.plan.value == "solo"
        break


@pytest.mark.asyncio
async def test_webhook_subscription_updated_infers_plan_from_price_id(client, db_session):
    """customer.subscription.updated realigns org.plan using Stripe price IDs."""
    from sqlalchemy import select
    from app.models.organisation import Organisation, OrgPlan

    await db_session.execute(
        text(
            "INSERT OR REPLACE INTO plan_config "
            "(plan_name, base_price_cents, included_users, extra_user_price_cents, "
            "max_active_documents, stripe_price_id, stripe_price_id_annual, features, is_active, updated_at) "
            "VALUES ('team', 2900, 3, 800, NULL, 'price_team_monthly', 'price_team_annual', '[]', 1, CURRENT_TIMESTAMP)"
        )
    )
    await db_session.execute(
        text(
            "INSERT OR REPLACE INTO plan_config "
            "(plan_name, base_price_cents, included_users, extra_user_price_cents, "
            "max_active_documents, stripe_price_id, stripe_price_id_annual, features, is_active, updated_at) "
            "VALUES ('organisation', 9900, 10, 600, NULL, 'price_org_monthly', 'price_org_annual', '[]', 1, CURRENT_TIMESTAMP)"
        )
    )
    await db_session.flush()

    jwt = await _register_and_login(client, "wh_sync_owner@example.com")
    await _create_org(client, jwt, "wh-sync-org")

    async for session in app.dependency_overrides[get_db]():
        result = await session.execute(
            select(Organisation).where(Organisation.slug == "wh-sync-org")
        )
        org = result.scalar_one()
        org.stripe_customer_id = "cus_wh_test_003"
        org.plan = OrgPlan.team
        await session.flush()
        break

    fake_event = _build_mock_event(
        "customer.subscription.updated",
        {
            "customer": "cus_wh_test_003",
            "items": {
                "data": [
                    {
                        "id": "si_org_001",
                        "quantity": 12,
                        "price": {"id": "price_org_monthly"},
                    }
                ]
            },
        },
    )

    with (
        patch("app.api.billing.settings") as mock_api_settings,
        patch("stripe.Webhook.construct_event", return_value=fake_event),
    ):
        mock_api_settings.stripe_secret_key = "sk_test_fake"
        mock_api_settings.stripe_webhook_secret = "whsec_fake"

        res = await client.post(
            "/api/billing/webhook",
            content=b'{"type":"customer.subscription.updated"}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )

    assert res.status_code == 200

    async for session in app.dependency_overrides[get_db]():
        result = await session.execute(
            select(Organisation).where(Organisation.slug == "wh-sync-org")
        )
        org = result.scalar_one()
        assert org.plan.value == "organisation"
        break


@pytest.mark.asyncio
async def test_webhook_subscription_updated_past_due_downgrades_plan(client):
    """A non-license-granting subscription status downgrades the org to solo."""
    from sqlalchemy import select
    from app.models.organisation import Organisation, OrgPlan

    jwt = await _register_and_login(client, "wh_past_due_owner@example.com")
    await _create_org(client, jwt, "wh-past-due-org")

    async for session in app.dependency_overrides[get_db]():
        result = await session.execute(
            select(Organisation).where(Organisation.slug == "wh-past-due-org")
        )
        org = result.scalar_one()
        org.stripe_customer_id = "cus_wh_test_004"
        org.plan = OrgPlan.team
        await session.flush()
        break

    fake_event = _build_mock_event(
        "customer.subscription.updated",
        {"customer": "cus_wh_test_004", "status": "past_due", "items": {"data": []}},
    )

    with (
        patch("app.api.billing.settings") as mock_api_settings,
        patch("stripe.Webhook.construct_event", return_value=fake_event),
    ):
        mock_api_settings.stripe_secret_key = "sk_test_fake"
        mock_api_settings.stripe_webhook_secret = "whsec_fake"

        res = await client.post(
            "/api/billing/webhook",
            content=b'{"type":"customer.subscription.updated"}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )

    assert res.status_code == 200

    async for session in app.dependency_overrides[get_db]():
        result = await session.execute(
            select(Organisation).where(Organisation.slug == "wh-past-due-org")
        )
        org = result.scalar_one()
        assert org.plan.value == "solo"
        break


@pytest.mark.asyncio
async def test_accept_invite_syncs_subscription_quantity(client, db_session):
    """Accepting an invite increases the Stripe subscription seat quantity."""
    from sqlalchemy import select
    from app.models.organisation import Organisation, OrgPlan

    await db_session.execute(
        text(
            "INSERT OR REPLACE INTO plan_config "
            "(plan_name, base_price_cents, included_users, extra_user_price_cents, "
            "max_active_documents, stripe_price_id, stripe_price_id_annual, features, is_active, updated_at) "
            "VALUES ('team', 2900, 3, 800, NULL, 'price_team_monthly', 'price_team_annual', '[]', 1, CURRENT_TIMESTAMP)"
        )
    )
    await db_session.flush()

    owner_jwt = await _register_and_login(client, "seat_owner@example.com")
    await _create_org(client, owner_jwt, "seat-sync-org")

    async for session in app.dependency_overrides[get_db]():
        result = await session.execute(
            select(Organisation).where(Organisation.slug == "seat-sync-org")
        )
        org = result.scalar_one()
        org.plan = OrgPlan.team
        org.stripe_customer_id = "cus_seat_sync_001"
        await session.flush()
        break

    await client.post(
        "/api/organisations/seat-sync-org/invite",
        json={"email": "seat_member@example.com"},
        headers={"Authorization": f"Bearer {owner_jwt}"},
    )
    member_jwt = await _register_and_login(client, "seat_member@example.com")
    token = await _get_invite_token(db_session, "seat_member@example.com")

    fake_subscriptions = {
        "data": [
            {
                "status": "active",
                "items": {
                    "data": [
                        {
                            "id": "si_team_001",
                            "quantity": 1,
                            "price": {"id": "price_team_monthly"},
                        }
                    ]
                },
            }
        ]
    }

    with (
        patch("app.services.billing.settings") as mock_settings,
        patch("stripe.Subscription.list", return_value=fake_subscriptions),
        patch("stripe.SubscriptionItem.modify") as mock_modify,
    ):
        mock_settings.stripe_secret_key = "sk_test_fake"

        res = await client.post(
            "/api/invitations/accept",
            json={"token": token},
            headers={"Authorization": f"Bearer {member_jwt}"},
        )

    assert res.status_code == 200
    mock_modify.assert_called_once_with(
        "si_team_001",
        quantity=2,
        proration_behavior="create_prorations",
    )


@pytest.mark.asyncio
async def test_accept_invite_paid_plan_rejects_past_due_subscription(client, db_session):
    """A paid-seat invite is rejected when the Stripe subscription is not license-granting."""
    from sqlalchemy import func, select, text
    from app.models.organisation import Organisation, OrgPlan
    from app.models.membership import Membership

    await db_session.execute(
        text(
            "INSERT OR REPLACE INTO plan_config "
            "(plan_name, base_price_cents, included_users, extra_user_price_cents, "
            "max_active_documents, stripe_price_id, stripe_price_id_annual, features, is_active, updated_at) "
            "VALUES ('team', 2900, 3, 800, NULL, 'price_team_monthly', 'price_team_annual', '[]', 1, CURRENT_TIMESTAMP)"
        )
    )
    await db_session.flush()

    owner_jwt = await _register_and_login(client, "seat_pd_owner@example.com")
    await _create_org(client, owner_jwt, "seat-past-due-org")

    async for session in app.dependency_overrides[get_db]():
        result = await session.execute(
            select(Organisation).where(Organisation.slug == "seat-past-due-org")
        )
        org = result.scalar_one()
        org.plan = OrgPlan.team
        org.stripe_customer_id = "cus_past_due_001"
        await session.flush()
        break

    await client.post(
        "/api/organisations/seat-past-due-org/invite",
        json={"email": "seat_pd_member@example.com"},
        headers={"Authorization": f"Bearer {owner_jwt}"},
    )
    member_jwt = await _register_and_login(client, "seat_pd_member@example.com")
    token = await _get_invite_token(db_session, "seat_pd_member@example.com")

    fake_subscriptions = {
        "data": [
            {
                "status": "past_due",
                "items": {
                    "data": [
                        {
                            "id": "si_team_pd_001",
                            "quantity": 1,
                            "price": {"id": "price_team_monthly"},
                        }
                    ]
                },
            }
        ]
    }

    with (
        patch("app.services.billing.settings") as mock_settings,
        patch("stripe.Subscription.list", return_value=fake_subscriptions),
    ):
        mock_settings.stripe_secret_key = "sk_test_fake"

        res = await client.post(
            "/api/invitations/accept",
            json={"token": token},
            headers={"Authorization": f"Bearer {member_jwt}"},
        )

    assert res.status_code == 402
    assert "resolve billing" in res.json()["detail"].lower()

    result = await db_session.execute(
        select(func.count())
        .select_from(Membership)
        .join(Organisation, Membership.org_id == Organisation.id)
        .where(Organisation.slug == "seat-past-due-org")
    )
    assert result.scalar_one() == 1


@pytest.mark.asyncio
async def test_remove_member_paid_plan_rolls_back_when_stripe_sync_fails(client, db_session):
    """Member removal is rolled back if the Stripe seat sync cannot complete."""
    from sqlalchemy import select, text
    from app.models.organisation import Organisation, OrgPlan

    await db_session.execute(
        text(
            "INSERT OR REPLACE INTO plan_config "
            "(plan_name, base_price_cents, included_users, extra_user_price_cents, "
            "max_active_documents, stripe_price_id, stripe_price_id_annual, features, is_active, updated_at) "
            "VALUES ('team', 2900, 3, 800, NULL, 'price_team_monthly', 'price_team_annual', '[]', 1, CURRENT_TIMESTAMP)"
        )
    )
    await db_session.flush()

    owner_jwt = await _register_and_login(client, "seat_rm_owner@example.com")
    await _create_org(client, owner_jwt, "seat-rm-org")
    member_jwt = await _add_member(client, owner_jwt, "seat-rm-org", "seat_rm_member@example.com")

    async for session in app.dependency_overrides[get_db]():
        result = await session.execute(
            select(Organisation).where(Organisation.slug == "seat-rm-org")
        )
        org = result.scalar_one()
        org.plan = OrgPlan.team
        org.stripe_customer_id = "cus_rm_001"
        await session.flush()
        break

    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {member_jwt}"})
    member_user_id = me.json()["id"]

    with (
        patch("app.services.billing.settings") as mock_settings,
        patch("stripe.Subscription.list", side_effect=Exception("stripe unavailable")),
    ):
        mock_settings.stripe_secret_key = "sk_test_fake"

        res = await client.delete(
            f"/api/organisations/seat-rm-org/members/{member_user_id}",
            headers={"Authorization": f"Bearer {owner_jwt}"},
        )

    assert res.status_code == 503
    assert "seat count" in res.json()["detail"].lower()

    members = await client.get(
        "/api/organisations/seat-rm-org/members",
        headers={"Authorization": f"Bearer {owner_jwt}"},
    )
    assert members.status_code == 200
    assert len(members.json()) == 2


@pytest.mark.asyncio
async def test_webhook_invalid_signature(client):
    """Invalid Stripe signature returns 400."""
    import stripe

    with (
        patch("app.api.billing.settings") as mock_settings,
        patch(
            "stripe.Webhook.construct_event",
            side_effect=stripe.error.SignatureVerificationError("bad sig", "sig_header"),
        ),
    ):
        mock_settings.stripe_secret_key = "sk_test_fake"
        mock_settings.stripe_webhook_secret = "whsec_fake"

        res = await client.post(
            "/api/billing/webhook",
            content=b'{}',
            headers={"stripe-signature": "t=1,v1=badsig"},
        )

    assert res.status_code == 400
    assert "signature" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_webhook_missing_secret(client):
    """Missing STRIPE_WEBHOOK_SECRET returns 400."""
    with patch("app.api.billing.settings") as mock_settings:
        mock_settings.stripe_webhook_secret = ""

        res = await client.post(
            "/api/billing/webhook",
            content=b'{}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )

    assert res.status_code == 400


@pytest.mark.asyncio
async def test_webhook_unknown_event_ignored(client):
    """Unknown event types are silently ignored and return 200."""
    fake_event = _build_mock_event("some.unknown.event", {})

    with (
        patch("app.api.billing.settings") as mock_settings,
        patch("stripe.Webhook.construct_event", return_value=fake_event),
    ):
        mock_settings.stripe_secret_key = "sk_test_fake"
        mock_settings.stripe_webhook_secret = "whsec_fake"

        res = await client.post(
            "/api/billing/webhook",
            content=b'{"type":"some.unknown.event"}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )

    assert res.status_code == 200


# ---------------------------------------------------------------------------
# Plan-based document limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_solo_plan_document_limit(client, db_session):
    """4th document on a solo-plan org (limit=3) returns 403 with an upgrade message."""
    await _seed_plan_config(db_session, "solo", 3)

    jwt = await _register_and_login(client, "freetier@example.com")
    await _create_org(client, jwt, "freetier-org")

    # Create 3 documents — all should succeed
    for i in range(3):
        res = await client.post(
            "/api/organisations/freetier-org/documents",
            json={"title": f"Doc {i + 1}"},
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert res.status_code == 201

    # 4th document should be blocked
    res = await client.post(
        "/api/organisations/freetier-org/documents",
        json={"title": "Doc 4 — should fail"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 403
    assert "upgrade" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_team_plan_no_document_limit(client, db_session):
    """A team-plan org (unlimited) can create more than 3 documents."""
    from sqlalchemy import select
    from app.models.organisation import Organisation, OrgPlan

    await _seed_plan_config(db_session, "team", None)

    jwt = await _register_and_login(client, "protier@example.com")
    await _create_org(client, jwt, "protier-org")

    # Manually upgrade the org to team
    async for session in app.dependency_overrides[get_db]():
        result = await session.execute(
            select(Organisation).where(Organisation.slug == "protier-org")
        )
        org = result.scalar_one()
        org.plan = OrgPlan.team
        await session.flush()
        break

    # Create 5 documents — all should succeed
    for i in range(5):
        res = await client.post(
            "/api/organisations/protier-org/documents",
            json={"title": f"Pro Doc {i + 1}"},
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert res.status_code == 201, f"Failed on doc {i + 1}: {res.json()}"


# ---------------------------------------------------------------------------
# POST /api/billing/portal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_portal_owner_with_customer_success(client):
    """Owner whose org has a Stripe customer ID gets a portal URL (200)."""
    from sqlalchemy import select
    from app.models.organisation import Organisation

    jwt = await _register_and_login(client, "portal_owner@example.com")
    await _create_org(client, jwt, "portal-owner-org")

    # Set a stripe_customer_id so the portal can be opened
    async for session in app.dependency_overrides[get_db]():
        result = await session.execute(
            select(Organisation).where(Organisation.slug == "portal-owner-org")
        )
        org = result.scalar_one()
        org.stripe_customer_id = "cus_portal_test_001"
        await session.flush()
        break

    fake_portal_session = MagicMock()
    fake_portal_session.url = "https://billing.stripe.com/session/fake_portal_id"

    with (
        patch("app.services.billing.settings") as mock_settings,
        patch("stripe.billing_portal.Session.create", return_value=fake_portal_session),
    ):
        mock_settings.stripe_secret_key = "sk_test_fake"
        mock_settings.stripe_webhook_secret = "whsec_fake"
        mock_settings.stripe_portal_return_url = "https://app.amendly.eu/orgs/portal-owner-org/billing"

        res = await client.post(
            "/api/billing/portal",
            json={"slug": "portal-owner-org"},
            headers={"Authorization": f"Bearer {jwt}"},
        )

    assert res.status_code == 200
    data = res.json()
    assert "portal_url" in data
    assert data["portal_url"] == "https://billing.stripe.com/session/fake_portal_id"


@pytest.mark.asyncio
async def test_portal_owner_no_customer_returns_400(client):
    """Owner whose org has no Stripe customer ID gets 400 (must subscribe first)."""
    jwt = await _register_and_login(client, "portal_nocust@example.com")
    await _create_org(client, jwt, "portal-nocust-org")

    with patch("app.services.billing.settings") as mock_settings:
        mock_settings.stripe_secret_key = "sk_test_fake"
        mock_settings.stripe_portal_return_url = ""

        res = await client.post(
            "/api/billing/portal",
            json={"slug": "portal-nocust-org"},
            headers={"Authorization": f"Bearer {jwt}"},
        )

    assert res.status_code == 400
    assert "subscription" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_portal_non_member_returns_404(client):
    """Non-member gets 404 on portal request."""
    jwt_owner = await _register_and_login(client, "portal_nm_owner@example.com")
    await _create_org(client, jwt_owner, "portal-nm-org")

    jwt_outsider = await _register_and_login(client, "portal_nm_outsider@example.com")

    with patch("app.services.billing.settings") as mock_settings:
        mock_settings.stripe_secret_key = "sk_test_fake"

        res = await client.post(
            "/api/billing/portal",
            json={"slug": "portal-nm-org"},
            headers={"Authorization": f"Bearer {jwt_outsider}"},
        )

    assert res.status_code == 404


@pytest.mark.asyncio
async def test_portal_unauthenticated(client):
    """Unauthenticated portal request returns 401 or 403."""
    res = await client.post(
        "/api/billing/portal",
        json={"slug": "some-org"},
    )
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_portal_stripe_not_configured(client):
    """Returns 400 when Stripe secret key is missing."""
    jwt = await _register_and_login(client, "portal_nk@example.com")
    await _create_org(client, jwt, "portal-nk-org")

    with patch("app.services.billing.settings") as mock_settings:
        mock_settings.stripe_secret_key = ""

        res = await client.post(
            "/api/billing/portal",
            json={"slug": "portal-nk-org"},
            headers={"Authorization": f"Bearer {jwt}"},
        )

    assert res.status_code == 400
    assert "not configured" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_portal_non_owner_member_returns_403(client):
    """Non-owner member gets 403 on portal request."""
    jwt_owner = await _register_and_login(client, "portal_role_owner@example.com")
    await _create_org(client, jwt_owner, "portal-role-org")
    jwt_member = await _add_member(client, jwt_owner, "portal-role-org", "portal_role_member@example.com")

    with patch("app.services.billing.settings") as mock_settings:
        mock_settings.stripe_secret_key = "sk_test_fake"

        res = await client.post(
            "/api/billing/portal",
            json={"slug": "portal-role-org"},
            headers={"Authorization": f"Bearer {jwt_member}"},
        )

    assert res.status_code == 403


# ---------------------------------------------------------------------------
# Idempotency: duplicate webhook events must not be processed twice
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_idempotency_duplicate_event_not_processed_twice(client, db_session):
    """
    Sending the same Stripe webhook event twice must not change the plan twice.
    The second delivery is silently skipped (200 ok, plan unchanged).
    """
    from sqlalchemy import select
    from app.models.organisation import Organisation, OrgPlan

    jwt = await _register_and_login(client, "idempotency_owner@example.com")
    await _create_org(client, jwt, "idempotency-org")

    # Pre-set the org to solo so the first event upgrades it to team
    async for session in app.dependency_overrides[get_db]():
        result = await session.execute(
            select(Organisation).where(Organisation.slug == "idempotency-org")
        )
        org = result.scalar_one()
        org.stripe_customer_id = "cus_idempotency_001"
        org.plan = OrgPlan.solo
        await session.flush()
        break

    # Build one event with a fixed ID
    shared_event_id = "evt_idempotency_test_fixed_001"
    fake_event = _build_mock_event(
        "checkout.session.completed",
        {"customer": "cus_idempotency_001", "metadata": {"plan_name": "team"}},
        event_id=shared_event_id,
    )

    async def _send_webhook():
        with (
            patch("app.core.config.settings") as mock_cfg,
            patch("app.api.billing.settings") as mock_api_settings,
            patch("stripe.Webhook.construct_event", return_value=fake_event),
        ):
            mock_cfg.stripe_secret_key = "sk_test_fake"
            mock_cfg.stripe_webhook_secret = "whsec_fake"
            mock_api_settings.stripe_secret_key = "sk_test_fake"
            mock_api_settings.stripe_webhook_secret = "whsec_fake"
            return await client.post(
                "/api/billing/webhook",
                content=b'{"type":"checkout.session.completed"}',
                headers={"stripe-signature": "t=1,v1=fake"},
            )

    # First delivery — should upgrade plan to team
    res1 = await _send_webhook()
    assert res1.status_code == 200

    async for session in app.dependency_overrides[get_db]():
        result = await session.execute(
            select(Organisation).where(Organisation.slug == "idempotency-org")
        )
        org = result.scalar_one()
        assert org.plan == OrgPlan.team, "First delivery must upgrade plan"
        # Manually downgrade to simulate what a second delivery would do if not guarded
        org.plan = OrgPlan.solo
        await session.flush()
        break

    # Second delivery — same event_id, must be skipped
    res2 = await _send_webhook()
    assert res2.status_code == 200

    async for session in app.dependency_overrides[get_db]():
        result = await session.execute(
            select(Organisation).where(Organisation.slug == "idempotency-org")
        )
        org = result.scalar_one()
        assert org.plan == OrgPlan.solo, (
            "Second delivery with same event_id must be a no-op; plan must not be re-upgraded"
        )
        break
