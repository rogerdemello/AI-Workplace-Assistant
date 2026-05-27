from __future__ import annotations

import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...auth import get_current_user, require_roles
from ...database import get_db
from ...models.hr_notification import HrNotification
from ...models.ticket import Ticket, TicketStatus
from ...models.user import User
from ...services.dashboard_analytics import compute_kpi_overview
from ...services.realtime_bus import realtime_bus

router = APIRouter(prefix="/realtime", tags=["realtime"])


def _build_snapshot_payload(db: Session) -> dict:
    unread_notifications = (
        db.query(func.count(HrNotification.id))
        .filter(HrNotification.is_read.is_(False))
        .scalar()
        or 0
    )
    open_tickets = (
        db.query(func.count(Ticket.id))
        .filter(Ticket.status.in_([TicketStatus.open, TicketStatus.in_progress, TicketStatus.escalated]))
        .scalar()
        or 0
    )
    metrics = compute_kpi_overview(db)
    return {
        "ts": datetime.utcnow().isoformat(),
        "unread_notifications": int(unread_notifications),
        "open_tickets": int(open_tickets),
        "engagement_score": float(metrics.get("engagement_score", 0)),
        "resolution_rate": float(metrics.get("resolution_rate", 0)),
        "total_tickets": int(metrics.get("total_tickets", 0)),
    }


@router.get("/hr/stream")
async def hr_realtime_stream(
    request: Request,
    db: Session = Depends(get_db),
    _hr: User = Depends(require_roles(["hr", "admin"])),
):
    def _event(name: str, payload: dict) -> str:
        return f"event: {name}\ndata: {json.dumps(payload)}\n\n"

    async def event_stream():
        queue = await realtime_bus.subscribe()
        while True:
            try:
                yield _event("hr_snapshot", _build_snapshot_payload(db))
                while True:
                    if await request.is_disconnected():
                        return
                    try:
                        message = await asyncio.wait_for(queue.get(), timeout=20)
                        yield _event(str(message.get("event_type", "hr_update")), message.get("payload", {}))
                        yield _event("hr_snapshot", _build_snapshot_payload(db))
                    except asyncio.TimeoutError:
                        # Keep connection healthy and send fresh heartbeat snapshot.
                        yield _event("hr_snapshot", _build_snapshot_payload(db))
            finally:
                await realtime_bus.unsubscribe(queue)
                break

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/me/stream")
async def employee_realtime_stream(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Per-user SSE stream. Forwards events addressed to this user (e.g.
    ``user_nudge``) so proactive nudges land in the open chat immediately,
    instead of waiting for the next 15-minute polling cycle."""

    user_id = str(current_user.id)

    def _event(name: str, payload: dict) -> str:
        return f"event: {name}\ndata: {json.dumps(payload)}\n\n"

    async def event_stream():
        queue = await realtime_bus.subscribe()
        try:
            # Initial comment so proxies flush headers and the client opens.
            yield ": connected\n\n"
            while True:
                if await request.is_disconnected():
                    return
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=20)
                    payload = message.get("payload", {}) or {}
                    if str(payload.get("user_id", "")) != user_id:
                        continue  # not addressed to this user
                    yield _event(str(message.get("event_type", "user_update")), payload)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"  # heartbeat keeps the connection alive
        finally:
            await realtime_bus.unsubscribe(queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
