from typing import Dict, List, Optional, Any, Union
from datetime import datetime, date
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import desc
import json
import re

from ..models.conversation_memory import ConversationMemory
from ..core.time import utcnow_naive
from ..models.user_profile import UserProfile
from ..models.user import User
from ..models.personal_fact import PersonalFact, PersonalFactType
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


class PersonalFactRecord:
    def __init__(self, id: UUID, user_id: UUID, fact_type: PersonalFactType, 
                 fact_value: str, source_message_id: Optional[UUID], created_at: datetime):
        self.id = id
        self.user_id = user_id
        self.fact_type = fact_type
        self.fact_value = fact_value
        self.source_message_id = source_message_id
        self.created_at = created_at
    
    def to_dict(self) -> Dict:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "fact_type": self.fact_type.value if isinstance(self.fact_type, PersonalFactType) else self.fact_type,
            "fact_value": self.fact_value,
            "source_message_id": str(self.source_message_id) if self.source_message_id else None,
            "created_at": self.created_at.isoformat()
        }


# Date extraction patterns for birthday and work anniversary
DATE_PATTERNS = [
    # MM/DD/YYYY or MM-DD-YYYY
    (r'\b(0?[1-9]|1[0-2])[/(-](0?[1-9]|[12]\d|3[01])[/(-](\d{4})\b', '%m/%d/%Y'),
    # Month DD, YYYY
    (r'\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{1,2}),?\s+(\d{4})\b', None),
    # DD Month YYYY
    (r'\b(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{4})\b', None),
]

# Keywords for fact type detection
FACT_TYPE_KEYWORDS = {
    'birthday': ['birthday', 'bday', 'born on', 'date of birth', 'dob', 'birth date'],
    'work_anniversary': ['work anniversary', 'joining date', 'joined', 'start date', 'hire date', 'anniversary'],
    'hobby': ['hobby', 'hobbies', 'like to', 'enjoy doing', 'passion', 'interest'],
    'family_note': ['family', 'spouse', 'wife', 'husband', 'kid', 'kids', 'child', 'children', 'mom', 'dad', 'parent'],
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
            profile.updated_at = utcnow_naive()
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
    
    def save_personal_fact(
        self, 
        user_id: UUID, 
        fact_type: Union[str, PersonalFactType], 
        fact_value: str,
        source_message_id: Optional[UUID] = None
    ) -> PersonalFactRecord:
        if isinstance(fact_type, str):
            fact_type = PersonalFactType(fact_type)
        
        fact = PersonalFact(
            user_id=user_id,
            fact_type=fact_type,
            fact_value=fact_value,
            source_message_id=source_message_id
        )
        self.db.add(fact)
        self.db.commit()
        self.db.refresh(fact)
        
        return PersonalFactRecord(
            id=fact.id,
            user_id=fact.user_id,
            fact_type=fact.fact_type,
            fact_value=fact.fact_value,
            source_message_id=fact.source_message_id,
            created_at=fact.created_at
        )
    
    def get_user_facts(self, user_id: UUID) -> List[PersonalFactRecord]:
        facts = self.db.query(PersonalFact).filter(
            PersonalFact.user_id == user_id
        ).order_by(desc(PersonalFact.created_at)).all()
        
        return [
            PersonalFactRecord(
                id=f.id,
                user_id=f.user_id,
                fact_type=f.fact_type,
                fact_value=f.fact_value,
                source_message_id=f.source_message_id,
                created_at=f.created_at
            )
            for f in facts
        ]
    
    def get_facts_by_type(
        self, 
        user_id: UUID, 
        fact_type: Union[str, PersonalFactType]
    ) -> List[PersonalFactRecord]:
        if isinstance(fact_type, str):
            fact_type = PersonalFactType(fact_type)
        
        facts = self.db.query(PersonalFact).filter(
            PersonalFact.user_id == user_id,
            PersonalFact.fact_type == fact_type
        ).order_by(desc(PersonalFact.created_at)).all()
        
        return [
            PersonalFactRecord(
                id=f.id,
                user_id=f.user_id,
                fact_type=f.fact_type,
                fact_value=f.fact_value,
                source_message_id=f.source_message_id,
                created_at=f.created_at
            )
            for f in facts
        ]
    
    def extract_facts_from_message(self, message: str) -> List[Dict[str, Any]]:
        extracted_facts = []
        message_lower = message.lower()
        
        for fact_type, keywords in FACT_TYPE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in message_lower:
                    fact_value = self._extract_date_or_value(message, fact_type)
                    if fact_value:
                        extracted_facts.append({
                            'fact_type': fact_type,
                            'fact_value': fact_value
                        })
                    break
        
        return extracted_facts
    
    def _extract_date_or_value(self, message: str, fact_type: str) -> Optional[str]:
        month_map = {
            'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
            'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6, 'jul': 7, 'july': 7,
            'aug': 8, 'august': 8, 'sep': 9, 'september': 9, 'oct': 10, 'october': 10,
            'nov': 11, 'november': 11, 'dec': 12, 'december': 12
        }
        
        patterns = [
            (r'\b(0?[1-9]|1[0-2])[/(-](0?[1-9]|[12]\d|3[01])[/(-](\d{4})\b', '%m/%d/%Y'),
            (r'\b(\d{1,2})[/(-](\d{1,2})[/(-](\d{4})\b', '%m/%d/%Y'),
            (r'\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2}),?\s+(\d{4})\b', None),
            (r'\b(\d{1,2})\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{4})\b', None),
        ]
        
        for pattern, _ in patterns:
            match = re.search(pattern, message.lower())
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    try:
                        if groups[0].isdigit():
                            month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
                        else:
                            month = month_map.get(groups[0][:3], 0)
                            day, year = int(groups[1]), int(groups[2])
                        
                        if 1 <= month <= 12 and 1 <= day <= 31 and 1900 <= year <= 2100:
                            return f"{year}-{month:02d}-{day:02d}"
                    except (ValueError, IndexError):
                        continue
        
        if fact_type in ['birthday', 'work_anniversary']:
            return None
        
        sentences = re.split(r'[.!?]+', message)
        for sentence in sentences:
            sentence_lower = sentence.lower()
            for keyword in FACT_TYPE_KEYWORDS.get(fact_type, []):
                if keyword in sentence_lower:
                    cleaned = sentence.strip()
                    if len(cleaned) > 3:
                        return cleaned
        
        return None


def get_memory_service(db: Session, ai_client: Optional[Any] = None) -> MemoryService:
    return MemoryService(db, ai_client)


def save_personal_fact(
    db: Session,
    user_id: UUID,
    fact_type: Union[str, PersonalFactType],
    fact_value: str,
    source_message_id: Optional[UUID] = None
) -> Dict:
    service = MemoryService(db)
    record = service.save_personal_fact(user_id, fact_type, fact_value, source_message_id)
    return record.to_dict()


def get_user_facts(db: Session, user_id: UUID) -> List[Dict]:
    service = MemoryService(db)
    records = service.get_user_facts(user_id)
    return [r.to_dict() for r in records]


def get_facts_by_type(
    db: Session,
    user_id: UUID,
    fact_type: Union[str, PersonalFactType]
) -> List[Dict]:
    service = MemoryService(db)
    records = service.get_facts_by_type(user_id, fact_type)
    return [r.to_dict() for r in records]


def extract_facts_from_message(message: str) -> List[Dict[str, Any]]:
    service = MemoryService(None)
    return service.extract_facts_from_message(message)