from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

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
from ...services.smart_chat import get_smart_chat_service
from ...services.sentiment import SentimentService
from ...services.mental_health import check_and_alert_mental_health
from ...services.engagement_score import EngagementScore
import logging

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


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
    active_flow: Optional[str] = None
    last_intent: Optional[str] = None
    completed: bool = False


@router.post("/message", response_model=UnifiedChatResponse)
def unified_chat_message(
    request: UnifiedChatRequest,
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
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
        sentiment_result = SentimentService(db).analyze(request.message)
        sentiment_label = sentiment_result.get("sentiment", "neutral")
        sentiment_score = sentiment_result.get("score", 0.0)
    except Exception:
        logger.warning("Sentiment analysis failed", exc_info=True)
        sentiment_label = result.get("sentiment", "neutral")
        sentiment_score = 0.0

    try:
        EngagementScore(db).calculate_user_engagement(current_user.id, days=30)
    except Exception:
        logger.warning("Engagement score calculation skipped", exc_info=True)

    # ── Step 9: persist both messages ─────────────────────────────────────
    try:
        chat_service.add_message(
            conversation_id=conversation_id,
            message_text=request.message,
            sender=MessageSender.user,
            sentiment=sentiment_label,
        )
        chat_service.add_message(
            conversation_id=conversation_id,
            message_text=result["response"],
            sender=MessageSender.bot,
        )
    except Exception:
        logger.warning("Failed to persist messages", exc_info=True)

    # ── Step 10: log sentiment ─────────────────────────────────────────────
    try:
        # SentimentService.log() persists a sentiment_logs row for analytics
        SentimentService(db).log_sentiment(
            user_id=current_user.id,
            text=request.message,
            sentiment=sentiment_label,
        )
    except Exception:
        logger.warning("Sentiment logging skipped", exc_info=True)

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

    # ── Capture wellbeing signal ──────────────────────────────────────────
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

    # ── Memory hint ─────────────────────────────────────────────────────
    try:
        _store_memory_hint(
            db=db,
            user_id=current_user.id,
            user_message=request.message,
            intent=result.get("intent") or "general_query",
            sentiment=result.get("sentiment"),
        )
    except Exception:
        logger.warning("Memory hint skipped", exc_info=True)

    return UnifiedChatResponse(
        response=result["response"],
        intent=result.get("intent"),
        sentiment=result.get("sentiment"),
        conversation_id=str(conversation_id),
        conversation_state={"state": result.get("conversation_state")},
        context=result.get("context"),
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
    if message.sender == MessageSender.user:
        try:
            sentiment_result = SentimentService(db).analyze(message.message_text)
            sentiment_label = sentiment_result.get("sentiment")
            sentiment_score = sentiment_result.get("score")
        except Exception:
            logger.warning("Sentiment analysis failed", exc_info=True)

    msg = service.add_message(
        conversation_id=conversation_id,
        message_text=message.message_text,
        sender=message.sender,
        sentiment=sentiment_label,
    )

    if message.sender == MessageSender.user:
        try:
            SentimentService(service.db).log_sentiment(
                user_id=current_user.id,
                text=message.message_text,
                sentiment=sentiment_label or "neutral",
            )
        except Exception:
            logger.warning("Sentiment logging skipped", exc_info=True)

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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
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
            conversation_id=conversation_id
        )
        result = smart_service.process_message(request.message)

        try:
            sentiment_result = SentimentService(db).analyze(request.message)
            sentiment_label = sentiment_result.get("sentiment", "neutral")
            sentiment_score = sentiment_result.get("score", 0.0)
        except Exception:
            sentiment_label = result.get("sentiment", "neutral")
            sentiment_score = 0.0

        try:
            EngagementScore(db).calculate_user_engagement(current_user.id, days=30)
        except Exception:
            logger.warning("Engagement score calculation skipped", exc_info=True)

        ChatService(db).add_message(
            conversation_id=conversation_id,
            message_text=request.message,
            sender=MessageSender.user,
            sentiment=sentiment_label,
        )

        try:
            SentimentService(db).log_sentiment(
                user_id=current_user.id,
                text=request.message,
                sentiment=sentiment_label,
            )
        except Exception:
            logger.warning("Sentiment logging skipped", exc_info=True)

        try:
            get_mark_proactive_service(db=db).capture_chat_signal(
                user_id=current_user.id,
                conversation_id=conversation_id,
                text=request.message,
                source="chat",
                sentiment_score_override=sentiment_score,
            )
        except Exception:
            logger.warning("Failed to capture respond() wellbeing signal", exc_info=True)

        try:
            check_and_alert_mental_health(db, current_user.id)
        except Exception:
            logger.warning("Mental health check skipped", exc_info=True)

        ChatService(db).add_message(
            conversation_id=conversation_id,
            message_text=result["response"],
            sender=MessageSender.bot
        )

        try:
            _store_memory_hint(
                db=db,
                user_id=current_user.id,
                user_message=request.message,
                intent=result.get("intent") or "general_query",
                sentiment=result.get("sentiment"),
            )
        except Exception:
            logger.warning("Memory hint capture skipped", exc_info=True)

        return ChatResponse(
            response=result["response"],
            intent=result.get("intent"),
            sentiment=result.get("sentiment"),
            conversation_state={"state": result.get("conversation_state")},
            context=result.get("context"),
            active_flow=result.get("context", {}).get("active_flow"),
            last_intent=result.get("intent"),
            completed=smart_service.flow_context.get("state_contract", {}).get("completed", False),
        )
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="I'm having trouble responding right now. Please try again in a moment."
        )


@router.post("/conversations/start", response_model=ConversationStartResponse)
def start_conversation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    conversation = ChatService(db).create_conversation(current_user.id)
    
    try:
        smart_service = get_smart_chat_service(
            db=db,
            user_id=current_user.id,
            use_mock=False,
            conversation_id=conversation.id
        )
        result = smart_service.process_message("hello")
        greeting = result.get("response", "Hey, I'm Mark. How are you doing today?")
    except Exception as e:
        logger.warning(f"Failed to generate greeting: {e}")
        greeting = "Hey, I'm Mark. How are you doing today?"
    
    ChatService(db).add_message(
        conversation_id=conversation.id,
        message_text=greeting,
        sender=MessageSender.bot
    )
    
    return ConversationStartResponse(
        conversation_id=conversation.id,
        greeting=greeting
    )


@router.get("/memory-cards", response_model=List[MemoryCardResponse])
def get_memory_cards(
    limit: int = Query(default=3, ge=1, le=6),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _memory_cards_for_user(db=db, user_id=current_user.id, limit=limit)
