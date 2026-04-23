from typing import Dict, List, Optional, Union
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, and_

from ..models.mood_entry import MoodEntry, MoodEmoji


class MoodRecord:
    def __init__(self, id: UUID, user_id: UUID, mood_emoji: MoodEmoji, 
                 mood_score: int, note: Optional[str], created_at: datetime):
        self.id = id
        self.user_id = user_id
        self.mood_emoji = mood_emoji
        self.mood_score = mood_score
        self.note = note
        self.created_at = created_at
    
    def to_dict(self) -> Dict:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "mood_emoji": self.mood_emoji.value if isinstance(self.mood_emoji, MoodEmoji) else self.mood_emoji,
            "mood_score": self.mood_score,
            "note": self.note,
            "created_at": self.created_at.isoformat()
        }


class MoodTrendRecord:
    def __init__(self, average_score: float, trend: str, total_entries: int, 
                 oldest_entry: Optional[datetime], newest_entry: Optional[datetime]):
        self.average_score = average_score
        self.trend = trend
        self.total_entries = total_entries
        self.oldest_entry = oldest_entry
        self.newest_entry = newest_entry
    
    def to_dict(self) -> Dict:
        return {
            "average_score": round(self.average_score, 2) if self.average_score else None,
            "trend": self.trend,
            "total_entries": self.total_entries,
            "oldest_entry": self.oldest_entry.isoformat() if self.oldest_entry else None,
            "newest_entry": self.newest_entry.isoformat() if self.newest_entry else None
        }


class MoodService:
    def __init__(self, db: Session):
        self.db = db
    
    def log_mood(
        self, 
        user_id: UUID, 
        mood_emoji: Union[str, MoodEmoji], 
        mood_score: int, 
        note: Optional[str] = None
    ) -> MoodRecord:
        if isinstance(mood_emoji, str):
            mood_emoji = MoodEmoji(mood_emoji)
        
        entry = MoodEntry(
            user_id=user_id,
            mood_emoji=mood_emoji,
            mood_score=mood_score,
            note=note
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        
        return MoodRecord(
            id=entry.id,
            user_id=entry.user_id,
            mood_emoji=entry.mood_emoji,
            mood_score=entry.mood_score,
            note=entry.note,
            created_at=entry.created_at
        )
    
    def get_mood_history(self, user_id: UUID, days: int = 7) -> List[MoodRecord]:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        entries = self.db.query(MoodEntry).filter(
            and_(
                MoodEntry.user_id == user_id,
                MoodEntry.created_at >= cutoff_date
            )
        ).order_by(desc(MoodEntry.created_at)).all()
        
        return [
            MoodRecord(
                id=e.id,
                user_id=e.user_id,
                mood_emoji=e.mood_emoji,
                mood_score=e.mood_score,
                note=e.note,
                created_at=e.created_at
            )
            for e in entries
        ]
    
    def get_mood_trend(self, user_id: UUID) -> MoodTrendRecord:
        entries = self.db.query(MoodEntry).filter(
            MoodEntry.user_id == user_id
        ).order_by(MoodEntry.created_at).all()
        
        if not entries:
            return MoodTrendRecord(
                average_score=0.0,
                trend="neutral",
                total_entries=0,
                oldest_entry=None,
                newest_entry=None
            )
        
        total_entries = len(entries)
        average_score = sum(e.mood_score for e in entries) / total_entries
        
        oldest = entries[0].created_at
        newest = entries[-1].created_at
        
        trend = self._calculate_trend(entries, average_score)
        
        return MoodTrendRecord(
            average_score=average_score,
            trend=trend,
            total_entries=total_entries,
            oldest_entry=oldest,
            newest_entry=newest
        )
    
    def _calculate_trend(self, entries: List[MoodEntry], average_score: float) -> str:
        if len(entries) < 2:
            return "neutral"
        
        half = len(entries) // 2
        first_half = entries[:half]
        second_half = entries[half:]
        
        first_avg = sum(e.mood_score for e in first_half) / len(first_half)
        second_avg = sum(e.mood_score for e in second_half) / len(second_half)
        
        diff = second_avg - first_avg
        
        if diff > 0.5:
            return "improving"
        elif diff < -0.5:
            return "declining"
        else:
            return "stable"


def get_mood_service(db: Session) -> MoodService:
    return MoodService(db)


def log_mood(
    db: Session,
    user_id: UUID,
    mood_emoji: Union[str, MoodEmoji],
    mood_score: int,
    note: Optional[str] = None
) -> Dict:
    service = MoodService(db)
    record = service.log_mood(user_id, mood_emoji, mood_score, note)
    return record.to_dict()


def get_mood_history(db: Session, user_id: UUID, days: int = 7) -> List[Dict]:
    service = MoodService(db)
    records = service.get_mood_history(user_id, days)
    return [r.to_dict() for r in records]


def get_mood_trend(db: Session, user_id: UUID) -> Dict:
    service = MoodService(db)
    record = service.get_mood_trend(user_id)
    return record.to_dict()