from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt

from ..config import settings

# Read through `settings` rather than os.getenv. These used to be read straight
# from the process environment, which silently disagreed with core/auth.py
# whenever SECRET_KEY was set in .env but not exported: tokens were signed here
# with the placeholder and verified there with the real key.
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require_exp": True}  # Require expiration claim
        )
        # Additional check: verify token is not expired
        exp = payload.get("exp")
        if exp and exp < datetime.now(timezone.utc).timestamp():
            return None
        return payload
    except JWTError:
        return None
