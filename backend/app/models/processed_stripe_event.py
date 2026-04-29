"""
ProcessedStripeEvent model — deduplicates incoming Stripe webhook events.

Stripe may deliver the same webhook event more than once (at-least-once
delivery guarantee).  Recording each processed event ID allows
handle_stripe_event to skip replays immediately, preventing double-upgrades
or double-downgrades caused by out-of-order or replayed webhooks.
"""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProcessedStripeEvent(Base):
    """
    Records Stripe event IDs that have already been processed.

    Attributes:
        event_id:     Stripe event ID (e.g. "evt_xxx"); serves as primary key.
        event_type:   Stripe event type string (e.g. "checkout.session.completed").
        processed_at: UTC timestamp when the event was first handled.
    """

    __tablename__ = "processed_stripe_events"

    event_id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
