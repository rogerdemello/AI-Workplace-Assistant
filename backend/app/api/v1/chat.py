from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Any, List, Optional
from uuid import UUID
from datetime import datetime, timedelta
import json
import time

from ...core import metrics
from ...core.time import utcnow_naive
from ...database import get_db
from ...core.feature_flags import get_feature_flags
from ...events import event_bus
from ...events.events import (
    DomainEvent,
    EVENT_MESSAGE_RECEIVED,
    EVENT_SENTIMENT_DETECTED,
)
from ...schemas.chat import (
    ConversationCreate,
    ConversationResponse,
    ConversationListResponse,
    MessageCreate,
    MessageResponse,
    ChatRequest,
    ChatResponse,
    ConversationStartResponse,
    FlowMetadata,
    MessageSender,
)
from ...models.conversation import (
    Conversation,
    Message as ConversationMessage,
    MessageSender as ConversationMessageSender,
)
from ...auth import get_current_user
from ...models.user import User
from ...services.chat import ChatService
from ...services.memory_filters import should_store_memory
from ...services.memory_service import get_memory_service
from ...services.mark_proactive import get_mark_proactive_service
from ...services.proactive_opening import build_proactive_chat_opening
from ...services.smart_chat import get_smart_chat_service
from ...services.sentiment import SentimentService
from ...services.sentiment_pipeline import SentimentPipelineService
from ...services.mental_health import check_and_alert_mental_health
from ...services.hr_personality import detect_conversation_mode
from ...services.chat_optimizations import sync_chat_sentiment_label_score
from ...config import settings
import logging
import os
import time

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)
CHAT_STREAM_TIMEOUT_MS = max(3000, int(os.getenv("CHAT_STREAM_TIMEOUT_MS", "12000")))


def _should_persist_sentiment_pipeline(_intelligence_snapshot: Optional[dict[str, Any]]) -> bool:
    """Always persist per-message sentiment + employee aggregates for HR dashboards."""
    return True


def _run_sentiment_pipeline_for_user_message(
    db: Session,
    *,
    employee_id: UUID,
    user_message: Optional[ConversationMessage],
    message_text: str,
    sentiment_label: str,
    sentiment_score: float,
    intelligence_snapshot: Optional[dict[str, Any]] = None,
    conversation_id: Optional[UUID] = None,
) -> None:
    """Updates sentiment_logs + employee_score so HR dashboards reflect chat tone."""
    if user_message is None:
        return

    started = time.monotonic()
    try:
        SentimentPipelineService(db).process_message(
            employee_id=employee_id,
            message_id=user_message.id,
            message_text=message_text,
            sentiment_label=sentiment_label,
            sentiment_score=sentiment_score,
            intelligence_snapshot=intelligence_snapshot,
            conversation_id=conversation_id,
        )
        metrics.increment("sentiment_pipeline_processed_total")
    except Exception as exc:
        # This failing means an employee's signal never reaches the HR dashboard,
        # so it needs to be countable and greppable, not just a stack trace.
        metrics.increment(
            "sentiment_pipeline_failures_total", {"error": type(exc).__name__}
        )
        logger.warning(
            "event=sentiment_pipeline_failed employee_id=%s message_id=%s error=%s",
            employee_id,
            user_message.id,
            type(exc).__name__,
            exc_info=True,
        )
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        metrics.observe_latency("sentiment_pipeline_seconds", time.monotonic() - started)


# ─────────────────────────────────────────────────────────────────────────────
# Unified /chat/message endpoint  (spec: POST /chat/message — MOST IMPORTANT)
# ─────────────────────────────────────────────────────────────────────────────

class UnifiedChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4096)
    conversation_id: Optional[UUID] = None  # if omitted, a new conversation is created


class UnifiedChatResponse(BaseModel):
    response: str
    intent: Optional[str] = None
    sentiment: Optional[str] = None
    conversation_id: str
    conversation_state: Optional[dict] = None
    context: Optional[dict] = None
    flow_metadata: Optional[FlowMetadata] = None
    active_flow: Optional[str] = None
    last_intent: Optional[str] = None
    completed: bool = False


@router.post("/message", response_model=UnifiedChatResponse)
def unified_chat_message(
    request: UnifiedChatRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Unified entry point for all employee chat interactions.

    Flow:
      1. Fetch or create conversation
      2. Detect intent (via SmartChatService)
      3. Extract entities
      4. Update state in DB
      5. Check missing fields
      6. Decide next step
      7. Trigger action when complete
      8. Generate response
      9. Store both messages
     10. Log sentiment
    """
    chat_service = ChatService(db)

    # ── Step 1: resolve conversation ──────────────────────────────────────
    conversation_id = request.conversation_id
    if conversation_id:
        conv = chat_service.get_conversation(conversation_id, current_user.id)
        if not conv:
            # Stale client id (reseed, new device) — start fresh instead of hard 404
            logger.warning(
                "Unknown conversation_id=%s for user=%s; creating a new conversation",
                conversation_id,
                current_user.id,
            )
            conv = chat_service.create_conversation(current_user.id)
            conversation_id = conv.id
    else:
        conv = chat_service.create_conversation(current_user.id)
        conversation_id = conv.id

    # ── Steps 2-7: conversation engine processes the message ──────────────
    try:
        smart_service = get_smart_chat_service(
            db=db,
            user_id=current_user.id,
            use_mock=False,
            conversation_id=conversation_id,
        )
        result = smart_service.process_message(request.message)
    except Exception as exc:
        logger.error(f"SmartChatService error: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Mark is having a moment. Please try again shortly.",
        )

    try:
        se = SentimentService(db)
        sentiment_label, sentiment_score = sync_chat_sentiment_label_score(se, request.message)
    except Exception:
        logger.warning("Sentiment analysis failed", exc_info=True)
        sentiment_label = result.get("sentiment", "neutral")
        sentiment_score = 0.0

    intel = smart_service.flow_context.pop("_intelligence_sentiment", None)
    if intel:
        sentiment_label = str(intel.get("label", sentiment_label))
        s0 = int(intel.get("score_0_100", 50))
        sentiment_score = max(-1.0, min(1.0, (s0 - 50) / 50.0))

    # ── Step 9: persist both messages (single commit) ─────────────────────
    try:
        user_message, _bot_msg = chat_service.add_user_and_bot_message_pair(
            conversation_id,
            user_text=request.message,
            user_sentiment=sentiment_label,
            bot_text=result["response"],
        )
    except Exception:
        logger.warning("Failed to persist messages", exc_info=True)
        user_message = None

    # Sentiment pipeline (sentiment_logs + employee_scores for HR dashboards) is
    # HR-facing only; it's deferred off the chat reply path below rather than run
    # synchronously. user_message is already committed, so its id is stable.
    pipeline_message_id = (
        user_message.id
        if (user_message is not None and _should_persist_sentiment_pipeline(intel))
        else None
    )

    try:
        event_bus.publish(
            DomainEvent(
                name=EVENT_MESSAGE_RECEIVED,
                payload={
                    "user_id": str(current_user.id),
                    "conversation_id": str(conversation_id),
                    "message": request.message,
                    "intent": result.get("intent") or "general_query",
                },
            )
        )
        event_bus.publish(
            DomainEvent(
                name=EVENT_SENTIMENT_DETECTED,
                payload={
                    "user_id": str(current_user.id),
                    "conversation_id": str(conversation_id),
                    "sentiment": sentiment_label,
                },
            )
        )
    except Exception:
        logger.warning("Event publish skipped", exc_info=True)

    intent_guess = result.get("intent") or "general_query"
    if settings.CHAT_DEFER_NONBLOCKING_SIDE_EFFECTS:
        background_tasks.add_task(
            _defer_chat_nonblocking_side_effects,
            employee_id=current_user.id,
            conversation_id=conversation_id,
            message_text=request.message,
            sentiment_score=sentiment_score,
            intent=intent_guess,
            sentiment_label=str(sentiment_label),
            pipeline_message_id=pipeline_message_id,
        )
    else:
        if pipeline_message_id is not None:
            _run_sentiment_pipeline_for_user_message(
                db,
                employee_id=current_user.id,
                user_message=user_message,
                message_text=request.message,
                sentiment_label=str(sentiment_label),
                sentiment_score=float(sentiment_score or 0.0),
                intelligence_snapshot=intel,
                conversation_id=conversation_id,
            )
        if get_feature_flags().enable_proactive:
            try:
                get_mark_proactive_service(db=db).capture_chat_signal(
                    user_id=current_user.id,
                    conversation_id=conversation_id,
                    text=request.message,
                    source="chat",
                    sentiment_score_override=sentiment_score,
                )
            except Exception:
                logger.warning("Wellbeing signal capture skipped", exc_info=True)

        try:
            check_and_alert_mental_health(db, current_user.id)
        except Exception:
            logger.warning("Mental health check skipped", exc_info=True)

        try:
            _store_memory_hint(
                db=db,
                user_id=current_user.id,
                user_message=request.message,
                intent=intent_guess,
                sentiment=sentiment_label,
            )
        except Exception:
            logger.warning("Memory hint skipped", exc_info=True)

    return UnifiedChatResponse(
        response=result["response"],
        intent=result.get("intent"),
        sentiment=str(sentiment_label),
        conversation_id=str(conversation_id),
        conversation_state={"state": result.get("conversation_state")},
        context=result.get("context"),
        flow_metadata=result.get("flow_metadata"),
        active_flow=result.get("context", {}).get("active_flow"),
        last_intent=result.get("intent"),
        completed=smart_service.flow_context.get("state_contract", {}).get("completed", False),
    )


class MemoryCardResponse(BaseModel):
    title: str
    summary: str
    tags: List[str] = Field(default_factory=list)
    last_updated: str


def _store_memory_hint(db: Session, user_id: UUID, user_message: str, intent: str, sentiment: str | None) -> None:
    """Persist lightweight memory snippets for later personalization cards."""
    cleaned = (user_message or "").strip()
    if not should_store_memory(cleaned, intent=intent, sentiment=sentiment):
        return

    intent_key = (intent or "general_query").strip().lower()
    summary = f"{intent_key.replace('_', ' ').title()} topic: {cleaned[:180]}"

    memory_service = get_memory_service(db)
    latest = memory_service.retrieve_memory(user_id=user_id, limit=1)
    if latest and latest[0].summary == summary:
        return

    tags = [intent_key]
    if sentiment:
        tags.append(str(sentiment).lower())
    memory_service.store_memory(user_id=user_id, summary=summary, tags=tags[:3])


def _memory_cards_for_user(db: Session, user_id: UUID, limit: int = 3) -> List[MemoryCardResponse]:
    memory_service = get_memory_service(db)
    stored = memory_service.retrieve_memory(user_id=user_id, limit=limit)
    if stored:
        cards: List[MemoryCardResponse] = []
        for item in stored:
            tags = [str(tag) for tag in (item.tags or []) if str(tag).strip()][:4]
            primary = tags[0].replace("_", " ").title() if tags else "Recent"
            cards.append(
                MemoryCardResponse(
                    title=f"{primary} memory",
                    summary=item.summary,
                    tags=tags,
                    last_updated=item.created_at.isoformat(),
                )
            )
        return cards

    recent_messages = (
        db.query(ConversationMessage.intent, ConversationMessage.message_text, ConversationMessage.created_at)
        .join(Conversation, ConversationMessage.conversation_id == Conversation.id)
        .filter(
            Conversation.user_id == user_id,
            ConversationMessage.sender == ConversationMessageSender.user,
        )
        .order_by(ConversationMessage.created_at.desc())
        .limit(40)
        .all()
    )

    if not recent_messages:
        return []

    cards: List[MemoryCardResponse] = []
    seen_keys: set[str] = set()
    for intent, message_text, created_at in recent_messages:
        intent_key = (intent or "general_query").strip().lower()
        if intent_key in seen_keys:
            continue

        snippet = (message_text or "").strip()
        if not snippet:
            continue

        seen_keys.add(intent_key)
        title = f"{intent_key.replace('_', ' ').title()} memory"
        summary = snippet if len(snippet) <= 180 else f"{snippet[:177]}..."
        cards.append(
            MemoryCardResponse(
                title=title,
                summary=summary,
                tags=[intent_key],
                last_updated=created_at.isoformat() if created_at else "",
            )
        )

        try:
            memory_service.store_memory(user_id=user_id, summary=summary, tags=[intent_key])
        except Exception:
            logger.warning("Failed to persist synthesized memory card", exc_info=True)

        if len(cards) >= limit:
            break

    return cards


def _defer_chat_nonblocking_side_effects(
    *,
    employee_id: UUID,
    conversation_id: UUID,
    message_text: str,
    sentiment_score: float,
    intent: str,
    sentiment_label: str,
    pipeline_message_id: Optional[UUID] = None,
) -> None:
    """Runs after HTTP response — own DB session; must not touch request-scoped `db`."""
    from ...database import SessionLocal

    db = SessionLocal()
    try:
        # Sentiment pipeline (sentiment_logs + employee_scores for HR dashboards)
        # writes to remote Postgres and recomputes aggregates — kept off the chat
        # reply path. The user_message was already committed by the request.
        if pipeline_message_id is not None:
            started = time.monotonic()
            try:
                SentimentPipelineService(db).process_message(
                    employee_id=employee_id,
                    message_id=pipeline_message_id,
                    message_text=message_text,
                    sentiment_label=sentiment_label,
                    sentiment_score=float(sentiment_score or 0.0),
                    conversation_id=conversation_id,
                )
                metrics.increment(
                    "sentiment_pipeline_processed_total", {"path": "deferred"}
                )
            except Exception as exc:
                # Same instrumentation as the synchronous path — this is the
                # default in production (CHAT_DEFER_NONBLOCKING_SIDE_EFFECTS),
                # so leaving it uncounted would blind the metric that matters.
                metrics.increment(
                    "sentiment_pipeline_failures_total",
                    {"error": type(exc).__name__, "path": "deferred"},
                )
                logger.warning(
                    "event=sentiment_pipeline_failed path=deferred employee_id=%s "
                    "message_id=%s error=%s",
                    employee_id,
                    pipeline_message_id,
                    type(exc).__name__,
                    exc_info=True,
                )
                try:
                    db.rollback()
                except Exception:
                    pass
            finally:
                metrics.observe_latency(
                    "sentiment_pipeline_seconds",
                    time.monotonic() - started,
                    {"path": "deferred"},
                )
        if get_feature_flags().enable_proactive:
            try:
                get_mark_proactive_service(db=db).capture_chat_signal(
                    user_id=employee_id,
                    conversation_id=conversation_id,
                    text=message_text,
                    source="chat",
                    sentiment_score_override=sentiment_score,
                )
            except Exception:
                logger.warning("Deferred wellbeing capture skipped", exc_info=True)
        try:
            check_and_alert_mental_health(db, employee_id)
        except Exception:
            logger.warning("Deferred mental health check skipped", exc_info=True)
        try:
            _store_memory_hint(
                db=db,
                user_id=employee_id,
                user_message=message_text,
                intent=intent,
                sentiment=sentiment_label,
            )
        except Exception:
            logger.warning("Deferred memory hint skipped", exc_info=True)
    finally:
        db.close()


def get_chat_service(db: Session = Depends(get_db)) -> ChatService:
    return ChatService(db)


def get_smart_service(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    return get_smart_chat_service(db=db, user_id=user.id, use_mock=False)

@router.post("/conversations", response_model=ConversationResponse)
def create_conversation(
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service)
):
    conversation = service.create_conversation(current_user.id)
    return conversation

@router.get("/conversations", response_model=List[ConversationListResponse])
def get_conversations(
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service)
):
    conversations = service.get_user_conversations(current_user.id)
    result = []
    for conv in conversations:
        last_msg = conv.messages[0].message_text if conv.messages else None
        result.append(ConversationListResponse(
            id=conv.id,
            user_id=conv.user_id,
            status=conv.status,
            started_at=conv.started_at,
            ended_at=conv.ended_at,
            last_message=last_msg
        ))
    return result

@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service)
):
    conversation = service.get_conversation(conversation_id, current_user.id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    return conversation

@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
def add_message(
    conversation_id: UUID,
    message: MessageCreate,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
    db: Session = Depends(get_db)
):
    conversation = service.get_conversation(conversation_id, current_user.id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    sentiment_label = None
    sentiment_score = None
    intelligence_snapshot: Optional[dict[str, Any]] = None
    if message.sender == MessageSender.user:
        try:
            se = SentimentService(db)
            sentiment_label, sentiment_score = sync_chat_sentiment_label_score(se, message.message_text)
        except Exception:
            logger.warning("Sentiment analysis failed", exc_info=True)

        intelligence_snapshot = None
        if getattr(settings, "ENABLE_MARK_INTELLIGENCE_PIPELINE", False) and not settings.CHAT_SKIP_INTELLIGENCE_SNAPSHOT:
            try:
                from ...services.intelligence.sentiment_service import analyze_user_message_intelligence

                intelligence_snapshot = analyze_user_message_intelligence(message.message_text)
            except Exception:
                logger.warning("Intelligence sentiment snapshot skipped", exc_info=True)
        if intelligence_snapshot:
            sentiment_label = str(intelligence_snapshot.get("label", sentiment_label or "neutral"))
            s0 = int(intelligence_snapshot.get("score_0_100", 50))
            sentiment_score = max(-1.0, min(1.0, (s0 - 50) / 50.0))

    msg = service.add_message(
        conversation_id=conversation_id,
        message_text=message.message_text,
        sender=message.sender,
        sentiment=sentiment_label,
    )

    if message.sender == MessageSender.user:
        if _should_persist_sentiment_pipeline(intelligence_snapshot):
            _run_sentiment_pipeline_for_user_message(
                db,
                employee_id=current_user.id,
                user_message=msg,
                message_text=message.message_text,
                sentiment_label=str(sentiment_label or "neutral"),
                sentiment_score=float(sentiment_score if sentiment_score is not None else 0.0),
                intelligence_snapshot=intelligence_snapshot,
                conversation_id=conversation_id,
            )

        try:
            get_mark_proactive_service(db=service.db).capture_chat_signal(
                user_id=current_user.id,
                conversation_id=conversation_id,
                text=message.message_text,
                source="chat",
                sentiment_score_override=sentiment_score,
            )
        except Exception:
            logger.warning("Failed to capture chat wellbeing signal", exc_info=True)

        try:
            check_and_alert_mental_health(service.db, current_user.id)
        except Exception:
            logger.warning("Mental health check skipped", exc_info=True)

    return msg

@router.post("/conversations/{conversation_id}/close")
def close_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service)
):
    conversation = service.close_conversation(conversation_id, current_user.id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    return {"status": "closed", "conversation_id": conversation_id}


@router.post("/conversations/{conversation_id}/respond", response_model=ChatResponse)
def respond_to_message(
    conversation_id: UUID,
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    result, smart_service = _process_conversation_message(
        db=db,
        current_user=current_user,
        conversation_id=conversation_id,
        message=request.message,
        background_tasks=background_tasks,
    )
    return ChatResponse(
        response=result["response"],
        intent=result.get("intent"),
        sentiment=result.get("sentiment"),
        conversation_state={"state": result.get("conversation_state")},
        context=result.get("context"),
        flow_metadata=result.get("flow_metadata"),
        active_flow=result.get("context", {}).get("active_flow"),
        last_intent=result.get("intent"),
        completed=smart_service.flow_context.get("state_contract", {}).get("completed", False),
    )


def _process_conversation_message(
    *,
    db: Session,
    current_user: User,
    conversation_id: UUID,
    message: str,
    background_tasks: Optional[BackgroundTasks] = None,
):
    conversation = ChatService(db).get_conversation(conversation_id, current_user.id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    try:
        smart_service = get_smart_chat_service(
            db=db,
            user_id=current_user.id,
            use_mock=False,
            conversation_id=conversation_id,
        )
        result = smart_service.process_message(message)

        try:
            se = SentimentService(db)
            sentiment_label, sentiment_score = sync_chat_sentiment_label_score(se, message)
        except Exception:
            sentiment_label = result.get("sentiment", "neutral")
            sentiment_score = 0.0

        intel = smart_service.flow_context.pop("_intelligence_sentiment", None)
        if intel:
            sentiment_label = str(intel.get("label", sentiment_label))
            s0 = int(intel.get("score_0_100", 50))
            sentiment_score = max(-1.0, min(1.0, (s0 - 50) / 50.0))

        chat_svc = ChatService(db)
        user_message, _bot = chat_svc.add_user_and_bot_message_pair(
            conversation_id,
            user_text=message,
            user_sentiment=str(sentiment_label),
            bot_text=result["response"],
        )
        if _should_persist_sentiment_pipeline(intel):
            _run_sentiment_pipeline_for_user_message(
                db,
                employee_id=current_user.id,
                user_message=user_message,
                message_text=message,
                sentiment_label=str(sentiment_label),
                sentiment_score=float(sentiment_score or 0.0),
                intelligence_snapshot=intel,
                conversation_id=conversation_id,
            )

        intent_guess = result.get("intent") or "general_query"
        if background_tasks is not None and settings.CHAT_DEFER_NONBLOCKING_SIDE_EFFECTS:
            background_tasks.add_task(
                _defer_chat_nonblocking_side_effects,
                employee_id=current_user.id,
                conversation_id=conversation_id,
                message_text=message,
                sentiment_score=sentiment_score,
                intent=intent_guess,
                sentiment_label=str(sentiment_label),
            )
        else:
            try:
                get_mark_proactive_service(db=db).capture_chat_signal(
                    user_id=current_user.id,
                    conversation_id=conversation_id,
                    text=message,
                    source="chat",
                    sentiment_score_override=sentiment_score,
                )
            except Exception:
                logger.warning("Failed to capture respond() wellbeing signal", exc_info=True)

            try:
                check_and_alert_mental_health(db, current_user.id)
            except Exception:
                logger.warning("Mental health check skipped", exc_info=True)

            try:
                _store_memory_hint(
                    db=db,
                    user_id=current_user.id,
                    user_message=message,
                    intent=intent_guess,
                    sentiment=sentiment_label,
                )
            except Exception:
                logger.warning("Memory hint capture skipped", exc_info=True)

        return result, smart_service
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="I'm having trouble responding right now. Please try again in a moment.",
        )


@router.post("/conversations/{conversation_id}/respond/stream")
def stream_respond_to_message(
    conversation_id: UUID,
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = ChatService(db).get_conversation(conversation_id, current_user.id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    smart_service = get_smart_chat_service(
        db=db,
        user_id=current_user.id,
        use_mock=False,
        conversation_id=conversation_id,
    )
    classified = smart_service.intent_classifier.classify(request.message, str(current_user.id))
    intent = smart_service._apply_intent_keyword_fallback(classified.get("intent", "general_query"), request.message)
    # Align with ConversationOrchestrator: phrase keywords must override the classifier (e.g. "apply leave").
    strong = smart_service._detect_strong_intent(request.message)
    if strong:
        intent = strong

    def _event(event_type: str, payload: dict) -> str:
        return f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"

    streamable_non_flow_intents = {"general_query", "help_request", "email_draft", "policy_query", "benefits_question"}
    has_active_flow = bool(smart_service.current_flow)

    if intent not in streamable_non_flow_intents or has_active_flow:
        result, processed_service = _process_conversation_message(
            db=db,
            current_user=current_user,
            conversation_id=conversation_id,
            message=request.message,
            background_tasks=background_tasks,
        )
        response_text = result.get("response") or ""
        metadata_payload = {
            "intent": result.get("intent"),
            "sentiment": result.get("sentiment"),
            "conversation_state": {"state": result.get("conversation_state")},
            "context": result.get("context"),
            "flow_metadata": result.get("flow_metadata"),
            "active_flow": result.get("context", {}).get("active_flow"),
            "last_intent": result.get("intent"),
            "completed": processed_service.flow_context.get("state_contract", {}).get("completed", False),
        }

        def event_stream_flow():
            yield _event("meta", {"conversation_id": str(conversation_id)})
            # Flow responses are deterministic (state-machine/templates);
            # fake word-by-word streaming adds latency without value.
            # Send the complete response immediately for better perceived speed.
            yield _event("token", {"text": response_text})
            yield _event("done", {"response": response_text, **metadata_payload})

        return StreamingResponse(event_stream_flow(), media_type="text/event-stream")

    try:
        se = SentimentService(db)
        sentiment, sentiment_score = sync_chat_sentiment_label_score(se, request.message)
    except Exception:
        sentiment = "neutral"
        sentiment_score = 0.0

    intel_stream: Optional[dict[str, Any]] = None
    if settings.ENABLE_MARK_INTELLIGENCE_PIPELINE and not settings.CHAT_SKIP_INTELLIGENCE_SNAPSHOT:
        from ...services.intelligence.sentiment_service import analyze_user_message_intelligence

        intel_stream = analyze_user_message_intelligence(request.message)
        if intel_stream:
            sentiment = str(intel_stream.get("label", sentiment))
            s0 = int(intel_stream.get("score_0_100", 50))
            sentiment_score = max(-1.0, min(1.0, (s0 - 50) / 50.0))

    mode = detect_conversation_mode(request.message, sentiment)

    def event_stream_general():
        yield _event("meta", {"conversation_id": str(conversation_id)})
        accumulated = ""
        stream_started = time.monotonic()
        try:
            for token in smart_service.stream_non_flow_intent_tokens(
                intent=intent,
                message=request.message,
                sentiment=sentiment,
                mode=mode,
            ):
                if not token:
                    continue
                accumulated += token
                yield _event("token", {"text": accumulated})
                if (time.monotonic() - stream_started) * 1000 >= CHAT_STREAM_TIMEOUT_MS:
                    raise TimeoutError("stream token timeout")
        except Exception:
            logger.warning("Token stream failed/timed out, reverting to buffered response", exc_info=True)
            try:
                if intent in {"policy_query", "benefits_question"}:
                    buffered = smart_service._handle_policy_query(request.message)
                else:
                    buffered = smart_service._handle_general_query(
                        request.message, sentiment=sentiment, mode=mode
                    )
            except Exception:
                # The buffered path calls the model too, so when the provider is
                # unreachable it fails exactly like the stream did. Letting that
                # escape kills the SSE response mid-flight ("No response
                # returned") and the user's message vanishes with no reply.
                # Degrade to a plain apology instead of dropping the turn.
                metrics.increment("chat_reply_unavailable_total", {"intent": intent})
                logger.error(
                    "event=chat_reply_unavailable intent=%s — model unreachable on "
                    "both stream and buffered paths",
                    intent,
                    exc_info=True,
                )
                buffered = (
                    "Sorry — I can't reach my language service right now, so I "
                    "can't answer that properly. Your message is saved. Please "
                    "try again in a moment, or raise a ticket and HR will pick "
                    "it up."
                )
            accumulated = buffered
            yield _event("token", {"text": accumulated})

        final_response = smart_service._finalize_response(
            accumulated,
            intent=intent,
            sentiment=sentiment,
            mode=mode,
            source_message=request.message,
        )

        chat_stream = ChatService(db)
        user_msg, _bot_stream = chat_stream.add_user_and_bot_message_pair(
            conversation_id,
            user_text=request.message,
            user_sentiment=str(sentiment),
            bot_text=final_response,
        )
        if _should_persist_sentiment_pipeline(intel_stream):
            _run_sentiment_pipeline_for_user_message(
                db,
                employee_id=current_user.id,
                user_message=user_msg,
                message_text=request.message,
                sentiment_label=str(sentiment),
                sentiment_score=sentiment_score,
                intelligence_snapshot=intel_stream,
                conversation_id=conversation_id,
            )
        if settings.CHAT_DEFER_NONBLOCKING_SIDE_EFFECTS:
            background_tasks.add_task(
                _defer_chat_nonblocking_side_effects,
                employee_id=current_user.id,
                conversation_id=conversation_id,
                message_text=request.message,
                sentiment_score=sentiment_score,
                intent=intent,
                sentiment_label=str(sentiment),
            )
        yield _event(
            "done",
            {
                "response": final_response,
                "intent": intent,
                "sentiment": sentiment,
                "conversation_state": {"state": "active"},
                "context": smart_service.user_context,
                "flow_metadata": None,
                "active_flow": None,
                "last_intent": intent,
                "completed": False,
            },
        )

    return StreamingResponse(event_stream_general(), media_type="text/event-stream")


@router.post("/conversations/start", response_model=ConversationStartResponse)
def start_conversation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Build the greeting BEFORE creating today's conversation row so the
    # first-time / first-chat-of-day detection isn't fooled by the new row.
    suggested_mood_checkin = False
    try:
        opening = build_proactive_chat_opening(db, current_user)
        greeting = opening.text
        suggested_mood_checkin = opening.suggested_mood_checkin
    except Exception as e:
        logger.warning("Failed to build proactive greeting: %s", e)
        greeting = "Hey — I'm Mark. What's on your mind today?"

    conversation = ChatService(db).create_conversation(current_user.id)

    ChatService(db).add_message(
        conversation_id=conversation.id,
        message_text=greeting,
        sender=MessageSender.bot,
    )

    return ConversationStartResponse(
        conversation_id=conversation.id,
        greeting=greeting,
        suggested_mood_checkin=suggested_mood_checkin,
    )


@router.get("/memory-cards", response_model=List[MemoryCardResponse])
def get_memory_cards(
    limit: int = Query(default=3, ge=1, le=6),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _memory_cards_for_user(db=db, user_id=current_user.id, limit=limit)


class PendingNudgeResponse(BaseModel):
    id: UUID
    text: str
    nudge_type: str
    created_at: datetime


@router.get("/nudges/pending", response_model=List[PendingNudgeResponse])
def get_pending_nudges(
    since: Optional[datetime] = Query(
        default=None,
        description="Only return nudges sent after this timestamp (client watermark).",
    ),
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Proactive messages the user missed while they had no chat open.

    The employee chat restores its transcript from local storage, so a nudge
    delivered over SSE reaches only an already-open tab. Quiet employees — the
    ones these check-ins exist for — are precisely the people without one. This
    lets the client pull anything sent since its own watermark on next open.
    """
    from ...services.mark_proactive import NUDGE_INTENT_PREFIX

    # Default window keeps a returning user from being buried in old nudges.
    cutoff = since or (utcnow_naive() - timedelta(days=7))

    rows = (
        db.query(ConversationMessage)
        .join(Conversation, ConversationMessage.conversation_id == Conversation.id)
        .filter(
            Conversation.user_id == current_user.id,
            ConversationMessage.sender == ConversationMessageSender.bot,
            ConversationMessage.intent.like(f"{NUDGE_INTENT_PREFIX}%"),
            ConversationMessage.created_at > cutoff,
        )
        .order_by(ConversationMessage.created_at.asc())
        .limit(limit)
        .all()
    )

    return [
        PendingNudgeResponse(
            id=row.id,
            text=row.message_text,
            nudge_type=(row.intent or "").removeprefix(NUDGE_INTENT_PREFIX),
            created_at=row.created_at,
        )
        for row in rows
    ]
