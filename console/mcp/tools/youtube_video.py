"""youtube_video — full /youtube page surface.

Read paths only in this commit; write/render-gate paths added in Task 22.
"""

from typing import Any

from console.mcp.errors import ConsoleError
from console.mcp.tools.music import (
    _ok, _bad_action, _require, _pick,
    _confirmed_sync, _confirmed_async, _confirmed_destructive,
)


async def youtube_video(*, action: str, _client: Any, **kw: Any) -> dict:
    """YouTube video lifecycle.

    Read actions:
      - list           [status, niche, limit, offset]
      - get            {video_id}
      - list_templates
      - get_template   {template_id}
      - get_render_state {video_id}
    """
    try:
        if action == "list":
            return _ok(await _client.get("/api/youtube-videos",
                                         params=_pick(kw, {"status", "niche", "limit", "offset"})))
        if action == "get":
            vid = _require(kw, "video_id")
            return _ok(await _client.get(f"/api/youtube-videos/{vid}", params={}))
        if action == "list_templates":
            return _ok(await _client.get("/api/youtube-videos/templates", params={}))
        if action == "get_template":
            tid = _require(kw, "template_id")
            return _ok(await _client.get(f"/api/youtube-videos/templates/{tid}", params={}))
        if action == "get_render_state":
            vid = _require(kw, "video_id")
            return _ok(await _client.get(f"/api/youtube-videos/{vid}/render/state", params={}))
        return _bad_action(action)
    except ConsoleError as e:
        return e.to_envelope()


def register(server, *, client_factory):
    @server.tool(name="youtube_video")
    async def _youtube_video(
        action: str,
        video_id: int = None,
        template_id: int = None,
        status: str = None,
        niche: str = None,
        limit: int = None,
        offset: int = None,
        # write/gate args declared so the schema is stable across T21→T22:
        fields: dict = None,
        payload: dict = None,
        confirm: bool = False,
        confirm_id: int = None,
    ) -> dict:
        client = client_factory()
        kw = {k: v for k, v in {
            "video_id": video_id, "template_id": template_id,
            "status": status, "niche": niche, "limit": limit, "offset": offset,
            "fields": fields, "payload": payload,
            "confirm": confirm, "confirm_id": confirm_id,
        }.items() if v is not None or k == "confirm"}
        return await youtube_video(action=action, _client=client, **kw)
