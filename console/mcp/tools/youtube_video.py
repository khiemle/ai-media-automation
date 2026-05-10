"""youtube_video — full /youtube page surface (read + write + render gates)."""

from typing import Any

from console.mcp.errors import ConsoleError
from console.mcp.idempotency import IdempotencyStore
from console.mcp.tools.music import (
    _ok, _bad_action, _require, _pick,
    _confirmed_sync, _confirmed_async, _confirmed_destructive,
)

# Module-level idempotency store. Set via set_idempotency_store(); None disables.
_store: "IdempotencyStore | None" = None


def set_idempotency_store(store: "IdempotencyStore | None") -> None:
    global _store
    _store = store


async def youtube_video(*, action: str, _client: Any, **kw: Any) -> dict:
    """YouTube video lifecycle.

    Read:
      - list, get, list_templates, get_template, get_render_state
      - get_chapters  {video_id} → {video_id, chapters: list | null}
          Returns the YouTube chapter list (seconds + title) that would be
          injected on upload. For non-music templates returns chapters=null.
          For music templates with fewer than 3 tracks returns chapters=null
          (YouTube minimum). Useful for previewing chapters before upload.

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

    Music template fields (only valid when template_id refers to the 'music' template):
      music_track_ids:           list[int] — ordered playlist (at least 1 track required)
      track_transition:          'gapless' | 'crossfade' | 'gap'  (default 'gapless')
      track_transition_seconds:  float, 0.5..10.0                  (default 2.0)
      playlist_overlay_style:    'chip' | 'sidebar' | 'bottom_bar' | null
      spectrum_enabled:          bool                               (default false)
      spectrum_position:         'bottom' | 'center'
      spectrum_height_pct:       float, 0..0.5
      spectrum_color:            '#rrggbb'
      spectrum_opacity:          float, 0..1.0
    """
    try:
        # ── Reads ────────────────────────────────────────────────────────────
        if action == "list":
            # Note: only `status` and `template_id` are read by the backend;
            # `niche`, `limit`, and `offset` are silently ignored.
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
        if action == "get_chapters":
            vid = _require(kw, "video_id")
            return _ok(await _client.get(f"/api/youtube-videos/{vid}/chapters", params={}))

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

        # ── Special-case render_final for idempotency ─────────────────────
        if action == "render_final":
            vid = _require(kw, "video_id")
            idem = kw.get("idempotency_key")
            gate = _GATE_ACTIONS["render_final"]

            async def run_call():
                return await _confirmed_async(
                    kw, summary=gate["summary"].format(vid=vid),
                    task_kind=gate["kind"],
                    run=lambda: _client.post(f"/api/youtube-videos/{vid}{gate['suffix']}"),
                )

            if idem and _store is not None:
                return await _store.run_once(key=f"yt_render_final:{idem}", run=run_call)
            return await run_call()

        # ── Render gates (general path) ───────────────────────────────────
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


def register(server, *, client_factory, audit_sink=None, transport="stdio", actor_jwt_sub=None):
    from console.mcp.audit import wrap_with_audit_log

    async def _core(**kw):
        client = client_factory()
        action = kw.get("action")
        rest = {k: v for k, v in kw.items() if k != "action"}
        return await youtube_video(action=action, _client=client, **rest)

    if audit_sink is not None:
        _audit_wrapped = wrap_with_audit_log(
            _core, tool_name="youtube_video",
            sink=audit_sink, transport=transport, actor_jwt_sub=actor_jwt_sub,
        )
    else:
        _audit_wrapped = None

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
        idempotency_key: str = None,
        confirm: bool = False,
        confirm_id: int = None,
    ) -> dict:
        client = client_factory()
        kw = {k: v for k, v in {
            "action": action,
            "video_id": video_id, "template_id": template_id,
            "status": status, "niche": niche, "limit": limit, "offset": offset,
            "fields": fields, "payload": payload,
            "idempotency_key": idempotency_key,
            "confirm": confirm, "confirm_id": confirm_id,
        }.items() if v is not None or k in ("confirm", "action")}
        if _audit_wrapped is not None:
            return await _audit_wrapped(**kw)
        act = kw.pop("action", action)
        return await youtube_video(action=act, _client=client, **kw)
