"""system_health tool — read-only observability."""
from typing import Any

from console.mcp.errors import ConsoleError

ACTIONS = {
    "health": "/api/system/health",
    "cron": "/api/system/cron",
    "errors": "/api/system/errors",
    "llm_quota": "/api/llm/quota",
    "performance_summary": "/api/performance/summary",
}


async def system_health(*, action: str, _client) -> dict[str, Any]:
    """Read-only system health and observability surface.

    Actions:
      - health: liveness + dependency check
      - cron: scheduled task status
      - errors: recent error log entries
      - llm_quota: Ollama/Gemini quota usage
      - performance_summary: pipeline performance summary
    """
    path = ACTIONS.get(action)
    if path is None:
        return ConsoleError(
            code="validation.invalid_args",
            message=f"unknown action {action!r}; valid: {list(ACTIONS)}",
            retryable=False,
            context={"action": action},
        ).to_envelope()
    try:
        data = await _client.get(path)
    except ConsoleError as e:
        return e.to_envelope()
    return {"ok": True, "data": data}


def register(server, *, client_factory):
    """Hook called by build_server."""
    @server.tool(name="system_health")
    async def _system_health(action: str) -> dict[str, Any]:
        client = client_factory()
        return await system_health(action=action, _client=client)
