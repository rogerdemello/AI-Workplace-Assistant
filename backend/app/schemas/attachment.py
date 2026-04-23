from pydantic import BaseModel, ConfigDict
from typing import Optional
from uuid import UUID
from datetime import datetime
from enum import Enum


class AttachmentEntityType(str, Enum):
    ticket = "ticket"
    leave_request = "leave_request"


class AttachmentResponse(BaseModel):
    id: UUID
    user_id: UUID
    file_name: str
    file_type: str
    file_size: int
    file_path: str
    entity_type: AttachmentEntityType
    entity_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
