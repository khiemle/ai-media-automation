"""End-to-end stdio test: spawn the entrypoint, send MCP framing, read replies."""
import asyncio
import json
import os
import subprocess
import sys

import pytest


@pytest.mark.asyncio
async def test_stdio_lists_system_health_tool(monkeypatch):
    monkeypatch.setenv("MCP_API_TOKEN", "stub")
    monkeypatch.setenv("MCP_CONSOLE_API_BASE", "http://nonexistent:1")

    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "console.mcp.stdio",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        # MCP initialize
        init = {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05",
                       "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}},
        }
        proc.stdin.write((json.dumps(init) + "\n").encode())
        await proc.stdin.drain()
        line = await asyncio.wait_for(proc.stdout.readline(), timeout=10)
        assert b"\"id\":1" in line or b'"id": 1' in line

        # Send initialized notification (required by MCP spec before tools/list)
        initialized = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        proc.stdin.write((json.dumps(initialized) + "\n").encode())
        await proc.stdin.drain()
        # Notifications get no response — do not read

        # tools/list
        list_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        proc.stdin.write((json.dumps(list_req) + "\n").encode())
        await proc.stdin.drain()
        line = await asyncio.wait_for(proc.stdout.readline(), timeout=10)
        body = json.loads(line)
        names = [t["name"] for t in body["result"]["tools"]]
        assert "system_health" in names
    finally:
        proc.terminate()
        await proc.wait()
