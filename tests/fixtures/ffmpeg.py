"""Canned ffmpeg/ffprobe stubs."""
from __future__ import annotations


def ffprobe_video(duration_s: float = 30.0, width: int = 1080, height: int = 1920) -> dict:
    """Shape returned by `ffprobe -v quiet -print_format json -show_streams -show_format`."""
    return {
        "streams": [
            {
                "index": 0,
                "codec_name": "h264",
                "codec_type": "video",
                "width": width,
                "height": height,
                "r_frame_rate": "30/1",
                "duration": str(duration_s),
            },
            {
                "index": 1,
                "codec_name": "aac",
                "codec_type": "audio",
                "sample_rate": "44100",
                "channels": 2,
                "duration": str(duration_s),
            },
        ],
        "format": {
            "filename": "test.mp4",
            "duration": str(duration_s),
            "size": str(int(duration_s * 100_000)),
            "bit_rate": "800000",
        },
    }


def silent_wav_bytes(duration_s: float = 1.0, sample_rate: int = 44100) -> bytes:
    """Minimal valid WAV header + silence. Use when a test only needs *some* WAV bytes."""
    import struct

    n_samples = int(duration_s * sample_rate)
    data_bytes = n_samples * 2  # 16-bit mono
    header = b"RIFF" + struct.pack("<I", 36 + data_bytes) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
    header += b"data" + struct.pack("<I", data_bytes)
    return header + b"\x00" * data_bytes
