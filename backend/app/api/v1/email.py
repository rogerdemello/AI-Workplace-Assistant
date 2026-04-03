from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Optional

from ...auth import get_current_user
from ...models.user import User
from ...services.email_draft import EmailDraftService, EMAIL_TYPES, TONES

router = APIRouter(prefix="/email", tags=["email"])


class EmailDraftRequest(BaseModel):
    type: str
    tone: str
    context: Optional[Dict] = {}


class EmailDraftResponse(BaseModel):
    subject: str
    body: str
    tone: str
    type: str
    context: Dict


@router.post("/draft", response_model=EmailDraftResponse)
def create_email_draft(
    request: EmailDraftRequest,
    current_user: User = Depends(get_current_user)
):
    if request.type not in EMAIL_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid email type. Must be one of: {EMAIL_TYPES}"
        )
    
    if request.tone not in TONES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tone. Must be one of: {TONES}"
        )
    
    service = EmailDraftService(user_id=current_user.id)
    draft = service.generate_draft(request.type, request.tone, request.context)
    
    return EmailDraftResponse(**draft)
