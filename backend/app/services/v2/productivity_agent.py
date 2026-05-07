from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID
from typing import Dict, List

from sqlalchemy.orm import Session

from ...core.time import utcnow_naive
from ...models.calendar_integration import CalendarIntegration
from ...models.room import Room, RoomBooking
from ..calendar import CalendarService


@dataclass
class ProductivityResponse:
    handled: bool
    reply: str


class ProductivityAgent:
    """
    V2 foundation agent for productivity tasks.
    Full booking/scheduling integrations will be wired incrementally.
    """

    def __init__(self, db: Session, user_id: UUID) -> None:
        self.db = db
        self.user_id = user_id

    def maybe_handle(self, message: str, flow_context: Dict | None = None) -> ProductivityResponse:
        text = (message or "").lower()
        state = flow_context if isinstance(flow_context, dict) else {}

        meeting_confirmation = self._handle_meeting_confirmation(text=text, flow_context=state)
        if meeting_confirmation:
            return ProductivityResponse(handled=True, reply=meeting_confirmation)

        if re.search(r"\b(book|reserve).*(room|meeting room)\b", text):
            booked = self._try_book_room(text)
            if booked:
                return ProductivityResponse(handled=True, reply=booked)
            return ProductivityResponse(
                handled=True,
                reply=(
                    "Got it — I can help book a meeting room. "
                    "Share date, time, and duration, and I will check availability next."
                ),
            )
        if re.search(r"\b(schedule|set up).*(meeting|call)\b", text):
            slots = self._suggest_meeting_slots()
            if slots:
                attendees = self._extract_attendees(text)
                state["v2_pending_meeting_slots"] = slots
                if attendees:
                    state["v2_pending_meeting_attendees"] = attendees
                return ProductivityResponse(
                    handled=True,
                    reply=f"I found these slots: {', '.join(slots)}. Tell me which one to schedule.",
                )
            return ProductivityResponse(
                handled=True,
                reply=(
                    "Sure — I can schedule that. "
                    "Tell me attendees and preferred time window, then I will suggest slots."
                ),
            )
        if re.search(r"\b(email|draft|write).*(mail|email|message)\b", text):
            return ProductivityResponse(
                handled=True,
                reply="I can draft that. Should it be formal or casual?",
            )
        return ProductivityResponse(handled=False, reply="")

    def _handle_meeting_confirmation(self, *, text: str, flow_context: Dict) -> str:
        slots = flow_context.get("v2_pending_meeting_slots")
        if not isinstance(slots, list) or not slots:
            return ""
        if not any(token in text for token in ["first", "second", "third", "1", "2", "3", "yes", "book", "confirm"]):
            return ""
        index = 0
        if "second" in text or re.search(r"\b2\b", text):
            index = 1
        elif "third" in text or re.search(r"\b3\b", text):
            index = 2
        if index >= len(slots):
            index = 0
        selected = str(slots[index])
        attendees = flow_context.get("v2_pending_meeting_attendees") or []
        attendee_emails = [item for item in attendees if isinstance(item, str) and "@" in item]
        created = self._create_calendar_event_for_slot(selected, attendee_emails)
        if created:
            flow_context.pop("v2_pending_meeting_slots", None)
            flow_context.pop("v2_pending_meeting_attendees", None)
            return f"Done — meeting scheduled for {selected}. I created the calendar event."
        return f"I can schedule {selected}, but your calendar is not connected yet. Connect Google/Microsoft calendar first."

    def _try_book_room(self, text: str) -> str:
        time_match = re.search(r"\b(at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", text)
        if not time_match:
            return ""
        hour = int(time_match.group(2))
        minute = int(time_match.group(3) or 0)
        ampm = (time_match.group(4) or "").lower()
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0

        now = utcnow_naive()
        start = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if start <= now:
            start = start + timedelta(days=1)
        end = start + timedelta(hours=1)

        rooms = self.db.query(Room).filter(Room.is_active == True).order_by(Room.capacity.desc()).all()  # noqa: E712
        for room in rooms:
            conflict = (
                self.db.query(RoomBooking)
                .filter(
                    RoomBooking.room_id == room.id,
                    RoomBooking.start_time < end,
                    RoomBooking.end_time > start,
                )
                .first()
            )
            if conflict:
                continue
            booking = RoomBooking(
                room_id=room.id,
                user_id=self.user_id,
                title="Meeting booked via MARK",
                start_time=start,
                end_time=end,
            )
            self.db.add(booking)
            self.db.commit()
            return f"Done — room '{room.name}' is booked for {start.strftime('%Y-%m-%d %H:%M')}."
        return "I could not find a free room for that time. Want me to suggest alternate slots?"

    def _suggest_meeting_slots(self) -> list[str]:
        integration = (
            self.db.query(CalendarIntegration)
            .filter(CalendarIntegration.user_id == self.user_id, CalendarIntegration.access_token.isnot(None))
            .order_by(CalendarIntegration.updated_at.desc())
            .first()
        )
        if not integration:
            return []

    def _extract_attendees(self, text: str) -> List[str]:
        emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
        if emails:
            return emails[:5]
        # lightweight name extraction after "with ..."
        match = re.search(r"\bwith\s+([a-zA-Z\s,]+)", text)
        if not match:
            return []
        names = [name.strip() for name in match.group(1).split(",") if name.strip()]
        return [f"{name.replace(' ', '.')}@example.com" for name in names[:3]]

    def _create_calendar_event_for_slot(self, slot_label: str, attendees: List[str]) -> bool:
        integration = (
            self.db.query(CalendarIntegration)
            .filter(CalendarIntegration.user_id == self.user_id, CalendarIntegration.access_token.isnot(None))
            .order_by(CalendarIntegration.updated_at.desc())
            .first()
        )
        if not integration:
            return False
        # slot format: YYYY-MM-DD HH:MM-HH:MM
        slot_match = re.match(r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})-(\d{2}:\d{2})", slot_label)
        if not slot_match:
            return False
        day, start_hm, end_hm = slot_match.groups()
        start = utcnow_naive()
        end = utcnow_naive()
        try:
            start = start.replace(
                year=int(day[0:4]),
                month=int(day[5:7]),
                day=int(day[8:10]),
                hour=int(start_hm[0:2]),
                minute=int(start_hm[3:5]),
                second=0,
                microsecond=0,
            )
            end = end.replace(
                year=int(day[0:4]),
                month=int(day[5:7]),
                day=int(day[8:10]),
                hour=int(end_hm[0:2]),
                minute=int(end_hm[3:5]),
                second=0,
                microsecond=0,
            )
            if end <= start:
                end = start + timedelta(hours=1)
        except Exception:
            return False
        try:
            import asyncio

            service = CalendarService(integration.provider, integration.access_token or "", integration.refresh_token)
            asyncio.run(
                service.create_event(
                    title="Meeting scheduled by MARK",
                    start_time=start,
                    end_time=end,
                    attendees=attendees,
                    description="Auto-scheduled from MARK chat",
                    location=None,
                )
            )
            return True
        except Exception:
            return False
        start = utcnow_naive() + timedelta(hours=1)
        end = start + timedelta(days=1)
        try:
            service = CalendarService(integration.provider, integration.access_token or "", integration.refresh_token)
            import asyncio

            availability = asyncio.run(service.get_availability(start, end))
            slots: list[str] = []
            for day in availability[:2]:
                for slot in day.get("slots", []):
                    if slot.get("available") is False:
                        continue
                    slots.append(f"{day.get('date')} {slot.get('start')}-{slot.get('end')}")
                    if len(slots) >= 3:
                        return slots
            return slots
        except Exception:
            return []
