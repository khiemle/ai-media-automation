"""Audit logging middleware — records every write operation to audit_log."""
import logging
from datetime import datetime, timezone

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from console.backend.models.audit_log import AuditLog

logger = logging.getLogger(__name__)

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Paths to skip (health, auth/me, websockets)
SKIP_PREFIXES = ("/api/health", "/api/auth/me", "/ws/")


def _should_audit(request: Request) -> bool:
    if request.method not in WRITE_METHODS:
        return False
    path = request.url.path
    return not any(path.startswith(p) for p in SKIP_PREFIXES)


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        if not _should_audit(request):
            return response

        # Only audit successful writes (2xx)
        if not (200 <= response.status_code < 300):
            return response

        try:
            # Extract user_id from JWT state (set by auth dependency if present)
            user_id: int | None = None
            if hasattr(request.state, "user_id"):
                user_id = request.state.user_id

            # Parse path into target_type / target_id
            parts = [p for p in request.url.path.strip("/").split("/") if p]
            # e.g. ['api', 'scripts', '42', 'approve']
            target_type = parts[2] if len(parts) > 2 else None
            target_id   = parts[3] if len(parts) > 3 and parts[3].isdigit() else None
            action      = f"{request.method} {request.url.path}"

            from console.backend.database import SessionLocal
            db = SessionLocal()
            try:
                entry = AuditLog(
                    user_id=user_id,
                    action=action,
                    target_type=target_type,
                    target_id=target_id,
                    details={"status_code": response.status_code},
                    created_at=datetime.now(timezone.utc),
                )
                db.add(entry)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Audit log write failed: {e}")

        return response
