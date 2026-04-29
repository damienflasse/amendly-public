"""
Billing service — Stripe Checkout and webhook handling.

Responsibilities:
  - create_checkout_session: Creates (or re-uses) a Stripe Customer for the org,
    then opens a Stripe Checkout session for the chosen plan. Reads pricing from
    the plan_config table; team/organisation seats are priced from live member
    count and fall back to inline price_data in development.
  - sync_subscription_seat_quantity: Best-effort update of the live Stripe
    subscription quantity after a member joins or leaves a billable workspace.
  - handle_stripe_event: Processes validated Stripe webhook events:
      * checkout.session.completed        → set org.plan from session metadata
      * customer.subscription.created/updated → infer org.plan from price IDs
      * customer.subscription.deleted     → set org.plan = 'solo'
    All other event types are silently ignored.

Stripe is not called when STRIPE_SECRET_KEY is empty (development / test mode) —
the service raises a ValueError that the router maps to HTTP 400.
"""

import logging

import stripe
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.core.config import settings
from app.models.membership import MemberRole, Membership
from app.models.organisation import OrgPlan, Organisation
from app.models.processed_stripe_event import ProcessedStripeEvent
from app.models.user import User
from app.services.plan_config import get_plan_config_by_name, list_plan_configs

LICENSE_GRANTING_STATUSES = {"active", "trialing"}
SEAT_SYNCABLE_STATUSES = {"active", "trialing", "past_due", "unpaid"}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


class BillingSyncError(Exception):
    """Raised when Stripe billing state prevents a seat/license change."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _configure_stripe() -> None:
    """
    Set stripe.api_key from settings.

    Raises:
        ValueError: If STRIPE_SECRET_KEY is not configured.
    """
    if not settings.stripe_secret_key:
        raise ValueError("Stripe is not configured. Set STRIPE_SECRET_KEY in .env.")
    stripe.api_key = settings.stripe_secret_key


async def _count_billable_members(
    db: AsyncSession,
    org_id: str,
) -> int:
    """
    Count accepted organisation memberships that should consume billable seats.

    Parameters:
        db: Async SQLAlchemy session.
        org_id: Target organisation UUID.

    Returns:
        Number of current memberships for the organisation.
    """
    result = await db.execute(
        select(func.count())
        .select_from(Membership)
        .where(Membership.org_id == org_id)
    )
    return int(result.scalar_one() or 0)


def _checkout_quantity(plan_name: str, member_count: int) -> int:
    """
    Return the Stripe Checkout quantity for the selected plan.

    Solo is always billed as a fixed subscription. Team and organisation plans
    are billed by seat quantity, with tiered Stripe prices expected to encode
    the included seats and additional-seat pricing.
    """
    if plan_name == OrgPlan.solo.value:
        return 1
    return max(member_count, 1)


def _stripe_attr(obj: object, key: str, default=None):
    """
    Read a field from either a StripeObject or a plain dict.
    """
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _build_inline_line_items(
    *,
    plan_name: str,
    plan_display: str,
    base_price_cents: int,
    extra_user_price_cents: int,
    included_users: int,
    member_count: int,
    annual: bool,
) -> list[dict]:
    """
    Build inline Checkout line items when explicit Stripe Price IDs are absent.

    This keeps development/test mode accurate for plans with included seats plus
    additional-seat charges, even when recurring Stripe prices have not yet been
    configured in the dashboard.
    """
    interval = "year" if annual else "month"
    multiplier = 10 if annual else 1
    suffix = " (Annual)" if annual else ""
    description_suffix = " — 2 months free" if annual else ""

    line_items = [
        {
            "price_data": {
                "currency": "eur",
                "unit_amount": base_price_cents * multiplier,
                "recurring": {"interval": interval},
                "product_data": {
                    "name": f"Amendly {plan_display}{suffix}",
                    "description": (
                        f"Amendly {plan_display} plan — {included_users} user(s) included"
                        f"{description_suffix}"
                    ),
                },
            },
            "quantity": 1,
        }
    ]

    if plan_name == OrgPlan.solo.value or extra_user_price_cents <= 0:
        return line_items

    extra_seats = max(member_count - included_users, 0)
    if extra_seats == 0:
        return line_items

    line_items.append(
        {
            "price_data": {
                "currency": "eur",
                "unit_amount": extra_user_price_cents * multiplier,
                "recurring": {"interval": interval},
                "product_data": {
                    "name": f"Amendly {plan_display} additional seat{suffix}",
                    "description": (
                        f"Additional seat for the Amendly {plan_display} plan"
                        f"{description_suffix}"
                    ),
                },
            },
            "quantity": extra_seats,
        }
    )
    return line_items


async def _infer_plan_from_subscription(
    db: AsyncSession,
    subscription: object,
) -> OrgPlan | None:
    """
    Infer the Amendly plan from Stripe subscription item price IDs.
    """
    items = _stripe_attr(_stripe_attr(subscription, "items", {}) or {}, "data", []) or []
    item_price_ids = {
        _stripe_attr(_stripe_attr(item, "price", {}) or {}, "id")
        for item in items
    }
    item_price_ids.discard(None)
    if not item_price_ids:
        return None

    for plan in await list_plan_configs(db, active_only=False):
        price_ids = {plan.stripe_price_id, plan.stripe_price_id_annual}
        price_ids.discard("")
        if item_price_ids.intersection(price_ids):
            try:
                return OrgPlan(plan.plan_name)
            except ValueError:
                return None

    return None


def _fail_sync(
    strict: bool,
    message: str,
    *,
    status_code: int = 400,
) -> None:
    """
    Raise BillingSyncError in strict mode; log a warning in non-strict mode.

    Non-strict failures must still be logged so that Stripe seat-count drift
    can be detected in production logs before it becomes a billing dispute.
    """
    if strict:
        raise BillingSyncError(message, status_code=status_code)
    logger.warning("Stripe seat sync skipped (non-strict): %s", message)


def _select_subscription_by_status(
    subscriptions: list[object],
    *,
    allowed_statuses: set[str],
) -> object | None:
    """
    Return the first subscription whose status is in allowed_statuses.
    """
    return next(
        (
            sub for sub in subscriptions
            if _stripe_attr(sub, "status") in allowed_statuses
        ),
        None,
    )


async def _require_owner(
    db: AsyncSession,
    current_user: User,
    slug: str,
) -> Organisation:
    """
    Fetch an organisation by slug and verify the caller is the owner.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user making the request.
        slug: URL slug of the target organisation.

    Returns:
        The Organisation ORM instance.

    Raises:
        ValueError: If the org is not found, the user is not a member,
                    or the user's role is not 'owner'.
    """
    result = await db.execute(
        select(Organisation, Membership)
        .join(
            Membership,
            (Membership.org_id == Organisation.id) & (Membership.user_id == current_user.id),
        )
        .where(Organisation.slug == slug)
    )
    row = result.one_or_none()
    if row is None:
        raise ValueError(f"Organisation '{slug}' not found or you are not a member.")
    org, membership = row
    if membership.role != MemberRole.owner:
        raise ValueError("Only the organisation owner can manage billing.")
    return org


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


async def create_checkout_session(
    db: AsyncSession,
    current_user: User,
    slug: str,
    success_url: str,
    cancel_url: str,
    plan_name: str = "solo",
    annual: bool = False,
) -> str:
    """
    Create a Stripe Checkout session for the chosen plan.

    Pricing is read from the plan_config table. When annual=True and a
    stripe_price_id_annual is configured, it is used instead of the monthly
    price ID. Otherwise, inline price_data is constructed from base_price_cents
    with a yearly billing interval (10-month equivalent rate).

    If the org does not yet have a Stripe Customer ID, one is created and
    persisted on the Organisation row before opening the Checkout session.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user (must be the org owner).
        slug: URL slug of the organisation to upgrade.
        success_url: URL to redirect to after a successful payment.
        cancel_url: URL to redirect to if the user cancels.
        plan_name: Canonical plan name to subscribe to ('solo', 'team', 'organisation').
        annual: If True, use the annual Stripe price (2 months free). Defaults to False.

    Returns:
        The Stripe Checkout session URL (a one-time HTTPS URL).

    Raises:
        ValueError: If Stripe is not configured, the plan is not found,
                    org is not found, or the user is not the org owner.
    """
    _configure_stripe()
    org = await _require_owner(db, current_user, slug)
    member_count = await _count_billable_members(db, org.id)

    # Resolve plan config from DB
    plan_config = await get_plan_config_by_name(db, plan_name)
    if plan_config is None:
        raise ValueError(f"Plan '{plan_name}' not found in plan_config table.")

    # Create or re-use a Stripe Customer for this org
    if not org.stripe_customer_id:
        customer = stripe.Customer.create(
            email=current_user.email,
            name=org.name,
            metadata={"org_id": org.id, "org_slug": org.slug},
        )
        org.stripe_customer_id = customer.id
        await db.flush()

    # Build line_items. Team and organisation plans should use Stripe prices
    # configured as per-seat licensed/tiered prices, with quantity equal to the
    # organisation's current membership count.
    plan_display = plan_name.capitalize()
    quantity = _checkout_quantity(plan_name, member_count)
    if annual:
        if plan_config.stripe_price_id_annual:
            line_items = [{"price": plan_config.stripe_price_id_annual, "quantity": quantity}]
        else:
            line_items = _build_inline_line_items(
                plan_name=plan_name,
                plan_display=plan_display,
                base_price_cents=plan_config.base_price_cents,
                extra_user_price_cents=plan_config.extra_user_price_cents,
                included_users=plan_config.included_users,
                member_count=member_count,
                annual=True,
            )
    elif plan_config.stripe_price_id:
        line_items = [{"price": plan_config.stripe_price_id, "quantity": quantity}]
    elif settings.stripe_price_id and plan_name == OrgPlan.solo.value:
        line_items = [{"price": settings.stripe_price_id, "quantity": 1}]
    else:
        line_items = _build_inline_line_items(
            plan_name=plan_name,
            plan_display=plan_display,
            base_price_cents=plan_config.base_price_cents,
            extra_user_price_cents=plan_config.extra_user_price_cents,
            included_users=plan_config.included_users,
            member_count=member_count,
            annual=False,
        )

    # Build the Checkout session — embed plan_name (and billing period) in
    # metadata so the webhook handler can set org.plan correctly.
    session = stripe.checkout.Session.create(
        customer=org.stripe_customer_id,
        mode="subscription",
        line_items=line_items,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "org_id": org.id,
            "org_slug": org.slug,
            "plan_name": plan_name,
            "billing_period": "annual" if annual else "monthly",
        },
        subscription_data={
            "metadata": {
                "org_id": org.id,
                "org_slug": org.slug,
                "plan_name": plan_name,
                "billing_period": "annual" if annual else "monthly",
            }
        },
    )

    return session.url


async def sync_subscription_seat_quantity(
    db: AsyncSession,
    org_id: str,
    *,
    strict: bool = False,
    require_license_grant: bool = False,
) -> None:
    """
    Best-effort sync of Stripe subscription quantity with accepted memberships.

    Team and organisation plans are expected to use Stripe recurring prices that
    support quantity-based seat billing. When a member joins or leaves, this
    helper updates the matching subscription item quantity to the live member
    count.

    In strict mode, a sync failure raises BillingSyncError so the caller can
    roll back the surrounding DB transaction. This is used to prevent local
    membership changes from succeeding when Stripe cannot provision the seat.
    """
    result = await db.execute(
        select(Organisation).where(Organisation.id == org_id)
    )
    org = result.scalar_one_or_none()
    if org is None:
        _fail_sync(strict, "Organisation not found.", status_code=404)
        return

    if org.plan == OrgPlan.solo:
        return

    try:
        _configure_stripe()
    except ValueError:
        _fail_sync(strict, "Stripe billing is not configured.", status_code=503)
        return

    member_count = await _count_billable_members(db, org.id)
    plan_config = await get_plan_config_by_name(db, org.plan.value)
    if plan_config is None:
        _fail_sync(strict, f"Plan '{org.plan.value}' is not configured.", status_code=503)
        return

    if not org.stripe_customer_id:
        _fail_sync(
            strict,
            "This organisation does not have an active paid subscription. Please update billing before adding members.",
            status_code=402,
        )
        return

    matching_price_ids = {plan_config.stripe_price_id, plan_config.stripe_price_id_annual}
    matching_price_ids.discard("")
    if not matching_price_ids:
        _fail_sync(
            strict,
            f"Billing is not configured for the {org.plan.value} plan.",
            status_code=503,
        )
        return

    try:
        subscriptions = stripe.Subscription.list(
            customer=org.stripe_customer_id,
            status="all",
            limit=10,
            expand=["data.items.data.price"],
        )
        subscription_data = _stripe_attr(subscriptions, "data", []) or []
        allowed_statuses = (
            LICENSE_GRANTING_STATUSES if require_license_grant else SEAT_SYNCABLE_STATUSES
        )
        active_subscription = _select_subscription_by_status(
            subscription_data,
            allowed_statuses=allowed_statuses,
        )
        if active_subscription is None:
            if require_license_grant and subscription_data:
                latest_status = _stripe_attr(subscription_data[0], "status", "unknown")
                _fail_sync(
                    strict,
                    f"Subscription status '{latest_status}' does not allow adding paid seats. Please resolve billing first.",
                    status_code=402,
                )
                return
            _fail_sync(
                strict,
                "No active paid subscription was found for this organisation.",
                status_code=402,
            )
            return

        items = _stripe_attr(_stripe_attr(active_subscription, "items", {}) or {}, "data", []) or []
        billable_item = next(
            (
                item for item in items
                if _stripe_attr(_stripe_attr(item, "price", {}) or {}, "id") in matching_price_ids
            ),
            None,
        )
        if billable_item is None:
            _fail_sync(
                strict,
                f"The Stripe subscription is missing the billable item for the {org.plan.value} plan.",
                status_code=503,
            )
            return

        if _stripe_attr(billable_item, "quantity") == member_count:
            return

        stripe.SubscriptionItem.modify(
            _stripe_attr(billable_item, "id"),
            quantity=member_count,
            proration_behavior="create_prorations",
        )
    except BillingSyncError:
        raise
    except Exception:
        _fail_sync(
            strict,
            "Stripe could not update the seat count for this organisation. Please try again.",
            status_code=503,
        )
        return


async def create_portal_session(
    db: AsyncSession,
    current_user: User,
    slug: str,
    return_url: str,
) -> str:
    """
    Create a Stripe Customer Portal session for an organisation.

    The portal lets the subscription holder manage their billing details,
    update payment methods, and cancel the subscription.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user (must be the org owner).
        slug: URL slug of the organisation whose billing is being managed.
        return_url: URL the portal redirects back to after the user is done.

    Returns:
        The Stripe Customer Portal session URL (a one-time HTTPS URL).

    Raises:
        ValueError: If Stripe is not configured, org is not found,
                    the user is not the org owner, or the org has no
                    Stripe Customer ID (must upgrade first).
    """
    _configure_stripe()
    org = await _require_owner(db, current_user, slug)

    if not org.stripe_customer_id:
        raise ValueError(
            "This organisation does not have a Stripe subscription yet. "
            "Please subscribe to a plan first."
        )

    session = stripe.billing_portal.Session.create(
        customer=org.stripe_customer_id,
        return_url=return_url,
    )

    return session.url


async def handle_stripe_event(
    db: AsyncSession,
    event: "stripe.Event",  # type: ignore[name-defined]
) -> None:
    """
    Process a validated Stripe webhook event.

    Handled events:
      * checkout.session.completed        — upgrades the org's plan to the value
        stored in session.metadata['plan_name'] (falls back to 'team').
      * customer.subscription.created/updated — infers the current plan from
        the active subscription item price IDs.
      * customer.subscription.deleted     — downgrades the org's plan to 'solo'.
      * invoice.payment_failed            — logs a warning; Stripe's own dunning
        logic retries the charge and fires subscription.deleted if all retries
        exhaust, so we do not downgrade proactively.
      * invoice.payment_action_required   — same as payment_failed.

    All other event types are silently ignored.

    Parameters:
        db: Async SQLAlchemy session.
        event: A fully constructed stripe.Event object (already signature-verified
               by the webhook endpoint before calling this function).

    Side effects:
        May update Organisation.plan in the database.
    """
    event_id: str = event["id"]
    event_type: str = event["type"]

    # Idempotency guard — skip events we have already handled.
    # Stripe guarantees at-least-once delivery; this prevents double-upgrades
    # or double-downgrades from replayed or out-of-order webhooks.
    # Savepoint (begin_nested) limits rollback scope to just this insert
    # so a duplicate delivery doesn't undo earlier session state.
    try:
        async with db.begin_nested():
            db.add(ProcessedStripeEvent(event_id=event_id, event_type=event_type))
            await db.flush()
    except IntegrityError:
        logger.info("Stripe event %s (%s) already processed — skipping.", event_id, event_type)
        return

    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        customer_id: str | None = session.get("customer")
        if not customer_id:
            return
        # Read plan_name from metadata (embedded at checkout creation time)
        metadata = session.get("metadata") or {}
        plan_name: str | None = metadata.get("plan_name")
        if not plan_name:
            logger.warning(
                "checkout.session.completed for customer %s has no plan_name in metadata; "
                "skipping plan upgrade to avoid silently granting wrong tier.",
                customer_id,
            )
            return
        try:
            new_plan = OrgPlan(plan_name)
        except ValueError:
            logger.warning(
                "checkout.session.completed for customer %s has unrecognised plan_name=%r; "
                "skipping plan upgrade.",
                customer_id,
                plan_name,
            )
            return

        result = await db.execute(
            select(Organisation).where(Organisation.stripe_customer_id == customer_id)
        )
        org = result.scalar_one_or_none()
        if org and org.plan != new_plan:
            org.plan = new_plan
            await db.flush()

    elif event_type in {"customer.subscription.created", "customer.subscription.updated"}:
        subscription = event["data"]["object"]
        customer_id = subscription.get("customer")
        if not customer_id:
            return
        result = await db.execute(
            select(Organisation).where(Organisation.stripe_customer_id == customer_id)
        )
        org = result.scalar_one_or_none()
        if org is None:
            return

        subscription_status = subscription.get("status")
        if subscription_status is not None and subscription_status not in LICENSE_GRANTING_STATUSES:
            if org.plan != OrgPlan.solo:
                org.plan = OrgPlan.solo
                await db.flush()
            return

        inferred_plan = await _infer_plan_from_subscription(db, subscription)
        if inferred_plan and org.plan != inferred_plan:
            org.plan = inferred_plan
            await db.flush()

    elif event_type == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        customer_id = subscription.get("customer")
        if not customer_id:
            return
        result = await db.execute(
            select(Organisation).where(Organisation.stripe_customer_id == customer_id)
        )
        org = result.scalar_one_or_none()
        if org and org.plan != OrgPlan.solo:
            org.plan = OrgPlan.solo
            await db.flush()

    elif event_type in {"invoice.payment_failed", "invoice.payment_action_required"}:
        # Stripe's dunning management will retry the charge automatically.
        # If all retries fail, Stripe fires customer.subscription.deleted which
        # downgrades the org. We log a warning here for observability but do not
        # proactively downgrade — that would incorrectly penalise transient failures.
        invoice = event["data"]["object"]
        customer_id = invoice.get("customer")
        attempt_count = invoice.get("attempt_count", "?")
        logger.warning(
            "Stripe payment event '%s' for customer %s (attempt %s). "
            "Stripe will retry automatically.",
            event_type,
            customer_id,
            attempt_count,
        )
