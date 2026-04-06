from typing import Dict, List, Optional, Any
from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import desc
import json

from ..models.conversation_memory import ConversationMemory
from ..models.user_profile import UserProfile
from ..models.user import User
from ..ai_client import get_ai_client


class MemoryRecord:
    def __init__(self, id: UUID, user_id: UUID, summary: str, tags: List[str], created_at: datetime):
        self.id = id
        self.user_id = user_id
        self.summary = summary
        self.tags = tags
        self.created_at = created_at
    
    def to_dict(self) -> Dict:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "summary": self.summary,
            "tags": self.tags or [],
            "created_at": self.created_at.isoformat()
        }


class UserProfileRecord:
    def __init__(self, id: UUID, user_id: UUID, name: Optional[str], 
                 department: Optional[str], preferences: Optional[Dict], 
                 last_summary: Optional[str], created_at: datetime, updated_at: datetime):
        self.id = id
        self.user_id = user_id
        self.name = name
        self.department = department
        self.preferences = preferences
        self.last_summary = last_summary
        self.created_at = created_at
        self.updated_at = updated_at
    
    def to_dict(self) -> Dict:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "name": self.name,
            "department": self.department,
            "preferences": self.preferences,
            "last_summary": self.last_summary,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class MemoryService:
    def __init__(self, db: Session, ai_client: Optional[Any] = None):
        self.db = db
        self.ai_client = ai_client
    
    def _get_ai_client(self):
        if self.ai_client is None:
            try:
                self.ai_client = get_ai_client()
            except Exception:
                return None
        return self.ai_client
    
    def store_memory(self, user_id: UUID, summary: str, tags: Optional[List[str]] = None) -> MemoryRecord:
        memory = ConversationMemory(
            user_id=user_id,
            summary=summary,
            tags=tags or []
        )
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)
        
        return MemoryRecord(
            id=memory.id,
            user_id=memory.user_id,
            summary=memory.summary,
            tags=memory.tags,
            created_at=memory.created_at
        )
    
    def retrieve_memory(self, user_id: UUID, limit: int = 3) -> List[MemoryRecord]:
        memories = self.db.query(ConversationMemory).filter(
            ConversationMemory.user_id == user_id
        ).order_by(desc(ConversationMemory.created_at)).limit(limit).all()
        
        return [
            MemoryRecord(
                id=m.id,
                user_id=m.user_id,
                summary=m.summary,
                tags=m.tags,
                created_at=m.created_at
            )
            for m in memories
        ]
    
    def extract_memory_from_conversation(self, messages: List[Dict]) -> Dict:
        """Extract summary and tags from conversation messages using LLM."""
        client = self._get_ai_client()
        
        if not client:
            return {"summary": "", "tags": []}
        
        conversation_text = "\n".join([
            f"{msg.get('role', 'user')}: {msg.get('content', '')}"
            for msg in messages
        ])
        
        extraction_prompt = f"""Analyze this conversation and extract key information:

{conversation_text}

Provide a JSON response with:
- summary: A brief (2-3 sentence) summary of the key points discussed
- tags: 3-5 relevant tags (like ["leave", "benefits", "policy", "career", "team"])

Return ONLY valid JSON with 'summary' and 'tags' keys."""

        try:
            response = client.chat_completion(
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that extracts key information from conversations."},
                    {"role": "user", "content": extraction_prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "{}")
            result = json.loads(content)
            return {
                "summary": result.get("summary", ""),
                "tags": result.get("tags", [])
            }
        except Exception:
            return {"summary": "", "tags": []}
    
    def update_user_profile(
        self, 
        user_id: UUID, 
        name: Optional[str] = None, 
        department: Optional[str] = None, 
        preferences: Optional[Dict] = None
    ) -> UserProfileRecord:
        profile = self.db.query(UserProfile).filter(
            UserProfile.user_id == user_id
        ).first()
        
        if profile:
            if name is not None:
                profile.name = name
            if department is not None:
                profile.department = department
            if preferences is not None:
                profile.preferences = preferences
            profile.updated_at = datetime.utcnow()
        else:
            profile = UserProfile(
                user_id=user_id,
                name=name,
                department=department,
                preferences=preferences
            )
            self.db.add(profile)
        
        self.db.commit()
        self.db.refresh(profile)
        
        return UserProfileRecord(
            id=profile.id,
            user_id=profile.user_id,
            name=profile.name,
            department=profile.department,
            preferences=profile.preferences,
            last_summary=profile.last_summary,
            created_at=profile.created_at,
            updated_at=profile.updated_at
        )
    
    def get_user_profile(self, user_id: UUID) -> Optional[UserProfileRecord]:
        profile = self.db.query(UserProfile).filter(
            UserProfile.user_id == user_id
        ).first()
        
        if not profile:
            return None
        
        return UserProfileRecord(
            id=profile.id,
            user_id=profile.user_id,
            name=profile.name,
            department=profile.department,
            preferences=profile.preferences,
            last_summary=profile.last_summary,
            created_at=profile.created_at,
            updated_at=profile.updated_at
        )


def get_memory_service(db: Session, ai_client: Optional[Any] = None) -> MemoryService:
    return MemoryService(db, ai_client)