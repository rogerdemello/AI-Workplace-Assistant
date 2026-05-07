from datetime import date, timedelta

from app.services.chat.contracts import FlowStateContract
from app.services.smart_chat import get_smart_chat_service


def test_flow_state_contract_normalizes_invalid_state_shape():
    contract = FlowStateContract.from_state(
        {"step": "issue", "data": "bad-shape", "completed": 1},
        intent="ticket_create",
    )
    assert contract.intent == "ticket_create"
    assert contract.step == "issue"
    assert contract.data == {}
    assert contract.completed is True


def test_ticket_flow_moves_to_next_missing_question(db, test_user):
    service = get_smart_chat_service(db=db, user_id=test_user.id, use_mock=True)

    first = service.process_message("I want to raise a complaint")
    second = service.process_message("My manager dismisses every idea I bring up")

    assert first["intent"] == "ticket_create"
    assert "mild, serious, or urgent" not in first["response"].lower()
    assert (
        "happened" in first["response"].lower()
        or "person" in first["response"].lower()
        or "specific" in first["response"].lower()
    )
    assert "person" in second["response"].lower() or "specific" in second["response"].lower()


def test_leave_flow_asks_one_missing_field_at_a_time(db, test_user):
    service = get_smart_chat_service(db=db, user_id=test_user.id, use_mock=True)
    start = (date.today() + timedelta(days=2)).isoformat()
    end = (date.today() + timedelta(days=3)).isoformat()

    step1 = service.process_message("I want to apply leave")
    step2 = service.process_message(start)
    step3 = service.process_message(end)
    step4 = service.process_message("sick leave")

    assert "start date" in step1["response"].lower()
    assert "end date" in step2["response"].lower()
    assert "type" in step3["response"].lower() or "leave" in step3["response"].lower()
    assert "reason" in step4["response"].lower()
