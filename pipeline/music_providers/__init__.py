"""Music provider utilities."""
import json
import subprocess


def probe_audio_duration(path: str) -> float:
    """Return duration in seconds using ffprobe. Returns 0.0 on failure."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams", str(path),
            ],
            capture_output=True, text=True, timeout=15,
        )
        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        if streams:
            return float(streams[0].get("duration", 0))
    except Exception:
        pass
    return 0.0
