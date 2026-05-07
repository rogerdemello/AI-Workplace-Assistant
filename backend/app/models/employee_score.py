from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UUID

from ..core.time import utcnow_naive
from ..database import Base


class EmployeeScore(Base):
    __tablename__ = "employee_scores"

    employee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True, index=True)
    sentiment_score = Column(Integer, nullable=False, default=50)
    engagement_score = Column(Integer, nullable=False, default=50)
    risk_score = Column(Integer, nullable=False, default=0)
    mental_health_score = Column(Integer, nullable=False, default=50)
    trend_delta = Column(Integer, nullable=False, default=0)
    trend_label = Column(String(20), nullable=False, default="stable")
    last_updated = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive, nullable=False)
