"""Cross-employee pattern detection for HR.

Surfaces the kind of signal you can't see from a single profile:
- emotion clusters affecting multiple employees
- department-level sentiment drops vs the prior window
- repeating complaint themes
- top at-risk individuals worth a 1:1

Each pattern carries a concrete recommendation so the HR view reads as
"here's the problem and what to do" rather than another chart to interpret.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List

from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from ..core.time import utcnow_naive
from ..models.department import Department
from ..models.employee_score import EmployeeScore
from ..models.sentiment_log import SentimentLog
from ..models.ticket import Ticket
from ..models.user import User


_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _push(out: List[Dict[str, Any]], **fields: Any) -> None:
    out.append(fields)


def detect_patterns(db: Session, days: int = 14) -> List[Dict[str, Any]]:
    """Return up to ~8 ranked patterns over the last `days`."""
    now = utcnow_naive()
    cutoff = now - timedelta(days=days)
    patterns: List[Dict[str, Any]] = []

    # 1) Emotion clusters — distinct employees expressing the same negative emotion.
    emotion_rows = (
        db.query(
            SentimentLog.emotion,
            func.count(distinct(SentimentLog.employee_id)).label("affected"),
        )
        .filter(SentimentLog.created_at >= cutoff)
        .filter(SentimentLog.label == "negative")
        .filter(SentimentLog.emotion.isnot(None))
        .filter(SentimentLog.emotion != "neutral")
        .filter(SentimentLog.emotion != "")
        .group_by(SentimentLog.emotion)
        .having(func.count(distinct(SentimentLog.employee_id)) >= 3)
        .order_by(func.count(distinct(SentimentLog.employee_id)).desc())
        .all()
    )
    for emotion, affected in emotion_rows[:4]:
        severity = "high" if affected >= 5 else "medium"
        _push(
            patterns,
            type="emotion_cluster",
            label=f"{affected} employees showed {emotion} in chat",
            affected_count=int(affected),
            severity=severity,
            recommendation=(
                f"Review what's driving {emotion} signals — schedule check-ins "
                "with the affected employees."
            ),
        )

    # 2) Department sentiment drop — current half-window vs prior half-window.
    half = max(3, days // 2)
    current_start = now - timedelta(days=half)
    prior_start = now - timedelta(days=half * 2)

    def _dept_avg_score(start, end) -> Dict[Any, float]:
        rows = (
            db.query(User.department_id, func.avg(SentimentLog.score).label("avg"))
            .join(User, User.id == SentimentLog.employee_id)
            .filter(SentimentLog.created_at >= start)
            .filter(SentimentLog.created_at < end)
            .filter(User.department_id.isnot(None))
            .group_by(User.department_id)
            .all()
        )
        return {r.department_id: float(r.avg or 0) for r in rows}

    current = _dept_avg_score(current_start, now)
    prior = _dept_avg_score(prior_start, current_start)
    dept_names = {d.id: d.name for d in db.query(Department).all()}

    for dept_id, curr_avg in current.items():
        prior_avg = prior.get(dept_id)
        if prior_avg is None or curr_avg <= 0 or prior_avg <= 0:
            continue
        drop = prior_avg - curr_avg
        if drop >= 8:
            severity = "high" if drop >= 15 else "medium"
            dname = dept_names.get(dept_id, "Department")
            _push(
                patterns,
                type="department_drop",
                label=f"{dname} sentiment dropped {int(drop)} points",
                affected_count=1,
                severity=severity,
                recommendation=(
                    f"Workload / morale review in {dname} — start with a manager 1:1."
                ),
            )

    # 3) Repeated complaint categories — clusters of tickets.
    ticket_rows = (
        db.query(Ticket.category, func.count(Ticket.id).label("n"))
        .filter(Ticket.created_at >= cutoff)
        .filter(Ticket.category.isnot(None))
        .filter(Ticket.category != "")
        .group_by(Ticket.category)
        .having(func.count(Ticket.id) >= 3)
        .order_by(func.count(Ticket.id).desc())
        .all()
    )
    for category, n in ticket_rows[:3]:
        severity = "high" if n >= 5 else "medium"
        _push(
            patterns,
            type="complaint_category",
            label=f"{n} {category} tickets in last {days} days",
            affected_count=int(n),
            severity=severity,
            recommendation=(
                f"Look for a common root cause in {category} tickets — group, "
                "skim summaries, and respond at the team level if it's systemic."
            ),
        )

    # 4) Top at-risk individuals — high risk_score on EmployeeScore.
    risk_rows = (
        db.query(EmployeeScore.employee_id, EmployeeScore.risk_score, User.name)
        .join(User, User.id == EmployeeScore.employee_id)
        .filter(EmployeeScore.risk_score >= 60)
        .order_by(EmployeeScore.risk_score.desc())
        .limit(3)
        .all()
    )
    for emp_id, risk, name in risk_rows:
        severity = "high" if int(risk) >= 80 else "medium"
        _push(
            patterns,
            type="at_risk_individual",
            label=f"{name} — risk score {int(risk)}/100",
            affected_count=1,
            severity=severity,
            recommendation=(
                f"Schedule a 1:1 with {name} — sustained negative signal puts "
                "them in the attrition-risk band."
            ),
        )

    patterns.sort(
        key=lambda p: (_SEVERITY_ORDER.get(p["severity"], 3), -p["affected_count"])
    )
    return patterns[:8]
