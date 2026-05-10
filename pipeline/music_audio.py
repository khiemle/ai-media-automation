"""Music playlist WAV builder for the music template.

Unlike pipeline.youtube_ffmpeg._build_music_playlist_wav (which loops to
fill a target duration), this module produces a WAV equal to the natural
sum of track durations (adjusted for transitions).
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def build_music_playlist_wav_with_transitions(
    tracks: list,
    total_duration_s: float,
    transition: str,
    transition_s: float,
    output_dir: Path,
    start_s: float = 0.0,
) -> str:
    """Render the playlist to a single WAV with the chosen transition mode.

    Supported *transition* values:

    * ``"gapless"`` — tracks are concatenated back-to-back with no gap or
      overlap.  *transition_s* is ignored.
    * ``"crossfade"`` — consecutive tracks are blended with a pairwise
      ``acrossfade`` of *transition_s* seconds using a triangular curve.
      Total rendered duration before trimming is
      ``sum(durations) - (n-1)*transition_s``.
    * ``"gap"`` — a silence segment of *transition_s* seconds is inserted
      between consecutive tracks.  Total rendered duration before trimming
      is ``sum(durations) + (n-1)*transition_s``.

    The output WAV is trimmed to *[start_s, start_s + total_duration_s]*
    and written to *output_dir/music_playlist.wav*.

    Returns the absolute path to the output WAV as a string.

    Raises
    ------
    RuntimeError
        When no playable tracks are found or when ffmpeg exits with a
        non-zero return code.
    ValueError
        When an unknown *transition* value is supplied.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "music_playlist.wav"

    # Filter to tracks that exist on disk, preserving order
    paths: list[tuple[str, float]] = []
    for t in tracks:
        if t.file_path and Path(t.file_path).is_file():
            paths.append((t.file_path, float(getattr(t, "volume", None) or 1.0)))
    if not paths:
        raise RuntimeError("No playable music tracks found")

    # Build ffmpeg command -----------------------------------------------
    cmd = ["ffmpeg", "-y"]
    for path, _vol in paths:
        cmd += ["-i", path]

    # filter_complex parts, collected as strings joined with ";"
    parts: list[str] = []

    # Step 1: apply per-track volume, label each stream [v0], [v1], …
    for i, (_p, vol) in enumerate(paths):
        parts.append(f"[{i}:a]volume={vol}[v{i}]")

    # Step 2: join streams according to transition mode
    if len(paths) == 1:
        # Single track — just relabel; atrim applied below
        parts.append("[v0]anull[joined]")

    elif transition == "gapless":
        chain = "".join(f"[v{i}]" for i in range(len(paths)))
        parts.append(f"{chain}concat=n={len(paths)}:v=0:a=1[joined]")

    elif transition == "crossfade":
        # Pairwise acrossfade: [v0][v1] → [x1] → [x2] → … → [joined]
        prev = "v0"
        for i in range(1, len(paths)):
            label = f"x{i}" if i < len(paths) - 1 else "joined"
            parts.append(
                f"[{prev}][v{i}]acrossfade=d={transition_s}:c1=tri:c2=tri[{label}]"
            )
            prev = label

    elif transition == "gap":
        # Generate silence via anullsrc (no extra input file needed).
        # Insert one silence segment between every pair of consecutive tracks.
        # anullsrc produces an infinite stream so we trim it to transition_s.
        sil_label_idx = 0
        chain_parts: list[str] = []
        for i in range(len(paths)):
            chain_parts.append(f"[v{i}]")
            if i < len(paths) - 1:
                sil_label = f"s{sil_label_idx}"
                parts.append(
                    f"anullsrc=r=44100:channel_layout=stereo,"
                    f"atrim=duration={transition_s},"
                    f"asetpts=PTS-STARTPTS[{sil_label}]"
                )
                chain_parts.append(f"[{sil_label}]")
                sil_label_idx += 1

        n_segments = len(paths) + (len(paths) - 1)
        parts.append(
            "".join(chain_parts) + f"concat=n={n_segments}:v=0:a=1[joined]"
        )

    else:
        raise ValueError(f"Unknown transition mode: {transition!r}")

    # Step 3: trim to [start_s, start_s + total_duration_s]
    end_s = start_s + total_duration_s
    parts.append(
        f"[joined]atrim=start={start_s}:end={end_s},"
        f"asetpts=PTS-STARTPTS[out]"
    )

    cmd += [
        "-filter_complex", ";".join(parts),
        "-map", "[out]",
        "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le",
        str(out_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (exit {result.returncode}): {result.stderr[-600:]}"
        )
    return str(out_path)
