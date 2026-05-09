"""music — full CRUD + AI-generate + ElevenLabs."""

from typing import Any

from console.mcp.errors import ConsoleError
from console.mcp.tools._common import returns_task


async def music(*, action: str, _client: Any, **kw: Any) -> dict:
    """Music library + generation.

    Actions:
      - list_templates                                      (R)
      - list_tracks  [niche, limit, offset]                 (R)
      - get          {track_id}                             (R)
      - stream_url   {track_id}                             (R)  → returns URL string
      - generate     {idea, niches?, moods?, genres?,
                      provider?, is_vocal?, title?,
                      expand_only?}                         (W async, confirm=true)
      - update       {track_id, fields}                     (W, confirm=true)
      - delete       {track_id}                             (W destructive)
      - elevenlabs_plan    {input, music_length_ms?}        (R)  pure LLM call, no side effects
      - elevenlabs_compose {composition_plan, title?,
                            niches?, moods?, genres?,
                            output_format?,
                            respect_sections_durations?}    (W async, confirm=true)
      - get_task     {task_id}                              (R)

    Note: upload (POST /api/music/upload) requires multipart/form-data with a binary
    file field; it cannot be called via JSON and is not supported by this tool.
    """
    try:
        if action == "list_templates":
            return _ok(await _client.get("/api/music/templates", params={}))
        if action == "list_tracks":
            params = {k: v for k, v in kw.items() if k in {"niche", "limit", "offset"} and v is not None}
            return _ok(await _client.get("/api/music", params=params))
        if action == "get":
            tid = _require(kw, "track_id")
            return _ok(await _client.get(f"/api/music/{tid}", params={}))
        if action == "stream_url":
            tid = _require(kw, "track_id")
            return {"ok": True, "data": {"url": f"/api/music/{tid}/stream"}}
        if action == "get_task":
            taskid = _require(kw, "task_id")
            return _ok(await _client.get(f"/api/music/tasks/{taskid}"))

        # elevenlabs_plan is read-only-ish (LLM plan generation, no DB side effects)
        # Backend: ElevenLabsPlanBody { input: str, music_length_ms: int = 60000 }
        if action == "elevenlabs_plan":
            return _ok(await _client.post("/api/music/elevenlabs/plan",
                                          json=_pick(kw, {"input", "music_length_ms"})))

        # Backend: GenerateBody { idea, niches, moods, genres, provider, is_vocal, title, expand_only }
        if action == "generate":
            return await _confirmed_async(
                kw, summary=f"generate music: {kw.get('idea', '')!r}",
                task_kind="music_generate",
                run=lambda: _client.post("/api/music/generate",
                                         json=_pick(kw, {"idea", "niches", "moods", "genres",
                                                          "provider", "is_vocal", "title", "expand_only"})),
            )
        # Backend: ElevenLabsComposeBody { composition_plan, title, niches, moods, genres,
        #                                   output_format, respect_sections_durations }
        if action == "elevenlabs_compose":
            return await _confirmed_async(
                kw, summary=f"elevenlabs compose",
                task_kind="music_elevenlabs_compose",
                run=lambda: _client.post("/api/music/elevenlabs/compose",
                                         json=_pick(kw, {"composition_plan", "title", "niches",
                                                          "moods", "genres", "output_format",
                                                          "respect_sections_durations"})),
            )
        if action == "update":
            tid = _require(kw, "track_id")
            # Backend: UpdateBody { title, niches, moods, genres, is_vocal, is_favorite,
            #                       volume, quality_score } — all optional
            return await _confirmed_sync(
                kw, summary=f"update music track {tid}",
                run=lambda: _client.put(f"/api/music/{tid}", json=kw.get("fields") or {}),
            )
        if action == "delete":
            tid = _require(kw, "track_id")
            return await _confirmed_destructive(
                kw, id_arg="track_id",
                summary=f"DELETE music track {tid}",
                run=lambda: _client.delete(f"/api/music/{tid}"),
            )

        return _bad_action(action)
    except ConsoleError as e:
        return e.to_envelope()


# ── shared helpers (also used by sfx, visual_asset, etc.) ────────────────────

def _ok(data: Any) -> dict:
    return {"ok": True, "data": data}


def _bad_action(action: str) -> dict:
    return ConsoleError(
        code="validation.invalid_args",
        message=f"unknown action {action!r}",
        retryable=False,
        context={"action": action},
    ).to_envelope()


def _require(kw: dict, name: str) -> Any:
    if kw.get(name) is None:
        raise ConsoleError(
            code="validation.invalid_args",
            message=f"missing required arg: {name}",
            retryable=False,
            context={"missing": name},
        )
    return kw[name]


def _pick(kw: dict, names: set) -> dict:
    return {k: kw[k] for k in names if k in kw and kw[k] is not None}


async def _confirmed_sync(kw, *, summary, run):
    if not kw.get("confirm", False):
        return _intent(summary, kw)
    data = await run()
    return _ok(data)


async def _confirmed_async(kw, *, summary, task_kind, run):
    if not kw.get("confirm", False):
        return _intent(summary, kw)
    data = await run()
    if isinstance(data, dict) and data.get("ok") is False:
        return data
    return {
        "ok": True,
        "task_id": (data or {}).get("task_id"),
        "status_tool": "task_status",
        "task_kind": task_kind,
        "poll_hint": "every 10s",
    }


async def _confirmed_destructive(kw, *, id_arg, summary, run):
    if not kw.get("confirm", False):
        return _intent(summary, kw, hint=f"call again with confirm=true and confirm_id={kw.get(id_arg)}")
    if kw.get("confirm_id") != kw.get(id_arg):
        return ConsoleError(
            code="validation.confirm_id_mismatch",
            message=f"confirm_id must equal {id_arg}",
            retryable=False,
            context={id_arg: kw.get(id_arg), "confirm_id": kw.get("confirm_id")},
        ).to_envelope()
    return _ok(await run())


def _intent(summary, kw, hint="call again with confirm=true"):
    return {
        "ok": False,
        "needs_confirmation": True,
        "intent": {"summary": summary, "args": {k: v for k, v in kw.items() if k != "_client" and not _is_secret(k)}},
        "to_proceed": hint,
    }


def _is_secret(name: str) -> bool:
    return name in {"password"} or name.endswith(("_token", "_key", "_secret"))


def register(server, *, client_factory, audit_sink=None, transport="stdio", actor_jwt_sub=None):
    from console.mcp.audit import wrap_with_audit_log

    async def _core(**kw):
        client = client_factory()
        action = kw.get("action")
        rest = {k: v for k, v in kw.items() if k != "action"}
        return await music(action=action, _client=client, **rest)

    if audit_sink is not None:
        _audit_wrapped = wrap_with_audit_log(
            _core, tool_name="music",
            sink=audit_sink, transport=transport, actor_jwt_sub=actor_jwt_sub,
        )
    else:
        _audit_wrapped = None

    @server.tool(name="music")
    async def _music(
        action: str,
        track_id: int = None,
        task_id: str = None,
        # generate fields (GenerateBody)
        idea: str = None,
        niches: list = None,
        moods: list = None,
        genres: list = None,
        provider: str = None,
        is_vocal: bool = None,
        title: str = None,
        expand_only: bool = None,
        # elevenlabs_plan fields (ElevenLabsPlanBody)
        input: str = None,
        music_length_ms: int = None,
        # elevenlabs_compose fields (ElevenLabsComposeBody)
        composition_plan: dict = None,
        output_format: str = None,
        respect_sections_durations: bool = None,
        # update fields
        fields: dict = None,
        # common
        confirm: bool = False,
        confirm_id: int = None,
        limit: int = None,
        offset: int = None,
    ) -> dict:
        client = client_factory()
        kw = {k: v for k, v in locals().items()
              if k not in ("client", "client_factory") and v is not None}
        kw.pop("kw", None)
        if _audit_wrapped is not None:
            return await _audit_wrapped(**kw)
        act = kw.pop("action", action)
        return await music(action=act, _client=client, **kw)
