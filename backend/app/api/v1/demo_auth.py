from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from uuid import uuid4

from ...database import get_db
from ...models.user import User, UserRole, UserStatus
from ...auth import create_access_token, hash_password

router = APIRouter(prefix="/demo", tags=["demo"])


class DemoLoginRequest(BaseModel):
    name: str = "Demo User"
    email: str = "demo@example.com"


class DemoLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str


@router.post("/login", response_model=DemoLoginResponse)
def demo_login(request: DemoLoginRequest, db: Session = Depends(get_db)):
    """Demo login - creates or gets a demo user in the database."""
    
    user = db.query(User).filter(User.email == request.email).first()
    
    if not user:
        user = User(
            id=uuid4(),
            email=request.email,
            name=request.name,
            employee_id="DEMO001",
            hashed_password=hash_password("demo123"),
            role=UserRole.employee,
            status=UserStatus.active
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})
    
    return DemoLoginResponse(
        access_token=access_token,
        user_id=str(user.id)
    )


__all__ = ["router"]
