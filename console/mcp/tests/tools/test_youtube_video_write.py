import pytest
from unittest.mock import AsyncMock

from console.mcp.tools.youtube_video import youtube_video


@pytest.mark.asyncio
async def test_create_with_full_config():
    c = AsyncMock()
    c.post.return_value = {"id": 9}
    fields = {
        "title": "Forest Rain 8h",
        "template_id": 2,
        "theme": "forest",
        "music_track_id": 14,
        "visual_asset_id": 3,
        "thumbnail_asset_id": 12,
        "thumbnail_text": "8 HOURS · DEEP SLEEP",
        "seo_title": "Forest Rain ASMR | 8 Hours",
        "seo_description": "...",
        "seo_tags": ["asmr", "rain", "sleep"],
        "target_duration_h": 8.0,
        "output_quality": "1080p",
        "sfx_density_seconds": 90,
        "visual_clip_durations_s": [12.0, 8.0, 16.0],
        "sfx_overrides": {"wind": [{"at_s": 30, "vol": 0.4}]},
    }
    out = await youtube_video(action="create", fields=fields, confirm=True, _client=c)
    c.post.assert_awaited_once_with("/api/youtube-videos", json=fields)
    assert out["ok"] is True


@pytest.mark.asyncio
async def test_update_partial_fields():
    c = AsyncMock()
    c.put.return_value = {"id": 9}
    await youtube_video(action="update", video_id=9, fields={"thumbnail_text": "NEW"},
                        confirm=True, _client=c)
    c.put.assert_awaited_once_with("/api/youtube-videos/9", json={"thumbnail_text": "NEW"})


@pytest.mark.asyncio
async def test_import_json_calls_create_with_payload():
    c = AsyncMock()
    c.post.return_value = {"id": 9}
    payload = {"title": "x", "theme": "ambient"}
    out = await youtube_video(action="import_json", payload=payload, confirm=True, _client=c)
    c.post.assert_awaited_once_with("/api/youtube-videos", json=payload)


@pytest.mark.asyncio
async def test_delete_destructive():
    c = AsyncMock()
    out = await youtube_video(action="delete", video_id=9, confirm=True, confirm_id=9, _client=c)
    c.delete.assert_awaited_once_with("/api/youtube-videos/9")


@pytest.mark.asyncio
async def test_render_gates_audio_preview_then_approve():
    c = AsyncMock()
    c.post.return_value = {"task_id": "audio-1"}
    out = await youtube_video(action="render_audio_preview", video_id=9, confirm=True, _client=c)
    c.post.assert_awaited_once_with("/api/youtube-videos/9/render/audio-preview")
    assert out["task_kind"] == "youtube_render_audio_preview"

    c.post.reset_mock()
    c.post.return_value = {"approved": True}
    await youtube_video(action="approve_audio_preview", video_id=9, confirm=True, _client=c)
    c.post.assert_awaited_once_with("/api/youtube-videos/9/render/audio-preview/approve")


@pytest.mark.asyncio
async def test_reject_video_preview_destructive():
    c = AsyncMock()
    out = await youtube_video(action="reject_video_preview", video_id=9,
                              confirm=True, confirm_id=9, _client=c)
    c.post.assert_awaited_once_with("/api/youtube-videos/9/render/video-preview/reject")


@pytest.mark.asyncio
async def test_render_final_and_cancel_and_resume():
    c = AsyncMock()
    c.post.return_value = {"task_id": "final-1"}
    out = await youtube_video(action="render_final", video_id=9, confirm=True, _client=c)
    c.post.assert_awaited_with("/api/youtube-videos/9/render/final")
    assert out["task_kind"] == "youtube_render_final"

    c.post.reset_mock()
    c.post.return_value = {"cancelled": True}
    await youtube_video(action="cancel_render", video_id=9, confirm=True, confirm_id=9, _client=c)
    c.post.assert_awaited_with("/api/youtube-videos/9/render/cancel")

    c.post.reset_mock()
    c.post.return_value = {"resumed": True}
    await youtube_video(action="resume_render", video_id=9, confirm=True, _client=c)
    c.post.assert_awaited_with("/api/youtube-videos/9/render/resume")
