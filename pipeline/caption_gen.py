"""
Caption Generator — faster-whisper base → SRT subtitles.
Merges all scene audio files, transcribes, and writes a timed .srt file.
"""
import logging
import os
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

WHISPER_MODEL    = "base"
WHISPER_LANGUAGE = "vi"    # force Vietnamese
MAX_WORDS_PER_LINE = 7
MIN_GAP_S          = 0.1

_whisper_model = None


def _get_model():
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel
            _whisper_model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
            logger.info(f"[Caption] faster-whisper {WHISPER_MODEL} loaded")
        except ImportError:
            logger.error("faster-whisper not installed. Run: pip install faster-whisper")
    return _whisper_model


def generate_captions(audio_path: str | Path) -> Path:
    """
    Transcribe audio file and write SRT subtitles alongside it.
    Returns path to .srt file.
    """
    audio_path = Path(audio_path)
    srt_path   = audio_path.with_suffix(".srt")
    srt_path.parent.mkdir(parents=True, exist_ok=True)

    model = _get_model()
    if model is None:
        return _empty_srt(srt_path)

    try:
        segments, _info = model.transcribe(
            str(audio_path),
            language=WHISPER_LANGUAGE,
            task="transcribe",
            word_timestamps=True,
        )
        srt_content = _segments_to_srt(list(segments))
        srt_path.write_text(srt_content, encoding="utf-8")
        logger.info(f"[Caption] SRT written: {srt_path}")
        return srt_path

    except Exception as e:
        logger.error(f"[Caption] Whisper transcription failed: {e}")
        return _empty_srt(srt_path)


def merge_audio_files(audio_paths: list[str | Path], output_path: str | Path) -> Path:
    """Concatenate multiple WAV files into a single file for Whisper transcription."""
    output_path = Path(output_path)
    if len(audio_paths) == 1:
        import shutil
        shutil.copy(str(audio_paths[0]), str(output_path))
        return output_path

    # Write ffmpeg concat list
    list_file = Path(tempfile.mktemp(suffix=".txt"))
    list_file.write_text("\n".join(f"file '{p}'" for p in audio_paths))
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file), "-c", "copy", str(output_path),
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=120)
    except Exception as e:
        logger.error(f"[Caption] Audio merge failed: {e}")
    finally:
        list_file.unlink(missing_ok=True)
    return output_path


def _segments_to_srt(segments: list) -> str:
    """Convert faster-whisper segments to SRT format, grouping by MAX_WORDS_PER_LINE."""
    lines = []
    idx   = 1

    for seg in segments:
        words = list(seg.words) if seg.words else []
        if not words:
            # Use segment-level timing if no word timestamps
            start = seg.start
            end   = seg.end
            text  = seg.text.strip()
            if text:
                lines.append(f"{idx}\n{_fmt_time(start)} --> {_fmt_time(end)}\n{text}\n")
                idx += 1
            continue

        # Group words into subtitle blocks
        block_words  = []
        block_start  = words[0].start
        block_end    = 0.0

        for w in words:
            block_words.append(w.word)
            block_end = w.end

            if len(block_words) >= MAX_WORDS_PER_LINE:
                text = "".join(block_words).strip()
                lines.append(f"{idx}\n{_fmt_time(block_start)} --> {_fmt_time(block_end)}\n{text}\n")
                idx += 1
                block_words = []
                block_start = block_end + MIN_GAP_S

        if block_words:
            text = "".join(block_words).strip()
            if text:
                lines.append(f"{idx}\n{_fmt_time(block_start)} --> {_fmt_time(block_end)}\n{text}\n")
                idx += 1

    return "\n".join(lines)


def _fmt_time(seconds: float) -> str:
    """Format seconds to SRT timecode HH:MM:SS,mmm."""
    hours   = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs    = int(seconds % 60)
    millis  = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _empty_srt(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    return path
