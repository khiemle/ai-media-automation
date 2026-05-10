"""stdio transport entrypoint: `python -m console.mcp.stdio`."""
from __future__ import annotations

import os

from console.mcp.activation import audit_kwargs, install_idempotency_store
from console.mcp.auth.adapters import StdioAuth
from console.mcp.client.console_client import ConsoleClient
from console.mcp.server import build_server
from console.mcp.tools import system_health, task_status, pipeline_jobs, music, sfx, visual_asset, channel_plan, channel, youtube_video, youtube_thumbnail, upload


def main() -> None:
    auth = StdioAuth.from_env()
    install_idempotency_store()

    def client_factory() -> ConsoleClient:
        return ConsoleClient(
            base_url=os.environ.get("MCP_CONSOLE_API_BASE", "http://localhost:8080"),
            token_provider=auth.token,
            actor_metadata=auth.actor_metadata(),
        )

    activation = audit_kwargs(transport="stdio")

    server = build_server(register=[
        lambda s: system_health.register(s, client_factory=client_factory, **activation),
        lambda s: task_status.register(s, client_factory=client_factory, **activation),
        lambda s: pipeline_jobs.register(s, client_factory=client_factory, **activation),
        lambda s: music.register(s, client_factory=client_factory, **activation),
        lambda s: sfx.register(s, client_factory=client_factory, **activation),
        lambda s: visual_asset.register(s, client_factory=client_factory, **activation),
        lambda s: channel_plan.register(s, client_factory=client_factory, **activation),
        lambda s: channel.register(s, client_factory=client_factory, **activation),
        lambda s: youtube_video.register(s, client_factory=client_factory, **activation),
        lambda s: youtube_thumbnail.register(s, client_factory=client_factory, **activation),
        lambda s: upload.register(s, client_factory=client_factory, **activation),
    ])
    server.run("stdio")


if __name__ == "__main__":
    main()
