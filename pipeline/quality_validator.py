"""
Quality Validator — verifies final video meets broadcast standards.
Uses ffprobe for metadata extraction.
"""
import json
import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

EXPECTED_W   = int(os.environ.get("VIDEO_WIDTH",  "1080"))
EXPECTED_H   = int(os.environ.get("VIDEO_HEIGHT", "1920"))
MIN_DURATION = 15     # seconds
MAX_DURATION = 80     # seconds
MIN_SIZE_MB  = 1      # MB
MAX_SIZE_MB  = 500    # MB
DURATION_TOLERANCE = 10  # ± seconds


def validate(video_path: str | Path) -> tuple[bool, dict]:
    """
    Validate a final video file.

    Checks:
    - File exists and is non-empty
    - Duration within acceptable range
    - Video codec is h264
    - Resolution is 1080×1920 (or close)
    - Audio track present
    - File size within bounds

    Returns: (valid: bool, report: dict)
    """
    path = Path(video_path)
    report = {"path": str(path), "checks": {}, "errors": []}

    # File existence
    if not path.exists():
        report["errors"].append(f"File not found: {path}")
        return False, report

    size_mb = path.stat().st_size / 1024 / 1024
    report["size_mb"] = round(size_mb, 2)

    if size_mb < MIN_SIZE_MB:
        report["errors"].append(f"File too small: {size_mb:.1f}MB (min {MIN_SIZE_MB}MB)")
        return False, report

    if size_mb > MAX_SIZE_MB:
        report["errors"].append(f"File too large: {size_mb:.1f}MB (max {MAX_SIZE_MB}MB)")
        report["checks"]["size"] = "warn"
    else:
        report["checks"]["size"] = "ok"

    # ffprobe metadata
    meta = _probe(path)
    if not meta:
        report["errors"].append("ffprobe failed — cannot read video metadata")
        return False, report

    report["duration_s"]  = meta.get("duration", 0)
    report["codec"]       = meta.get("codec", "")
    report["resolution"]  = meta.get("resolution", "")
    report["has_audio"]   = meta.get("has_audio", False)

    # Duration check
    dur = meta.get("duration", 0)
    if dur < MIN_DURATION:
        report["errors"].append(f"Too short: {dur:.1f}s (min {MIN_DURATION}s)")
        report["checks"]["duration"] = "fail"
    elif dur > MAX_DURATION:
        report["errors"].append(f"Too long: {dur:.1f}s (max {MAX_DURATION}s)")
        report["checks"]["duration"] = "warn"
    else:
        report["checks"]["duration"] = "ok"

    # Codec check
    codec = meta.get("codec", "")
    if "h264" not in codec and "avc" not in codec.lower():
        report["errors"].append(f"Unexpected codec: {codec} (expected h264)")
        report["checks"]["codec"] = "warn"
    else:
        report["checks"]["codec"] = "ok"

    # Resolution check (allow ±5px tolerance)
    w, h = meta.get("width", 0), meta.get("height", 0)
    if abs(w - EXPECTED_W) > 5 or abs(h - EXPECTED_H) > 5:
        report["errors"].append(f"Resolution mismatch: {w}×{h} (expected {EXPECTED_W}×{EXPECTED_H})")
        report["checks"]["resolution"] = "warn"
    else:
        report["checks"]["resolution"] = "ok"

    # Audio track
    if not meta.get("has_audio"):
        report["errors"].append("No audio track detected")
        report["checks"]["audio"] = "fail"
    else:
        report["checks"]["audio"] = "ok"

    # Hard failures only: missing audio or file too small
    hard_failures = [k for k, v in report["checks"].items() if v == "fail"]
    valid = len(hard_failures) == 0

    if valid:
        logger.info(f"[Validator] ✅ {path.name} passed ({dur:.1f}s, {size_mb:.1f}MB)")
    else:
        logger.warning(f"[Validator] ❌ {path.name} failed: {report['errors']}")

    return valid, report


def _probe(path: Path) -> dict | None:
    """Run ffprobe and parse JSON output."""
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", "-show_format", str(path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        data   = json.loads(result.stdout)

        streams = data.get("streams", [])
        video   = next((s for s in streams if s.get("codec_type") == "video"), {})
        audio   = next((s for s in streams if s.get("codec_type") == "audio"), None)

        return {
            "duration":  float(data.get("format", {}).get("duration", 0)),
            "codec":     video.get("codec_name", ""),
            "width":     int(video.get("width", 0)),
            "height":    int(video.get("height", 0)),
            "resolution": f"{video.get('width', 0)}×{video.get('height', 0)}",
            "has_audio": audio is not None,
        }
    except Exception as e:
        logger.error(f"[Validator] ffprobe error: {e}")
        return None
