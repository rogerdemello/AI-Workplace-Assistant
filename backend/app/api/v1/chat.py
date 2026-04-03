from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from ...database import get_db
from ...schemas.chat import (
    ConversationCreate, 
    ConversationResponse, 
    ConversationListResponse,
    MessageCreate,
    MessageResponse,
    ChatRequest,
    ChatResponse,
    ConversationStartResponse,
    MessageSender
)
from ...models.conversation import Conversation
from ...auth import get_current_user
from ...models.user import User
from ...services.chat import ChatService
from ...services.smart_chat import get_smart_chat_service
import logging

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


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
    service: ChatService = Depends(get_chat_service)
):
    conversation = service.get_conversation(conversation_id, current_user.id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    msg = service.add_message(
        conversation_id=conversation_id,
        message_text=message.message_text,
        sender=message.sender,
    )
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
        
        ChatService(db).add_message(
            conversation_id=conversation_id,
            message_text=request.message,
            sender=MessageSender.user
        )
        ChatService(db).add_message(
            conversation_id=conversation_id,
            message_text=result["response"],
            sender=MessageSender.bot
        )
        
        return ChatResponse(
            response=result["response"],
            intent=result.get("intent"),
            sentiment=result.get("sentiment"),
            conversation_state={"state": result.get("conversation_state")},
            context=result.get("context")
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
        greeting = result.get("response", "Hello! How can I help you today?")
    except Exception as e:
        logger.warning(f"Failed to generate greeting: {e}")
        greeting = "Hello! How can I help you today?"
    
    ChatService(db).add_message(
        conversation_id=conversation.id,
        message_text=greeting,
        sender=MessageSender.bot
    )
    
    return ConversationStartResponse(
        conversation_id=conversation.id,
        greeting=greeting
    )
