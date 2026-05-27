from sqlalchemy import Column, DateTime, String, Text, UUID
import uuid

from ..database import Base
from ..core.time import utcnow_naive


class AnonymousFeedback(Base):
    """Identity-free feedback submissions.

    Deliberately has NO user_id / FK to users — anonymity is structural, not a
    policy we have to remember to enforce. Only a one-way hash of the tracking
    token is stored so a submitter can later check status without revealing who
    they are.
    """

    __tablename__ = "anonymous_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    category = Column(String(32), nullable=False, index=True)
    message = Column(Text, nullable=False)
    status = Column(String(24), nullable=False, default="submitted", index=True)
    created_at = Column(DateTime, default=utcnow_naive, index=True)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)
