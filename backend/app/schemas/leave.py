from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from typing import Optional
from uuid import UUID
from datetime import date, datetime, timedelta
from enum import Enum

class LeaveStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"

class LeaveType(str, Enum):
    paid = "paid"
    sick = "sick"
    work_from_home = "work_from_home"
    unpaid = "unpaid"

class LeaveCreate(BaseModel):
    start_date: date
    end_date: date
    leave_type: LeaveType
    reason: Optional[str] = None

    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_year_range(cls, v: date) -> date:
        if v.year < 2000 or v.year > 2100:
            raise ValueError('Date year must be between 2000 and 2100')
        return v

    @field_validator('start_date')
    @classmethod
    def validate_start_date_not_past(cls, v: date) -> date:
        today = date.today()
        if v < today - timedelta(days=1):
            raise ValueError('Start date cannot be more than 1 day in the past')
        return v

    @model_validator(mode='after')
    def validate_date_range(self):
        if self.end_date < self.start_date:
            raise ValueError('End date must be on or after start date')
        duration = (self.end_date - self.start_date).days + 1
        if duration > 60:
            raise ValueError('Leave duration cannot exceed 60 days')
        return self

class LeaveUpdate(BaseModel):
    status: Optional[LeaveStatus] = None
    review_comment: Optional[str] = None

class LeaveResponse(BaseModel):
    id: UUID
    user_id: UUID
    start_date: date
    end_date: date
    leave_type: LeaveType
    reason: Optional[str] = None
    status: LeaveStatus
    manager_id: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    review_comment: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    employee_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class LeaveApproveReject(BaseModel):
    review_comment: Optional[str] = None