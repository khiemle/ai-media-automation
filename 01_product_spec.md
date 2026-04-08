# AI Media Management Console — Product Specification

> **Version:** 1.0 | **Date:** April 2026
> **Product:** Management Console for AI Media Automation System
> **Team:** 1 Engineer + 1 Business | **Target:** 4-week build

---

## 1. Product Overview

### 1.1 Problem Statement

The AI Media Automation system (v1.1) operates as a fully automated pipeline — scrape, generate, produce, upload, measure. However, the current system lacks a human control layer. Editors and admins have no way to:

- Curate scraped data and pick the best trends for content
- Review LLM-generated scripts before they enter production
- Adjust video scenes (replace clips, change audio, edit overlays) mid-pipeline
- Manage OAuth credentials and upload channels without touching config files
- Monitor pipeline health, performance, or LLM quotas in real time

### 1.2 Solution

Build a **web-based Management Console** that wraps around the existing automation core, providing editorial control at every stage of the pipeline while preserving the system's ability to run fully automated when desired.

### 1.3 Core Principles

- **Non-invasive integration.** The console reads from and writes to the same PostgreSQL database and file system the core pipeline already uses. It does not replace any pipeline module — it adds a control layer above them.
- **Human-in-the-loop optional.** Every feature supports both "auto" (system decides) and "manual" (editor decides) modes. The system can still run overnight in full-auto batch mode.
- **API-first.** The console is a React frontend consuming a REST API. The same API can later power a mobile app, Slack bot, or n8n webhooks.
- **One engineer can build it.** Tech choices prioritize simplicity: FastAPI backend, React frontend, the existing PostgreSQL instance.

### 1.4 Users

| Role | Description | Primary Actions |
|------|-------------|-----------------|
| **Admin** | The engineer who runs the system | System config, auth credentials, LLM mode, batch controls, cron management |
| **Editor** | The business person who curates content | Review scraped data, select topics, edit scripts, adjust video scenes, approve uploads |

---

## 2. Module Specifications

### 2.1 Scraper Management

**Purpose:** Give editors visibility into scraped trending data, let them select high-potential videos as RAG context, and generate script topics from curated selections.

| Feature | Description | Priority |
|---------|-------------|----------|
| Source Manager | View, enable/disable scraper sources (TikTok Research API, Playwright, Apify). Architecture supports future sources (YouTube Trending, news websites like VnExpress, Tuổi Trẻ) via a pluggable adapter interface | P0 |
| Scraped Data Browser | Tabular view of all scraped videos with columns: hook text, author, play count, ER, niche, region, tags, indexed status. Supports filtering by source, niche, region, and sorting by views/ER/likes | P0 |
| Multi-select & Topic Creation | Editor selects 1–N scraped videos, clicks "Generate Script", enters a topic/niche/template, and the system sends the selected videos as RAG context to the LLM Router for script generation | P0 |
| Manual Scrape Trigger | Button to trigger an immediate scrape run outside the cron schedule | P1 |
| ChromaDB Index Control | Manually index or de-index selected videos from the vector database | P1 |
| Source Plugin API | Adapter interface for adding new scraper sources without modifying core code. Each adapter implements `scrape(config) → list[ScrapedVideo]` | P2 |

**Data Model:** Reads from existing `viral_videos` and `viral_patterns` tables. No schema changes.

**Integration:** Scraper Manager → `viral_videos` table → `rag/script_writer.py` → `generated_scripts` table.

---

### 2.2 Script Editor

**Purpose:** Allow editors to review, edit, approve, or reject LLM-generated scripts before they enter the production pipeline.

| Feature | Description | Priority |
|---------|-------------|----------|
| Script List with Status Workflow | Scripts flow through: `draft` → `pending_review` → `approved` (or back to `draft` on rejection). Only `approved` scripts enter the production queue | P0 |
| Full Script Editor | Edit all fields of `script.json`: topic, niche, template, title, description, hashtags, voice, speed, mood, CTA, affiliate links | P0 |
| Scene-level Editing | Per-scene: edit narration text, visual hint, text overlay, overlay style, duration, type (hook/body/transition/cta), transition type. Reorder scenes with drag or arrow buttons. Add/remove scenes | P0 |
| LLM Regeneration | One-click regenerate entire script or individual scenes using the LLM Router, preserving the editor's other edits | P0 |
| Bulk Approve/Reject | Select multiple scripts and approve or reject in one action | P1 |
| Script Diff View | Show what the LLM generated vs. what the editor changed | P2 |

**Data Model:** Uses `generated_scripts` table. Adds columns: `status` (enum), `editor_notes` (text), `edited_by` (FK), `approved_at` (timestamp).

**Integration:** Reads/writes `generated_scripts.script_json`. When approved, the batch runner picks it up.

---

### 2.3 Production Editor

**Purpose:** Give editors visual control over the video production process — replace scene clips, regenerate audio, adjust overlays — before final rendering.

| Feature | Description | Priority |
|---------|-------------|----------|
| Visual Timeline | Proportional horizontal bar showing all scenes by duration. Click a scene to expand its editor | P0 |
| Scene Asset Replacement | Per-scene: browse the Video Asset DB (Tier 1), search Pexels (Tier 2A), or trigger a Veo generation (Tier 2B). Select a replacement clip from a visual grid | P0 |
| Audio Regeneration | Re-run Kokoro TTS for a scene after editing its narration text. Option to upload a custom audio file | P0 |
| Asset DB Browser | Full-screen modal to search the `video_assets` table by keywords, niche, source, duration. Shows thumbnail grid with metadata | P0 |
| Overlay Editing | Edit text overlay content and style (5 built-in styles). Live preview of text on a colored placeholder | P1 |
| Asset Resolver Mode | Switch between `db_only`, `db_then_pexels`, `db_then_veo`, `db_then_hybrid` from the UI | P1 |
| Render Preview | Generate a low-res preview before committing to full NVENC render | P2 |

**Data Model:** Reads/writes `generated_scripts.script_json` (scenes array). Reads `video_assets` table.

**Integration:** Calls `pipeline/asset_resolver.py`, `pipeline/tts_engine.py`, `pipeline/overlay_builder.py` as Celery tasks. After editor approves, `script.json` passes to `pipeline/composer.py`.

---

### 2.4 Upload & Distribution Manager

**Purpose:** Manage OAuth credentials for all platforms, configure channels, assign target channels to videos, and control the upload queue.

| Feature | Description | Priority |
|---------|-------------|----------|
| Production Videos List | All rendered videos with status, template, niche, target channels, schedule, views. Delete option per video | P0 |
| Multi-Channel Targeting | Each video can target multiple channels across platforms. Default channels auto-assigned based on template. Editor can override via multi-select dropdown | P0 |
| OAuth Credential Manager | Per-platform: store client ID/secret, redirect URI, scopes. Initiate OAuth flow, view/refresh access tokens, monitor token expiry, test connection | P0 |
| Channel Management | CRUD for channels: name, platform, email, category, language, monetization status | P0 |
| Upload Controls | Upload All Ready, Pause All, Refresh All Tokens, Optimize Schedule | P0 |
| Default Upload Settings | Per-platform defaults: privacy, category, language, comments | P1 |
| Environment Variable Export | Export/import all credentials as a `.env` file | P1 |

**Template → Default Channel Mapping:**

| Template | Default Channels |
|----------|-----------------|
| `tiktok_viral` | HealthHub + FitnessPro (TikTok) |
| `tiktok_30s` | HealthHub (TikTok) |
| `youtube_clean` | MainChannel + LifestyleVN (YouTube) |
| `shorts_hook` | MainChannel + FinanceTips (YouTube) |

**Data Model:** New tables: `platform_credentials`, `channels`, `template_channel_defaults`, `upload_targets`.

**Integration:** Calls `uploader/youtube_uploader.py` and `uploader/tiktok_uploader.py` with stored OAuth credentials.

---

### 2.5 Pipeline Monitor

| Feature | Description | Priority |
|---------|-------------|----------|
| Job List | All jobs with status, progress %, LLM used, duration, error message | P0 |
| Batch Controls | Start/pause batch, adjust worker counts, queue overnight, cancel all queued | P0 |
| Job Actions | Retry failed, cancel active, expand for details | P0 |
| Live Updates | WebSocket-powered real-time progress without polling | P0 |
| Status Filters | Filter by status, LLM, template, niche | P1 |

---

### 2.6 LLM Router Control

| Feature | Description | Priority |
|---------|-------------|----------|
| Mode Selector | Switch between local/gemini/auto/hybrid | P0 |
| Quota Monitor | Gemini RPD/RPM usage, Ollama health, average latency | P0 |
| Hybrid Routing Config | Edit which LLM handles which template | P1 |
| Rate Limiter Dashboard | Per-model usage bars, auto-fallback status | P1 |

---

### 2.7 Performance & Feedback

| Feature | Description | Priority |
|---------|-------------|----------|
| 14-day Dashboard | Charts: daily video output, total views, average ER, revenue | P0 |
| Feedback Scoring View | Scoring formula, reindexed count (>70), low-performers (<40) | P0 |
| Per-niche Breakdown | ER and views grouped by niche | P1 |
| Top Performing Videos | Ranked list with links | P1 |

---

### 2.8 System Health

| Feature | Description | Priority |
|---------|-------------|----------|
| Resource Gauges | CPU, GPU, RAM, Disk with warning thresholds | P0 |
| Service Status | Green/yellow/red for PostgreSQL, ChromaDB, Ollama, NVENC, Kokoro, Whisper, ffmpeg, Pexels | P0 |
| Cron Schedule | All scheduled jobs with status and last-run time | P0 |
| Error Log | Last 24h of errors from all pipeline modules | P0 |

---

## 3. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Page load time | < 2s |
| API response time (reads) | < 200ms |
| API response time (writes) | < 500ms |
| WebSocket latency | < 100ms |
| Concurrent users | 2–5 |
| Browser support | Chrome 120+, Firefox 120+, Safari 17+ |
| Authentication | JWT with 24h expiry, role-based (admin/editor) |
| Secrets | Encrypted at rest (Fernet) |
| Audit | All write operations logged with user, action, target, timestamp |

---

*Product Specification v1.0 — April 2026*
