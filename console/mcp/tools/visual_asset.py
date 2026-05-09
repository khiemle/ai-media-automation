"""visual_asset — videos/images library used as backgrounds in YouTube videos."""

from typing import Any

from console.mcp.errors import ConsoleError
from console.mcp.tools.music import (
    _ok, _bad_action, _require, _pick,
    _confirmed_sync, _confirmed_async, _confirmed_destructive,
)


async def visual_asset(*, action: str, _client: Any, **kw: Any) -> dict:
    """Visual assets (background videos/images).

    Actions:
      - list                {niche, limit, offset}
      - get                 {asset_id}
      - stream_url          {asset_id}
      - get_thumbnail       {asset_id}
      - upload              **Note:** Currently broken — backend expects multipart file
                            upload; ConsoleClient only sends JSON. See FOLLOWUPS.md.
      - update              {asset_id, fields}
      - delete              {asset_id}                    (destructive)
      - animate             {asset_id, prompt}            (W async, Runway)
      - upscale             {asset_id, target}            (W async, Topaz)
                            Note: target and model are silently ignored by the backend;
                            the endpoint always upscales to 4K with Topaz.
    """
    try:
        if action == "list":
            return _ok(await _client.get("/api/production/assets",
                                         params=_pick(kw, {"niche", "limit", "offset"})))
        if action == "get":
            aid = _require(kw, "asset_id")
            return _ok(await _client.get(f"/api/production/assets/{aid}", params={}))
        if action == "stream_url":
            aid = _require(kw, "asset_id")
            return {"ok": True, "data": {"url": f"/api/production/assets/{aid}/stream"}}
        if action == "get_thumbnail":
            aid = _require(kw, "asset_id")
            return {"ok": True, "data": {"url": f"/api/production/assets/{aid}/thumbnail"}}
        if action == "upload":
            return ConsoleError(
                code="not_implemented",
                message="action 'upload' requires multipart upload, which ConsoleClient doesn't support yet. See FOLLOWUPS.md.",
                retryable=False,
                context={"action": action},
            ).to_envelope()
        if action == "update":
            aid = _require(kw, "asset_id")
            return await _confirmed_sync(
                kw, summary=f"update visual asset {aid}",
                run=lambda: _client.put(f"/api/production/assets/{aid}", json=kw.get("fields") or {}),
            )
        if action == "animate":
            aid = _require(kw, "asset_id")
            return await _confirmed_async(
                kw, summary=f"animate visual asset {aid}",
                task_kind="visual_asset_animate",
                run=lambda: _client.post(f"/api/production/assets/{aid}/animate",
                                         json=_pick(kw, {"prompt", "duration_s", "model"})),
            )
        if action == "upscale":
            aid = _require(kw, "asset_id")
            return await _confirmed_async(
                kw, summary=f"upscale visual asset {aid}",
                task_kind="visual_asset_upscale",
                run=lambda: _client.post(f"/api/production/assets/{aid}/upscale",
                                         json=_pick(kw, {"target", "model"})),
            )
        if action == "delete":
            aid = _require(kw, "asset_id")
            return await _confirmed_destructive(
                kw, id_arg="asset_id",
                summary=f"DELETE visual asset {aid}",
                run=lambda: _client.delete(f"/api/production/assets/{aid}"),
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
        return await visual_asset(action=action, _client=client, **rest)

    if audit_sink is not None:
        _audit_wrapped = wrap_with_audit_log(
            _core, tool_name="visual_asset",
            sink=audit_sink, transport=transport, actor_jwt_sub=actor_jwt_sub,
        )
    else:
        _audit_wrapped = None

    @server.tool(name="visual_asset")
    async def _visual_asset(
        action: str,
        asset_id: int = None,
        niche: str = None,
        limit: int = None,
        offset: int = None,
        file_path: str = None,
        title: str = None,
        tags: list = None,
        duration_s: int = None,
        fields: dict = None,
        prompt: str = None,
        model: str = None,
        target: str = None,
        confirm: bool = False,
        confirm_id: int = None,
    ) -> dict:
        client = client_factory()
        kw = {k: v for k, v in locals().items()
              if k not in ("client", "client_factory") and v is not None}
        kw.pop("kw", None)
        if _audit_wrapped is not None:
            return await _audit_wrapped(**kw)
        act = kw.pop("action", action)
        return await visual_asset(action=act, _client=client, **kw)
