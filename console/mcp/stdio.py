"""stdio transport entrypoint: `python -m console.mcp.stdio`."""
from __future__ import annotations

import os

from console.mcp.auth.adapters import StdioAuth
from console.mcp.client.console_client import ConsoleClient
from console.mcp.server import build_server
from console.mcp.tools import system_health


def main() -> None:
    auth = StdioAuth.from_env()

    def client_factory() -> ConsoleClient:
        return ConsoleClient(
            base_url=os.environ.get("MCP_CONSOLE_API_BASE", "http://localhost:8080"),
            token_provider=auth.token,
            actor_metadata=auth.actor_metadata(),
        )

    server = build_server(register=[
        lambda s: system_health.register(s, client_factory=client_factory),
    ])
    server.run("stdio")


if __name__ == "__main__":
    main()
