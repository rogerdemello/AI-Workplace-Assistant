from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UUID
from sqlalchemy.dialects.postgresql import JSONB

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
    #: Why the risk score is what it is: the weighted components and the raw
    #: inputs behind them, plus how much data they rest on. Without this the
    #: dashboard shows a number nobody can interrogate — and a risk score
    #: driven entirely by someone being on holiday looks identical to one
    #: driven by repeated distress.
    risk_factors = Column(JSONB, nullable=True)
    last_updated = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive, nullable=False)
