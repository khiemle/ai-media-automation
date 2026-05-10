"""stdio transport entrypoint: `python -m console.mcp.stdio`.

Usage:
    python -m console.mcp.stdio              # normal JSON-RPC stdio server
    python -m console.mcp.stdio --self-test  # validate token + backend; exit 0/1
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

from console.mcp.activation import audit_kwargs, install_idempotency_store
from console.mcp.auth.adapters import StdioAuth
from console.mcp.client.console_client import ConsoleClient
from console.mcp.errors import ConsoleError
from console.mcp.server import build_server
from console.mcp.tools import (
    channel,
    channel_plan,
    music,
    pipeline_jobs,
    sfx,
    system_health,
    task_status,
    upload,
    visual_asset,
    youtube_thumbnail,
    youtube_video,
)


def _build_client() -> ConsoleClient:
    auth = StdioAuth.from_env()
    return ConsoleClient(
        base_url=os.environ.get("MCP_CONSOLE_API_BASE", "http://localhost:8080"),
        token_provider=auth.token,
        actor_metadata=auth.actor_metadata(),
    )


async def _self_test() -> int:
    """Validate that the configured backend accepts our token. Returns exit code."""
    base = os.environ.get("MCP_CONSOLE_API_BASE", "http://localhost:8080")
    client = None
    try:
        client = _build_client()
        await client.get("/api/system/health")
    except ConsoleError as e:
        if e.code == "auth.unauthorized" or (e.context or {}).get("status") == 401:
            if not os.environ.get("MCP_API_TOKEN"):
                print(
                    "FAIL: MCP_API_TOKEN is not set. "
                    "Set it to a valid service-account JWT before running --self-test.",
                    file=sys.stderr,
                )
            else:
                print(
                    f"FAIL: token rejected by {base} (401). "
                    "Re-mint in the System tab of the console UI.",
                    file=sys.stderr,
                )
            return 1
        print(f"FAIL: {base} returned error: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # connection refused, DNS failure, timeout, ...
        print(
            f"FAIL: cannot reach {base}: {e}. "
            "Check the URL / network (use a LAN IP or host.docker.internal "
            "from inside Docker).",
            file=sys.stderr,
        )
        return 1
    finally:
        if client is not None:
            await client.aclose()

    print(f"OK: {base} reachable, token accepted.")
    return 0


def _run_self_test_sync() -> int:
    return asyncio.run(_self_test())


def main() -> None:
    parser = argparse.ArgumentParser(prog="console.mcp.stdio")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Validate token + backend reachability, then exit (no JSON-RPC).",
    )
    args = parser.parse_args()

    if args.self_test:
        sys.exit(_run_self_test_sync())

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
