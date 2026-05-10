"""Mount MCP routes onto an existing FastAPI app at /mcp.

Designed for the editor chat surface: forwards the end-user's JWT (already
established by the existing console auth flow) to the console API.

NOTE — Audit gap: the /mcp/call route below dispatches via a hand-rolled
if/elif ladder and calls tool functions directly, bypassing wrap_with_audit_log.
MCP traffic through this transport is NOT covered by DbAuditSink. To fix this,
refactor mount.py to use FastMCP-style registration (like stdio.py) instead of
the manual dispatch table. Tracked in FOLLOWUPS.md.
"""
import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request

from console.mcp.activation import install_idempotency_store
from console.mcp.auth.adapters import ChatAuth
from console.mcp.client.console_client import ConsoleClient
from console.mcp.tools import system_health, task_status, pipeline_jobs, music, sfx, visual_asset, channel_plan, channel, youtube_video, youtube_thumbnail, upload


def attach(app: FastAPI) -> None:
    install_idempotency_store()
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
            {"name": "channel_plan", "description": "channel plan CRUD + JSON import + AI helpers (SEO, prompts, autofill, ask)"},
            {"name": "channel", "description": "channel CRUD + template defaults + credential status"},
            {"name": "youtube_video", "description": "youtube video lifecycle (CRUD + render gates)"},
            {"name": "youtube_thumbnail", "description": "youtube thumbnail upload, AI-generate-with-text, fetch"},
            {"name": "upload", "description": "multi-channel YouTube upload targeting + execution"},
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
        elif tool_name == "channel_plan":
            return await channel_plan.channel_plan(_client=client, **args)
        elif tool_name == "channel":
            return await channel.channel(_client=client, **args)
        elif tool_name == "youtube_video":
            return await youtube_video.youtube_video(_client=client, **args)
        elif tool_name == "youtube_thumbnail":
            return await youtube_thumbnail.youtube_thumbnail(_client=client, **args)
        elif tool_name == "upload":
            return await upload.upload(_client=client, **args)
        raise HTTPException(status_code=404, detail=f"unknown tool {tool_name}")


def _require_user_jwt(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="bearer token required")
    return authorization.split(None, 1)[1]
