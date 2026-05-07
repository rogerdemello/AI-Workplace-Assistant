"""Persist WhatsApp ↔ chat conversation linkage for multi-turn smart chat state."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from ...models.conversation import Conversation, ConversationStatus
from ...services.chat import ChatService
from ...services.memory_service import MemoryService

_MARK_WHATSAPP_KEY = "_mark_whatsapp"


def _merge_prefs(db: Session, user_id: UUID, whatsapp_patch: dict) -> None:
    ms = MemoryService(db)
    rec = ms.get_user_profile(user_id)
    prefs = dict(rec.preferences) if rec and rec.preferences else {}
    inner = dict(prefs.get(_MARK_WHATSAPP_KEY) or {})
    inner.update(whatsapp_patch)
    prefs[_MARK_WHATSAPP_KEY] = inner
    ms.update_user_profile(user_id=user_id, preferences=prefs)


def save_whatsapp_conversation_id(db: Session, user_id: UUID, conversation_id: UUID) -> None:
    _merge_prefs(db, user_id, {"conversation_id": str(conversation_id)})


def get_or_resume_whatsapp_conversation(db: Session, user_id: UUID, chat_service: ChatService) -> Conversation:
    """Reuse latest active WhatsApp-linked conversation when possible."""
    ms = MemoryService(db)
    rec = ms.get_user_profile(user_id)
    cid_str = None
    if rec and rec.preferences:
        nest = rec.preferences.get(_MARK_WHATSAPP_KEY) or {}
        cid_str = nest.get("conversation_id")

    if cid_str:
        try:
            cid = UUID(cid_str)
            conv = chat_service.get_conversation(cid, user_id)
            if conv is not None and conv.status == ConversationStatus.active:
                return conv
        except (ValueError, TypeError):
            pass

    conv = chat_service.create_conversation(user_id)
    save_whatsapp_conversation_id(db, user_id, conv.id)
    return conv
