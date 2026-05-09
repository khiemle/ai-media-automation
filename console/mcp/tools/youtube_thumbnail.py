"""youtube_thumbnail — upload, AI-generate-with-text, fetch."""

from typing import Any

from console.mcp.errors import ConsoleError
from console.mcp.tools.music import (
    _ok, _bad_action, _require,
    _confirmed_sync,
)


async def youtube_thumbnail(*, action: str, _client: Any, **kw: Any) -> dict:
    """YouTube thumbnail surface.

    Actions:
      - upload_image        **Note:** Currently broken — backend expects multipart
                            image upload; ConsoleClient only sends JSON. See FOLLOWUPS.md.
      - generate_with_text  {video_id, text, style?, font?, color?}  (W sync)
                            Note: style, font, color are currently ignored by the backend
                            (ThumbnailGenerateRequest only accepts `text`); they are kept
                            in the signature for forward-compatibility.
      - get_current         {video_id}                               (R) → URL
      - get_source          {video_id}                               (R) → URL
    """
    try:
        vid = _require(kw, "video_id")
        if action == "upload_image":
            return ConsoleError(
                code="not_implemented",
                message="action 'upload_image' requires multipart upload, which ConsoleClient doesn't support yet. See FOLLOWUPS.md.",
                retryable=False,
                context={"action": action},
            ).to_envelope()
        if action == "generate_with_text":
            text = _require(kw, "text")
            return await _confirmed_sync(
                kw, summary=f"generate thumbnail with text for video {vid}",
                run=lambda: _client.post(f"/api/youtube-videos/{vid}/thumbnail-generate",
                                         json={"text": text}),
            )
        if action == "get_current":
            return {"ok": True, "data": {"url": f"/api/youtube-videos/{vid}/thumbnail"}}
        if action == "get_source":
            return {"ok": True, "data": {"url": f"/api/youtube-videos/{vid}/thumbnail-source"}}
        return _bad_action(action)
    except ConsoleError as e:
        return e.to_envelope()


def register(server, *, client_factory, audit_sink=None, transport="stdio", actor_jwt_sub=None):
    from console.mcp.audit import wrap_with_audit_log

    async def _core(**kw):
        client = client_factory()
        action = kw.get("action")
        rest = {k: v for k, v in kw.items() if k != "action"}
        return await youtube_thumbnail(action=action, _client=client, **rest)

    if audit_sink is not None:
        _audit_wrapped = wrap_with_audit_log(
            _core, tool_name="youtube_thumbnail",
            sink=audit_sink, transport=transport, actor_jwt_sub=actor_jwt_sub,
        )
    else:
        _audit_wrapped = None

    @server.tool(name="youtube_thumbnail")
    async def _youtube_thumbnail(
        action: str,
        video_id: int = None,
        file_path: str = None,
        text: str = None,
        style: str = None,
        font: str = None,
        color: str = None,
        confirm: bool = False,
        confirm_id: int = None,
    ) -> dict:
        client = client_factory()
        kw = {k: v for k, v in {
            "action": action,
            "video_id": video_id, "file_path": file_path,
            "text": text, "style": style, "font": font, "color": color,
            "confirm": confirm, "confirm_id": confirm_id,
        }.items() if v is not None or k in ("confirm", "action")}
        if _audit_wrapped is not None:
            return await _audit_wrapped(**kw)
        act = kw.pop("action", action)
        return await youtube_thumbnail(action=act, _client=client, **kw)
