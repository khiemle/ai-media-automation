# Channel Plans — Feature Design

**Date:** 2026-05-02
**Status:** Approved

---

## Overview

Add a **Channel Plans** feature that lets users import, edit, and leverage Markdown-based channel strategy documents (e.g. `Channel_Launch_Plan_ASMR.md`) as first-class entities in the management console. Each plan powers three AI features (SEO generation, prompt generation, Q&A) via Gemini and drives a richer "New Video" creation flow in the YouTube Videos page.

---

## Scope

Two surfaces are affected:

1. **New "Channel Plans" page** — dedicated management tab (import, view, edit, AI assistant)
2. **Modified "YouTube Videos" page** — channel plans accordion + AI Autofill in New Video modal

---

## Data Model

### New table: `channel_plans`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | auto-increment |
| `name` | text NOT NULL | e.g. "ASMR Sleep & Relax" — extracted from MD H1 |
| `slug` | text UNIQUE NOT NULL | e.g. "asmr" — used in API paths and UI labels |
| `focus` | text | extracted from Overview table "Focus" row |
| `upload_frequency` | text | e.g. "3–4 video/tuần" |
| `rpm_estimate` | text | e.g. "$10–$11" |
| `md_content` | text NOT NULL | full raw markdown of the channel plan |
| `md_filename` | text | original filename (e.g. `Channel_Launch_Plan_ASMR.md`) |
| `channel_id` | int FK → channels | optional — links to actual YouTube channel for upload targeting |
| `created_at` | timestamptz | server default now() |
| `updated_at` | timestamptz | updated on every PUT |

**Metadata extraction logic (import + save):**
Parse the markdown at import time and on every save. Extract from the `## 1. Tổng quan kênh` overview table:
- `name` — from the H1 heading (`# Channel Launch Plan — {name}`)
- `slug` — auto-derived from the filename: strip `Channel_Launch_Plan_` prefix and `.md` suffix, lowercase (e.g. `Channel_Launch_Plan_ASMR.md` → `asmr`)
- `focus` — row where col1 = "**Focus**"
- `upload_frequency` — row where col1 = "**Upload frequency**"
- `rpm_estimate` — row where col1 = "**RPM ước tính**"

**No changes to existing tables.** `VideoTemplate`, `Channel`, and all other tables are untouched.

---

## Backend

### New files

| File | Purpose |
|---|---|
| `models/channel_plan.py` | SQLAlchemy model |
| `services/channel_plan_service.py` | CRUD + metadata parser + AI methods |
| `routers/channel_plans.py` | FastAPI router, registered in `main.py` |
| `alembic/versions/012_channel_plans.py` | Migration: creates `channel_plans` table |

### API endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/channel-plans` | editor+ | List all plans (metadata only, no `md_content`) |
| `POST` | `/api/channel-plans/import` | editor+ | Multipart `.md` file upload — parse, store |
| `GET` | `/api/channel-plans/{id}` | editor+ | Get one plan including full `md_content` |
| `PUT` | `/api/channel-plans/{id}` | editor+ | Save edited `md_content`, re-parse metadata |
| `DELETE` | `/api/channel-plans/{id}` | admin | Delete plan |
| `POST` | `/api/channel-plans/{id}/ai/seo` | editor+ | Gemini → `{title, description, tags}` |
| `POST` | `/api/channel-plans/{id}/ai/prompts` | editor+ | Gemini → `{suno, midjourney, runway, thumbnail}` |
| `POST` | `/api/channel-plans/{id}/ai/ask` | editor+ | Gemini → plain text answer |
| `POST` | `/api/channel-plans/{id}/ai/autofill` | editor+ | Gemini → all New Video modal fields |

**AI endpoint request bodies:**
- `/ai/seo`, `/ai/prompts`, `/ai/autofill` → `{ "theme": "Heavy Rain on Window", "context": "optional extra context" }`
- `/ai/ask` → `{ "question": "What is the recommended upload schedule?" }`

**AI endpoint response shapes:**
- `/ai/seo` → `{ "title": "...", "description": "...", "tags": "tag1, tag2, ..." }`
- `/ai/prompts` → `{ "suno": "...", "midjourney": "...", "runway": "...", "thumbnail": "..." }`
- `/ai/ask` → `{ "answer": "..." }`
- `/ai/autofill` → `{ "title": "...", "description": "...", "tags": "...", "suno_prompt": "...", "runway_prompt": "...", "target_duration_h": 8 }`

### Gemini integration

`ChannelPlanAIService` (inside `channel_plan_service.py`) uses the existing `GEMINI_API_KEY` from `api_config`. All calls share this system prompt structure:

```
You are an expert YouTube content strategist.
Below is the full channel launch plan for this channel:

---
{md_content}
---

{task-specific instruction}
```

**Per-endpoint task instructions:**

| Endpoint | Instruction |
|---|---|
| `/ai/seo` | Generate 1 YouTube title (≤70 chars), 1 description (≤300 chars), and 10 comma-separated tags for theme `{theme}`. Return JSON `{title, description, tags}`. |
| `/ai/prompts` | Generate a Suno prompt, a Midjourney prompt, a Runway Gen-4 prompt, and a Thumbnail prompt (based on the Midjourney prompt you just wrote) for theme `{theme}`. Follow the prompt formats defined in the channel plan. Return JSON `{suno, midjourney, runway, thumbnail}`. |
| `/ai/ask` | Answer this question about the channel: `{question}` |
| `/ai/autofill` | Fill all video creation fields for theme `{theme}`: title, description, tags, suno_prompt, runway_prompt, recommended target_duration_h. Return JSON `{title, description, tags, suno_prompt, runway_prompt, target_duration_h}`. |

---

## Frontend

### New files

| File | Purpose |
|---|---|
| `pages/ChannelPlansPage.jsx` | New Channel Plans management page |
| `components/AIAssistantPanel.jsx` | Shared AI features panel (SEO / Prompts / Q&A) — used in both ChannelPlansPage and YouTubeVideosPage |
| `api/client.js` | Add `channelPlansApi` methods |

### Channel Plans Page

**Route/nav:** New sidebar entry "Channel Plans", between "YouTube Videos" and "Uploads", accessible to `admin` and `editor`.

**List view (default):**
- Header: "Channel Plans" + count + "Import Plan" button
- Cards grid: one card per plan showing `name`, `focus`, `upload_frequency`, `rpm_estimate`, `md_filename`, optional linked channel badge
- Click card → opens Detail panel

**Detail panel (right slide-over, full height):**
- Header: plan name + "Save" button + close (✕)
- Two tabs: **Plan** | **AI Assistant**

**Plan tab:**
- Metadata strip: 4 chips — focus, upload_frequency, rpm_estimate, linked channel (if set)
- Channel link field: dropdown of existing `Channel` rows (platform=youtube) — selecting one sets `channel_id` and is saved with the "Save" action
- Body: `<textarea>` with raw `md_content`, monospace font, full height, auto-resize
- "Save" → `PUT /api/channel-plans/{id}` → updates DB + re-renders metadata chips on success

**AI Assistant tab — three sections (accordion):**

1. **SEO**
   - Inputs: theme text field + optional context text field
   - "Generate" button → calls `/ai/seo` → shows title / description / tags blocks, each with a Copy button

2. **Prompts**
   - Inputs: theme text field + optional context text field
   - "Generate All" button → calls `/ai/prompts` → shows 4 blocks: Suno / Midjourney / Runway / Thumbnail
   - Thumbnail block labelled "Thumbnail (based on Midjourney)"
   - Each block has a Copy button

3. **Q&A**
   - Single question text field
   - "Ask" button → calls `/ai/ask` → shows answer block below

**AI UX rules (all three sections):**
- Button shows spinner + is disabled during generation
- Inputs disabled during generation
- Errors shown as inline red text below the button (not toast) — preserves input state for retry

**Import flow:**
- "Import Plan" button → small modal: `.md` file picker only + "Import" button
- `POST /api/channel-plans/import` (multipart)
- On success: new card appears in list, slide-over opens for the new plan, toast confirms import

---

### YouTube Videos Page (modifications)

**Header row:** Remove dynamically-rendered `+ New {template.label}` buttons. Replace with a single **"+ New Video"** button.

**Channel Plans accordion** (inserted between header and filters):
- Collapsed by default — toggle bar shows "Channel Plans (N)"
- Expanded: compact list of channel plan rows
  - Each row: plan name · focus chip · rpm chip · chevron (▶)
  - Click row → expands inline to show:
    - 4 metadata chips
    - `AIAssistantPanel` component (shared with ChannelPlansPage)
    - **"+ New Video for this channel"** button

**"+ New Video" button behaviour:**
- From channel row → opens `CreationPanel` with channel plan pre-selected
- From header button → opens `CreationPanel` with a channel plan picker dropdown as the first field

**`CreationPanel` changes:**
- Add read-only "Channel Plan" field at top (shows plan name)
- Add **"✦ AI Autofill"** button in the panel header (next to the title)
- AI Autofill → enabled only when `theme` field is non-empty
- On click → calls `/api/channel-plans/{id}/ai/autofill` with current `theme`
- Fills: `seo_title`, `seo_description`, `seo_tags`, `suno_prompt` (reference block), `runway_prompt` (reference block), `target_duration_h` (selects matching preset or sets custom)
- All fields remain editable after autofill
- Autofill button shows spinner during call; inline error on failure

---

## Out of Scope

- WYSIWYG / rich-text editing of MD content (raw textarea only)
- Parsing MD into individual structured fields beyond the 5 metadata columns
- Linking a channel plan to a `VideoTemplate` (user picks template at video creation time, unchanged)
- Streaming Gemini responses (single-shot responses only)
- Channel plan versioning / history

---

*Implementation plan to follow via writing-plans skill.*
