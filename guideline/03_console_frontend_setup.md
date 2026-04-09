# Management Console — Frontend Setup & Usage Guide

> **Purpose:** Set up and run the web-based Management Console (React + FastAPI).
> **URL:** `http://localhost:5173` (frontend) → proxied to `http://localhost:8080` (API)
> **Stack:** React 18 · Vite · Tailwind CSS · FastAPI · Celery + Redis

---

## Architecture Overview

```
Browser (localhost:5173)
    ↕  Vite dev proxy
FastAPI (localhost:8080)   ← uvicorn / console/start.sh
    ↕
PostgreSQL + Redis + Celery workers
    ↕
Core pipeline modules (scraper/, rag/, pipeline/, uploader/, feedback/)
```

The frontend never talks to the pipeline directly — all pipeline actions go through FastAPI as Celery tasks that return a `task_id` immediately.

---

## First-Time Setup

### Step 1 — Configure backend environment

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console

cp .env.example .env
```

Edit `console/.env`:

```bash
# Database (must exist — create with: createdb ai_media)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_media

# Security — generate with: python3 -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET=your_jwt_secret_here

# Fernet key for encrypting OAuth tokens — generate with:
# python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FERNET_KEY=your_fernet_key_here

# Redis (default local)
REDIS_URL=redis://localhost:6379/0

# Optional — set if you want Gemini from the console too
GEMINI_API_KEY=your_key_here
```

`FERNET_KEY` is required for the credentials, uploads, and scheduled token refresh flows. If it is blank or invalid, the console startup now stops early instead of letting Celery fail later when it tries to decrypt stored OAuth secrets.

### Step 2 — Create the database

```bash
createdb ai_media
```

Or in psql:
```sql
CREATE DATABASE ai_media;
```

### Step 3 — Install backend dependencies

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console
pip install -r requirements.txt
```

### Step 4 — Run migrations

Always run from `console/backend/`:
```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/backend
alembic upgrade head
cd ../..
```

Expected: migrations 001, 002, 003 applied.

### Step 5 — Install frontend dependencies

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/frontend
npm install
```

---

## Starting the Console

### Option A — One command (recommended)

Run from the **project root**:
```bash
cd /Volumes/SSD/Workspace/ai-media-automation
./console/start.sh
```

This starts: migrations → Redis check → Celery workers → FastAPI (port 8080).

Then in a **separate terminal**, start the frontend:
```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/frontend
npm run dev
```

Open: **http://localhost:5173**

---

### Option B — Manual start (debugging)

```bash
# Terminal 1 — FastAPI backend
cd /Volumes/SSD/Workspace/ai-media-automation
uvicorn console.backend.main:app --port 8080 --reload

# Terminal 2 — Celery worker (all queues)
cd /Volumes/SSD/Workspace/ai-media-automation
celery -A console.backend.celery_app worker --loglevel=info \
  -Q scrape_q,script_q,render_q,upload_q

# Terminal 3 — Celery beat (scheduled tasks: token refresh)
cd /Volumes/SSD/Workspace/ai-media-automation
celery -A console.backend.celery_app beat --loglevel=info

# Terminal 4 — Frontend
cd /Volumes/SSD/Workspace/ai-media-automation/console/frontend
npm run dev
```

---

## First Login

1. Open **http://localhost:5173**
2. Register the first admin account:

```bash
curl -X POST http://localhost:8080/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "email": "admin@example.com", "password": "changeme", "role": "admin"}'
```

Or via API docs at **http://localhost:8080/docs** → `POST /api/auth/register`.

3. Log in with those credentials on the login page.

> **Note:** After the first admin is created, subsequent registrations require an admin JWT token.

---

## Console Tabs

| Tab | Role | Purpose |
|-----|------|---------|
| **Scraper** | admin + editor | View scraped TikTok videos, manage scraper sources, trigger manual scrapes |
| **Scripts** | admin + editor | Review, approve, reject, edit, and regenerate AI scripts |
| **Production** | admin + editor | Assemble scene assets, trigger TTS regen, start video rendering |
| **Uploads** | admin + editor | Manage YouTube/TikTok channels, OAuth credentials, schedule uploads |
| **Pipeline** | admin + editor | Monitor Celery job queue, view running/failed tasks, retry jobs |
| **LLM** | admin only | Configure LLM mode (local/gemini/auto/hybrid), test prompts |
| **Performance** | admin + editor | View video performance metrics, quality scores, top performers |
| **System** | admin only | System resource usage (CPU/GPU/disk), service health checks |

---

## Typical Editor Workflow

```
Scraper tab  →  trigger scrape  →  videos appear in table
    ↓
Scripts tab  →  review generated scripts  →  approve / reject / edit
    ↓
Production tab  →  select approved script  →  swap scene assets  →  render
    ↓
Uploads tab  →  pick channels  →  schedule upload
    ↓
Performance tab  →  monitor views / engagement after 24h
```

---

## API Reference

Full interactive docs at: **http://localhost:8080/docs**

Key endpoints:

```
POST  /api/auth/login              → returns JWT token
POST  /api/auth/register           → admin only after first user

GET   /api/scraper/sources         → list scraper source configs
POST  /api/scraper/run             → trigger manual scrape (Celery task)
GET   /api/scraper/videos          → paginated scraped video list

GET   /api/scripts                 → list scripts (filterable by status)
POST  /api/scripts/generate        → generate new script (Celery task)
GET   /api/scripts/{id}            → full script detail
PUT   /api/scripts/{id}            → update script content
PATCH /api/scripts/{id}/approve    → approve for production
PATCH /api/scripts/{id}/reject     → reject with reason
POST  /api/scripts/{id}/regenerate → regenerate full script via LLM
POST  /api/scripts/{id}/scenes/{n}/regenerate  → regenerate single scene
```

---

## Script Status Workflow

```
draft
  ↓  (editor submits for review)
pending_review
  ↓               ↘
approved         rejected  (back to draft if re-edited)
  ↓
editing           (approved script being modified — returns to approved on save)
  ↓
producing         (render started)
  ↓
completed         (video_final.mp4 produced and uploaded)
```

---

## Frontend Development

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/frontend

npm run dev      # dev server with HMR → http://localhost:5173
npm run build    # production build → dist/
npm run preview  # preview production build locally
```

### Proxy config (`vite.config.js`)

All `/api/*` requests are proxied to `http://localhost:8080` — the backend must be running.  
All `/ws/*` requests are proxied as WebSocket to `ws://localhost:8080`.

### Key source files

| File | Purpose |
|------|---------|
| `src/App.jsx` | Sidebar nav, login guard, role-based tab filtering |
| `src/api/client.js` | JWT-in-memory fetch wrapper, API helpers per module |
| `src/hooks/useApi.js` | Data-fetching hook with loading/error state |
| `src/components/index.jsx` | Shared UI: Card, Badge, Button, Modal, Toast, Spinner, etc. |
| `src/pages/ScraperPage.jsx` | Scraper stats, source manager, video table |
| `src/pages/ScriptsPage.jsx` | Status tabs, bulk approve/reject, script editor modal |
| `src/pages/ProductionPage.jsx` | Scene timeline, asset browser, TTS regen |
| `src/pages/PipelinePage.jsx` | Job queue monitor, batch controls |
| `src/pages/UploadsPage.jsx` | Channel management, OAuth credentials |
| `src/pages/PerformancePage.jsx` | Metrics dashboard, quality scores |

### Design tokens (Tailwind)

| Color | Value | Usage |
|-------|-------|-------|
| Page bg | `#0d0d0f` | Page background |
| Surface | `#16161a` | Sidebar, cards |
| Border | `#2a2a32` | Dividers, inputs |
| Primary text | `#e8e8f0` | Main text |
| Muted text | `#9090a8` | Labels, secondary |
| Accent purple | `#7c6af7` | Active nav, buttons |
| Green | `#34d399` | Success, approved |
| Red | `#f87171` | Error, rejected |
| Yellow | `#fbbf24` | Warning, pending |
| Blue | `#4a9eff` | Info, editing |

Font: **IBM Plex Mono** (numbers/code) · **IBM Plex Sans** (body)

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `npm run dev` — blank page | Backend not running — start `./console/start.sh` first |
| `401 Unauthorized` on all API calls | JWT expired — log out and log in again |
| `422 Unprocessable Entity` on register | Check request body matches schema (see `/docs`) |
| Celery tasks stuck in `PENDING` | Redis not running — `brew services start redis` |
| `alembic: target database is not up to date` | Run `alembic upgrade head` from `console/backend/` |
| Frontend shows old data after backend change | Hard reload: `Cmd+Shift+R` |
| `CORS error` in browser console | Backend not running on port 8080 or `start.sh` not from project root |
| Token refresh not working | Check `FERNET_KEY` is set in `console/.env` |

---

*Guide version: April 2026 — AI Media Automation Project*
