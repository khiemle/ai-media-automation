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
