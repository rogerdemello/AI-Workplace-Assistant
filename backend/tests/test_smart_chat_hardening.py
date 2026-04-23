from unittest.mock import MagicMock

from app.models.ticket import Ticket, TicketPriority, TicketStatus
from app.services.smart_chat import SmartChatService


def _empty_ticket_entities():
    return {
        "department": None,
        "issue": None,
        "severity": None,
        "anonymous": None,
        "against": None,
        "timeline": None,
        "details": None,
    }


def test_leave_balance_intent_overrides_ticket_classifier(db, test_user, monkeypatch):
    service = SmartChatService(db=db, user_id=test_user.id, use_mock=True)

    monkeypatch.setattr(service.intent_classifier, "classify", lambda *_args, **_kwargs: {"intent": "ticket_create"})
    monkeypatch.setattr(service.sentiment_service, "analyze", lambda *_args, **_kwargs: {"sentiment": "neutral"})
    monkeypatch.setattr(service, "_handle_leave_balance", lambda: "Leave balance answer")

    result = service.process_message("How many leaves do I have left?")

    assert result["intent"] == "leave_balance"
    assert result["response"] == "Leave balance answer"
    assert service.current_flow is None


def test_reminder_intent_routes_to_reminder_handler(db, test_user, monkeypatch):
    service = SmartChatService(db=db, user_id=test_user.id, use_mock=True)

    monkeypatch.setattr(service.sentiment_service, "analyze", lambda *_args, **_kwargs: {"sentiment": "neutral"})
    monkeypatch.setattr(service, "_handle_reminder", lambda _msg: "Reminder created")

    result = service.process_message("Set alarm for 11am everyday")

    assert result["intent"] == "reminder"
    assert result["response"] == "Reminder created"


def test_ticket_flow_collects_severity_against_department_then_anonymous(db, test_user, monkeypatch):
    service = SmartChatService(db=db, user_id=test_user.id, use_mock=True)

    def extract_ticket_entities(message: str):
        lower = message.lower()
        data = _empty_ticket_entities()
        if "unfair" in lower or "manager" in lower:
            data["issue"] = message
            data["category"] = "complaint"
        if "sam" in lower:
            data["against"] = "Sam"
        if "hr" in lower:
            data["department"] = "HR"
        return data

    monkeypatch.setattr(service.entity_extractor, "extract_ticket_entities", extract_ticket_entities)
    monkeypatch.setattr(service, "_detect_strong_intent", lambda _msg: "ticket_create")
    monkeypatch.setattr(service.sentiment_service, "analyze", lambda *_args, **_kwargs: {"sentiment": "neutral"})

    first = service.process_message("There is unfair treatment in my team")["response"]
    second = service.process_message("urgent")["response"]
    third = service.process_message("It is against Sam")["response"]
    fourth = service.process_message("HR")["response"]

    assert "mild, serious, or urgent" in first
    assert "who is this against" in second.lower()
    assert "which department should handle this" in third.lower()
    assert "stay anonymous" in fourth.lower()
    assert service.flow_context["ticket_data"]["severity"] == "urgent"
    assert service.flow_context["ticket_data"]["issue"] == "There is unfair treatment in my team"
    assert service.flow_context["ticket_data"]["category"] == "complaint"


def test_duplicate_ticket_is_not_created_within_24_hours(db, test_user):
    import hashlib
    # Compute the exact query text and hash that _complete_ticket will produce
    query_text = (
        "wrong salary deduction for april payroll issue\n"
        "Severity: serious\n"
        "Against: Payroll Team\n"
        "Details: Amounts do not match expected payout."
    )
    ticket_hash = hashlib.sha256(query_text.lower().strip().encode()).hexdigest()

    existing = Ticket(
        user_id=test_user.id,
        query=query_text,
        category="finance",
        status=TicketStatus.open,
        priority=TicketPriority.medium,
        hash=ticket_hash,
    )
    db.add(existing)
    db.commit()

    service = SmartChatService(db=db, user_id=test_user.id, use_mock=True)
    ticket_data = {
        "issue": "wrong salary deduction for april payroll issue",
        "severity": "serious",
        "department": "Finance",
        "against": "Payroll Team",
        "details": "Amounts do not match expected payout.",
        "anonymous": False,
    }

    response = service._complete_ticket(ticket_data)
    total_tickets = db.query(Ticket).filter(Ticket.user_id == test_user.id).count()

    assert "already have a ticket for this" in response.lower()
    assert total_tickets == 1


def test_update_memory_skips_noise_and_stores_meaningful_inputs(db, test_user):
    service = SmartChatService(db=db, user_id=test_user.id, use_mock=True)
    recorder = MagicMock()
    service.emotional_memory.record_interaction = recorder

    service._update_memory("thanks", intent="general_query", sentiment="neutral")
    service._update_memory(
        "I feel overwhelmed due to deadlines and long hours",
        intent="general_query",
        sentiment="negative",
    )

    assert recorder.call_count == 1


def test_emotional_intent_detected_for_stressed_message(db, test_user):
    service = SmartChatService(db=db, user_id=test_user.id, use_mock=True)

    result = service.process_message("I feel stressed")

    assert result["intent"] == "emotional"
    assert "sorry" in result["response"].lower() or "here" in result["response"].lower()


def test_escalate_ticket_intent_sets_priority_to_critical(db, test_user):
    from app.models.ticket import Ticket, TicketStatus, TicketPriority
    from uuid import uuid4

    ticket = Ticket(
        id=uuid4(),
        user_id=test_user.id,
        query="Payroll issue",
        category="finance",
        status=TicketStatus.open,
        priority=TicketPriority.medium,
    )
    db.add(ticket)
    db.commit()

    service = SmartChatService(db=db, user_id=test_user.id, use_mock=True)
    monkeypatch = None

    result = service.process_message("escalate my ticket")

    db.refresh(ticket)
    assert result["intent"] == "escalate_ticket"
    assert ticket.priority == TicketPriority.critical
    assert ticket.status == TicketStatus.escalated
    assert "escalated" in result["response"].lower()
