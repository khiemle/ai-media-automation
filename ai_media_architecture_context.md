# AI Media Automation — System Architecture

> **Version:** 1.1 | **Updated:** 2026 | **Team:** 1 Engineer + 1 Business
> **LLM Options:** Local (Qwen2.5 7B via Ollama) · Cloud (Gemini 2.5 Flash / Flash-Lite)

---

## Table of Contents

1. [High-Level Architecture](#1-high-level-architecture)
2. [Core Data Flow](#2-core-data-flow)
3. [Layers Overview](#3-layers-overview)
4. [LLM Strategy](#4-llm-strategy)
5. [Folder Structure](#5-folder-structure)
6. [Data Architecture](#6-data-architecture)
7. [Module Specifications](#7-module-specifications)
8. [Integration Map](#8-integration-map)
9. [Tech Stack & Cost](#9-tech-stack--cost)
10. [Risk & Mitigation](#10-risk--mitigation)
11. [KPIs & Success Metrics](#11-kpis--success-metrics)

---

## 1. High-Level Architecture

The system is designed as a **Data-Driven Content Factory** operating on five layers:

```
Thu thập xu hướng → AI sáng tạo nội dung → Tự động sản xuất → Phân phối đa kênh → Kiếm tiền
        ↑                                                                              |
        └──────────────────── Feedback loop từ kết quả thực tế ──────────────────────┘
```

### Design Principles

- **Multi-LLM** — Flexible switching between Local (Qwen2.5) and Cloud (Gemini API), even hybrid within the same pipeline
- **Template-based** — Scripts define everything; the engine only executes
- **Async-parallel** — Maximum parallel processing for throughput
- **Self-improving** — Learns from real performance results via feedback loop

### System Diagram

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                              AI MEDIA COMPANY                                  │
│                                                                                │
│  ┌──────────────────────┐   ┌────────────────────────────────────────────────┐ │
│  │      DATA LAYER      │   │                   AI LAYER                     │ │
│  │                      │   │  ┌──────────────────────────────────────────┐  │ │
│  │  • TikTok Scraper    │   │  │              LLM ROUTER                  │  │ │
│  │  • PostgreSQL        │──▶│  │  Mode A: LOCAL    │  Mode B: GEMINI      │  │ │
│  │  • ChromaDB          │   │  │  Qwen2.5 7B       │  gemini-2.5-flash    │  │ │
│  │  • Viral DB          │   │  │  Ollama :11434    │  Google AI API       │  │ │
│  │                      │   │  │  Free, offline    │  Free / Pay-as-go    │  │ │
│  └──────────────────────┘   │  └──────────────────────────────────────────┘  │ │
│                              │  • RAG Engine (ChromaDB retrieval)             │ │
│                              │  • Embedding Model (vietnamese-sbert)          │ │
│                              └────────────────────────────────────────────────┘ │
│                                                  │                              │
│                                                  ▼  script.json                 │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │                          PRODUCTION LAYER                              │    │
│  │                                                                        │    │
│  │  [Thread 1]  narration  ──▶  Kokoro TTS                ──▶ audio.wav  │    │
│  │                                                                        │    │
│  │  [Thread 2]  visual_hint ──▶ ASSET RESOLVER (3-tier)                  │    │
│  │              │                                                         │    │
│  │              ├─ Tier 1: Video Asset DB ◀─────────────────────────────┐│    │
│  │              │  (PostgreSQL + /assets/video_db/)   write-back ───────┘│    │
│  │              │                                                         │    │
│  │              ├─ Tier 2A: Pexels API  ──▶ download ──▶ resize+crop     │    │
│  │              │                                                         │    │
│  │              └─ Tier 2B: Google Veo  ──▶ generate (8s segments)       │    │
│  │                          (GEMINI_API_KEY)  n=ceil(dur/8) ──▶ concat   │    │
│  │                          ──▶ resize+crop ──────────────────▶ clip.mp4 │    │
│  │                                                                        │    │
│  │  [Thread 3]  text_overlay ──▶ Overlay Builder (Pillow) ──▶ frame.png  │    │
│  │                                                                        │    │
│  │  ──────────────────────── all scenes ready ─────────────────────────  │    │
│  │                                                                        │    │
│  │  Scene Composer (MoviePy)  ──▶  raw_video.mp4                         │    │
│  │  Caption Gen   (Whisper)   ──▶  subtitles.srt   ──┐                   │    │
│  │  Music Selector (Suno lib) ──▶  track.mp3       ──┤                   │    │
│  │                                                    ▼                  │    │
│  │  Final Renderer  ffmpeg + h264_nvenc  ──▶  subtitle burn-in + mix     │    │
│  │                                                    │                  │    │
│  │  Quality Validation  ──────────────────────────────┘                  │    │
│  │  (duration · codec · resolution · audio · file size)                  │    │
│  │                                        │                              │    │
│  │                                        ▼                              │    │
│  │                              video_final.mp4 + metadata.json          │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│                                                  │                              │
│                                                  ▼                              │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │                         DISTRIBUTION LAYER                             │    │
│  │     YouTube API (multi-channel)  │  TikTok API  │  Instagram Reels    │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│                                                  │                              │
│                                                  ▼                              │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │                         MONETIZATION LAYER                             │    │
│  │        AdSense  │  TikTok Shop  │  Affiliate links  │  Dropshipping   │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│                                                  │                              │
│                               ┌──────────────────┘                             │
│                               ▼                                                 │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │                   FEEDBACK LOOP  (daily at 06:50)                      │    │
│  │   Track views/ER → Score → Reindex top videos → ChromaDB viral_scripts │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────────────────────┘

Asset Resolver modes:
  db_only         → Video Asset DB only, no external API calls
  db_then_pexels  → DB first, Pexels on miss
  db_then_veo     → DB first, Veo generation on miss
  db_then_hybrid  → DB first, then hook/cta → Veo · body/transition → Pexels  [recommended]

Resize + crop rule (all sources):
  scale = max(target_w / src_w, target_h / src_h)   ← preserves aspect ratio, no black bars
  center-crop to 1080 × 1920                         ← portrait output for all platforms
```

---

## 2. Core Data Flow

```
[TOPIC INPUT]
     │
     ▼
[TREND ANALYZER] ── pulls ──▶ [PostgreSQL: viral_videos]
     │                              │
     │                              ▼
     │                        [ChromaDB: vector embeddings]
     │                              │
     ▼                              ▼
[RAG RETRIEVER] ◀── queries ── [similar scripts + hooks + patterns]
     │
     ▼
[PROMPT BUILDER]
     │  (topic + 5 viral scripts + top hooks + trend patterns)
     ▼
┌─────────────────────────────────────────────────┐
│           LLM ROUTER (llm_router.py)             │
│  Mode A: LOCAL    │   Mode B: GEMINI API         │
│  Qwen2.5 7B       │   gemini-2.5-flash           │
│  Ollama :11434    │   ai.google.dev API           │
│  Free, offline    │   Free tier / Pay-as-go       │
└──────────────┬──────────────────────────────────┘
               │
               ▼
[script.json]  (topic · niche · scenes[] · cta · affiliate)
  │
  ├── scenes[].narration    ──▶  [Kokoro TTS]                  ──▶  audio_N.wav
  │
  ├── scenes[].visual_hint  ──▶  [ASSET RESOLVER — 3-tier]
  │       + topic · niche          │
  │       + narration[:120]        ├─ Tier 1: Video Asset DB (PostgreSQL + disk)
  │                                │    search: keywords · niche · duration · aspect
  │                                │    hit (score ≥ 0.72) → return clip ──────────┐
  │                                │                                                │
  │                                ├─ Tier 2A: Pexels API                           │
  │                                │    portrait search → download                  │
  │                                │    → write-back to Asset DB ────────────────┐  │
  │                                │                                              │  │
  │                                └─ Tier 2B: Google Veo  (GEMINI_API_KEY)       │  │
  │                                     prompt: topic+hint+narration+niche style  │  │
  │                                     n = ceil(scene.duration / 8s)             │  │
  │                                     generate n × 8s segments                  │  │
  │                                     → write each segment to Asset DB ─────────┘  │
  │                                     → concat n clips → trim to duration          │
  │                                                │                                 │
  │                             resize+crop (scale=max ratio, center-crop) ◀────────┘
  │                             → 1080×1920, 30fps → clip_N.mp4
  │
  ├── scenes[].text_overlay ──▶  [Overlay Builder (Pillow)]    ──▶  overlay_N.png
  │
  └── (all scenes ready)
            │
            ▼
      [Scene Composer — MoviePy]
        composite overlay + narration audio + music (0.08 vol) + transitions
            │
            ▼
      [Caption Gen — Whisper base]  ──▶  subtitles.srt
            │
            ▼
      [Final Renderer — ffmpeg + h264_nvenc]
        burn subtitles · merge audio · 1080×1920 · 30fps · CRF 23 · AAC 192k
            │
            ▼
      [Quality Validation]
        duration · codec · resolution · audio track · file size
            │
            ▼
      [video_final.mp4 + metadata.json]
            │
      ┌─────┘
      ▼
[AUTO UPLOADER + SCHEDULER]
  ├── YouTube  (title, desc, tags, thumbnail)
  ├── TikTok   (caption, hashtags, music)
  └── metadata.json (affiliate links, schedule)
```

---

## 3. Layers Overview

### Layer 1 — Data Layer

| Component | Technology | Purpose |
|---|---|---|
| TikTok Scraper | Playwright / Research API / Apify | Collects trending video data |
| Relational DB | PostgreSQL 16 | Stores viral videos, patterns, scripts |
| Vector DB | ChromaDB | Semantic similarity search |
| Trend Analyzer | Custom Python | Extracts viral patterns per niche/region |

### Layer 2 — AI Layer

| Component | Technology | Purpose |
|---|---|---|
| LLM Router | `llm_router.py` | Dispatches to Local or Gemini |
| Local LLM | Qwen2.5 7B via Ollama | Offline script generation |
| Cloud LLM | Gemini 2.5 Flash / Flash-Lite | High-quality / batch script generation |
| RAG Engine | ChromaDB + SBERT | Retrieves viral context for prompts |
| Embedding Model | vietnamese-sbert | Vietnamese semantic embeddings |

### Layer 3 — Production Layer

| Component | Technology | Purpose |
|---|---|---|
| TTS Engine | Kokoro ONNX | Vietnamese voiceover generation |
| Asset Resolver | Video Asset DB + Pexels API + Google Veo | 3-tier: DB → Pexels → Veo |
| Overlay Builder | Pillow / OpenCV | Renders text overlays on frames |
| Caption Generator | Whisper base | Generates SRT subtitles from audio |
| Scene Composer | MoviePy | Assembles scenes into raw video |
| Final Renderer | ffmpeg + h264_nvenc | GPU-accelerated final encode |
| Music Selector | Suno Pro library | Matches background music to mood/niche |

---

## Production Layer — Detailed Design

### Overview

The Production Layer takes a validated `script.json` and outputs a broadcast-ready `video_final.mp4`. It operates in two phases:

**Phase 1 — Per-scene parallel processing.** For each scene in `script.json`, three threads run concurrently: TTS generates the voiceover, the asset resolver fetches footage, and the overlay builder renders the text graphic. All three complete before the scene is considered ready.

**Phase 2 — Sequential assembly and encode.** Once all scene assets are ready, they are composited and concatenated by the scene composer (MoviePy), subtitles are generated by Whisper and burned in, music is mixed, and the final file is encoded by ffmpeg with h264_nvenc.

```
script.json
     │
     ├── [Thread 1] TTS engine      → audio_N.wav
     ├── [Thread 2] Asset resolver  → clip_N.mp4       } per scene, parallel
     └── [Thread 3] Overlay builder → overlay_N.png
                  │
                  ▼ (all scenes ready)
          Scene composer (MoviePy)  → raw_video.mp4
                  │
          ┌───────┴────────┐
          │                │
    Caption gen         Final renderer
    (Whisper → SRT)     (ffmpeg NVENC)
          │                │
          └───────┬─────────┘
                  ▼
        Subtitle burn-in + audio mix
                  ▼
        Quality validation
                  ▼
        video_final.mp4 + metadata.json
```

---

### Module 1 — TTS Engine (`pipeline/tts_engine.py`)

**Responsibility:** Convert `scene.narration` text into a time-aligned `.wav` audio file for each scene.

**Technology:** Kokoro ONNX — a lightweight neural TTS model that runs fully offline on CPU.

#### Processing steps

| Step | Action | Detail |
|---|---|---|
| 1 | Read input | `scene.narration` string from script.json |
| 2 | Text normalize | Expand numbers, abbreviations, punctuation for natural speech |
| 3 | Kokoro inference | Voice: `af_heart`, speed: `1.1×`, CPU mode |
| 4 | Resample | Output resampled to 44.1 kHz, mono channel |
| 5 | Duration fit | Pad silence or speed-adjust to match `scene.duration` |
| 6 | Write output | `audio_N.wav` — 44.1 kHz, 16-bit PCM, mono |

#### Config

```python
TTS_CONFIG = {
    "engine":        "kokoro",
    "model":         "kokoro-v0_19.onnx",
    "voice":         "af_heart",        # female Vietnamese voice
    "speed":         1.1,               # slightly faster for social media
    "sample_rate":   44100,
    "channels":      1,                 # mono
    "threads":       8,                 # Ryzen 9 parallel scenes
    "max_duration_pad": 0.5,            # seconds of allowed silence padding
}
```

#### Fallback

If Kokoro fails on a scene, the system retries once with speed `1.0`, then falls back to a silent audio track with a warning logged. The scene is flagged in the report JSON.

---

### Module 2 — Asset Resolver (`pipeline/asset_resolver.py`)

**Responsibility:** Resolve the best available video clip for each scene. The resolver operates as a three-tier system: it always checks the **Video Asset Database** first (free, instant), then falls back to external sources — **Pexels** (stock footage) or **Google Veo** (AI-generated) — and writes every new clip back into the database so it can be reused by future videos.

---

#### Three-tier architecture

```
scene.visual_hint + scene.narration + meta.topic
          │
          ▼
┌─────────────────────────────────────────────────┐
│         TIER 1 — Video Asset Database           │
│         (asset_db.py — PostgreSQL + file store) │
│                                                 │
│  Search by: keywords, niche, tags, source,      │
│             min_duration, aspect_ratio          │
│                                                 │
│  Contains clips from ALL past sources:          │
│    • Previously downloaded Pexels clips         │
│    • Previously generated Veo clips             │
│    • Manually added B-roll                      │
└──────────────────┬──────────────────────────────┘
                   │
          found?   │   not found / low quality score
          ──────── │ ──────────────────────────────
         ↙                        ↘
  return asset_db clip      TIER 2 — Source selection
  (skip API entirely)              │
                            ┌──────┴──────┐
                            ▼             ▼
                       Pexels API     Veo (Google AI)
                       (stock)        (AI-generated)
                            │             │
                            └──────┬──────┘
                                   ▼
                         download / generate clip
                                   │
                                   ▼
                    TIER 3 — Write back to Asset DB
                    (index + tag + store for reuse)
                                   │
                                   ▼
                              clip_N.mp4
```

**Key benefit:** A Veo clip generated for "morning productivity routine, lifestyle niche" on Day 1 is stored in the Asset DB with tags `[morning, productivity, lifestyle, person, sunrise]`. On Day 5, any video needing a similar scene finds it instantly — zero API cost, zero generation wait time.

---

#### Source selection modes

```python
ASSET_RESOLVER_CONFIG = {
    # Primary source selection mode
    "source_mode": "db_then_hybrid",
    # Options:
    #   "db_only"          — only use Asset DB, never call external APIs
    #   "db_then_pexels"   — DB first, Pexels on miss
    #   "db_then_veo"      — DB first, Veo on miss
    #   "db_then_hybrid"   — DB first, then route by scene.type (recommended)
    #   "pexels"           — always fetch from Pexels (legacy mode)
    #   "veo"              — always generate with Veo (premium mode)

    # Hybrid routing rules (used when source_mode = "db_then_hybrid")
    "hybrid_rules": {
        "hook":       "veo",     # first scene — most impactful, generate fresh
        "cta":        "veo",     # last scene — closing shot, generate fresh
        "body":       "pexels",  # middle scenes — stock is fine
        "transition": "pexels",  # filler — always stock
    },

    # Asset DB match quality threshold (0.0–1.0)
    # Below this score, treat as a miss and go to external source
    "db_min_score":  0.72,

    # Veo settings
    "veo_model":    "veo-3.0-generate-preview",  # or "veo-2.0-generate-001"
    "veo_fallback": "pexels",

    # Write every new clip back to Asset DB
    "write_back":    True,
}
```

---

#### Tier 1 — Video Asset Database (`pipeline/asset_db.py`)

**Storage:** PostgreSQL metadata table + local file system (`/assets/video_db/`).

##### PostgreSQL schema

```sql
CREATE TABLE video_assets (
    id              SERIAL PRIMARY KEY,
    file_path       TEXT NOT NULL,              -- /assets/video_db/{hash}.mp4
    file_hash       TEXT UNIQUE NOT NULL,       -- SHA256 of file content
    source          TEXT NOT NULL,              -- 'pexels' | 'veo' | 'manual'
    source_id       TEXT,                       -- Pexels video ID or Veo op ID
    veo_prompt      TEXT,                       -- full prompt used (Veo only)

    -- Descriptive metadata for search
    keywords        TEXT[],                     -- ['morning', 'person', 'sunrise']
    niche           TEXT[],                     -- ['lifestyle', 'health']
    tags            TEXT[],                     -- free-form tags
    description     TEXT,                       -- human-readable summary

    -- Technical metadata
    duration_s      FLOAT NOT NULL,             -- actual clip duration in seconds
    resolution      TEXT NOT NULL,              -- '1080x1920' | '1920x1080'
    aspect_ratio    TEXT NOT NULL,              -- '9:16' | '16:9'
    fps             INT  NOT NULL,              -- 30
    file_size_mb    FLOAT,

    -- Usage tracking
    usage_count     INT DEFAULT 0,              -- how many videos used this clip
    last_used_at    TIMESTAMP,
    quality_score   FLOAT,                      -- manual or auto-rated 0.0–1.0

    -- Timestamps
    created_at      TIMESTAMP DEFAULT NOW(),
    expires_at      TIMESTAMP                   -- NULL = permanent
);

CREATE INDEX idx_va_keywords    ON video_assets USING GIN(keywords);
CREATE INDEX idx_va_niche       ON video_assets USING GIN(niche);
CREATE INDEX idx_va_source      ON video_assets(source);
CREATE INDEX idx_va_duration    ON video_assets(duration_s);
CREATE INDEX idx_va_quality     ON video_assets(quality_score DESC);
CREATE INDEX idx_va_aspect      ON video_assets(aspect_ratio);
```

##### Search algorithm

```python
def search_asset_db(
    keywords:     list[str],
    niche:        str,
    min_duration: float,
    aspect_ratio: str = "9:16",
    min_score:    float = 0.72,
) -> Asset | None:
    """
    Score each candidate asset by keyword overlap.
    Return highest-scoring asset above min_score threshold.
    """
    candidates = db.query("""
        SELECT *, (
            array_length(
                ARRAY(SELECT unnest(keywords) INTERSECT SELECT unnest(%s)),
                1
            )::float / GREATEST(array_length(keywords, 1), 1)
        ) AS match_score
        FROM video_assets
        WHERE duration_s   >= %s
          AND aspect_ratio  = %s
          AND (niche @> %s OR niche IS NULL)
        ORDER BY match_score DESC, usage_count ASC, quality_score DESC
        LIMIT 5
    """, [keywords, min_duration, aspect_ratio, [niche]])

    best = candidates[0] if candidates else None
    if best and best.match_score >= min_score:
        db.execute("UPDATE video_assets SET usage_count = usage_count + 1,
                    last_used_at = NOW() WHERE id = %s", [best.id])
        return best
    return None
```

##### Write-back (after any external fetch or generation)

```python
def write_to_asset_db(
    file_path:    str,
    source:       str,       # 'pexels' | 'veo'
    keywords:     list[str],
    niche:        str,
    veo_prompt:   str = None,
    source_id:    str = None,
    quality_score: float = 0.8,
) -> int:
    """
    Ingest a new clip into the Asset DB after downloading or generating it.
    Returns the new asset ID.
    """
    meta = probe_video(file_path)     # ffprobe: duration, resolution, fps
    file_hash = sha256_file(file_path)

    return db.insert("video_assets", {
        "file_path":     file_path,
        "file_hash":     file_hash,
        "source":        source,
        "source_id":     source_id,
        "veo_prompt":    veo_prompt,
        "keywords":      keywords,
        "niche":         [niche],
        "duration_s":    meta.duration,
        "resolution":    meta.resolution,
        "aspect_ratio":  meta.aspect_ratio,
        "fps":           meta.fps,
        "file_size_mb":  meta.size_mb,
        "quality_score": quality_score,
    })
```

##### File store layout

```
/assets/video_db/
  pexels/
    a3f2c1d8...mp4     ← keyed by SHA256
    b7e9a0f1...mp4
  veo/
    c4d1e2f3...mp4     ← Veo-generated, 8s segments
    d5e2f3a4...mp4
  manual/
    niche_default_finance.mp4
    niche_default_lifestyle.mp4
```

---

#### Tier 2A — Pexels backend

Triggered when Asset DB returns no match and `source_mode` routes to Pexels.

| Step | Action | Detail |
|---|---|---|
| 1 | Build query | Extract top keywords from `scene.visual_hint` |
| 2 | Pexels search | `GET /videos/search?query=…&orientation=portrait` |
| 3 | Select clip | Highest resolution result with duration ≥ `scene.duration` |
| 4 | Download | Stream to `/assets/video_db/pexels/{hash}.mp4` |
| 5 | Trim | `subclip(0, scene.duration)` — loop if shorter |
| 6 | Resize + crop | Center-crop to `1080×1920`, 30fps |
| 7 | Write to Asset DB | Tag with keywords, niche, source=pexels |
| 8 | Return path | `clip_N.mp4` ready for composer |

**Rate limiting:** 200 req/hr free tier — shared token bucket across all workers.

---

#### Tier 2B — Veo backend (Google AI)

Triggered when Asset DB returns no match and `source_mode` routes to Veo.

##### Key constraint — 8-second clip length

Veo generates exactly **8 seconds** per request. The resolver handles longer scenes by chaining multiple calls:

```python
def veo_clips_needed(scene_duration: float) -> int:
    return math.ceil(scene_duration / 8.0)
```

| Scene duration | Calls needed | Generated total | Trimmed to |
|---|---|---|---|
| 4s | 1 | 1 × 8s = 8s | 4s |
| 8s | 1 | 1 × 8s = 8s | 8s |
| 10s | 2 | 2 × 8s = 16s | 10s |
| 20s | 3 | 3 × 8s = 24s | 20s |
| 45s | 6 | 6 × 8s = 48s | 45s |

**Important:** Each 8s segment is stored individually in the Asset DB, not only the trimmed result. This maximises reuse — a future 6s scene can reuse one of those segments directly.

##### Prompt construction (`pipeline/veo_prompt_builder.py`)

```python
def build_veo_prompt(scene: dict, meta: dict) -> str:
    topic       = meta["topic"]          # e.g. "5 thói quen buổi sáng"
    niche       = meta["niche"]          # e.g. "lifestyle"
    narration   = scene["narration"]     # e.g. "Thức dậy lúc 5 giờ sáng..."
    visual_hint = scene["visual_hint"]   # e.g. "person waking up sunrise bedroom"
    style       = VEO_STYLE_DIRECTIVES[niche]

    return (
        f"Cinematic vertical video, 9:16 portrait, 1080x1920. "
        f"Topic: {topic}. "
        f"Scene: {visual_hint}. "
        f"Context: {narration[:120]}. "
        f"Style: {style}. "
        f"Requirements: no text, no subtitles, no watermark, natural lighting, "
        f"smooth motion, suitable for {niche} social media content. "
        f"Duration: 8 seconds."
    )

VEO_STYLE_DIRECTIVES = {
    "finance":   "professional setting, clean office, confident person, warm tones, 4K cinematic",
    "health":    "bright natural light, clean minimal space, wellness aesthetic, soft focus",
    "lifestyle": "golden hour, lifestyle vlog style, authentic candid feel, warm color grade",
    "fitness":   "dynamic movement, gym or outdoor, high contrast, energetic pacing",
    "food":      "overhead or 45-degree shot, soft natural light, appetizing close-up, warm tones",
}
```

##### Veo processing steps

| Step | Action | Detail |
|---|---|---|
| 1 | Asset DB lookup | Search by `visual_hint` keywords + niche + source=veo |
| 2 | Build prompt | Assemble from topic + narration + visual_hint + niche style |
| 3 | Calculate n | `n = ceil(scene.duration / 8)` |
| 4 | Submit n jobs | `client.models.generate_videos(model, prompt, aspect_ratio=9:16, duration=8)` |
| 5 | Poll per job | Check every 5s — timeout 180s per job |
| 6 | Download segments | Each 8s segment → `/assets/video_db/veo/{hash}.mp4` |
| 7 | Write each segment | Insert each 8s clip into Asset DB independently |
| 8 | Concatenate | Join n segments if `n > 1` |
| 9 | Trim | `subclip(0, scene.duration)` |
| 10 | Resize + crop | Center-crop to `1080×1920` (Veo may output 16:9) |
| 11 | Return path | `clip_N.mp4` ready for composer |

##### Veo API call

```python
class VeoBackend:
    MODELS = {
        "veo2": "veo-2.0-generate-001",
        "veo3": "veo-3.0-generate-preview",
    }

    def __init__(self, model: str = "veo2"):
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        self.client = genai.Client()
        self.model  = self.MODELS[model]

    def generate_segment(self, prompt: str, scene_id: int, seg_idx: int) -> str:
        op = self.client.models.generate_videos(
            model=self.model,
            prompt=prompt,
            config=genai.GenerateVideosConfig(
                aspect_ratio       = "9:16",
                duration_seconds   = 8,        # fixed — Veo hard limit
                number_of_videos   = 1,
                resolution         = "1080p",
                person_generation  = "allow_adult",
            ),
        )
        start = time.time()
        while not op.done:
            time.sleep(5)
            op = self.client.operations.get(op)
            if time.time() - start > 180:
                raise TimeoutError(f"Veo timeout scene={scene_id} seg={seg_idx}")

        raw_path = f"./assets/video_db/veo/{sha256_str(prompt)}_{seg_idx}.mp4"
        op.response.generated_videos[0].video.save(raw_path)

        # Write this 8s segment into Asset DB immediately
        asset_db.write(raw_path, source="veo", veo_prompt=prompt, ...)
        return raw_path
```

##### Veo cost estimate

```
~$0.35 per 8s clip (Veo 2, approximate — verify on Google AI pricing)

Hybrid mode (Veo for hook + CTA, Pexels for body):
  2 Veo calls × $0.35 = $0.70 per video
  200 videos/day = $140/day

With Asset DB reuse (realistic after Week 1):
  DB hit rate ~40% on hook/CTA scenes → 0.6 × $0.70 = $0.42 per video
  200 videos/day = $84/day

After 1 month (DB grows to 500+ clips):
  DB hit rate ~70% → 0.3 × $0.70 = $0.21 per video
  200 videos/day = $42/day
```

---

#### Full resolution flow

```
scene (visual_hint, narration, topic, niche, duration, type)
  │
  ▼
[1] Asset DB search (keywords + niche + duration + aspect_ratio)
  │
  ├─ MATCH (score ≥ 0.72)
  │     └─▶ return asset_db.file_path  ──────────────────┐
  │                                                       │
  └─ NO MATCH                                            │
       │                                                  │
       ▼                                                  │
  [2] Source routing (hybrid_rules by scene.type)         │
       │                                                  │
       ├─ "pexels" ──▶ Pexels /videos/search             │
       │                  └─ found  → download            │
       │                  └─ miss   → niche-default B-roll│
       │                       └─▶ write_to_asset_db ─────┤
       │                                                  │
       └─ "veo" ──▶ Build prompt                         │
                      └─▶ n = ceil(duration / 8)         │
                      └─▶ submit n Veo jobs               │
                      └─▶ poll → download each 8s segment │
                      └─▶ write each segment to asset_db  │
                      └─▶ concat + trim ──────────────────┤
                      └─ timeout → fallback to Pexels      │
                                                           │
  [3] Post-process (shared)  ◀────────────────────────────┘
       └─▶ resize + crop → 1080x1920, 30fps
       └─▶ clip_N.mp4  →  Scene Composer
```

---

### Module 3 — Overlay Builder (`pipeline/overlay_builder.py`)

**Responsibility:** Render styled text as a transparent PNG image that can be composited over the video frame.

**Technology:** Pillow (PIL) for text rendering, OpenCV for any pixel-level operations.

#### Processing steps

| Step | Action | Detail |
|---|---|---|
| 1 | Read input | `scene.text_overlay`, `scene.overlay_style` |
| 2 | Load template | Style config: font, size, color, position, shadow |
| 3 | Text wrap | Compute line breaks for max width (800px usable) |
| 4 | Layout calc | Compute bounding box, center on canvas |
| 5 | Render shadow | Draw offset copy in semi-transparent black |
| 6 | Render text | Draw text in configured color on RGBA canvas |
| 7 | Alpha channel | Background is fully transparent (0 alpha) |
| 8 | Write output | `overlay_N.png` — 1080×1920, RGBA |

#### Built-in overlay styles

| Style ID | Font | Size | Color | Position | Use case |
|---|---|---|---|---|---|
| `big_white_center` | Roboto Bold | 72px | White + black shadow | Center | TikTok hook text |
| `bottom_caption` | Roboto Regular | 40px | White + dark bar | Bottom 20% | Subtitle-style |
| `top_title` | Roboto Bold | 56px | White + shadow | Top 15% | YouTube title card |
| `highlight_box` | Roboto Medium | 48px | Yellow fill, dark text | Center | Key stat callout |
| `minimal` | Roboto Light | 36px | White, no shadow | Lower third | Clean aesthetic |

#### Template config example

```python
OVERLAY_STYLES = {
    "big_white_center": {
        "font":        "Roboto-Bold.ttf",
        "font_size":   72,
        "color":       (255, 255, 255, 255),
        "shadow":      (0, 0, 0, 160),
        "shadow_offset": (3, 3),
        "position":    "center",
        "max_width_px": 900,
        "line_spacing": 1.2,
    }
}
```

---

### Module 4 — Scene Composer (`pipeline/composer.py`)

**Responsibility:** Take all per-scene assets (audio, clip, overlay) and assemble them into a single `raw_video.mp4` with transitions and background music.

**Technology:** MoviePy.

#### Compositing steps per scene

```
clip_N.mp4
    + overlay_N.png (alpha composite, full duration)
    + audio_N.wav   (set as scene audio)
    + music track   (mixed at 0.08 volume)
    + transition_in / transition_out
    → composed_scene_N
```

#### Concatenation

```python
final = concatenate_videoclips(
    [composed_scene_0, composed_scene_1, ...],
    method="compose"
)
```

#### Music mixing

Music is loaded once for the full video and mixed at `volume=0.08` under narration. The narration audio sits at full volume (1.0). An `audiofx.MultiplyVolume` ramp can optionally duck music further during speech.

#### Transition types

| Transition | Effect | Duration |
|---|---|---|
| `cut` | Instant cut | 0s |
| `fade` | Fade to black, fade in | 0.3s |
| `crossfade` | Cross-dissolve between clips | 0.4s |

#### Output

`raw_video.mp4` — full-duration video, no subtitles, no final encode optimization. Codec: libx264 at draft quality (fast write, will be re-encoded by the renderer).

---

### Module 5 — Caption Generator (`pipeline/caption_gen.py`)

**Responsibility:** Transcribe the narration audio and generate a word-level timed `.srt` subtitle file.

**Technology:** OpenAI Whisper — `base` model, local CPU inference.

#### Processing steps

| Step | Action | Detail |
|---|---|---|
| 1 | Merge audio | Concatenate all `audio_N.wav` into full narration track |
| 2 | Whisper ASR | Model: `base`, language: `vi` (Vietnamese) |
| 3 | Word timestamps | Extract word-level start/end times |
| 4 | SRT format | Group into subtitle blocks of ≤ 7 words per line |
| 5 | Timing adjust | Offset by scene start times |
| 6 | Write output | `subtitles.srt` |

#### Config

```python
WHISPER_CONFIG = {
    "model":     "base",       # 74M params, fast enough for batch
    "language":  "vi",         # force Vietnamese for accuracy
    "task":      "transcribe",
    "word_timestamps": True,
    "max_words_per_line": 7,
    "min_gap_between_subs": 0.1,  # seconds
}
```

#### Subtitle style (burned in by ffmpeg)

```
font: Arial, size 24, white text, black border 2px
position: bottom center, margin 60px from bottom
```

---

### Module 6 — Final Renderer (`pipeline/renderer.py`)

**Responsibility:** Take `raw_video.mp4` + `subtitles.srt` + music track and produce the final broadcast-ready `video_final.mp4` using GPU-accelerated encoding.

**Technology:** ffmpeg + h264_nvenc (GTX 1660 Super).

#### Full ffmpeg command

```bash
ffmpeg \
  -i raw_video.mp4 \
  -i music_track.mp3 \
  -vf "subtitles=subtitles.srt:force_style='FontName=Arial,FontSize=24,
       PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,
       Alignment=2,MarginV=60'" \
  -filter_complex "[0:a][1:a]amerge=inputs=2,pan=stereo|c0<c0+c2|c1<c1+c3[a]" \
  -map 0:v -map "[a]" \
  -c:v h264_nvenc \
  -preset fast \
  -crf 23 \
  -b:v 4M \
  -maxrate 6M \
  -bufsize 12M \
  -c:a aac \
  -b:a 192k \
  -ar 44100 \
  -r 30 \
  -s 1080x1920 \
  -movflags +faststart \
  video_final.mp4
```

#### Encode settings

| Parameter | Value | Reason |
|---|---|---|
| Codec | h264_nvenc | GPU encode — ~10× faster than CPU |
| Preset | fast | Balances quality and encode speed |
| CRF | 23 | Good quality, acceptable file size |
| Bitrate cap | 4M / max 6M | TikTok and YouTube compatible |
| Audio codec | AAC 192kbps | Universal compatibility |
| Frame rate | 30fps | Standard for social media |
| Resolution | 1080×1920 | TikTok / Reels portrait format |
| `faststart` | enabled | Web streaming — metadata at front of file |

#### CPU fallback

If NVENC is unavailable (driver crash, VRAM full), the renderer automatically falls back:

```python
RENDER_FALLBACK = {
    "codec":   "libx264",
    "preset":  "medium",     # slower but CPU-only
    "threads": 12,           # Ryzen 9 cores
}
```

Fallback encode time: ~4–5 min/video vs ~45s with NVENC.

---

### Module 7 — Music Selector (`music/selector.py`)

**Responsibility:** Choose the most appropriate background music track from the local Suno library for a given video.

**Selection logic:**

```python
def select_track(niche: str, mood: str, duration: int) -> str:
    candidates = library.filter(mood=mood, duration_gte=duration)
    if not candidates:
        candidates = library.filter(niche=niche, duration_gte=duration)
    track = random.choice(candidates)
    library.increment_usage(track)
    return track.path
```

#### Mood mapping

| Niche | Default mood | Alternative |
|---|---|---|
| finance | trust | calm_focus |
| health | trust | uplifting |
| lifestyle | uplifting | energetic |
| fitness | energetic | uplifting |
| productivity | calm_focus | uplifting |

#### Library structure

```
/assets/music/
  uplifting_120bpm_180s.mp3
  calm_focus_85bpm_240s.mp3
  energetic_140bpm_120s.mp3
  trust_95bpm_200s.mp3
  ...
```

Naming format: `{mood}_{bpm}_{duration_seconds}.mp3`. Target library size: 25–30 tracks for monthly rotation without repetition.

---

### Quality Validation (`pipeline/renderer.py`)

After encoding, a validation step probes the output file before it enters the upload queue:

```python
VALIDATION_CHECKS = [
    "duration_within_5pct_of_target",   # render didn't truncate
    "file_size_between_10mb_and_500mb", # not corrupt, not oversized
    "codec_is_h264",                    # ffprobe confirms codec
    "resolution_is_1080x1920",          # correct orientation
    "audio_track_present",              # not silent
    "no_zero_byte_frames",              # no encoder glitch
]
```

If any check fails, the video is flagged as `render_failed` in the DB, the topic is re-queued, and the error is logged for the engineer dashboard.

---

### Production Layer Performance Targets

| Metric | Target | Notes |
|---|---|---|
| TTS time per scene | < 8s | Kokoro on Ryzen 9, 8 threads |
| Asset fetch time (cache hit) | < 1s | Local disk |
| Asset fetch time (cache miss) | < 5s | Pexels API + download |
| Overlay render time per scene | < 2s | Pillow on CPU |
| Scene compose time | < 30s | MoviePy, 8–12 scenes |
| Caption gen time | < 20s | Whisper base, full audio |
| NVENC encode time | < 60s | GTX 1660 Super, 1080p |
| Total pipeline (per video) | < 3 min | End-to-end, with NVENC |
| Concurrent videos (workers=3) | 3 | 3 parallel pipelines |
| Daily throughput (overnight) | 160–200 | Overnight batch, 8h window |

### Layer 4 — Distribution Layer

| Platform | API | Auth |
|---|---|---|
| YouTube (multi-channel) | YouTube Data API v3 | OAuth 2.0 |
| TikTok | TikTok Content Posting API | OAuth 2.0 |
| Instagram Reels | (planned) | OAuth 2.0 |

### Layer 5 — Monetization Layer

| Stream | Method |
|---|---|
| YouTube AdSense | CPM from watch time |
| TikTok Creator Fund | Per-view payments |
| Affiliate marketing | Commission on linked product sales |
| TikTok Shop | Product promotions |

### Layer 6 — Feedback Loop

Runs daily at **06:50** via cron job.

```
Pull 48h metrics (views, likes, shares)
        │
        ▼
Score = ER_score × 0.6 + reach_score × 0.4
        │
        ├── score > 70  → Reindex into ChromaDB viral_scripts
        ├── score 40–70 → Store in DB, do not reindex
        └── score < 40  → Flag format as low-performing
```

---

## 4. LLM Strategy

### 4.1 Mode Comparison

| Criteria | Local — Qwen2.5 7B | Cloud — Gemini API |
|---|---|---|
| Cost | $0 | Free tier / Pay-as-go |
| Speed | 8–20 tok/s | ~100–200 tok/s |
| Script quality | Good (85% with RAG) | Very good (90%+) |
| Vietnamese | Good | Excellent (native multilingual) |
| Offline | ✅ Fully offline | ❌ Requires internet |
| Privacy | ✅ Data stays local | ⚠️ Data sent to Google |
| Rate limits | None | By tier |
| Setup time | 30 min | 5 min |
| Scalability | Limited by hardware | Unlimited |

### 4.2 Gemini API Free Tier (as of April 2026)

| Model | RPM | RPD | TPM | Best for |
|---|---|---|---|---|
| gemini-2.5-flash | 10 | 250 | 250k | Primary script generation |
| gemini-2.5-flash-lite | 15 | 1,000 | 250k | Batch / short-form content |
| ~~gemini-2.5-pro~~ | — | — | — | Removed from free tier Apr 2026 |

### 4.3 LLM Router — Decision Logic

```
Initializing mode?
  "local"  → Use Qwen2.5 7B via Ollama
  "gemini" → Use Gemini 2.5 Flash via Google AI API
  "auto"   → Check Ollama :11434 → if up: LOCAL, else: GEMINI
  "hybrid" → TikTok scripts → LOCAL | YouTube scripts → GEMINI

Runtime fallback:
  LOCAL fails  → auto-switch to GEMINI
  GEMINI quota → auto-switch to LOCAL
```

### 4.4 Hybrid Strategy Config

```python
LLM_STRATEGY = {
    "youtube_10min": { "llm": "gemini", "model": "gemini-2.5-flash" },
    "tiktok_60s":    { "llm": "local",  "model": "qwen2.5:7b" },
    "fallback":      { "llm": "gemini", "model": "gemini-2.5-flash-lite",
                       "trigger": "local_queue_size > 10" }
}
```

### 4.5 Mode Selection Guide

| Situation | Recommended Mode |
|---|---|
| Testing / prototyping | LOCAL |
| Machine with < 8GB RAM | GEMINI free |
| Fully offline / private | LOCAL only |
| < 200 videos/day (free) | GEMINI Flash-Lite free tier |
| Best Vietnamese quality | GEMINI Flash or Pro (paid) |
| > 1,000 videos/day | GEMINI Flash-Lite paid (~$5–10/month) |
| YouTube scripts | GEMINI Flash |
| TikTok scripts (volume) | LOCAL or GEMINI Flash-Lite |

---

## 5. Folder Structure

```
ai_media_company/
│
├── config/
│   ├── config.py                  # Global system configuration
│   ├── templates/
│   │   ├── tiktok_viral.json      # 9:16, 60s template
│   │   ├── tiktok_30s.json
│   │   ├── youtube_clean.json     # 16:9, 10min template
│   │   └── shorts_hook.json
│   └── prompts/
│       ├── tiktok_60s.txt
│       ├── youtube_10min.txt
│       └── base_rag.txt
│
├── scraper/
│   ├── tiktok_playwright.py       # Playwright scraper (backup)
│   ├── tiktok_research_api.py     # TikTok Research API (primary)
│   ├── apify_scraper.py           # Apify (backup)
│   └── trend_analyzer.py          # Viral pattern analysis
│
├── database/
│   ├── models.py                  # SQLAlchemy models
│   ├── migrations/                # Alembic migrations
│   └── queries.py                 # Common query helpers
│
├── vector_db/
│   ├── setup.py                   # ChromaDB init + collections
│   ├── indexer.py                 # PostgreSQL → ChromaDB sync
│   └── retriever.py               # Semantic search interface
│
├── rag/
│   ├── llm_router.py              # ★ Multi-LLM router
│   ├── rate_limiter.py            # Gemini rate limit manager
│   ├── prompt_builder.py          # RAG prompt construction
│   ├── script_writer.py           # Pipeline orchestrator
│   └── script_validator.py        # JSON output validator + auto-fix
│
├── pipeline/
│   ├── tts_engine.py              # Kokoro TTS wrapper
│   ├── asset_resolver.py          # 3-tier resolver: Asset DB → Pexels → Veo
│   ├── asset_db.py                # Video Asset Database interface (PG + file store)
│   ├── veo_prompt_builder.py      # Veo prompt constructor from scene + meta
│   ├── overlay_builder.py         # Text overlay renderer
│   ├── caption_gen.py             # Whisper ASR → SRT
│   ├── composer.py                # Scene assembler
│   └── renderer.py                # MoviePy final render
│
├── music/
│   ├── library_manager.py         # Local music library manager
│   └── selector.py                # Mood/niche-based track selection
│
├── uploader/
│   ├── youtube_uploader.py        # YouTube Data API v3
│   ├── tiktok_uploader.py         # TikTok Content Posting API
│   └── scheduler.py               # Post scheduling logic
│
├── feedback/
│   ├── tracker.py                 # Collect views / likes / shares
│   ├── scorer.py                  # Compute performance score
│   └── reindexer.py               # Feed top videos back to ChromaDB
│
├── batch_runner.py                # Main batch orchestrator
├── daily_pipeline.py              # Cron entry point
└── dashboard.py                   # CLI status dashboard
```

---

## 6. Data Architecture

### 6.1 PostgreSQL Schema

**viral_videos** — raw trending data scraped from TikTok / YouTube

| Column | Type | Description |
|---|---|---|
| id | TEXT PK | Platform video ID |
| platform | TEXT | `tiktok` or `youtube` |
| region | TEXT | `VN`, `US`, `TH` |
| niche | TEXT | `finance`, `health`, `lifestyle` |
| play_count | BIGINT | Total views |
| engagement_rate | FLOAT | (likes+comments+shares) / plays × 100 |
| script_text | TEXT | Transcript if available |
| hook_text | TEXT | Opening line |
| cta_text | TEXT | Closing call-to-action |
| is_indexed | BOOLEAN | Has been synced to ChromaDB |

**viral_patterns** — weekly trend aggregates per niche/region

| Column | Type | Description |
|---|---|---|
| niche, region, week_start | TEXT/DATE | Partition key |
| top_hooks | JSONB | `[{text, count, avg_er}]` |
| top_formats | JSONB | `[{format, count}]` |
| top_hashtags | JSONB | `[{tag, count}]` |
| best_post_hours | JSONB | `{hour: count}` |

**generated_scripts** — AI-generated scripts and their outcomes

| Column | Type | Description |
|---|---|---|
| topic, niche, template | TEXT | Script identity |
| script_json | JSONB | Full script object |
| upload_ids | JSONB | `{youtube: id, tiktok: id}` |
| performance_48h | JSONB | `{views, likes, shares, er}` |
| performance_score | FLOAT | 0–100 composite score |
| is_successful | BOOLEAN | score > 70 |

**upload_schedule** — future and past upload jobs

**assets** — local footage, image, and music library

### 6.2 ChromaDB Collections

| Collection | Content | Used for |
|---|---|---|
| `viral_scripts` | Full script text + metadata | Semantic topic matching |
| `viral_hooks` | Best hook sentences | Hook retrieval per niche |
| `viral_patterns` | Pattern summaries by niche/region | Trend context injection |

**Metadata schema per document:**

```python
{
    "video_id":        "tiktok_xxx",
    "niche":           "finance",
    "region":          "VN",
    "engagement_rate": 8.5,
    "play_count":      2400000,
    "duration":        58,
    "source":          "scraped" | "self_generated",
    "performance":     85.0,
}
```

### 6.3 Script JSON Schema

```json
{
  "meta": {
    "topic":     "5 thói quen buổi sáng tăng năng suất",
    "niche":     "lifestyle",
    "region":    "VN",
    "template":  "tiktok_60s"
  },
  "video": {
    "title":          "YouTube / TikTok title",
    "description":    "SEO-optimized description",
    "hashtags":       ["xuhuong", "lifestyle"],
    "total_duration": 62,
    "music_mood":     "uplifting"
  },
  "scenes": [
    {
      "id":             1,
      "type":           "hook",
      "duration":       4,
      "narration":      "Hook text for TTS...",
      "text_overlay":   "Overlay text on screen",
      "overlay_style":  "big_white_center",
      "visual_hint":    "morning productive person sunrise",
      "transition_out": "cut",
      "music_volume":   0.08
    }
  ],
  "cta": {
    "text":       "Follow để xem thêm tip hay!",
    "start_time": 55,
    "duration":   7
  },
  "affiliate": {
    "product":    "Product name",
    "link":       "https://...",
    "mention_at": 30
  }
}
```

---

## 7. Module Specifications

### 7.1 Scraper Module

```
Input:   Regions (VN/US), niches, keywords
Output:  Rows inserted into viral_videos table
Schedule: Daily at 07:00
SLA:     > 100 videos / region / day

Priority chain:
  1. TikTok Research API  (primary)
  2. Playwright scraper   (if quota exceeded)
  3. Apify actor          (if blocked)
  → trend_analyzer.py → viral_patterns table
```

### 7.2 RAG Script Writer

```
Input:   topic (str), niche (str), template (str)
Output:  script.json (validated)
Latency: 35–45 seconds per script
Quality: ~85% (vs 40% without RAG)

Flow:
  topic
   └─▶ ChromaDB.query(top_k=5)       ← similar scripts
   └─▶ ChromaDB.hooks(top_k=8)       ← top hooks for niche
   └─▶ PostgreSQL.patterns(niche)    ← current trend context
   └─▶ prompt_builder                ← assemble RAG prompt
   └─▶ LLM Router                   ← generate raw JSON
   └─▶ script_validator              ← validate + auto-fix
   └─▶ script.json                  ← final output
```

### 7.3 Video Pipeline

```
Input:   script.json + template_name
Output:  video_final.mp4 + metadata.json
Latency: 2–3 minutes per video
Output:  1080p / 30fps

Per-scene (parallel threads):
  scene[i]
    ├─▶ [Thread 1] TTS(narration)      → audio_i.wav
    ├─▶ [Thread 2] Pexels(visual_hint) → clip_i.mp4
    └─▶ [Thread 3] Overlay(text)       → overlay_i.png

Post-scene assembly:
  composer.assemble(scenes) → raw_video.mp4
  caption_gen.whisper(audio) → subtitles.srt
  renderer.encode(NVENC)     → video_final.mp4
```

### 7.4 Batch Runner

```
Config:
  script_workers:  2    (LLM generation)
  video_workers:   3    (parallel renders)
  daily_target:    200  (videos/day)
  overnight_limit: 160

Cron schedule:
  07:00  daily_pipeline.py --scan      (scrape trending)
  07:30  daily_pipeline.py --index     (sync to ChromaDB)
  08:00  batch_runner.py --daily-morning
  13:00  batch_runner.py --daily-afternoon
  22:00  batch_runner.py --overnight
  06:50  feedback/tracker.py --check-48h
```

### 7.5 Feedback Scoring

```
er_score    = engagement_rate × 10         (max 100)
reach_score = log10(views + 1) × 20        (max 100)
final_score = er_score × 0.6 + reach_score × 0.4

Actions:
  score > 70   → reindex into viral_scripts (self-training)
  score 40–70  → store in DB, skip reindex
  score < 40   → mark format as low-performing
```

---

## 8. Integration Map

### 8.1 External APIs

| Service | Endpoint | Auth | Free Tier | Paid Cost |
|---|---|---|---|---|
| TikTok Research API | research.tiktok.com | OAuth | 1,000 req/day | Apply separately |
| Pexels | api.pexels.com | API Key | 200 req/hr | Free sufficient |
| Apify | api.apify.com | Token | $5/month | Pay per use |
| YouTube Data v3 | googleapis.com | OAuth | 10k units/day | Quota-based |
| TikTok Content API | open.tiktok.com | OAuth | Apply | Free |
| Gemini API | ai.google.dev | API Key | 250–1000 req/day | $0.10–$0.30/1M tokens |
| Google Veo (via Gemini) | ai.google.dev | API Key (same) | Limited preview | ~$0.35/8s clip (approx.) |
| Suno | suno.com | Subscription | — | $10/month |

### 8.2 Internal Services

| Service | Port | Purpose |
|---|---|---|
| Ollama | :11434 | Local LLM inference (Qwen2.5 7B) |
| PostgreSQL | :5432 | Persistent relational storage |
| ChromaDB | file-based | Local vector similarity search |
| Whisper | subprocess | Speech-to-text for captions |

### 8.3 Hardware Configuration

| Component | Spec | Role |
|---|---|---|
| CPU | AMD Ryzen 9, 16 cores | Batch processing, Ollama inference |
| GPU | GTX 1660 Super, 6GB VRAM | h264_nvenc video encoding |
| RAM | 32 GB | Concurrent workers + model loading |
| Encode codec | h264_nvenc | GPU-accelerated render |
| LLM mode | CPU-only | Preserves VRAM for encoding |

---

## 9. Tech Stack & Cost

### 9.1 Full Tech Stack

| Layer | Tool | License | Cost |
|---|---|---|---|
| LLM Runtime | Ollama | MIT | Free |
| Local Model | Qwen2.5 7B Q4 | Apache 2.0 | Free |
| Cloud Model (primary) | Gemini 2.5 Flash | Google ToS | Free / $0.30/1M tokens |
| Cloud Model (batch) | Gemini 2.5 Flash-Lite | Google ToS | Free / $0.10/1M tokens |
| TTS | Kokoro ONNX | Apache 2.0 | Free |
| STT / Captions | Whisper base | MIT | Free |
| Vector DB | ChromaDB | Apache 2.0 | Free |
| Relational DB | PostgreSQL 16 | PostgreSQL | Free |
| Embeddings | SBERT Vietnamese | Apache 2.0 | Free |
| Video assembly | MoviePy | MIT | Free |
| Image processing | Pillow | HPND | Free |
| Encoder | ffmpeg + NVENC | LGPL | Free |
| Scraping | Playwright | Apache 2.0 | Free |
| Stock footage | Pexels API | Free tier | Free |
| AI video gen | Google Veo 2 / Veo 3 | Google ToS | ~$0.35/8s clip |
| Music | Suno Pro | Commercial | $10/month |
| Orchestration | cron / n8n | Apache 2.0 | Free |
| Language | Python 3.11 | PSF | Free |

### 9.2 Monthly Cost Estimates

| Configuration | Monthly Cost |
|---|---|
| 100% Local LLM | $10 (Suno only) |
| 100% Gemini free tier (< 250 vid/day) | $10 |
| Hybrid (local TikTok + Gemini YouTube) | $10–12 |
| Gemini Flash-Lite paid (200 vid/day) | ~$10.60 |
| Gemini Flash paid (200 vid/day) | ~$11.80 |
| With Apify backup scraper | add $5–10 |

### 9.3 Gemini Cost Calculation at Scale

```
200 videos/day × 1,000 tokens/script = 200,000 tokens/day

gemini-2.5-flash-lite:  200,000 × $0.10/1M = $0.02/day = ~$0.60/month
gemini-2.5-flash:       200,000 × $0.30/1M = $0.06/day = ~$1.80/month
```

---

## 10. Risk & Mitigation

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| TikTok API revoked | Medium | High | Playwright + Apify fallbacks |
| Pexels API changes | Low | Medium | Local cache + Pixabay backup |
| Veo generation timeout | Medium | Low | Auto-fallback to Pexels per scene |
| Veo cost overrun at scale | Medium | High | Hybrid mode — Veo for hook/CTA only |
| Gemini free tier cut further | High | Medium | Hybrid mode + local fallback |
| Gemini 429 rate limit | Medium | Low | `GeminiRateLimiter` class + local fallback |
| Gemini model deprecated | Medium | Low | Pin model version, monitor deprecation notices |
| Video Content ID claim | Medium | Medium | Suno Pro + YouTube Audio Library |
| Channel banned | Low | High | Multi-channel strategy, no spam |
| Disk full (video output) | High | Medium | Auto-cleanup after successful upload |
| NVENC driver crash | Low | Medium | Fallback to libx264 CPU encode |
| Qwen2.5 invalid JSON output | Medium | Low | `script_validator.py` auto-fix + retry |
| RAM OOM on large batches | Medium | Medium | `workers=3` cap, chunk batches |

---

## 11. KPIs & Success Metrics

### 11.1 Technical KPIs

| Metric | Month 1 Target | Month 3 Target |
|---|---|---|
| Video render success rate | > 95% | > 98% |
| Script valid JSON rate | 100% | 100% |
| Render time per video | < 3 minutes | < 2 minutes |
| Daily video output | 50 | 200 |
| System uptime | > 95% | > 99% |

### 11.2 Content KPIs

| Metric | Month 1 Target | Month 3 Target |
|---|---|---|
| TikTok engagement rate | > 2% | > 4% |
| YouTube click-through rate | > 3% | > 5% |
| YouTube average watch time | > 35% | > 45% |
| Videos reaching 100k views | 1–2 | 5–10 |

### 11.3 Business KPIs

| Metric | Month 1 | Month 3 | Month 6 |
|---|---|---|---|
| Gross revenue | $50–200 | $500–1,500 | $3,000–10,000 |
| Active channels | 3 | 6 | 10+ |
| Cost per video | < $0.10 | < $0.05 | < $0.03 |
| ROI | — | > 10× | > 50× |

---

## Appendix A — System Config Reference

```python
SYSTEM_CONFIG = {
    "hardware": {
        "gpu":         "GTX 1660 Super",
        "vram_gb":     6,
        "ram_gb":      32,
        "cpu_cores":   16,
        "video_codec": "h264_nvenc",
    },
    "llm_router": {
        "mode":           "auto",    # local | gemini | auto | hybrid
        "tiktok_engine":  "local",
        "youtube_engine": "gemini",
        "fallback":       "gemini",
    },
    "llm_gemini": {
        "model_primary": "gemini-2.5-flash",
        "model_batch":   "gemini-2.5-flash-lite",
        "api_key_env":   "GEMINI_API_KEY",
    },
    "batch": {
        "script_workers":  2,
        "video_workers":   3,
        "daily_target":    200,
        "overnight_limit": 160,
    },
    "render": {
        "fps":     30,
        "codec":   "h264_nvenc",
        "preset":  "fast",
        "crf":     23,
    },
}
```

## Appendix B — LLM Decision Cheat Sheet

| Situation | Use |
|---|---|
| Fresh setup, no config yet | LOCAL (fast, free) |
| Low RAM machine (< 8GB) | GEMINI free tier |
| Must be fully offline | LOCAL only |
| < 200 videos/day, free | GEMINI Flash-Lite free tier |
| 200–1,000 videos/day | HYBRID |
| > 1,000 videos/day | GEMINI Flash-Lite paid |
| YouTube scripts (quality matters) | GEMINI Flash |
| TikTok scripts (volume matters) | LOCAL or Flash-Lite |
| Data privacy required | LOCAL only |
| Ollama crashed / maintenance | Auto-fallback GEMINI |
| Gemini daily quota exhausted | Auto-fallback LOCAL |

## Appendix C — Quick Commands

```bash
# Test all LLM modes
python rag/llm_router.py --test local
python rag/llm_router.py --test gemini
python rag/llm_router.py --test auto

# Check Gemini quota remaining today
python rag/rate_limiter.py --status

# Manual scrape
python daily_pipeline.py --scan --region VN

# Generate a single test video
python batch_runner.py --topic "5 cách tiết kiệm" --template tiktok_viral --llm local
python batch_runner.py --topic "5 cách tiết kiệm" --template youtube_clean --llm gemini

# Daily batch (hybrid mode)
python batch_runner.py --file topics/today.csv --workers 3 --llm hybrid

# Check 7-day performance
python feedback/tracker.py --report --days 7

# CLI dashboard
python dashboard.py
```

---

*AI Media Automation — System Architecture v1.1*
*Internal document — 2026*
*1 Engineer + 1 Business = Fully automated content factory*
