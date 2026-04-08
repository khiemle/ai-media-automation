from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from console.backend.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_admin,
)
from console.backend.database import get_db
from console.backend.models.console_user import ConsoleUser

router = APIRouter(prefix="/auth", tags=["auth"])


# ─── Schemas (inline for this router) ────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: str = "editor"


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(ConsoleUser).filter(ConsoleUser.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    token = create_access_token(user.id, user.role)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/register", response_model=UserResponse, dependencies=[Depends(require_admin)])
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if body.role not in ("admin", "editor"):
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'editor'")
    if db.query(ConsoleUser).filter(ConsoleUser.username == body.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")
    if db.query(ConsoleUser).filter(ConsoleUser.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = ConsoleUser(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.get("/me", response_model=UserResponse)
def me(user=Depends(get_current_user)):
    return UserResponse.model_validate(user)
