from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    employee_id: Optional[str] = None
    designation: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[UUID] = None

class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    role: str
    employee_id: Optional[str] = None
    designation: Optional[str] = None
    
    class Config:
        from_attributes = True
