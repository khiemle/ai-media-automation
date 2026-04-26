from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from console.backend.config import settings
from console.backend.database import get_db

bearer_scheme = HTTPBearer()


# ─── Password helpers ─────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ─── JWT helpers ──────────────────────────────────────────────────────────────

def create_access_token(user_id: int, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ─── FastAPI dependencies ─────────────────────────────────────────────────────

def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: Session = Depends(get_db),
):
    """Decode JWT and return the ConsoleUser record."""
    from console.backend.models.console_user import ConsoleUser

    payload = decode_token(credentials.credentials)
    user_id = int(payload["sub"])
    user = db.query(ConsoleUser).filter(ConsoleUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_admin(user=Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def require_editor_or_admin(user=Depends(get_current_user)):
    if user.role not in ("admin", "editor"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return user
