"""HTTP/SSE transport: `python -m console.mcp.http` or mountable as ASGI app.

For the skateboard we expose:
  - GET  /healthz          — liveness
  - GET  /mcp/tools        — tool catalog (requires X-API-Key)
  - POST /mcp/call         — call a tool (requires X-API-Key)

A full SSE/streamable-HTTP MCP transport will be wired in once the FastMCP
SDK's HTTP server stabilizes (see spec §11). This skeleton is sufficient to
validate the auth + dispatch pipeline.
"""
import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request

from console.mcp.auth.adapters import HttpAuth
from console.mcp.auth.tokens import InMemoryApiKeyRegistry
from console.mcp.client.console_client import ConsoleClient
from console.mcp.server import build_server
from console.mcp.tools import system_health, task_status, pipeline_jobs, music, sfx, visual_asset, channel_plan, channel, youtube_video, youtube_thumbnail


def build_http_app(*, registry: InMemoryApiKeyRegistry) -> FastAPI:
    app = FastAPI(title="console-mcp-http")

    def make_client(api_key: str) -> ConsoleClient:
        auth = HttpAuth(registry=registry, header_value=api_key)
        return ConsoleClient(
            base_url=os.environ.get("MCP_CONSOLE_API_BASE", "http://localhost:8080"),
            token_provider=auth.token,
            actor_metadata=auth.actor_metadata(),
        )

    server = build_server(register=[
        lambda s: system_health.register(s, client_factory=lambda: ConsoleClient(
            base_url=os.environ.get("MCP_CONSOLE_API_BASE", "http://localhost:8080"),
            token_provider=lambda: "placeholder",  # overridden per-request below
        )),
        lambda s: task_status.register(s, client_factory=lambda: ConsoleClient(
            base_url=os.environ.get("MCP_CONSOLE_API_BASE", "http://localhost:8080"),
            token_provider=lambda: "placeholder",
        )),
        lambda s: pipeline_jobs.register(s, client_factory=lambda: ConsoleClient(
            base_url=os.environ.get("MCP_CONSOLE_API_BASE", "http://localhost:8080"),
            token_provider=lambda: "placeholder",
        )),
        lambda s: music.register(s, client_factory=lambda: ConsoleClient(
            base_url=os.environ.get("MCP_CONSOLE_API_BASE", "http://localhost:8080"),
            token_provider=lambda: "placeholder",
        )),
        lambda s: sfx.register(s, client_factory=lambda: ConsoleClient(
            base_url=os.environ.get("MCP_CONSOLE_API_BASE", "http://localhost:8080"),
            token_provider=lambda: "placeholder",
        )),
        lambda s: visual_asset.register(s, client_factory=lambda: ConsoleClient(
            base_url=os.environ.get("MCP_CONSOLE_API_BASE", "http://localhost:8080"),
            token_provider=lambda: "placeholder",
        )),
        lambda s: channel_plan.register(s, client_factory=lambda: ConsoleClient(
            base_url=os.environ.get("MCP_CONSOLE_API_BASE", "http://localhost:8080"),
            token_provider=lambda: "placeholder",
        )),
        lambda s: channel.register(s, client_factory=lambda: ConsoleClient(
            base_url=os.environ.get("MCP_CONSOLE_API_BASE", "http://localhost:8080"),
            token_provider=lambda: "placeholder",
        )),
        lambda s: youtube_video.register(s, client_factory=lambda: ConsoleClient(
            base_url=os.environ.get("MCP_CONSOLE_API_BASE", "http://localhost:8080"),
            token_provider=lambda: "placeholder",
        )),
        lambda s: youtube_thumbnail.register(s, client_factory=lambda: ConsoleClient(
            base_url=os.environ.get("MCP_CONSOLE_API_BASE", "http://localhost:8080"),
            token_provider=lambda: "placeholder",
        )),
    ])

    def _require_key(x_api_key: str | None) -> str:
        if not x_api_key or registry.lookup(x_api_key) is None:
            raise HTTPException(status_code=401, detail="invalid api key")
        return x_api_key

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/mcp/tools")
    async def list_tools(x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
        _require_key(x_api_key)
        tools = server.list_tools()
        if hasattr(tools, "__await__"):
            tools = await tools
        return {"tools": [{"name": t.name, "description": t.description} for t in tools]}

    @app.post("/mcp/call")
    async def call_tool(req: Request, x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
        api_key = _require_key(x_api_key)
        body = await req.json()
        tool_name = body["name"]
        args = body.get("arguments", {})
        # Per-request client wired with this caller's API key
        client = make_client(api_key)
        if tool_name == "system_health":
            return await system_health.system_health(_client=client, **args)
        elif tool_name == "task_status":
            return await task_status.task_status(_client=client, **args)
        elif tool_name == "pipeline_jobs":
            return await pipeline_jobs.pipeline_jobs(_client=client, **args)
        elif tool_name == "music":
            return await music.music(_client=client, **args)
        elif tool_name == "sfx":
            return await sfx.sfx(_client=client, **args)
        elif tool_name == "visual_asset":
            return await visual_asset.visual_asset(_client=client, **args)
        elif tool_name == "channel_plan":
            return await channel_plan.channel_plan(_client=client, **args)
        elif tool_name == "channel":
            return await channel.channel(_client=client, **args)
        elif tool_name == "youtube_video":
            return await youtube_video.youtube_video(_client=client, **args)
        elif tool_name == "youtube_thumbnail":
            return await youtube_thumbnail.youtube_thumbnail(_client=client, **args)
        raise HTTPException(status_code=404, detail=f"unknown tool {tool_name}")

    return app


def main() -> None:
    import uvicorn
    registry = InMemoryApiKeyRegistry()
    # In production, registry would load from `mcp_api_keys` table.
    if os.environ.get("MCP_HTTP_DEV_API_KEY"):
        registry.register(
            "dev",
            os.environ["MCP_HTTP_DEV_API_KEY"],
            service_jwt=os.environ.get("MCP_API_TOKEN", ""),
        )
    app = build_http_app(registry=registry)
    uvicorn.run(
        app,
        host=os.environ.get("MCP_HTTP_HOST", "0.0.0.0"),
        port=int(os.environ.get("MCP_HTTP_PORT", "8765")),
    )


if __name__ == "__main__":
    main()
