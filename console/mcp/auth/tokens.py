"""API-key registry. Production impl reads from `mcp_api_keys` table; the
in-memory variant is used by tests and for the trivial single-key dev case.
"""
from __future__ import annotations

import bcrypt
from dataclasses import dataclass


@dataclass
class ApiKeyEntry:
    name: str
    service_jwt: str  # long-lived JWT for the mapped service-account user
    scopes: list[str]


class InMemoryApiKeyRegistry:
    def __init__(self) -> None:
        self._by_hash: dict[bytes, ApiKeyEntry] = {}

    def register(self, name: str, plaintext_key: str, *, service_jwt: str, scopes: list[str] | None = None) -> None:
        h = bcrypt.hashpw(plaintext_key.encode(), bcrypt.gensalt())
        self._by_hash[h] = ApiKeyEntry(name=name, service_jwt=service_jwt, scopes=scopes or [])

    def lookup(self, plaintext_key: str) -> ApiKeyEntry | None:
        for h, entry in self._by_hash.items():
            if bcrypt.checkpw(plaintext_key.encode(), h):
                return entry
        return None


class DbApiKeyRegistry:
    """Reads `mcp_api_keys` rows on each lookup. Caches nothing — keeps the
    revoked_at check cheap and reflects revocations immediately.

    For each row: bcrypt-checks the plaintext key against `key_hash`.
    """

    def lookup(self, plaintext_key: str) -> ApiKeyEntry | None:
        import os
        from datetime import datetime, timezone

        from sqlalchemy import MetaData, select
        from sqlalchemy import update as sa_update

        from console.backend.database import SessionLocal, engine

        # Lazy reflect to avoid duplicating ORM model definitions.
        # We only need: name, key_hash, scopes, service_user_id, revoked_at.
        meta = MetaData()
        meta.reflect(bind=engine, only=["mcp_api_keys"])
        t = meta.tables["mcp_api_keys"]

        db = SessionLocal()
        try:
            rows = db.execute(
                select(t.c.id, t.c.name, t.c.key_hash, t.c.scopes, t.c.service_user_id, t.c.revoked_at)
                .where(t.c.revoked_at.is_(None))
            ).all()
            for row in rows:
                if bcrypt.checkpw(plaintext_key.encode(), row.key_hash.encode()):
                    # Service user's JWT is provided by an env var or a longer-lived
                    # mechanism — for the registry's purpose, we hand back the entry
                    # and let the caller resolve a token. The simplest production
                    # contract: a single MCP_API_TOKEN env var is the JWT for all
                    # service-account calls, and the registry only authenticates the
                    # caller, not the token mapping.
                    service_jwt = os.environ.get("MCP_API_TOKEN", "")
                    # update last_used_at for forensics
                    db.execute(
                        sa_update(t).where(t.c.id == row.id).values(last_used_at=datetime.now(timezone.utc))
                    )
                    db.commit()
                    return ApiKeyEntry(
                        name=row.name,
                        service_jwt=service_jwt,
                        scopes=list(row.scopes or []),
                    )
            return None
        finally:
            db.close()
