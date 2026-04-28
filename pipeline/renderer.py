"""
Final Renderer — ffmpeg h264_nvenc GPU encode with subtitle burn-in.
CPU fallback (libx264) when NVENC is unavailable.
MoviePy fallback for subtitle burn-in when ffmpeg lacks libass.
Output: video_final.mp4 at 1080×1920, 30fps, AAC 192kbps.
"""
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

from dotenv import load_dotenv

_root = Path(__file__).parent.parent
load_dotenv(_root / ".env", override=False)

logger = logging.getLogger(__name__)

OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "./assets/output")
TARGET_W    = int(os.environ.get("VIDEO_WIDTH",  "1080"))
TARGET_H    = int(os.environ.get("VIDEO_HEIGHT", "1920"))
TARGET_FPS  = int(os.environ.get("VIDEO_FPS",    "30"))


def _parse_srt(path: Path) -> list[dict]:
    """Parse SRT file → list of {start: float, end: float, text: str}."""
    content = path.read_text(encoding="utf-8", errors="replace")
    entries = []
    for block in re.split(r"\n\s*\n", content.strip()):
        lines = block.strip().splitlines()
        if len(lines) < 2:
            continue
        for i, line in enumerate(lines):
            m = re.match(
                r"(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})",
                line,
            )
            if m:
                def _t(ts: str) -> float:
                    h, mn, s = ts.replace(",", ".").split(":")
                    return int(h) * 3600 + int(mn) * 60 + float(s)
                text = " ".join(lines[i + 1:]).strip()
                text = re.sub(r"<[^>]+>", "", text).strip()
                if text:
                    entries.append({"start": _t(m.group(1)), "end": _t(m.group(2)), "text": text})
                break
    return entries


def _burn_subtitles_moviepy(raw_path: Path, subtitle_file: Path, final_path: Path) -> bool:
    """
    Burn SRT subtitles into video via MoviePy TextClip.
    Used as fallback when ffmpeg lacks the libass subtitles filter.
    Returns True on success, False on any failure.
    """
    try:
        from moviepy import VideoFileClip, TextClip, CompositeVideoClip
    except ImportError:
        return False

    try:
        entries = _parse_srt(subtitle_file)
        if not entries:
            logger.warning("[Renderer] SRT parsed but no entries found")
            return False

        # Use Roboto for full Unicode / Vietnamese support
        from pipeline.subtitle_builder import FONT_ROBOTO_BOLD, _ensure_roboto_fonts
        _ensure_roboto_fonts()
        font = FONT_ROBOTO_BOLD
        max_text_w = int(TARGET_W * 0.90)  # 90% width so text never overflows frame

        video = VideoFileClip(str(raw_path))
        clips = [video]

        for entry in entries:
            end = min(entry["end"], video.duration)
            if end <= entry["start"]:
                continue
            try:
                txt = TextClip(
                    text=entry["text"],
                    font=font,
                    font_size=55,
                    color=(255, 255, 255),
                    stroke_color=(0, 0, 0),
                    stroke_width=2,
                    size=(max_text_w, None),
                    method="caption",
                    text_align="center",
                ).with_start(entry["start"]).with_end(end).with_position(
                    ("center", 0.85), relative=True
                )
                clips.append(txt)
            except Exception as exc:
                logger.debug(f"[Renderer] TextClip skipped for entry: {exc}")

        composed = CompositeVideoClip(clips)
        audio = video.audio
        if audio:
            composed = composed.with_audio(audio)
        composed.write_videofile(
            str(final_path),
            fps=TARGET_FPS,
            codec="libx264",
            audio_codec="aac",
            bitrate="4M",
            logger=None,
        )
        video.close()
        logger.info(f"[Renderer] Subtitles burned via MoviePy fallback → {final_path}")
        return True
    except Exception as exc:
        logger.error(f"[Renderer] MoviePy subtitle burn failed: {exc}")
        return False


def render_final(
    raw_video_path: str | Path | None = None,
    srt_path:       str | Path | None = None,
    music_path:     str | Path | None = None,
    raw_path:       str | Path | None = None,
) -> Path:
    """
    Encode raw_video.mp4 → video_final.mp4 with:
    - h264_nvenc (GPU) or libx264 (CPU fallback)
    - Subtitle burn-in from SRT
    - Final audio mix (if music not already embedded)
    - 1080×1920, 30fps, CRF 23, AAC 192k

    Returns path to video_final.mp4.
    """
    raw_video_path = raw_video_path or raw_path
    if raw_video_path is None:
        raise TypeError("render_final() missing required argument: 'raw_video_path'")

    raw_path_obj = Path(raw_video_path)
    final_path = raw_path_obj.parent / "video_final.mp4"

    nvenc_available = _check_nvenc()
    codec   = "h264_nvenc" if nvenc_available else "libx264"
    preset  = "fast" if nvenc_available else "medium"
    logger.info(f"[Renderer] Using codec: {codec}")

    vf_filters = [
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease",
        f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2",
        f"fps={TARGET_FPS}",
    ]

    # Burn-in subtitles: SRT takes priority; fall back to subtitles.ass in same directory
    ass_candidate = raw_path_obj.parent / "subtitles.ass"
    subtitle_file = None
    if srt_path and Path(srt_path).exists() and Path(srt_path).stat().st_size > 0:
        subtitle_file = Path(srt_path)
    elif ass_candidate.exists() and ass_candidate.stat().st_size > 0:
        subtitle_file = ass_candidate

    if subtitle_file and _check_subtitles_filter():
        escaped = subtitle_file.resolve().as_posix().replace(":", "\\:")
        vf_filters.append(f"subtitles=filename='{escaped}'")
    elif subtitle_file:
        logger.warning("[Renderer] ffmpeg subtitles filter unavailable; trying MoviePy fallback")
        if _burn_subtitles_moviepy(raw_path_obj, subtitle_file, final_path):
            return final_path
        logger.warning("[Renderer] MoviePy subtitle burn failed; producing video without subtitles")

    vf = ",".join(vf_filters)

    cmd = [
        "ffmpeg", "-y",
        "-err_detect", "ignore_err",
        "-i", str(raw_path_obj),
    ]

    # Audio filter: mix external music if provided
    if music_path and Path(music_path).exists():
        cmd += ["-i", str(music_path)]
        cmd += [
            "-filter_complex",
            "[0:a][1:a]amerge=inputs=2,pan=stereo|c0<c0+c2|c1<c1+c3[a]",
            "-map", "0:v", "-map", "[a]",
        ]
    else:
        cmd += ["-map", "0:v", "-map", "0:a"]

    cmd += [
        "-vf", vf,
        "-c:v", codec,
        "-preset", preset,
        "-crf", "23",
        "-b:v", "4M",
        "-maxrate", "6M",
        "-bufsize", "12M",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "44100",
        "-r", str(TARGET_FPS),
        "-s", f"{TARGET_W}x{TARGET_H}",
        "-movflags", "+faststart",
        str(final_path),
    ]

    if nvenc_available:
        # Insert NVENC-specific flags
        idx = cmd.index(codec)
        cmd[idx + 1:idx + 1] = ["-rc", "vbr", "-qmin", "18", "-qmax", "28"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            error_msg = result.stderr[-2000:]
            # If NVENC failed mid-run, retry with CPU
            if nvenc_available and ("nvenc" in error_msg.lower() or "cuda" in error_msg.lower()):
                logger.warning("[Renderer] NVENC failed, retrying with libx264")
                return render_final(raw_video_path, srt_path, music_path)
            # If audio decode failed, retry with corrupt-tolerant flags
            if "decode error rate" in error_msg.lower() or "aresample" in error_msg.lower():
                if "-fflags" not in cmd:
                    logger.warning("[Renderer] Audio decode errors detected, retrying with fflags +discardcorrupt")
                    cmd_retry = ["ffmpeg", "-y", "-fflags", "+discardcorrupt", "-err_detect", "ignore_err",
                                 "-i", str(raw_path_obj)] + cmd[cmd.index("-map"):]
                    result2 = subprocess.run(cmd_retry, capture_output=True, text=True, timeout=600)
                    if result2.returncode == 0:
                        logger.info(f"[Renderer] video_final.mp4 → {final_path} (retry OK)")
                        return final_path
            raise RuntimeError(f"ffmpeg failed:\n{error_msg}")

        logger.info(f"[Renderer] video_final.mp4 → {final_path} ({final_path.stat().st_size // 1024 // 1024}MB)")
        return final_path

    except subprocess.TimeoutExpired:
        raise RuntimeError(f"ffmpeg timed out after 600s rendering {raw_path_obj}")


def _check_nvenc() -> bool:
    """Check if h264_nvenc is available."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-encoders"],
            capture_output=True, text=True, timeout=10,
        )
        return "h264_nvenc" in result.stdout
    except Exception:
        return False


def _check_subtitles_filter() -> bool:
    """Check if ffmpeg was built with the subtitles filter (libass)."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-filters"],
            capture_output=True, text=True, timeout=10,
        )
        return " subtitles " in result.stdout or result.stdout.lstrip().startswith("subtitles")
    except Exception:
        return False
