"""Mint a long-lived JWT for the mcp-system service-account user.

Usage:
    python -m console.mcp.scripts.mint_token            # prints token, expires in 90 days
    python -m console.mcp.scripts.mint_token --days 30  # custom lifetime
    python -m console.mcp.scripts.mint_token --json     # machine-readable output

The token bypasses JWT_EXPIRE_MINUTES — service tokens use an explicit `exp`.
Treat the printed value like a password; never check it into git.
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

from jose import jwt

from console.backend.config import settings
from console.backend.database import SessionLocal
from console.backend.models.console_user import ConsoleUser


def mint(days: int) -> dict:
    db = SessionLocal()
    try:
        user = (
            db.query(ConsoleUser)
            .filter(ConsoleUser.username == "mcp-system")
            .one_or_none()
        )
        if user is None:
            raise SystemExit(
                "mcp-system user not found in console_users. "
                "Apply alembic migrations: cd console/backend && alembic upgrade head"
            )
        user_id = user.id
        user_role = user.role
        username = user.username
    finally:
        db.close()

    expire = datetime.now(timezone.utc) + timedelta(days=days)
    payload = {"sub": str(user_id), "role": user_role, "exp": expire}
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return {
        "token": token,
        "user_id": user_id,
        "username": username,
        "role": user_role,
        "expires_at": expire.isoformat(),
        "lifetime_days": days,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Mint a long-lived JWT for the mcp-system user.")
    p.add_argument("--days", type=int, default=90, help="Lifetime in days (default 90).")
    p.add_argument("--json", action="store_true", help="Emit JSON instead of just the token.")
    args = p.parse_args()

    info = mint(days=args.days)
    if args.json:
        print(json.dumps(info, indent=2))
    else:
        print(info["token"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
