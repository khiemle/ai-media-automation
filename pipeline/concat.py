"""ffmpeg concat-demuxer wrapper for stream-copy joining of video chunks."""
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def _write_concat_list(parts: list[Path]) -> Path:
    """Write parts to a tempfile in ffmpeg concat-demuxer format."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8",
    ) as listfile:
        for p in parts:
            # ffmpeg concat list format requires single quotes and ' -> '\''
            escaped = str(p.resolve()).replace("'", "'\\''")
            listfile.write(f"file '{escaped}'\n")
        return Path(listfile.name)


def concat_parts(part_paths: list[Path | str], output_path: Path | str) -> Path:
    """
    Concatenate identical-codec MP4 chunks into one file via ffmpeg's concat
    demuxer with -c copy. No re-encoding — joins are bit-perfect when chunks
    share codec, params, and GOP cadence.

    Caller MUST ensure all part files were produced with the same encoder
    settings (codec, fps, resolution, audio sample rate, profile/level).
    """
    if not part_paths:
        raise ValueError("part_paths is empty")

    parts = [Path(p) for p in part_paths]
    for p in parts:
        if not p.exists():
            raise FileNotFoundError(f"chunk not found: {p}")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    listfile_path = _write_concat_list(parts)

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(listfile_path),
        "-c", "copy",
        str(output_path),
    ]
    # Allow 300s per chunk — WSL2/Windows filesystem I/O for large (3+ GB) chunks
    # can be very slow. +faststart is intentionally omitted: YouTube re-encodes on
    # ingest so stream-start seeking is irrelevant, and the moov-rewrite pass would
    # double the I/O cost for multi-hundred-GB concatenated outputs.
    timeout = max(3600, len(parts) * 300)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg concat failed:\n{result.stderr[-2000:]}")
        logger.info(f"[Concat] {len(parts)} parts → {output_path} ({output_path.stat().st_size // 1024 // 1024}MB)")
        return output_path
    except Exception:
        # Remove any partially-written output so callers don't find a corrupt file.
        try:
            output_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    finally:
        try:
            listfile_path.unlink()
        except OSError:
            pass


def concat_video_and_mux_audio(
    video_parts: list[Path | str],
    audio_path: Path | str,
    output_path: Path | str,
) -> Path:
    """Concat video-only chunks then mux in a single full-duration audio track.

    Used by the chunked render pipeline to avoid AAC priming/concat artifacts
    at chunk seams: each chunk is rendered video-only, all chunks are joined
    with ``-c copy``, and the audio (encoded in one continuous pass) is then
    muxed in. Both streams are stream-copied — no re-encoding.

    The audio file MUST cover at least the duration of the concatenated
    video; ``-shortest`` clips any excess to the video's duration so we
    don't emit a tail of silent video / audio-only frames.

    Returns the path to the final muxed MP4.
    """
    if not video_parts:
        raise ValueError("video_parts is empty")
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH")

    parts = [Path(p) for p in video_parts]
    for p in parts:
        if not p.exists():
            raise FileNotFoundError(f"chunk not found: {p}")

    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"audio not found: {audio_path}")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    listfile_path = _write_concat_list(parts)

    # One ffmpeg invocation: input 0 is the concat demuxer reading the video
    # chunks, input 1 is the audio file. Stream-copy both, -shortest trims to
    # the shorter stream (defends against audio slightly longer than video).
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(listfile_path),
        "-i", str(audio_path),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c", "copy",
        "-shortest",
        str(output_path),
    ]
    timeout = max(3600, len(parts) * 300)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg concat+mux failed:\n{result.stderr[-2000:]}"
            )
        logger.info(
            "[ConcatMux] %s video parts + 1 audio → %s (%sMB)",
            len(parts), output_path, output_path.stat().st_size // 1024 // 1024,
        )
        return output_path
    except Exception:
        try:
            output_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    finally:
        try:
            listfile_path.unlink()
        except OSError:
            pass
