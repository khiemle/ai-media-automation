"""Mount MCP routes onto an existing FastAPI app at /mcp.

Designed for the editor chat surface: forwards the end-user's JWT (already
established by the existing console auth flow) to the console API.
"""
import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request

from console.mcp.auth.adapters import ChatAuth
from console.mcp.client.console_client import ConsoleClient
from console.mcp.tools import system_health, task_status, pipeline_jobs, music, sfx, visual_asset


def attach(app: FastAPI) -> None:
    @app.get("/mcp/tools")
    async def list_tools(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        _require_user_jwt(authorization)
        return {"tools": [
            {"name": "system_health", "description": "system observability"},
            {"name": "task_status", "description": "poll any task_id returned by an async-kicking tool"},
            {"name": "pipeline_jobs", "description": "list/get/retry/cancel/get_logs/stats over the Celery job table"},
            {"name": "music", "description": "music library CRUD + AI-generate + ElevenLabs compose"},
            {"name": "sfx", "description": "sound effects library + generation"},
            {"name": "visual_asset", "description": "background video/image library + Runway animate + Topaz upscale"},
        ]}

    @app.post("/mcp/call")
    async def call_tool(req: Request, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        jwt = _require_user_jwt(authorization)
        body = await req.json()
        tool_name = body["name"]
        args = body.get("arguments", {})
        auth = ChatAuth(forwarded_jwt=jwt)
        client = ConsoleClient(
            base_url=os.environ.get("MCP_CONSOLE_API_BASE", "http://localhost:8080"),
            token_provider=auth.token,
            actor_metadata=auth.actor_metadata(),
        )
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
        raise HTTPException(status_code=404, detail=f"unknown tool {tool_name}")


def _require_user_jwt(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="bearer token required")
    return authorization.split(None, 1)[1]
