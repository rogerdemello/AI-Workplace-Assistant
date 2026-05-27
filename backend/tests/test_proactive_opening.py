"""Tests for the daily-ritual + memory-aware proactive opener."""

from datetime import timedelta

from app.core.time import utcnow_naive
from app.models.conversation import Conversation, ConversationStatus
from app.models.personal_fact import PersonalFact, PersonalFactType
from app.services import proactive_opening
from app.services.proactive_opening import ProactiveOpening, build_proactive_chat_opening


def test_first_time_user_gets_first_time_opener_and_mood_chip(db, test_user):
    opening = build_proactive_chat_opening(db, test_user)
    assert isinstance(opening, ProactiveOpening)
    assert opening.suggested_mood_checkin is True
    # First-time copy mentions Mark / welcome, not the returning-user starters.
    assert "Mark" in opening.text or "Welcome" in opening.text


def test_first_chat_of_day_invites_mood_checkin(db, test_user):
    # A conversation from *yesterday* makes the user "returning" but with no
    # conversation today → daily check-in branch.
    convo = Conversation(user_id=test_user.id, status=ConversationStatus.active)
    db.add(convo)
    db.commit()
    convo.started_at = utcnow_naive() - timedelta(days=2)
    db.commit()

    opening = build_proactive_chat_opening(db, test_user)
    assert opening.suggested_mood_checkin is True


def test_second_chat_same_day_no_mood_checkin(db, test_user):
    # Two conversations already today → not the first chat of the day.
    for _ in range(2):
        convo = Conversation(user_id=test_user.id, status=ConversationStatus.active)
        db.add(convo)
        db.commit()

    opening = build_proactive_chat_opening(db, test_user)
    assert opening.suggested_mood_checkin is False


def test_memory_reference_skips_sensitive_tags(db, test_user, monkeypatch):
    # Force the probability gate open so the only thing under test is the
    # sensitive-tag filter.
    monkeypatch.setattr(proactive_opening.random, "random", lambda: 0.0)

    class _Mem:
        summary = "the big launch and how stressful crunch week was"
        tags = ["stress", "burnout"]

    class _Svc:
        def retrieve_memory(self, user_id, limit=1):
            return [_Mem()]

    monkeypatch.setattr(proactive_opening, "get_memory_service", lambda db: _Svc())

    ref = proactive_opening._recent_memory_reference(db, test_user.id)
    assert ref is None  # sensitive tags must never surface in a light greeting


def test_memory_reference_surfaces_neutral_summary(db, test_user, monkeypatch):
    monkeypatch.setattr(proactive_opening.random, "random", lambda: 0.0)

    class _Mem:
        summary = "your weekend hiking trip"
        tags = ["hobby", "weekend"]

    class _Svc:
        def retrieve_memory(self, user_id, limit=1):
            return [_Mem()]

    monkeypatch.setattr(proactive_opening, "get_memory_service", lambda db: _Svc())

    ref = proactive_opening._recent_memory_reference(db, test_user.id)
    assert ref is not None
    assert "hiking" in ref


def test_start_endpoint_returns_mood_flag(client, test_user, auth_headers, mock_redis):
    res = client.post("/api/v1/chat/conversations/start", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert "greeting" in body and body["greeting"].strip()
    assert "suggested_mood_checkin" in body
    # Fresh test user → first-time → mood check-in suggested.
    assert body["suggested_mood_checkin"] is True
