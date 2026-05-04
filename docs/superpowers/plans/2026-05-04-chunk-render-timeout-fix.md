# Chunk Render Timeout + Smooth Concat Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the ffmpeg output-side seek bug that causes chunk render timeouts and audio/visual glitches at every chunk boundary in concatenated YouTube videos.

**Architecture:** All changes are in `pipeline/youtube_ffmpeg.py`. A new `_probe_duration()` helper uses ffprobe to compute the modulo seek position for looped video/audio inputs. The music pre-render gains a `start_s` parameter so each chunk renders the right time window of the playlist. SFX override layer inputs gain the same modulo seek.

**Tech Stack:** Python 3.11, ffmpeg/ffprobe (subprocess), pytest + unittest.mock

---

## Files

| File | Change |
|---|---|
| `pipeline/youtube_ffmpeg.py` | Add `_probe_duration()`, fix visual seek, fix music atrim, fix SFX layer seek, fix timeout floor |
| `tests/test_youtube_ffmpeg.py` | Add tests for all four sub-fixes |

---

## Context: how tests work in this file

Tests patch `subprocess.run` to avoid running real ffmpeg, then inspect the command list passed to it. The helper `_make_video()` at the top of the test file produces a mock video object. Add new test helpers as needed but keep them at module level (not inside test functions). All tests run from the project root with:

```bash
python -m pytest tests/test_youtube_ffmpeg.py -v
```

---

## Task 1: `_probe_duration` helper

**Files:**
- Modify: `pipeline/youtube_ffmpeg.py` — insert after `_run_ffmpeg` (currently ends at line 196)
- Modify: `tests/test_youtube_ffmpeg.py` — add tests after the `_escape_drawtext` section

---

- [ ] **Step 1.1: Write the failing tests**

Add to `tests/test_youtube_ffmpeg.py` after the `test_escape_drawtext_*` tests:

```python
# ── _probe_duration ────────────────────────────────────────────────────────────

def test_probe_duration_returns_float_from_ffprobe_stdout():
    from pipeline.youtube_ffmpeg import _probe_duration
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="120.5\n", stderr="")
        result = _probe_duration("/some/file.mp4")
    assert result == pytest.approx(120.5)


def test_probe_duration_returns_zero_on_bad_output():
    from pipeline.youtube_ffmpeg import _probe_duration
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="not_a_float\n", stderr="")
        result = _probe_duration("/some/file.mp4")
    assert result == 0.0


def test_probe_duration_returns_zero_on_timeout():
    import subprocess
    from pipeline.youtube_ffmpeg import _probe_duration
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ffprobe", 15)):
        result = _probe_duration("/some/file.mp4")
    assert result == 0.0
```

- [ ] **Step 1.2: Run to verify they fail**

```bash
python -m pytest tests/test_youtube_ffmpeg.py::test_probe_duration_returns_float_from_ffprobe_stdout tests/test_youtube_ffmpeg.py::test_probe_duration_returns_zero_on_bad_output tests/test_youtube_ffmpeg.py::test_probe_duration_returns_zero_on_timeout -v
```

Expected: all three FAIL with `ImportError` or `AttributeError` — `_probe_duration` does not exist yet.

- [ ] **Step 1.3: Implement `_probe_duration`**

In `pipeline/youtube_ffmpeg.py`, insert this function immediately after `_run_ffmpeg` (after line 196):

```python
def _probe_duration(path: str) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet",
             "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1",
             path],
            capture_output=True, text=True, timeout=15,
        )
        return float(result.stdout.strip())
    except (ValueError, AttributeError, subprocess.TimeoutExpired):
        return 0.0
```

- [ ] **Step 1.4: Run to verify they pass**

```bash
python -m pytest tests/test_youtube_ffmpeg.py::test_probe_duration_returns_float_from_ffprobe_stdout tests/test_youtube_ffmpeg.py::test_probe_duration_returns_zero_on_bad_output tests/test_youtube_ffmpeg.py::test_probe_duration_returns_zero_on_timeout -v
```

Expected: all three PASS.

- [ ] **Step 1.5: Verify no regressions**

```bash
python -m pytest tests/test_youtube_ffmpeg.py -v
```

Expected: all 23 tests PASS.

- [ ] **Step 1.6: Commit**

```bash
git add pipeline/youtube_ffmpeg.py tests/test_youtube_ffmpeg.py
git commit -m "feat(yt-render): add _probe_duration ffprobe helper"
```

---

## Task 2: Visual input-side seek

Replace the output-side `-ss` with an input-side modulo seek for the single-asset looped video path.

**Files:**
- Modify: `pipeline/youtube_ffmpeg.py`
- Modify: `tests/test_youtube_ffmpeg.py`

---

- [ ] **Step 2.1: Write the failing tests**

Add to `tests/test_youtube_ffmpeg.py` after the existing `render_landscape` tests:

```python
def test_render_landscape_chunk_places_ss_before_visual_input(tmp_path):
    """start_s=300, file_dur=120 → effective_seek=60 → -ss 60 is BEFORE -i visual_path"""
    output = tmp_path / "chunk.mp4"
    visual = tmp_path / "visual.mp4"
    visual.write_bytes(b"fake")

    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("pipeline.youtube_ffmpeg.resolve_visual_playlist", return_value=[]), \
         patch("pipeline.youtube_ffmpeg.resolve_visual", return_value=str(visual)), \
         patch("pipeline.youtube_ffmpeg._build_music_playlist_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_sfx_pool_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg.resolve_sfx_layers", return_value=[]), \
         patch("pipeline.youtube_ffmpeg._probe_duration", return_value=120.0), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_landscape
        render_landscape(_make_video(), output, MagicMock(), start_s=300.0, end_s=600.0)

    cmd = mock_run.call_args[0][0]
    assert "-ss" in cmd
    ss_idx = cmd.index("-ss")
    i_idx = cmd.index(str(visual))
    assert ss_idx < i_idx, "-ss must appear before -i visual_path"
    assert cmd[ss_idx + 1] == "60", f"expected effective_seek=60, got {cmd[ss_idx + 1]}"


def test_render_landscape_chunk_no_ss_when_effective_seek_is_zero(tmp_path):
    """start_s=360, file_dur=120 → effective_seek=0 → no -ss in cmd"""
    output = tmp_path / "chunk.mp4"
    visual = tmp_path / "visual.mp4"
    visual.write_bytes(b"fake")

    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("pipeline.youtube_ffmpeg.resolve_visual_playlist", return_value=[]), \
         patch("pipeline.youtube_ffmpeg.resolve_visual", return_value=str(visual)), \
         patch("pipeline.youtube_ffmpeg._build_music_playlist_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_sfx_pool_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg.resolve_sfx_layers", return_value=[]), \
         patch("pipeline.youtube_ffmpeg._probe_duration", return_value=120.0), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_landscape
        render_landscape(_make_video(), output, MagicMock(), start_s=360.0, end_s=660.0)

    cmd = mock_run.call_args[0][0]
    assert "-ss" not in cmd, "effective_seek=0 should produce no -ss flag"


def test_render_landscape_no_output_side_ss_after_map(tmp_path):
    """Even with start_s > 0, -ss must never appear after -map in the command."""
    output = tmp_path / "chunk.mp4"
    visual = tmp_path / "visual.mp4"
    visual.write_bytes(b"fake")

    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("pipeline.youtube_ffmpeg.resolve_visual_playlist", return_value=[]), \
         patch("pipeline.youtube_ffmpeg.resolve_visual", return_value=str(visual)), \
         patch("pipeline.youtube_ffmpeg._build_music_playlist_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_sfx_pool_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg.resolve_sfx_layers", return_value=[]), \
         patch("pipeline.youtube_ffmpeg._probe_duration", return_value=120.0), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_landscape
        render_landscape(_make_video(), output, MagicMock(), start_s=300.0, end_s=600.0)

    cmd = mock_run.call_args[0][0]
    map_idx = cmd.index("-map")
    assert "-ss" not in cmd[map_idx:], "-ss must not appear after -map (no output-side seek)"
```

- [ ] **Step 2.2: Run to verify they fail**

```bash
python -m pytest tests/test_youtube_ffmpeg.py::test_render_landscape_chunk_places_ss_before_visual_input tests/test_youtube_ffmpeg.py::test_render_landscape_chunk_no_ss_when_effective_seek_is_zero tests/test_youtube_ffmpeg.py::test_render_landscape_no_output_side_ss_after_map -v
```

Expected: all three FAIL — the output-side `-ss` appears after `-map`, and no input-side `-ss` exists yet.

- [ ] **Step 2.3: Implement input-side seek**

In `pipeline/youtube_ffmpeg.py`, find the visual input block inside `render_landscape`. It currently reads:

```python
    # Visual input
    if visual_path and Path(visual_path).is_file():
        if is_image:
            cmd += ["-loop", "1", "-i", visual_path]
        elif playlist_segment_path is not None:
            # Pre-rendered playlist segment: exact duration, no looping needed
            cmd += ["-i", visual_path]
        else:
            cmd += ["-stream_loop", "-1", "-i", visual_path]
    else:
        cmd += ["-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r=30"]
```

Replace the `else:` branch (the `cmd += ["-stream_loop", "-1", "-i", visual_path]` line) with:

```python
        else:
            if start_s > 0.5:
                vid_dur = _probe_duration(visual_path)
                effective_seek = (start_s % vid_dur) if vid_dur > 1.0 else 0.0
                if effective_seek > 0.5:
                    cmd += ["-stream_loop", "-1", "-ss", str(int(effective_seek)), "-i", visual_path]
                else:
                    cmd += ["-stream_loop", "-1", "-i", visual_path]
            else:
                cmd += ["-stream_loop", "-1", "-i", visual_path]
```

Then find and **delete** the output-side seek block (a few lines before `cmd += ["-t", str(target_dur)]`). It currently reads:

```python
    # Window: -ss only for single-asset looping path; playlist segments are already pre-cut
    # to target_dur, so applying -ss would seek past their end and produce empty output.
    # NOTE: this means each chunk's playlist starts from item 0 (not continuous across
    # chunks) — acceptable for ambient/loop content. To restore continuity across chunks
    # would require passing start_s into _build_visual_segment and using input-side seek
    # on the looped concat.
    if start_s > 0 and playlist_segment_path is None:
        cmd += ["-ss", str(int(start_s))]
    cmd += ["-t", str(target_dur)]
```

Replace those lines with just:

```python
    cmd += ["-t", str(target_dur)]
```

- [ ] **Step 2.4: Run to verify new tests pass**

```bash
python -m pytest tests/test_youtube_ffmpeg.py::test_render_landscape_chunk_places_ss_before_visual_input tests/test_youtube_ffmpeg.py::test_render_landscape_chunk_no_ss_when_effective_seek_is_zero tests/test_youtube_ffmpeg.py::test_render_landscape_no_output_side_ss_after_map -v
```

Expected: all three PASS.

- [ ] **Step 2.5: Verify no regressions**

```bash
python -m pytest tests/test_youtube_ffmpeg.py -v
```

Expected: all 26 tests PASS.

- [ ] **Step 2.6: Commit**

```bash
git add pipeline/youtube_ffmpeg.py tests/test_youtube_ffmpeg.py
git commit -m "fix(yt-render): input-side seek with modulo replaces output-side -ss"
```

---

## Task 3: Music WAV continuity

Add `start_s` to `_build_music_playlist_wav` so each chunk renders the correct window of the playlist instead of always starting from t=0.

**Files:**
- Modify: `pipeline/youtube_ffmpeg.py`
- Modify: `tests/test_youtube_ffmpeg.py`

---

- [ ] **Step 3.1: Write the failing tests**

Add to `tests/test_youtube_ffmpeg.py`:

```python
# ── _build_music_playlist_wav ─────────────────────────────────────────────────

def _make_music_video_and_db(tmp_path):
    """Return (video_mock, db_mock) with one music track file on disk."""
    music_file = tmp_path / "track.mp3"
    music_file.write_bytes(b"fake")

    track = MagicMock()
    track.id = 1
    track.file_path = str(music_file)
    track.volume = 1.0

    video = MagicMock()
    video.music_track_ids = [1]
    video.music_track_id = None

    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [track]
    return video, db


def test_build_music_playlist_wav_uses_start_s_in_atrim(tmp_path):
    """start_s=300, target_dur=300 → atrim=start=300.0:end=600.0"""
    video, db = _make_music_video_and_db(tmp_path)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        from pipeline.youtube_ffmpeg import _build_music_playlist_wav
        _build_music_playlist_wav(video, db, 300, tmp_path, start_s=300.0)

    cmd = " ".join(mock_run.call_args[0][0])
    assert "atrim=start=300.0:end=600.0" in cmd
    assert "asetpts=PTS-STARTPTS" in cmd


def test_build_music_playlist_wav_default_start_s_is_zero(tmp_path):
    """Default start_s=0 → atrim=start=0:end=300"""
    video, db = _make_music_video_and_db(tmp_path)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        from pipeline.youtube_ffmpeg import _build_music_playlist_wav
        _build_music_playlist_wav(video, db, 300, tmp_path)

    cmd = " ".join(mock_run.call_args[0][0])
    assert "atrim=start=0" in cmd
    assert "asetpts=PTS-STARTPTS" in cmd
```

- [ ] **Step 3.2: Run to verify they fail**

```bash
python -m pytest tests/test_youtube_ffmpeg.py::test_build_music_playlist_wav_uses_start_s_in_atrim tests/test_youtube_ffmpeg.py::test_build_music_playlist_wav_default_start_s_is_zero -v
```

Expected: both FAIL — `atrim=start=` not found (current code uses `atrim=duration=`), and `asetpts` not found.

- [ ] **Step 3.3: Implement the fix**

In `pipeline/youtube_ffmpeg.py`, change the `_build_music_playlist_wav` signature from:

```python
def _build_music_playlist_wav(video, db, target_duration_s: int, output_dir: Path) -> str | None:
```

to:

```python
def _build_music_playlist_wav(video, db, target_duration_s: int, output_dir: Path, start_s: float = 0.0) -> str | None:
```

Then find the last line of the `parts` assembly inside that function. It currently reads:

```python
    parts.append(f"[looped]atrim=duration={target_duration_s}[out]")
```

Replace it with:

```python
    parts.append(
        f"[looped]atrim=start={start_s}:end={start_s + target_duration_s},"
        f"asetpts=PTS-STARTPTS[out]"
    )
```

Then find the call site in `render_landscape`. It currently reads:

```python
    music_wav = _build_music_playlist_wav(video, db, target_dur, output_dir)
```

Replace it with:

```python
    music_wav = _build_music_playlist_wav(video, db, target_dur, output_dir, start_s=start_s)
```

- [ ] **Step 3.4: Run to verify new tests pass**

```bash
python -m pytest tests/test_youtube_ffmpeg.py::test_build_music_playlist_wav_uses_start_s_in_atrim tests/test_youtube_ffmpeg.py::test_build_music_playlist_wav_default_start_s_is_zero -v
```

Expected: both PASS.

- [ ] **Step 3.5: Verify no regressions**

```bash
python -m pytest tests/test_youtube_ffmpeg.py -v
```

Expected: all 28 tests PASS.

- [ ] **Step 3.6: Commit**

```bash
git add pipeline/youtube_ffmpeg.py tests/test_youtube_ffmpeg.py
git commit -m "fix(yt-render): music playlist WAV starts at start_s not t=0"
```

---

## Task 4: SFX override layer continuity

Apply the same `_probe_duration` + modulo seek to SFX override layer inputs (foreground/midground/background) in the audio input loop.

**Files:**
- Modify: `pipeline/youtube_ffmpeg.py`
- Modify: `tests/test_youtube_ffmpeg.py`

---

- [ ] **Step 4.1: Write the failing test**

Add to `tests/test_youtube_ffmpeg.py`:

```python
def test_render_landscape_sfx_layer_uses_input_side_seek(tmp_path):
    """SFX override layer with start_s=310, file_dur=60 → effective_seek=10 → -ss 10 before -i sfx_path"""
    output = tmp_path / "chunk.mp4"
    sfx_file = tmp_path / "ambient.wav"
    sfx_file.write_bytes(b"fake")

    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("pipeline.youtube_ffmpeg.resolve_visual_playlist", return_value=[]), \
         patch("pipeline.youtube_ffmpeg.resolve_visual", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_music_playlist_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_sfx_pool_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg.resolve_sfx_layers", return_value=[(str(sfx_file), 0.5)]), \
         patch("pipeline.youtube_ffmpeg._probe_duration", return_value=60.0), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_landscape
        render_landscape(_make_video(), output, MagicMock(), start_s=310.0, end_s=610.0)

    cmd = mock_run.call_args[0][0]
    assert "-ss" in cmd
    ss_idx = cmd.index("-ss")
    i_idx = cmd.index(str(sfx_file))
    assert ss_idx < i_idx, "-ss must appear before -i sfx_path"
    assert cmd[ss_idx + 1] == "10", f"expected effective_seek=10, got {cmd[ss_idx + 1]}"


def test_render_landscape_sfx_layer_no_ss_when_start_s_is_zero(tmp_path):
    """SFX override layers with start_s=0 → no -ss in cmd"""
    output = tmp_path / "chunk.mp4"
    sfx_file = tmp_path / "ambient.wav"
    sfx_file.write_bytes(b"fake")

    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("pipeline.youtube_ffmpeg.resolve_visual_playlist", return_value=[]), \
         patch("pipeline.youtube_ffmpeg.resolve_visual", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_music_playlist_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_sfx_pool_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg.resolve_sfx_layers", return_value=[(str(sfx_file), 0.5)]), \
         patch("pipeline.youtube_ffmpeg._probe_duration", return_value=60.0), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_landscape
        render_landscape(_make_video(), output, MagicMock(), start_s=0.0, end_s=300.0)

    cmd = mock_run.call_args[0][0]
    assert "-ss" not in cmd
```

- [ ] **Step 4.2: Run to verify they fail**

```bash
python -m pytest tests/test_youtube_ffmpeg.py::test_render_landscape_sfx_layer_uses_input_side_seek tests/test_youtube_ffmpeg.py::test_render_landscape_sfx_layer_no_ss_when_start_s_is_zero -v
```

Expected: `test_render_landscape_sfx_layer_uses_input_side_seek` FAILS (no `-ss` for SFX layers yet). `test_render_landscape_sfx_layer_no_ss_when_start_s_is_zero` may already PASS — that's fine.

- [ ] **Step 4.3: Implement the fix**

In `pipeline/youtube_ffmpeg.py`, find the audio input loop inside `render_landscape`. It currently reads:

```python
    if audio_inputs:
        for path, _ in audio_inputs:
            # music_wav and sfx_wav are exact-duration WAVs — don't loop them
            if path in (music_wav, sfx_wav):
                cmd += ["-i", path]
            else:
                cmd += ["-stream_loop", "-1", "-i", path]
```

Replace the `else:` branch with:

```python
            else:
                if start_s > 0.5:
                    sfx_dur = _probe_duration(path)
                    effective_seek = (start_s % sfx_dur) if sfx_dur > 1.0 else 0.0
                    if effective_seek > 0.5:
                        cmd += ["-stream_loop", "-1", "-ss", str(int(effective_seek)), "-i", path]
                    else:
                        cmd += ["-stream_loop", "-1", "-i", path]
                else:
                    cmd += ["-stream_loop", "-1", "-i", path]
```

- [ ] **Step 4.4: Run to verify new tests pass**

```bash
python -m pytest tests/test_youtube_ffmpeg.py::test_render_landscape_sfx_layer_uses_input_side_seek tests/test_youtube_ffmpeg.py::test_render_landscape_sfx_layer_no_ss_when_start_s_is_zero -v
```

Expected: both PASS.

- [ ] **Step 4.5: Verify no regressions**

```bash
python -m pytest tests/test_youtube_ffmpeg.py -v
```

Expected: all 30 tests PASS.

- [ ] **Step 4.6: Commit**

```bash
git add pipeline/youtube_ffmpeg.py tests/test_youtube_ffmpeg.py
git commit -m "fix(yt-render): SFX override layers use input-side seek with modulo"
```

---

## Task 5: Timeout floor + final verification

Add an explicit `max(120, …)` at the `render_landscape` call site for clarity, then run the full test suite and verify everything is green.

**Files:**
- Modify: `pipeline/youtube_ffmpeg.py`

---

- [ ] **Step 5.1: Implement the timeout floor**

Find the last line of `render_landscape` (the `_run_ffmpeg` call). It currently reads:

```python
    _run_ffmpeg(cmd, target_dur * 2)
```

Replace with:

```python
    _run_ffmpeg(cmd, max(120, target_dur * 2))
```

- [ ] **Step 5.2: Run the full test suite**

```bash
python -m pytest tests/test_youtube_ffmpeg.py -v
```

Expected: all 30 tests PASS.

- [ ] **Step 5.3: Commit**

```bash
git add pipeline/youtube_ffmpeg.py
git commit -m "fix(yt-render): explicit 120s timeout floor for short tail chunks"
```

---

## Verification checklist (after all tasks complete)

- [ ] `python -m pytest tests/test_youtube_ffmpeg.py -v` → 30 passed, 0 failed
- [ ] In the rendered ffmpeg log for any chunk with `start_s > 0`, `-ss N` appears **before** `-i visual_path` and **not** after `-map`
- [ ] Scrubbing through chunk boundaries in the final concatenated video shows no visual loop reset, no music restart, no SFX ambient reset
