from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..core.auth import get_hr_context
from ..core.time import utcnow_naive
from ..database import get_db
from ..models.user import User, UserStatus
from ..services.supabase_client import supabase_or_503

router = APIRouter(prefix="/employees", tags=["hr-employees"])
legacy_router = APIRouter(tags=["hr-employees"], include_in_schema=False)


# Response schemas
class EmployeeScore(BaseModel):
    user_id: str
    name: str
    email: str
    department: Optional[str]
    mental_health: int
    sentiment: int
    engagement: int
    risk: int
    status: str  # healthy | stable | at_risk | struggling | critical


class EmployeeScoresResponse(BaseModel):
    scores: List[EmployeeScore]
    org_average: float
    risk_alerts: List[Dict[str, Any]]


@router.get("")
def get_employees(user: dict = Depends(get_hr_context)):
    supabase = supabase_or_503()
    return supabase.table("employee_insights").select("*").execute().data or []


@router.get("/{employee_id}")
def get_employee_detail(employee_id: str, user: dict = Depends(get_hr_context)):
    supabase = supabase_or_503()
    insights = (
        supabase.table("employee_insights")
        .select("*")
        .eq("employee_id", employee_id)
        .execute()
        .data
        or []
    )
    tickets = (
        supabase.table("tickets")
        .select("*")
        .eq("user_id", employee_id)
        .execute()
        .data
        or []
    )
    return {
        "insights": insights,
        "tickets": tickets,
    }


@router.get("/scores", response_model=EmployeeScoresResponse)
def get_employee_scores(
    limit: int = 50,
    include_alerts: bool = True,
    user: dict = Depends(get_hr_context),
    db: Session = Depends(get_db),
):
    from ..services.mental_health import calculate_mental_health, check_and_alert_mental_health
    
    employees = db.query(User).filter(
        User.status == UserStatus.active
    ).limit(limit).all()

    scores: List[EmployeeScore] = []
    total_mental_health = 0
    risk_alerts: List[Dict[str, Any]] = []

    for emp in employees:
        try:
            user_id = UUID(str(emp.id))
            result = calculate_mental_health(db, user_id, days=30)
            emp_name = str(emp.name) if emp.name else (str(emp.email) if emp.email else "Unknown")
            emp_email = str(emp.email) if emp.email else ""
            score = EmployeeScore(
                user_id=str(emp.id),
                name=emp_name,
                email=emp_email,
                department=emp.department,
                mental_health=result["mental_health"],
                sentiment=result["sentiment"],
                engagement=result["engagement"],
                risk=result["risk"],
                status=result["status"],
            )
            scores.append(score)
            total_mental_health += result["mental_health"]

            if include_alerts and result["status"] in ("struggling", "critical", "at_risk"):
                alert = check_and_alert_mental_health(db, user_id, days=30)
                if alert.get("alert_created"):
                    risk_alerts.append({
                        "user_id": str(emp.id),
                        "name": emp_name,
                        "mental_health": result["mental_health"],
                        "status": result["status"],
                        "alert_id": alert.get("alert_id"),
                    })
        except Exception:
            continue

    org_average = round(total_mental_health / len(scores), 1) if scores else 0.0

    return EmployeeScoresResponse(
        scores=scores,
        org_average=org_average,
        risk_alerts=risk_alerts,
    )


@legacy_router.get("/employees/scores", response_model=EmployeeScoresResponse)
def get_employee_scores_legacy(
    limit: int = 50,
    include_alerts: bool = True,
    user: dict = Depends(get_hr_context),
    db: Session = Depends(get_db),
):
    return get_employee_scores(limit=limit, include_alerts=include_alerts, user=user, db=db)
