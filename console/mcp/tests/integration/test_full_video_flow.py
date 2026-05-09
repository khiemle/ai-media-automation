"""Integration test: agent's full 'make a YouTube video' flow.

Runs all 11 MCP tools in sequence against a respx-mocked FastAPI, asserting
every tool returns ok=true and that the final upload returns a task_id.
"""
import httpx
import pytest
import respx

from console.mcp.client.console_client import ConsoleClient
from console.mcp.tools import (
    channel_plan, music, sfx, visual_asset,
    youtube_video, youtube_thumbnail, upload, task_status,
)


@pytest.mark.asyncio
@respx.mock
async def test_full_make_a_video_flow():
    base = "http://test"

    # ── Mock every endpoint the flow touches ─────────────────────────────────
    respx.post(f"{base}/api/channel-plans/import").mock(return_value=httpx.Response(201, json={"id": 1}))
    respx.post(f"{base}/api/channel-plans/1/ai/seo").mock(return_value=httpx.Response(200, json={
        "title": "Forest Rain ASMR", "description": "...", "tags": ["asmr"]
    }))

    respx.get(f"{base}/api/music").mock(return_value=httpx.Response(200, json={"items": [], "total": 0}))
    respx.post(f"{base}/api/music/generate").mock(return_value=httpx.Response(202, json={"task_id": "music-1"}))
    respx.get(f"{base}/api/pipeline/jobs/music-1").mock(return_value=httpx.Response(200, json={
        "status": "SUCCESS", "result": {"track_id": 14}, "progress": None, "error": None
    }))

    respx.get(f"{base}/api/sfx").mock(return_value=httpx.Response(200, json=[]))

    respx.get(f"{base}/api/production/assets").mock(return_value=httpx.Response(200, json={"items": [], "total": 0}))
    respx.post(f"{base}/api/production/assets/upload").mock(return_value=httpx.Response(201, json={"id": 3}))

    respx.post(f"{base}/api/youtube-videos").mock(return_value=httpx.Response(201, json={"id": 9}))
    respx.put(f"{base}/api/youtube-videos/9").mock(return_value=httpx.Response(200, json={"id": 9}))

    respx.post(f"{base}/api/youtube-videos/9/thumbnail-generate").mock(
        return_value=httpx.Response(202, json={"task_id": "thumb-1"})
    )
    respx.get(f"{base}/api/pipeline/jobs/thumb-1").mock(return_value=httpx.Response(200, json={
        "status": "SUCCESS", "result": {"thumbnail_path": "/x.png"}, "progress": None, "error": None
    }))

    respx.post(f"{base}/api/youtube-videos/9/render/audio-preview").mock(return_value=httpx.Response(202, json={"task_id": "audio-1"}))
    respx.get(f"{base}/api/pipeline/jobs/audio-1").mock(return_value=httpx.Response(200, json={"status": "SUCCESS", "result": {}, "progress": None, "error": None}))
    respx.post(f"{base}/api/youtube-videos/9/render/audio-preview/approve").mock(return_value=httpx.Response(200, json={"approved": True}))

    respx.post(f"{base}/api/youtube-videos/9/render/video-preview").mock(return_value=httpx.Response(202, json={"task_id": "video-1"}))
    respx.get(f"{base}/api/pipeline/jobs/video-1").mock(return_value=httpx.Response(200, json={"status": "SUCCESS", "result": {}, "progress": None, "error": None}))
    respx.post(f"{base}/api/youtube-videos/9/render/video-preview/approve").mock(return_value=httpx.Response(200, json={"approved": True}))

    respx.post(f"{base}/api/youtube-videos/9/render/final").mock(return_value=httpx.Response(202, json={"task_id": "final-1"}))
    respx.get(f"{base}/api/pipeline/jobs/final-1").mock(return_value=httpx.Response(200, json={
        "status": "SUCCESS", "result": {"output_path": "/r/final.mp4", "duration_s": 28800}, "progress": None, "error": None
    }))

    respx.put(f"{base}/api/uploads/videos/9/targets").mock(return_value=httpx.Response(200, json={"video_id": 9, "channels": [1]}))
    respx.post(f"{base}/api/uploads/videos/9/upload").mock(return_value=httpx.Response(202, json={"task_id": "up-1"}))

    # ── Drive the flow as an agent would ─────────────────────────────────────
    client = ConsoleClient(base_url=base, token_provider=lambda: "tok")

    # 1. Import channel plan
    out = await channel_plan.channel_plan(action="import_json", payload={"channel": "x"}, confirm=True, _client=client)
    assert out["ok"] is True

    # 2. AI SEO suggestion
    out = await channel_plan.channel_plan(action="ai_seo", plan_id=1, confirm=True, _client=client)
    assert out["ok"] is True

    # 3. Music — list, generate, poll until ready
    await music.music(action="list_tracks", _client=client)
    out = await music.music(action="generate", prompt="forest dawn", duration_s=480, confirm=True, _client=client)
    assert out["ok"] is True and out["task_id"] == "music-1"
    out = await task_status.task_status(task_id="music-1", _client=client)
    assert out["status"] == "SUCCESS"

    # 4. SFX — list (empty)
    out = await sfx.sfx(action="list", _client=client)
    assert out["ok"] is True

    # 5. Visual asset — list + upload
    await visual_asset.visual_asset(action="list", _client=client)
    out = await visual_asset.visual_asset(action="upload", file_path="/x.mp4", title="forest", confirm=True, _client=client)
    assert out["ok"] is True

    # 6. Create youtube video with all fields
    fields = {
        "title": "Forest Rain ASMR | 8 Hours",
        "template_id": 1,
        "music_track_id": 14,
        "visual_asset_id": 3,
        "thumbnail_text": "DEEP SLEEP",
        "seo_title": "Forest Rain ASMR",
        "target_duration_h": 8.0,
        "output_quality": "1080p",
    }
    out = await youtube_video.youtube_video(action="create", fields=fields, confirm=True, _client=client)
    assert out["ok"] is True

    # 7. Thumbnail with text
    out = await youtube_thumbnail.youtube_thumbnail(
        action="generate_with_text", video_id=9, text="DEEP SLEEP", style="bold-yellow",
        confirm=True, _client=client,
    )
    assert out["ok"] is True and out["task_id"] == "thumb-1"
    out = await task_status.task_status(task_id="thumb-1", _client=client)
    assert out["status"] == "SUCCESS"

    # 8. Audio preview gate
    out = await youtube_video.youtube_video(action="render_audio_preview", video_id=9, confirm=True, _client=client)
    assert out["task_id"] == "audio-1"
    await task_status.task_status(task_id="audio-1", _client=client)
    await youtube_video.youtube_video(action="approve_audio_preview", video_id=9, confirm=True, _client=client)

    # 9. Video preview gate
    out = await youtube_video.youtube_video(action="render_video_preview", video_id=9, confirm=True, _client=client)
    await task_status.task_status(task_id="video-1", _client=client)
    await youtube_video.youtube_video(action="approve_video_preview", video_id=9, confirm=True, _client=client)

    # 10. Render final
    out = await youtube_video.youtube_video(action="render_final", video_id=9, confirm=True, _client=client)
    assert out["task_id"] == "final-1"
    out = await task_status.task_status(task_id="final-1", _client=client)
    assert out["result"]["output_path"] == "/r/final.mp4"

    # 11. Upload
    await upload.upload(action="set_targets", video_id=9, channels=[1], confirm=True, _client=client)
    out = await upload.upload(action="upload_one", video_id=9, confirm=True, confirm_id=9, _client=client)
    assert out["task_id"] == "up-1"
