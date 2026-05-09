"""Smoke test: DbApiKeyRegistry can be imported and instantiated without error.

Does NOT exercise lookup() — that requires a live Postgres with the
mcp_api_keys table. This test guards against import-time breakage only.
"""


def test_db_api_key_registry_imports():
    from console.mcp.auth.tokens import DbApiKeyRegistry

    DbApiKeyRegistry()  # constructor should not raise
