"""ffmpeg concat-demuxer wrapper for stream-copy joining of video chunks."""
import logging
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


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

    # Write a tempfile listing each input — concat demuxer reads this format
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8",
    ) as listfile:
        for p in parts:
            # ffmpeg concat list format requires single quotes and ' -> '\''
            escaped = str(p.resolve()).replace("'", "'\\''")
            listfile.write(f"file '{escaped}'\n")
        listfile_path = Path(listfile.name)

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(listfile_path),
        "-c", "copy",
        "-movflags", "+faststart",
        str(output_path),
    ]
    # Allow 60s per chunk minimum; WSL2/Windows filesystem I/O can be slow for large files.
    timeout = max(1800, len(parts) * 60)
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
