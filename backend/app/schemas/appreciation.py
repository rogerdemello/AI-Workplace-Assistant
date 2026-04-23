from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class AppreciationCreate(BaseModel):
    to_user_id: UUID = Field(..., description="User ID to send appreciation to")
    message: str = Field(..., min_length=1, max_length=1000, description="Appreciation message")
    is_anonymous: bool = Field(default=False, description="Whether the appreciation is anonymous")


class AppreciationResponse(BaseModel):
    id: UUID
    from_user_id: Optional[UUID] = None
    to_user_id: UUID
    message: str
    is_anonymous: bool
    created_at: datetime

    class Config:
        from_attributes = True