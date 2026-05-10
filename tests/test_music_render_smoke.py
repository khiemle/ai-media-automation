"""Smoke test: render a 30-second music video with overlay + spectrum.

Requires working ffmpeg + Postgres test DB (with migration 022 applied).
Marked slow — not run in the default fast suite.
"""
import subprocess
from pathlib import Path
import pytest

pytestmark = pytest.mark.slow


@pytest.fixture
def make_sine(tmp_path):
    def _make(name, dur, freq=440):
        out = tmp_path / f"{name}.wav"
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi", "-i",
                f"sine=frequency={freq}:duration={dur}",
                "-ar", "44100", "-ac", "2", str(out),
            ],
            check=True, capture_output=True,
        )
        return out
    return _make


@pytest.fixture
def make_visual(tmp_path):
    def _make(name, dur=6):
        out = tmp_path / f"{name}.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", f"color=c=darkblue:size=1920x1080:duration={dur}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out),
            ],
            check=True, capture_output=True,
        )
        return out
    return _make


def _probe_duration(path):
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def _seed_music_template(db):
    """Insert a music VideoTemplate if not already present."""
    from console.backend.models.video_template import VideoTemplate
    existing = db.query(VideoTemplate).filter_by(slug="music").first()
    if existing:
        return existing
    t = VideoTemplate(
        slug="music",
        label="Music Video",
        output_format="landscape_long",
        ui_features=[],
    )
    db.add(t)
    db.commit()
    return t


def test_music_render_30s(db, make_sine, make_visual, tmp_path):
    from console.backend.models.video_asset import VideoAsset
    from console.backend.models.youtube_video import YoutubeVideo
    from database.models import MusicTrack
    from pipeline.youtube_ffmpeg import render_landscape

    # Seed template
    template = _seed_music_template(db)

    # Create 3 tracks: 5s + 10s + 15s = 30s total (gapless)
    tracks = []
    for i, dur in enumerate([5, 10, 15], start=1):
        wav = make_sine(f"t{i}", dur, freq=440 + i * 50)
        t = MusicTrack(
            title=f"Track {i}",
            file_path=str(wav),
            duration_s=float(dur),
            volume=1.0,
        )
        db.add(t)
        tracks.append(t)
    db.commit()

    # Create a visual video asset
    visual_mp4 = make_visual("vis", dur=6)
    visual = VideoAsset(
        file_path=str(visual_mp4),
        duration_s=6.0,
        source="test",
        asset_type="video_clip",
    )
    db.add(visual)
    db.commit()

    # Create the YoutubeVideo record
    video = YoutubeVideo(
        title="Smoke Music 30s",
        template_id=template.id,
        music_track_ids=[t.id for t in tracks],
        visual_asset_id=visual.id,
        track_transition="gapless",
        track_transition_seconds=2.0,
        playlist_overlay_style="sidebar",
        spectrum_enabled=True,
        spectrum_position="bottom",
        spectrum_height_pct=0.12,
        spectrum_color="#ffffff",
        spectrum_opacity=0.6,
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    out = tmp_path / "final.mp4"
    render_landscape(video, out, db)

    assert out.is_file(), "Output file was not created"
    duration = _probe_duration(out)
    assert duration == pytest.approx(30.0, abs=0.5), (
        f"Expected ~30s but got {duration:.2f}s"
    )


def test_music_render_no_overlay_no_spectrum(db, make_sine, make_visual, tmp_path):
    """Minimal music render: single track, no overlay, no spectrum."""
    from console.backend.models.video_asset import VideoAsset
    from console.backend.models.youtube_video import YoutubeVideo
    from database.models import MusicTrack
    from pipeline.youtube_ffmpeg import render_landscape

    template = _seed_music_template(db)

    wav = make_sine("solo", 8, freq=440)
    track = MusicTrack(title="Solo", file_path=str(wav), duration_s=8.0, volume=1.0)
    db.add(track)
    db.commit()

    visual_mp4 = make_visual("vis2", dur=4)
    visual = VideoAsset(
        file_path=str(visual_mp4),
        duration_s=4.0,
        source="test",
        asset_type="video_clip",
    )
    db.add(visual)
    db.commit()

    video = YoutubeVideo(
        title="Smoke Music Minimal",
        template_id=template.id,
        music_track_ids=[track.id],
        visual_asset_id=visual.id,
        track_transition="gapless",
        track_transition_seconds=2.0,
        playlist_overlay_style=None,
        spectrum_enabled=False,
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    out = tmp_path / "minimal.mp4"
    render_landscape(video, out, db)

    assert out.is_file()
    duration = _probe_duration(out)
    assert duration == pytest.approx(8.0, abs=0.5)
