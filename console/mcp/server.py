"""Server builder shared by all transport entrypoints."""
from __future__ import annotations

from typing import Callable, Iterable

from mcp.server.fastmcp import FastMCP


SERVER_NAME = "ai-media-console"
SERVER_VERSION = "0.1.0"


def build_server(
    *,
    register: Iterable[Callable[[FastMCP], None]],
) -> FastMCP:
    """Build a FastMCP instance and let each `register` callback wire its tools."""
    server = FastMCP(SERVER_NAME)
    for reg in register:
        reg(server)
    return server
