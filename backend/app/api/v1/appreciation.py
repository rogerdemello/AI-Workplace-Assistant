from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from ...database import get_db
from ...schemas.appreciation import AppreciationCreate, AppreciationResponse
from ...auth import get_current_user
from ...models.user import User
from ...services.appreciation_service import create_appreciation, get_all_appreciations, get_user_appreciations

router = APIRouter(prefix="/appreciation", tags=["appreciation"])


@router.post("", response_model=AppreciationResponse, status_code=status.HTTP_201_CREATED)
def send_appreciation(
    appreciation: AppreciationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    record = create_appreciation(
        db=db,
        from_user_id=current_user.id,
        to_user_id=appreciation.to_user_id,
        message=appreciation.message,
        is_anonymous=appreciation.is_anonymous
    )
    return record


@router.get("", response_model=List[AppreciationResponse])
def list_appreciations(
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only HR/admin can see all appreciate
    if current_user.role not in ["hr", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized to view all appreciations")
    
    records = get_all_appreciations(db=db, limit=limit)
    return records


@router.get("/user/{user_id}", response_model=List[AppreciationResponse])
def user_appreciations(
    user_id: UUID,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Users can only view their own appreciate unless they're manager/hr/admin
    if user_id != current_user.id and current_user.role not in ["hr", "admin", "manager"]:
        raise HTTPException(status_code=403, detail="Not authorized to view this user's appreciate")
    
    records = get_user_appreciations(db=db, user_id=user_id, limit=limit)
    return records