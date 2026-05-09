"""channel — channel CRUD + template defaults + credential status (read-only)."""

from typing import Any

from console.mcp.errors import ConsoleError
from console.mcp.tools.music import (
    _ok, _bad_action, _require, _pick,
    _confirmed_sync, _confirmed_destructive,
)


async def channel(*, action: str, _client: Any, **kw: Any) -> dict:
    """Channels (per-platform target + template defaults).

    Actions:
      - list                              (R)
      - get          {channel_id}         (R)
      - create       {fields}             (W)
      - update       {channel_id, fields} (W)
      - delete       {channel_id}         (W destructive)
      - get_defaults {template}           (R)
      - set_defaults {template, fields}   (W)
      - credential_status {platform}      (R) — read-only on secrets
    """
    try:
        if action == "list":
            return _ok(await _client.get("/api/channels", params={}))
        if action == "get":
            cid = _require(kw, "channel_id")
            return _ok(await _client.get(f"/api/channels/{cid}", params={}))
        if action == "create":
            fields = _require(kw, "fields")
            return await _confirmed_sync(
                kw, summary="create channel",
                run=lambda: _client.post("/api/channels", json=fields),
            )
        if action == "update":
            cid = _require(kw, "channel_id")
            return await _confirmed_sync(
                kw, summary=f"update channel {cid}",
                run=lambda: _client.put(f"/api/channels/{cid}", json=kw.get("fields") or {}),
            )
        if action == "delete":
            cid = _require(kw, "channel_id")
            return await _confirmed_destructive(
                kw, id_arg="channel_id",
                summary=f"DELETE channel {cid}",
                run=lambda: _client.delete(f"/api/channels/{cid}"),
            )
        if action == "get_defaults":
            tpl = _require(kw, "template")
            return _ok(await _client.get(f"/api/channels/defaults/{tpl}", params={}))
        if action == "set_defaults":
            tpl = _require(kw, "template")
            return await _confirmed_sync(
                kw, summary=f"set defaults for template {tpl!r}",
                run=lambda: _client.put(f"/api/channels/defaults/{tpl}", json=kw.get("fields") or {}),
            )
        if action == "credential_status":
            platform = _require(kw, "platform")
            return _ok(await _client.get(f"/api/credentials/{platform}", params={}))
        return _bad_action(action)
    except ConsoleError as e:
        return e.to_envelope()


def register(server, *, client_factory, audit_sink=None, transport="stdio", actor_jwt_sub=None):
    from console.mcp.audit import wrap_with_audit_log

    async def _core(**kw):
        client = client_factory()
        action = kw.get("action")
        rest = {k: v for k, v in kw.items() if k != "action"}
        return await channel(action=action, _client=client, **rest)

    if audit_sink is not None:
        _audit_wrapped = wrap_with_audit_log(
            _core, tool_name="channel",
            sink=audit_sink, transport=transport, actor_jwt_sub=actor_jwt_sub,
        )
    else:
        _audit_wrapped = None

    @server.tool(name="channel")
    async def _channel(
        action: str,
        channel_id: int = None,
        template: str = None,
        platform: str = None,
        fields: dict = None,
        confirm: bool = False,
        confirm_id: int = None,
    ) -> dict:
        client = client_factory()
        kw = {k: v for k, v in {
            "action": action,
            "channel_id": channel_id, "template": template,
            "platform": platform, "fields": fields,
            "confirm": confirm, "confirm_id": confirm_id,
        }.items() if v is not None or k in ("confirm", "action")}
        if _audit_wrapped is not None:
            return await _audit_wrapped(**kw)
        act = kw.pop("action", action)
        return await channel(action=act, _client=client, **kw)
