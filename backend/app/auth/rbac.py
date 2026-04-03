from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from ..database import get_db
from ..models.user import User, UserRole, UserStatus

security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    from .jwt import verify_token
    token = credentials.credentials
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    user_id = payload.get("sub")
    email = payload.get("email", "demo@example.com")
    
    # Try to find by ID first, then by email
    user = db.query(User).filter(User.id == user_id).first()
    
    if user is None:
        user = db.query(User).filter(User.email == email).first()
    
    if user is None:
        user = User(
            id=UUID(user_id),
            email=email,
            name="Demo User",
            employee_id=f"DEMO{user_id[:4]}",
            hashed_password="",
            role=UserRole.employee,
            status=UserStatus.active
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    return user

def require_roles(allowed_roles: List[str]):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return role_checker
