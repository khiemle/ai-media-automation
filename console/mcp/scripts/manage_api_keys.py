"""Manage MCP API keys stored in `mcp_api_keys`.

Usage:
    python -m console.mcp.scripts.manage_api_keys create --name cron-bot
    python -m console.mcp.scripts.manage_api_keys list
    python -m console.mcp.scripts.manage_api_keys revoke --id 3
"""
import argparse
import secrets
import sys
from datetime import datetime, timezone

import bcrypt
from sqlalchemy import MetaData, insert, select, update

from console.backend.database import SessionLocal, engine
from console.backend.models.console_user import ConsoleUser


def _table():
    meta = MetaData()
    meta.reflect(bind=engine, only=["mcp_api_keys"])
    return meta.tables["mcp_api_keys"]


def cmd_create(args) -> int:
    plaintext = secrets.token_urlsafe(32)
    key_hash = bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt()).decode()
    t = _table()
    db = SessionLocal()
    try:
        # Resolve the service user id (default: mcp-system)
        user = db.query(ConsoleUser).filter(ConsoleUser.username == args.service_user).one_or_none()
        if user is None:
            print(
                f"Service user not found: {args.service_user!r}. "
                "Apply migrations or pick another --service-user.",
                file=sys.stderr,
            )
            return 2
        result = db.execute(
            insert(t).values(
                name=args.name,
                key_hash=key_hash,
                scopes=args.scopes or [],
                service_user_id=user.id,
                created_at=datetime.now(timezone.utc),
            ).returning(t.c.id)
        )
        new_id = result.scalar_one()
        db.commit()
    finally:
        db.close()

    print()
    print(f"  id:      {new_id}")
    print(f"  name:    {args.name}")
    print(f"  scopes:  {args.scopes or 'all'}")
    print(f"  api_key: {plaintext}")
    print()
    print("Save this api_key now — it will NEVER be retrievable again.")
    print("Pass it as the X-API-Key header value when calling /mcp/*.")
    return 0


def cmd_list(args) -> int:
    t = _table()
    db = SessionLocal()
    try:
        rows = db.execute(
            select(
                t.c.id, t.c.name, t.c.scopes, t.c.service_user_id,
                t.c.created_at, t.c.last_used_at, t.c.revoked_at,
            ).order_by(t.c.id)
        ).all()
    finally:
        db.close()

    if not rows:
        print("No API keys.")
        return 0
    print(f"{'id':<5}{'name':<25}{'status':<12}{'last used':<25}{'created':<25}")
    for r in rows:
        status = "REVOKED" if r.revoked_at else "active"
        last = r.last_used_at.isoformat() if r.last_used_at else "-"
        created = r.created_at.isoformat() if r.created_at else "-"
        print(f"{r.id:<5}{r.name:<25}{status:<12}{last:<25}{created:<25}")
    return 0


def cmd_revoke(args) -> int:
    t = _table()
    db = SessionLocal()
    try:
        result = db.execute(
            update(t)
            .where(t.c.id == args.id)
            .where(t.c.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        db.commit()
    finally:
        db.close()
    if result.rowcount == 0:
        print(f"No active API key with id={args.id}.", file=sys.stderr)
        return 1
    print(f"Revoked API key id={args.id}.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Manage MCP API keys.")
    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("create", help="Create a new API key.")
    pc.add_argument("--name", required=True, help="Human-readable label (e.g. cron-bot).")
    pc.add_argument(
        "--service-user", default="mcp-system",
        help="Console user the key authenticates as.",
    )
    pc.add_argument("--scopes", nargs="*", help="Tool/action allow-list. Empty = all.")
    pc.set_defaults(fn=cmd_create)

    pl = sub.add_parser("list", help="List API keys.")
    pl.set_defaults(fn=cmd_list)

    pr = sub.add_parser("revoke", help="Revoke an API key by id.")
    pr.add_argument("--id", required=True, type=int)
    pr.set_defaults(fn=cmd_revoke)

    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
