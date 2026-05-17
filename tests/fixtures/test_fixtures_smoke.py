"""Smoke tests proving each fixture module imports and produces sensible output."""
from tests.fixtures import llm, youtube, ffmpeg, elevenlabs


def test_gemini_text_response_has_text():
    r = llm.gemini_text_response("hello")
    assert r["candidates"][0]["content"]["parts"][0]["text"] == "hello"


def test_ollama_chat_response_has_content():
    r = llm.ollama_chat_response("hi", model="m")
    assert r["message"]["content"] == "hi"
    assert r["model"] == "m"


def test_youtube_video_resource_has_id():
    r = youtube.video_resource("xyz", "T")
    assert r["id"] == "xyz"
    assert r["snippet"]["title"] == "T"


def test_youtube_upload_progress_pct():
    r = youtube.upload_progress(50)
    assert r["resumable_progress"] == 50
    assert r["progress"] == 0.5


def test_ffprobe_video_shape():
    r = ffmpeg.ffprobe_video(duration_s=10.0, width=1280, height=720)
    assert r["streams"][0]["width"] == 1280
    assert r["streams"][0]["height"] == 720
    assert float(r["format"]["duration"]) == 10.0


def test_silent_wav_bytes_starts_with_riff():
    b = ffmpeg.silent_wav_bytes(duration_s=0.1)
    assert b[:4] == b"RIFF"
    assert b[8:12] == b"WAVE"


def test_elevenlabs_music_response_has_url():
    r = elevenlabs.music_generation_response("m1")
    assert r["id"] == "m1"
    assert r["audio_url"].endswith("m1.mp3")


def test_elevenlabs_sfx_response_has_url():
    r = elevenlabs.sfx_generation_response("s1")
    assert r["id"] == "s1"
    assert r["audio_url"].endswith("s1.mp3")
