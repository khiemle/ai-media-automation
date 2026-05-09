"""upload — multi-channel YouTube upload targeting + execution."""

from typing import Any

from console.mcp.errors import ConsoleError
from console.mcp.tools.music import (
    _ok, _bad_action, _require, _pick,
    _confirmed_sync, _confirmed_async, _confirmed_destructive,
)


async def upload(*, action: str, _client: Any, **kw: Any) -> dict:
    """Upload pipeline.

    Actions:
      - list_videos       [status, niche, limit, offset]      (R)
      - set_targets       {video_id, channels: [int]}         (W)
      - upload_one        {video_id}                          (W destructive async)
      - upload_all        {filter?}                           (W destructive async)
      - delete_target     {video_id}                          (W destructive)
      - stream_url        {video_id}                          (R)
    """
    try:
        if action == "list_videos":
            return _ok(await _client.get("/api/uploads/videos",
                                         params=_pick(kw, {"status", "niche", "limit", "offset"})))
        if action == "set_targets":
            vid = _require(kw, "video_id")
            channels = _require(kw, "channels")
            return await _confirmed_sync(
                kw, summary=f"set upload targets for video {vid} → channels {channels}",
                run=lambda: _client.put(f"/api/uploads/videos/{vid}/targets",
                                        json={"channels": channels}),
            )
        if action == "upload_one":
            vid = _require(kw, "video_id")
            return await _async_destructive(
                kw, id_arg="video_id",
                summary=f"UPLOAD video {vid} to its targeted channels",
                task_kind="youtube_upload",
                run=lambda: _client.post(f"/api/uploads/videos/{vid}/upload", json={}),
            )
        if action == "upload_all":
            return await _async_destructive(
                kw, id_arg=None, fixed_id="all",
                summary=f"UPLOAD ALL with filter {kw.get('filter') or {}}",
                task_kind="youtube_upload_all",
                run=lambda: _client.post("/api/uploads/upload-all",
                                         json={"filter": kw.get("filter") or {}}),
            )
        if action == "delete_target":
            vid = _require(kw, "video_id")
            return await _confirmed_destructive(
                kw, id_arg="video_id",
                summary=f"DELETE upload target for video {vid}",
                run=lambda: _client.delete(f"/api/uploads/videos/{vid}"),
            )
        if action == "stream_url":
            vid = _require(kw, "video_id")
            return {"ok": True, "data": {"url": f"/api/uploads/videos/{vid}/stream"}}
        return _bad_action(action)
    except ConsoleError as e:
        return e.to_envelope()


async def _async_destructive(kw, *, id_arg, summary, task_kind, run, fixed_id=None):
    """Async + destructive: confirm + confirm_id match + return task envelope."""
    expected = fixed_id if fixed_id is not None else kw.get(id_arg)
    if not kw.get("confirm", False):
        return {
            "ok": False,
            "needs_confirmation": True,
            "intent": {"summary": summary, "args": {k: v for k, v in kw.items() if k != "_client"}},
            "to_proceed": f"call again with confirm=true and confirm_id={expected}",
        }
    if kw.get("confirm_id") != expected:
        return ConsoleError(
            code="validation.confirm_id_mismatch",
            message=f"confirm_id must equal {expected!r}",
            retryable=False,
            context={"expected": expected, "got": kw.get("confirm_id")},
        ).to_envelope()
    data = await run()
    return {
        "ok": True,
        "task_id": (data or {}).get("task_id"),
        "status_tool": "task_status",
        "task_kind": task_kind,
        "poll_hint": "every 15s, ~2-10 min depending on file size",
    }


def register(server, *, client_factory):
    @server.tool(name="upload")
    async def _upload(
        action: str,
        video_id: int = None,
        channels: list = None,
        filter: dict = None,
        status: str = None,
        niche: str = None,
        limit: int = None,
        offset: int = None,
        confirm: bool = False,
        confirm_id: Any = None,
    ) -> dict:
        client = client_factory()
        kw = {k: v for k, v in {
            "video_id": video_id, "channels": channels, "filter": filter,
            "status": status, "niche": niche, "limit": limit, "offset": offset,
            "confirm": confirm, "confirm_id": confirm_id,
        }.items() if v is not None or k == "confirm"}
        return await upload(action=action, _client=client, **kw)
