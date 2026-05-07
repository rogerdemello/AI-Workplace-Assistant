from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Iterable, List
from uuid import UUID

from ..database import get_db
from ..models.user import User, UserRole, UserStatus

security = HTTPBearer()


def _normalize_role_value(role: str | UserRole | None) -> str:
    if isinstance(role, UserRole):
        return role.value
    return str(role or "").strip().lower()


def _normalize_allowed_roles(allowed_roles: Iterable[str | UserRole]) -> set[str]:
    return {_normalize_role_value(role) for role in allowed_roles if _normalize_role_value(role)}


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

    # Try to find by UUID first (when token subject is UUID), then by email.
    user = None
    user_uuid = None
    try:
        if user_id:
            user_uuid = UUID(str(user_id))
    except Exception:
        user_uuid = None

    if user_uuid is not None:
        user = db.query(User).filter(User.id == user_uuid).first()
    
    if user is None:
        user = db.query(User).filter(User.email == email).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found for the provided token",
        )

    if user.status != UserStatus.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )

    return user


def require_roles(allowed_roles: List[str | UserRole]):
    normalized_allowed_roles = _normalize_allowed_roles(allowed_roles)

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        current_role = _normalize_role_value(current_user.role)
        if current_role not in normalized_allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return role_checker
