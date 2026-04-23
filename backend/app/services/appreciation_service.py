from typing import Dict, List, Optional
from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..models.appreciation_note import AppreciationNote


class AppreciationRecord:
    def __init__(self, id: UUID, from_user_id: Optional[UUID], to_user_id: UUID,
                 message: str, is_anonymous: bool, created_at: datetime):
        self.id = id
        self.from_user_id = from_user_id
        self.to_user_id = to_user_id
        self.message = message
        self.is_anonymous = is_anonymous
        self.created_at = created_at
    
    def to_dict(self) -> Dict:
        return {
            "id": str(self.id),
            "from_user_id": str(self.from_user_id) if self.from_user_id else None,
            "to_user_id": str(self.to_user_id),
            "message": self.message,
            "is_anonymous": self.is_anonymous,
            "created_at": self.created_at.isoformat()
        }


class AppreciationService:
    def __init__(self, db: Session):
        self.db = db
    
    def create_appreciation(
        self,
        from_user_id: Optional[UUID],
        to_user_id: UUID,
        message: str,
        is_anonymous: bool = False
    ) -> AppreciationRecord:
        note = AppreciationNote(
            from_user_id=None if is_anonymous else from_user_id,
            to_user_id=to_user_id,
            message=message,
            is_anonymous=is_anonymous
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        
        return AppreciationRecord(
            id=note.id,
            from_user_id=note.from_user_id,
            to_user_id=note.to_user_id,
            message=note.message,
            is_anonymous=note.is_anonymous,
            created_at=note.created_at
        )
    
    def get_all_appreciations(self, limit: int = 100) -> List[AppreciationRecord]:
        notes = self.db.query(AppreciationNote).order_by(
            desc(AppreciationNote.created_at)
        ).limit(limit).all()
        
        return [
            AppreciationRecord(
                id=n.id,
                from_user_id=n.from_user_id,
                to_user_id=n.to_user_id,
                message=n.message,
                is_anonymous=n.is_anonymous,
                created_at=n.created_at
            )
            for n in notes
        ]
    
    def get_user_appreciations(self, user_id: UUID, limit: int = 50) -> List[AppreciationRecord]:
        notes = self.db.query(AppreciationNote).filter(
            AppreciationNote.to_user_id == user_id
        ).order_by(desc(AppreciationNote.created_at)).limit(limit).all()
        
        return [
            AppreciationRecord(
                id=n.id,
                from_user_id=n.from_user_id,
                to_user_id=n.to_user_id,
                message=n.message,
                is_anonymous=n.is_anonymous,
                created_at=n.created_at
            )
            for n in notes
        ]


def get_appreciation_service(db: Session) -> AppreciationService:
    return AppreciationService(db)


def create_appreciation(
    db: Session,
    from_user_id: Optional[UUID],
    to_user_id: UUID,
    message: str,
    is_anonymous: bool = False
) -> Dict:
    service = AppreciationService(db)
    record = service.create_appreciation(from_user_id, to_user_id, message, is_anonymous)
    return record.to_dict()


def get_all_appreciations(db: Session, limit: int = 100) -> List[Dict]:
    service = AppreciationService(db)
    records = service.get_all_appreciations(limit)
    return [r.to_dict() for r in records]


def get_user_appreciations(db: Session, user_id: UUID, limit: int = 50) -> List[Dict]:
    service = AppreciationService(db)
    records = service.get_user_appreciations(user_id, limit)
    return [r.to_dict() for r in records]