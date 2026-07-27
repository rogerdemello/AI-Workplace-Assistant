import json
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
import redis
import os

from ...models.conversation import Conversation, Message, ConversationStatus, MessageSender as ModelMessageSender
from ...schemas.chat import MessageSender as SchemaMessageSender

_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> Optional[redis.Redis]:
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(
                os.getenv("REDIS_URL", "redis://localhost:6379"),
                socket_connect_timeout=0.3, socket_timeout=0.3,
            )
            _redis_client.ping()  # type: ignore[attr-defined]
        except Exception:
            _redis_client = None
    return _redis_client


class ChatService:
    def __init__(self, db: Session):
        self.db = db

    def create_conversation(self, user_id: UUID) -> Conversation:
        conversation = Conversation(
            user_id=user_id,
            status=ConversationStatus.active,
        )
        self.db.add(conversation)
        self.db.flush()  # assign client-side defaults (id) within the txn
        cid = conversation.id  # capture before commit expires the instance
        self.db.commit()
        # Post-commit refresh is a needless round-trip and, on a shared DB
        # connection under concurrency, can raise even though the row is already
        # committed. Re-fetch by PK; fall back to the in-memory object if that
        # hiccups so we never 500 a successful create.
        try:
            return self.db.get(Conversation, cid) or conversation
        except Exception:
            return conversation

    def get_user_conversations(self, user_id: UUID, limit: int = 50) -> List[Conversation]:
        return (
            self.db.query(Conversation)
            .filter(Conversation.user_id == user_id)
            .order_by(Conversation.started_at.desc())
            .limit(limit)
            .all()
        )

    def get_conversation(self, conversation_id: UUID, user_id: UUID) -> Optional[Conversation]:
        return (
            self.db.query(Conversation)
            .filter(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
            .first()
        )

    def add_message(
        self,
        conversation_id: UUID,
        message_text: str,
        sender: SchemaMessageSender,
        intent: Optional[str] = None,
        sentiment: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> Message:
        model_sender = ModelMessageSender(sender.value)
        message = Message(
            conversation_id=conversation_id,
            sender=model_sender,
            message_text=message_text,
            intent=intent,
            sentiment=sentiment,
            confidence=str(confidence) if confidence else None,
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)

        self._update_cache(conversation_id)

        return message

    def add_user_and_bot_message_pair(
        self,
        conversation_id: UUID,
        *,
        user_text: str,
        user_sentiment: Optional[str],
        bot_text: str,
    ) -> tuple[Message, Message]:
        """Persist employee + assistant turns in one transaction (faster than two commits)."""
        user_row = Message(
            conversation_id=conversation_id,
            sender=ModelMessageSender.user,
            message_text=user_text,
            sentiment=user_sentiment,
        )
        bot_row = Message(
            conversation_id=conversation_id,
            sender=ModelMessageSender.bot,
            message_text=bot_text,
        )
        self.db.add_all([user_row, bot_row])
        self.db.commit()
        self.db.refresh(user_row)
        self.db.refresh(bot_row)
        self._update_cache(conversation_id)
        return user_row, bot_row

    def get_conversation_context(self, conversation_id: UUID, limit: int = 10) -> List[Message]:
        messages = (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
            .all()
        )
        return list(reversed(messages))

    def close_conversation(self, conversation_id: UUID, user_id: UUID) -> Optional[Conversation]:
        conversation = self.get_conversation(conversation_id, user_id)
        if conversation:
            conversation.status = ConversationStatus.closed  # type: ignore[assignment]
            self.db.commit()
            rc = get_redis_client()
            if rc:
                rc.delete(f"chat:conversation:{conversation_id}")
        return conversation

    def _update_cache(self, conversation_id: UUID) -> None:
        global _redis_client
        try:
            messages = self.get_conversation_context(conversation_id)
            rc = get_redis_client()
            if rc and messages:
                cache_key = f"chat:conversation:{conversation_id}"
                cached_data = [
                    {
                        "sender": m.sender.value,
                        "message_text": m.message_text,
                        "created_at": m.created_at.isoformat(),
                    }
                    for m in messages
                ]
                rc.setex(cache_key, 3600, json.dumps(cached_data))
        except Exception:
            _redis_client = None


__all__ = ["ChatService", "get_redis_client"]
