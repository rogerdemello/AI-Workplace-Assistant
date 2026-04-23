"""HR-facing proactive alerts (stored scans + manual refresh)."""

import json
import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ...auth import require_roles
from ...database import get_db
from ...models.hr_alert import HrAlert
from ...services.proactive_wellbeing import get_proactive_monitor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertOut(BaseModel):
    id: str
    title: str
    body: str | None
    severity: str
    alert_type: str | None
    source: str
    created_at: datetime
    acknowledged: bool

    model_config = ConfigDict(from_attributes=True)


def _store_from_wellbeing(db: Session) -> int:
    monitor = get_proactive_monitor(db)
    found = monitor.check_all_users()
    n = 0
    for a in found:
        row = HrAlert(
            title=(a.message or "Alert")[:500],
            body=json.dumps(a.to_dict()),
            severity=a.severity,
            alert_type=a.alert_type,
            source="proactive_wellbeing",
        )
        db.add(row)
        n += 1
    db.commit()
    return n


@router.get("", response_model=List[AlertOut])
def list_alerts(
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    rows = db.query(HrAlert).order_by(HrAlert.created_at.desc()).limit(limit).all()
    return [
        AlertOut(
            id=str(r.id),
            title=r.title,
            body=r.body,
            severity=r.severity,
            alert_type=r.alert_type,
            source=r.source,
            created_at=r.created_at,
            acknowledged=r.acknowledged,
        )
        for r in rows
    ]


@router.post("/run-scan")
def run_scan(
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    """Manual trigger: run wellbeing scan and persist new alerts."""
    try:
        n = _store_from_wellbeing(db)
        return {"ok": True, "alerts_stored": n}
    except Exception as e:
        logger.exception("run-scan failed")
        db.rollback()
        return {"ok": False, "error": str(e), "alerts_stored": 0}


@router.patch("/{alert_id}/ack")
def acknowledge_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    from uuid import UUID

    row = db.query(HrAlert).filter(HrAlert.id == UUID(alert_id)).first()
    if not row:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    row.acknowledged = True
    db.commit()
    return {"ok": True}
