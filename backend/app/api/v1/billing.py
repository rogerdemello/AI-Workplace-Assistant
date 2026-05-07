"""SaaS billing / subscription stub — extend with Stripe or your provider."""
from __future__ import annotations

import os
from datetime import date, timedelta
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...auth import require_roles
from ...database import get_db
from sqlalchemy.orm import Session
from sqlalchemy import func

from ...models.user import User, UserStatus

router = APIRouter(prefix="/billing", tags=["billing"])


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


@router.get("/subscription", response_model=SubscriptionResponse)
def get_subscription(
    db: Session = Depends(get_db),
    _hr: User = Depends(require_roles(["hr", "admin"])),
):
    seats_used = db.query(func.count(User.id)).filter(User.status == UserStatus.active).scalar() or 0
    seat_limit = int(os.getenv("BILLING_SEAT_LIMIT", "250"))
    plan = os.getenv("BILLING_PLAN_NAME", "MARK Business")
    tier = os.getenv("BILLING_PLAN_TIER", "business")
    renews = date.today() + timedelta(days=int(os.getenv("BILLING_RENEWAL_DAYS", "30")))

    return SubscriptionResponse(
        plan_name=plan,
        plan_tier=tier,
        billing_cycle=os.getenv("BILLING_CYCLE", "annual"),
        seat_limit=seat_limit,
        seats_used=int(seats_used),
        renews_on=renews.isoformat(),
        currency=os.getenv("BILLING_CURRENCY", "USD"),
        monthly_estimate=float(os.getenv("BILLING_MONTHLY_ESTIMATE", "499.0")),
        features=[
            "HR analytics & insights",
            "Tickets & SLA",
            "Surveys & eNPS",
            "MARK chat & memory",
            "Leave & approvals",
        ],
    )
