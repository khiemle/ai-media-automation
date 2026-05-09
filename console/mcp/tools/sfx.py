"""sfx — sound effects library + generation."""

from typing import Any

from console.mcp.errors import ConsoleError
from console.mcp.tools.music import (  # reuse helpers
    _ok, _bad_action, _require, _pick,
    _confirmed_sync, _confirmed_async, _confirmed_destructive,
)


async def sfx(*, action: str, _client: Any, **kw: Any) -> dict:
    """SFX library.

    Actions:
      - list_sound_types
      - list                   [sound_type, limit, offset]
      - get_stream_url         {sfx_id}
      - generate               {text, duration_seconds?, loop?}  (W sync — returns SFX row directly)
      - import_file            **Note:** Currently broken — backend expects multipart file upload;
                               ConsoleClient only sends JSON. See FOLLOWUPS.md.
      - delete                 {sfx_id} (destructive)
    """
    try:
        if action == "list_sound_types":
            return _ok(await _client.get("/api/sfx/sound-types", params={}))
        if action == "list":
            params = _pick(kw, {"sound_type", "limit", "offset"})
            return _ok(await _client.get("/api/sfx", params=params))
        if action == "get_stream_url":
            sid = _require(kw, "sfx_id")
            return {"ok": True, "data": {"url": f"/api/sfx/{sid}/stream"}}
        if action == "generate":
            return await _confirmed_sync(
                kw, summary=f"generate sfx: {kw.get('text')!r}",
                run=lambda: _client.post("/api/sfx/generate",
                                         json=_pick(kw, {"text", "duration_seconds", "loop", "title"})),
            )
        if action == "import_file":
            return ConsoleError(
                code="not_implemented",
                message=f"action 'import_file' requires multipart upload, which ConsoleClient doesn't support yet. See FOLLOWUPS.md.",
                retryable=False,
                context={"action": action},
            ).to_envelope()
        if action == "delete":
            sid = _require(kw, "sfx_id")
            return await _confirmed_destructive(
                kw, id_arg="sfx_id",
                summary=f"DELETE sfx {sid}",
                run=lambda: _client.delete(f"/api/sfx/{sid}"),
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
        return await sfx(action=action, _client=client, **rest)

    if audit_sink is not None:
        _audit_wrapped = wrap_with_audit_log(
            _core, tool_name="sfx",
            sink=audit_sink, transport=transport, actor_jwt_sub=actor_jwt_sub,
        )
    else:
        _audit_wrapped = None

    @server.tool(name="sfx")
    async def _sfx(
        action: str,
        sfx_id: int = None,
        sound_type: str = None,
        text: str = None,
        duration_seconds: float = None,
        loop: bool = None,
        title: str = None,
        file_path: str = None,
        name: str = None,
        limit: int = None,
        offset: int = None,
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
        return await sfx(action=act, _client=client, **kw)
