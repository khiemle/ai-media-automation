from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from jose import jwt
from pydantic import BaseModel, Field

from console.backend.auth import require_admin, require_editor_or_admin
from console.backend.config import settings
from console.backend.database import SessionLocal
from console.backend.models.console_user import ConsoleUser
from console.backend.services.system_service import SystemService

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
def get_health(_user=Depends(require_editor_or_admin)):
    return SystemService().get_health()


@router.get("/cron")
def get_cron(_user=Depends(require_editor_or_admin)):
    return SystemService().get_cron()


@router.get("/errors")
def get_errors(
    limit: int = Query(50, ge=1, le=200),
    _user=Depends(require_editor_or_admin),
):
    return SystemService().get_errors(limit)


# ── MCP service-account token minter ──────────────────────────────────────────

class MintMcpTokenBody(BaseModel):
    days: int = Field(default=90, ge=1, le=365, description="Lifetime in days (1-365).")


class MintMcpTokenResponse(BaseModel):
    token: str
    user_id: int
    username: str
    role: str
    expires_at: str
    lifetime_days: int


@router.post("/mcp/mint-token", response_model=MintMcpTokenResponse)
def mint_mcp_token(
    body: MintMcpTokenBody = Body(default_factory=MintMcpTokenBody),
    _user=Depends(require_admin),
):
    """Mint a long-lived JWT for the mcp-system service-account user.

    Used to configure local Claude Code MCP without SSH-ing into the host.
    Admin-only. Audited via the standard audit middleware.

    Returns the JWT in the response body; the caller is responsible for
    treating it as sensitive (it's effectively a password for the
    mcp-system user, which has admin role).
    """
    db = SessionLocal()
    try:
        mcp_user = (
            db.query(ConsoleUser)
            .filter(ConsoleUser.username == "mcp-system")
            .one_or_none()
        )
        if mcp_user is None:
            raise HTTPException(
                status_code=503,
                detail="mcp-system user not seeded — apply alembic migrations",
            )

        expire = datetime.now(timezone.utc) + timedelta(days=body.days)
        payload = {"sub": str(mcp_user.id), "role": mcp_user.role, "exp": expire}
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

        return MintMcpTokenResponse(
            token=token,
            user_id=mcp_user.id,
            username=mcp_user.username,
            role=mcp_user.role,
            expires_at=expire.isoformat(),
            lifetime_days=body.days,
        )
    finally:
        db.close()
