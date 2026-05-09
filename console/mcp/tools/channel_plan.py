"""channel_plan — CRUD + JSON import + AI helpers."""

from typing import Any

from console.mcp.errors import ConsoleError
from console.mcp.tools.music import (
    _ok, _bad_action, _require, _pick,
    _confirmed_sync, _confirmed_destructive,
)


async def channel_plan(*, action: str, _client: Any, **kw: Any) -> dict:
    """Channel plans (the upstream brief for a channel's content).

    Actions:
      - list                                                          (R)
      - get          {plan_id}                                        (R)
      - import_json  **Note:** Currently broken — backend expects a .md file
                     upload (multipart); ConsoleClient only sends JSON.
                     See FOLLOWUPS.md.
      - update       {plan_id, fields}                                (W)
      - delete       {plan_id}                                        (W destructive)
      - ai_seo       {plan_id, theme, context?}                       (W) → SEO suggestion
      - ai_prompts   {plan_id, theme, context?}                       (W) → prompt suggestions
      - ai_autofill  {plan_id, theme, context?}                       (W) → bulk autofill
      - ai_ask       {plan_id, question}                              (W) → answer
    """
    try:
        if action == "list":
            return _ok(await _client.get("/api/channel-plans", params={}))
        if action == "get":
            pid = _require(kw, "plan_id")
            return _ok(await _client.get(f"/api/channel-plans/{pid}", params={}))
        if action == "import_json":
            return ConsoleError(
                code="not_implemented",
                message="action 'import_json' requires multipart upload, which ConsoleClient doesn't support yet. See FOLLOWUPS.md.",
                retryable=False,
                context={"action": action},
            ).to_envelope()
        if action == "update":
            pid = _require(kw, "plan_id")
            return await _confirmed_sync(
                kw, summary=f"update channel plan {pid}",
                run=lambda: _client.put(f"/api/channel-plans/{pid}", json=kw.get("fields") or {}),
            )
        if action == "delete":
            pid = _require(kw, "plan_id")
            return await _confirmed_destructive(
                kw, id_arg="plan_id",
                summary=f"DELETE channel plan {pid}",
                run=lambda: _client.delete(f"/api/channel-plans/{pid}"),
            )
        if action == "ai_seo":
            pid = _require(kw, "plan_id")
            theme = _require(kw, "theme")
            body = {"theme": theme, "context": kw.get("context", "")}
            return await _confirmed_sync(
                kw, summary=f"ai SEO for plan {pid} (theme={theme!r})",
                run=lambda: _client.post(f"/api/channel-plans/{pid}/ai/seo", json=body),
            )
        if action == "ai_prompts":
            pid = _require(kw, "plan_id")
            theme = _require(kw, "theme")
            body = {"theme": theme, "context": kw.get("context", "")}
            return await _confirmed_sync(
                kw, summary=f"ai prompts for plan {pid} (theme={theme!r})",
                run=lambda: _client.post(f"/api/channel-plans/{pid}/ai/prompts", json=body),
            )
        if action == "ai_autofill":
            pid = _require(kw, "plan_id")
            theme = _require(kw, "theme")
            body = {"theme": theme, "context": kw.get("context", "")}
            return await _confirmed_sync(
                kw, summary=f"ai autofill plan {pid} (theme={theme!r})",
                run=lambda: _client.post(f"/api/channel-plans/{pid}/ai/autofill", json=body),
            )
        if action == "ai_ask":
            pid = _require(kw, "plan_id")
            q = _require(kw, "question")
            return await _confirmed_sync(
                kw, summary=f"ai ask on plan {pid}: {q!r}",
                run=lambda: _client.post(f"/api/channel-plans/{pid}/ai/ask", json={"question": q}),
            )
        return _bad_action(action)
    except ConsoleError as e:
        return e.to_envelope()


def register(server, *, client_factory, audit_sink=None, transport="stdio", actor_jwt_sub=None):
    from console.mcp.audit import wrap_with_audit_log

    async def _core(**kw):
        client = client_factory()
        action = kw.get("action")
        rest = {k: v for k, v in kw.items() if k != "action"}
        return await channel_plan(action=action, _client=client, **rest)

    if audit_sink is not None:
        _audit_wrapped = wrap_with_audit_log(
            _core, tool_name="channel_plan",
            sink=audit_sink, transport=transport, actor_jwt_sub=actor_jwt_sub,
        )
    else:
        _audit_wrapped = None

    @server.tool(name="channel_plan")
    async def _channel_plan(
        action: str,
        plan_id: int = None,
        fields: dict = None,
        theme: str = None,
        context: str = None,
        question: str = None,
        confirm: bool = False,
        confirm_id: int = None,
    ) -> dict:
        client = client_factory()
        kw = {k: v for k, v in {
            "action": action,
            "plan_id": plan_id, "fields": fields,
            "theme": theme, "context": context,
            "question": question,
            "confirm": confirm, "confirm_id": confirm_id,
        }.items() if v is not None or k in ("confirm", "action")}
        if _audit_wrapped is not None:
            return await _audit_wrapped(**kw)
        act = kw.pop("action", action)
        return await channel_plan(action=act, _client=client, **kw)
