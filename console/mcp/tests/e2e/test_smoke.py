"""Manual smoke test — run with `pytest -m manual` or `python -m`.

Verifies the package starts and lists the full tool catalog.
"""
import asyncio
import json
import os
import subprocess
import sys

import pytest


@pytest.mark.manual
@pytest.mark.asyncio
async def test_smoke_lists_all_eleven_tools(monkeypatch):
    monkeypatch.setenv("MCP_API_TOKEN", "stub")
    monkeypatch.setenv("MCP_CONSOLE_API_BASE", "http://nonexistent:1")

    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "console.mcp.stdio",
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}
        proc.stdin.write((json.dumps(init) + "\n").encode())
        await proc.stdin.drain()
        await asyncio.wait_for(proc.stdout.readline(), timeout=10)

        # MCP requires `notifications/initialized` before tools/list
        initialized = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        proc.stdin.write((json.dumps(initialized) + "\n").encode())
        await proc.stdin.drain()

        list_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        proc.stdin.write((json.dumps(list_req) + "\n").encode())
        await proc.stdin.drain()
        line = await asyncio.wait_for(proc.stdout.readline(), timeout=10)
        body = json.loads(line)
        names = sorted(t["name"] for t in body["result"]["tools"])
        assert names == sorted([
            "youtube_video", "youtube_thumbnail", "music", "sfx", "visual_asset",
            "channel_plan", "channel", "upload", "task_status", "pipeline_jobs", "system_health",
        ])
    finally:
        proc.terminate()
        await proc.wait()
