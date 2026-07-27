"""SaaS billing / subscription.

Live mode pulls the real plan/seat/renewal data from Stripe when
``STRIPE_API_KEY`` is configured (optionally scoped to ``STRIPE_SUBSCRIPTION_ID``
or ``STRIPE_CUSTOMER_ID``). When Stripe isn't wired — or a call fails — the
endpoint falls back to env-derived values so the Billing screen always renders.
Seat *usage* is always the live count of active users from our own DB.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...auth import require_roles
from ...database import get_db
from ...models.user import User, UserStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])

_STRIPE_API = "https://api.stripe.com/v1"
_DEFAULT_FEATURES = [
    "HR analytics & insights",
    "Tickets & SLA",
    "Surveys & eNPS",
    "MARK chat & memory",
    "Leave & approvals",
]


class SubscriptionResponse(BaseModel):
    plan_name: str
    plan_tier: str
    billing_cycle: str
    seat_limit: int
    seats_used: int
    renews_on: str
    currency: str
    monthly_estimate: float
    features: list[str]
    source: str = "config"  # "stripe" when live, else "config"


def _env_subscription(seats_used: int) -> SubscriptionResponse:
    seat_limit = int(os.getenv("BILLING_SEAT_LIMIT", "250"))
    renews = date.today() + timedelta(days=int(os.getenv("BILLING_RENEWAL_DAYS", "30")))
    return SubscriptionResponse(
        plan_name=os.getenv("BILLING_PLAN_NAME", "MARK Business"),
        plan_tier=os.getenv("BILLING_PLAN_TIER", "business"),
        billing_cycle=os.getenv("BILLING_CYCLE", "annual"),
        seat_limit=seat_limit,
        seats_used=seats_used,
        renews_on=renews.isoformat(),
        currency=os.getenv("BILLING_CURRENCY", "USD"),
        monthly_estimate=float(os.getenv("BILLING_MONTHLY_ESTIMATE", "499.0")),
        features=_DEFAULT_FEATURES,
        source="config",
    )


def _fetch_stripe_subscription(api_key: str, seats_used: int) -> SubscriptionResponse | None:
    """Best-effort Stripe lookup. Returns None on any failure (caller falls back)."""
    headers = {"Authorization": f"Bearer {api_key}"}
    params = [("expand[]", "items.data.price.product")]
    sub_id = os.getenv("STRIPE_SUBSCRIPTION_ID", "").strip()
    customer_id = os.getenv("STRIPE_CUSTOMER_ID", "").strip()
    try:
        with httpx.Client(timeout=12.0) as client:
            if sub_id:
                resp = client.get(f"{_STRIPE_API}/subscriptions/{sub_id}", headers=headers, params=params)
                resp.raise_for_status()
                sub = resp.json()
            else:
                list_params = params + [("status", "active"), ("limit", "1")]
                if customer_id:
                    list_params.append(("customer", customer_id))
                resp = client.get(f"{_STRIPE_API}/subscriptions", headers=headers, params=list_params)
                resp.raise_for_status()
                data = resp.json().get("data") or []
                if not data:
                    return None
                sub = data[0]
    except Exception:
        logger.warning("Stripe subscription lookup failed; using config fallback.", exc_info=True)
        return None

    items = (sub.get("items") or {}).get("data") or []
    if not items:
        return None
    item = items[0]
    price = item.get("price") or {}
    product = price.get("product") if isinstance(price.get("product"), dict) else {}

    interval = (price.get("recurring") or {}).get("interval", "month")
    billing_cycle = "annual" if interval == "year" else "monthly"
    quantity = int(item.get("quantity") or 1)
    unit_amount = (price.get("unit_amount") or 0) / 100.0
    period_total = unit_amount * quantity
    monthly_estimate = round(period_total / 12.0, 2) if interval == "year" else round(period_total, 2)

    plan_name = (
        product.get("name")
        or price.get("nickname")
        or os.getenv("BILLING_PLAN_NAME", "MARK Business")
    )
    period_end = sub.get("current_period_end")
    if period_end:
        renews_on = datetime.fromtimestamp(int(period_end), tz=timezone.utc).date().isoformat()
    else:
        renews_on = (date.today() + timedelta(days=30)).isoformat()

    features = _DEFAULT_FEATURES
    marketing = product.get("marketing_features") if isinstance(product, dict) else None
    if isinstance(marketing, list) and marketing:
        extracted = [f.get("name") for f in marketing if isinstance(f, dict) and f.get("name")]
        if extracted:
            features = extracted

    return SubscriptionResponse(
        plan_name=plan_name,
        plan_tier=str((product.get("metadata") or {}).get("tier", os.getenv("BILLING_PLAN_TIER", "business"))),
        billing_cycle=billing_cycle,
        seat_limit=quantity,
        seats_used=seats_used,
        renews_on=renews_on,
        currency=(price.get("currency") or "usd").upper(),
        monthly_estimate=monthly_estimate,
        features=features,
        source="stripe",
    )


@router.get("/subscription", response_model=SubscriptionResponse)
def get_subscription(
    db: Session = Depends(get_db),
    _hr: User = Depends(require_roles(["hr", "admin"])),
):
    seats_used = int(db.query(func.count(User.id)).filter(User.status == UserStatus.active).scalar() or 0)

    api_key = os.getenv("STRIPE_API_KEY", "").strip()
    if api_key:
        live = _fetch_stripe_subscription(api_key, seats_used)
        if live is not None:
            return live

    return _env_subscription(seats_used)
