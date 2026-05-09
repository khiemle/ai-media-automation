"""youtube_video — full /youtube page surface (read + write + render gates)."""

from typing import Any

from console.mcp.errors import ConsoleError
from console.mcp.tools.music import (
    _ok, _bad_action, _require, _pick,
    _confirmed_sync, _confirmed_async, _confirmed_destructive,
)


async def youtube_video(*, action: str, _client: Any, **kw: Any) -> dict:
    """YouTube video lifecycle.

    Read:
      - list, get, list_templates, get_template, get_render_state

    Write (CRUD + import):
      - create       {fields}
      - update       {video_id, fields}
      - delete       {video_id}                    (destructive)
      - import_json  {payload}                     — same as create with the JSON payload

    Render gates:
      - render_audio_preview  {video_id}           (W async)
      - approve_audio_preview {video_id}           (W)
      - reject_audio_preview  {video_id}           (W destructive)
      - render_video_preview  {video_id}           (W async)
      - approve_video_preview {video_id}           (W)
      - reject_video_preview  {video_id}           (W destructive)
      - render_final          {video_id}           (W async)
      - cancel_render         {video_id}           (W destructive)
      - resume_render         {video_id}           (W async)
    """
    try:
        # ── Reads ────────────────────────────────────────────────────────────
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

        # ── CRUD ─────────────────────────────────────────────────────────────
        if action in ("create", "import_json"):
            payload = kw.get("payload") if action == "import_json" else kw.get("fields")
            if payload is None:
                raise ConsoleError(
                    code="validation.invalid_args",
                    message=f"missing required arg: {'payload' if action == 'import_json' else 'fields'}",
                    retryable=False,
                    context={"missing": "payload" if action == "import_json" else "fields"},
                )
            return await _confirmed_sync(
                kw, summary=f"create youtube video {payload.get('title', '<untitled>')!r}",
                run=lambda: _client.post("/api/youtube-videos", json=payload),
            )
        if action == "update":
            vid = _require(kw, "video_id")
            return await _confirmed_sync(
                kw, summary=f"update youtube video {vid}",
                run=lambda: _client.put(f"/api/youtube-videos/{vid}", json=kw.get("fields") or {}),
            )
        if action == "delete":
            vid = _require(kw, "video_id")
            return await _confirmed_destructive(
                kw, id_arg="video_id",
                summary=f"DELETE youtube video {vid}",
                run=lambda: _client.delete(f"/api/youtube-videos/{vid}"),
            )

        # ── Render gates ─────────────────────────────────────────────────────
        gate = _GATE_ACTIONS.get(action)
        if gate is not None:
            vid = _require(kw, "video_id")
            path = f"/api/youtube-videos/{vid}{gate['suffix']}"
            kind = gate.get("kind")
            summary = gate["summary"].format(vid=vid)
            if gate["destructive"]:
                return await _confirmed_destructive(
                    kw, id_arg="video_id", summary=summary,
                    run=lambda: _client.post(path),
                )
            if gate["async"]:
                return await _confirmed_async(
                    kw, summary=summary, task_kind=kind,
                    run=lambda: _client.post(path),
                )
            return await _confirmed_sync(
                kw, summary=summary,
                run=lambda: _client.post(path),
            )

        return _bad_action(action)
    except ConsoleError as e:
        return e.to_envelope()


_GATE_ACTIONS: dict = {
    "render_audio_preview":  {"suffix": "/render/audio-preview",         "async": True,  "destructive": False, "kind": "youtube_render_audio_preview", "summary": "render audio preview for video {vid}"},
    "approve_audio_preview": {"suffix": "/render/audio-preview/approve", "async": False, "destructive": False, "summary": "approve audio preview for video {vid}"},
    "reject_audio_preview":  {"suffix": "/render/audio-preview/reject",  "async": False, "destructive": True,  "summary": "REJECT audio preview for video {vid}"},
    "render_video_preview":  {"suffix": "/render/video-preview",         "async": True,  "destructive": False, "kind": "youtube_render_video_preview", "summary": "render video preview for video {vid}"},
    "approve_video_preview": {"suffix": "/render/video-preview/approve", "async": False, "destructive": False, "summary": "approve video preview for video {vid}"},
    "reject_video_preview":  {"suffix": "/render/video-preview/reject",  "async": False, "destructive": True,  "summary": "REJECT video preview for video {vid}"},
    "render_final":          {"suffix": "/render/final",                 "async": True,  "destructive": False, "kind": "youtube_render_final",         "summary": "render FINAL for video {vid}"},
    "cancel_render":         {"suffix": "/render/cancel",                "async": False, "destructive": True,  "summary": "CANCEL render for video {vid}"},
    "resume_render":         {"suffix": "/render/resume",                "async": True,  "destructive": False, "kind": "youtube_render_resume",        "summary": "resume render for video {vid}"},
}


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
