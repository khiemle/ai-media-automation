# Deployment Design — Windows Single-Machine + GitHub Actions CI/CD

**Date:** 2026-05-02  
**Status:** Approved

---

## Overview

Deploy the full AI Media Automation stack to a single Windows machine (ASUS TUF, NVIDIA GTX 1660 Super). Mac is development-only — engineers push to GitHub, GitHub Actions builds Docker images and the self-hosted runner on Windows deploys them automatically.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  WINDOWS (docker-compose.yml)  GTX 1660S               │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────┐   │
│  │ frontend │  │   api    │  │  celery-worker     │   │
│  │ (Nginx)  │  │(FastAPI) │  │  scrape_q          │   │
│  │  :3000   │  │  :8080   │  │  script_q          │   │
│  └──────────┘  └──────────┘  │  upload_q          │   │
│                               └────────────────────┘   │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────┐   │
│  │  redis   │  │ postgres │  │  celery-render     │   │
│  │  :6379   │  │  :5432   │  │  render_q (NVIDIA) │   │
│  └──────────┘  └──────────┘  └────────────────────┘   │
│                                                         │
│  + Self-hosted GitHub Actions runner (bare metal)       │
└─────────────────────────────────────────────────────────┘

MAC = development only (code → git push → GitHub → Windows)
```

---

## Docker Images

Three images, each built by GitHub Actions and pushed to GitHub Container Registry (GHCR).

### `Dockerfile.api` (existing, minor update)
- **Base:** `python:3.11-slim`
- **Deps:** `console/requirements.txt` only
- **Change:** Remove `alembic upgrade head` from CMD — migrations run as a one-off deploy step
- **Used by:** `api`, `celery-worker`, `celery-beat`

### `Dockerfile.render` (new)
- **Base:** `nvidia/cuda:12.3.2-runtime-ubuntu22.04`
- **System deps:** `ffmpeg`, `libsndfile1`, `libgomp1` (ONNX)
- **Deps:** `console/requirements.txt` + `requirements.pipeline.txt`
- **Used by:** `celery-render` only
- **Why separate:** Needs CUDA base + pipeline deps. Keeping it separate avoids bloating the API image with GPU/pipeline tooling.

### `Dockerfile.frontend` (existing)
- **Base:** `node:20-alpine` → `nginx:alpine`
- **Requires:** `nginx.conf` (new file)
- **Used by:** `frontend`

---

## docker-compose.yml (Windows)

Replaces `docker-compose.console.yml`.

| Service | Image | Ports | Queues / Notes |
|---|---|---|---|
| `postgres` | `postgres:16-alpine` | 5432 | volume: `postgres_data` |
| `redis` | `redis:7-alpine` | 6379 | |
| `api` | `ghcr.io/.../api:latest` | 8080 | env: `console/.env` |
| `celery-worker` | `ghcr.io/.../api:latest` | — | scrape_q, script_q, upload_q |
| `celery-beat` | `ghcr.io/.../api:latest` | — | beat scheduler |
| `celery-render` | `ghcr.io/.../render:latest` | — | render_q, NVIDIA GPU device |
| `frontend` | `ghcr.io/.../frontend:latest` | 3000 | Nginx, proxies `/api` and `/ws` to api:8080 |

`celery-render` NVIDIA reservation:
```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

---

## nginx.conf

```
/api/*  → proxy_pass http://api:8080
/ws/*   → proxy_pass http://api:8080 (WebSocket upgrade)
/*      → /usr/share/nginx/html, try_files → index.html
```

Single port (3000) serves both the React SPA and proxies the API — no CORS issues in production.

---

## CI/CD Pipeline — `.github/workflows/deploy.yml`

**Trigger:** push to `main`, or manual `workflow_dispatch`.

### Job 1: `build` (GitHub-hosted, `ubuntu-latest`)

Builds all three images in parallel, pushes to GHCR using `GITHUB_TOKEN` (no extra secret needed).

```
build-api      → Dockerfile.api      → ghcr.io/<owner>/ai-media/api:latest
build-render   → Dockerfile.render   → ghcr.io/<owner>/ai-media/render:latest
build-frontend → Dockerfile.frontend → ghcr.io/<owner>/ai-media/frontend:latest
```

### Job 2: `deploy` (self-hosted Windows runner)

Runs after `build` succeeds. Steps:
1. Checkout repo
2. Write `console/.env` from GitHub Secrets (PowerShell)
3. Write `config/api_keys.json` from GitHub Secrets (PowerShell)
4. Write `pipeline.env` from GitHub Secrets + Variables (PowerShell)
5. `docker compose pull` — pull latest images from GHCR
6. Run migrations — one-off container: `alembic upgrade head`
7. `docker compose up -d` — restart all services

Env file generation uses PowerShell `Out-File -Encoding utf8NoBOM` to avoid BOM issues with Python dotenv parsers.

---

## Three Generated Files (never committed to git)

### `console/.env`
```
DATABASE_URL=postgresql://admin:<DB_PASSWORD>@postgres:5432/ai_media
REDIS_URL=redis://redis:6379/0
JWT_SECRET=<JWT_SECRET>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
FERNET_KEY=<FERNET_KEY>
CORE_PIPELINE_PATH=/app
CONSOLE_PORT=8080
FRONTEND_ORIGIN=http://localhost:3000
ENV=production
```

Note: `localhost` in DATABASE_URL/REDIS_URL replaced with Docker service names (`postgres`, `redis`).

### `config/api_keys.json`
```json
{
  "gemini": {
    "script": { "api_key": "<GEMINI_SCRIPT_API_KEY>", "model": "gemini-2.5-flash" },
    "media":  { "api_key": "<GEMINI_MEDIA_API_KEY>",  "model": "veo-3.1-lite-generate-preview" },
    "music":  { "api_key": "<GEMINI_MEDIA_API_KEY>",  "model": "lyria-3-clip-preview" }
  },
  "elevenlabs": {
    "api_key":     "<ELEVENLABS_API_KEY>",
    "voice_id_en": "<ELEVENLABS_VOICE_ID_EN>",
    "voice_id_vi": "<ELEVENLABS_VOICE_ID_VI>",
    "model":       "eleven_flash_v2_5"
  },
  "suno":    { "api_key": "<SUNO_API_KEY>", "model": "V4_5" },
  "sunoapi": { "api_key": "<SUNO_API_KEY>" },
  "pexels":  { "api_key": "<PEXELS_API_KEY>" }
}
```

### `pipeline.env`
```
OUTPUT_PATH=<OUTPUT_PATH>
ASSET_DB_PATH=<ASSET_DB_PATH>
MODELS_PATH=<MODELS_PATH>
MUSIC_PATH=<MUSIC_PATH>
TTS_ENGINE=auto
TIKTOK_SCRAPER_ENGINE=auto
TIKTOK_BROWSER_HEADLESS=true
TIKTOK_BROWSER_HEADFUL_RETRY_ON_EMPTY=true
TIKTOK_SELENIUM_FALLBACK=true
```

---

## GitHub Secrets & Variables

### Secrets (sensitive)
```bash
gh secret set DB_PASSWORD
gh secret set JWT_SECRET
gh secret set FERNET_KEY
gh secret set GEMINI_SCRIPT_API_KEY
gh secret set GEMINI_MEDIA_API_KEY
gh secret set ELEVENLABS_API_KEY
gh secret set ELEVENLABS_VOICE_ID_EN
gh secret set ELEVENLABS_VOICE_ID_VI
gh secret set SUNO_API_KEY
gh secret set PEXELS_API_KEY
```

### Variables (non-sensitive, visible in logs)
```bash
gh variable set OUTPUT_PATH   --body "C:/render/output"
gh variable set ASSET_DB_PATH --body "C:/render/assets/video_db"
gh variable set MODELS_PATH   --body "C:/render/models"
gh variable set MUSIC_PATH    --body "C:/render/assets/music"
```

---

## Self-hosted Runner Setup (one-time, Windows)

1. GitHub repo → Settings → Actions → Runners → New self-hosted runner → Windows
2. Follow the generated PowerShell commands to download and configure
3. Install as Windows Service so it survives reboots:
   ```powershell
   .\svc.cmd install
   .\svc.cmd start
   ```
4. Runner needs Docker Desktop installed and running

Runner runs **outside Docker** — it manages Docker, not the other way around.

---

## File Changes Summary

| File | Action |
|---|---|
| `Dockerfile.render` | **New** — CUDA base, pipeline deps |
| `docker-compose.yml` | **New** — replaces `docker-compose.console.yml` |
| `nginx.conf` | **New** — required by `Dockerfile.frontend` |
| `.github/workflows/deploy.yml` | **New** — CI/CD pipeline |
| `Dockerfile.api` | **Modify** — remove alembic from CMD |
| `.gitignore` | **Modify** — add `pipeline.env` |
| `console/.env.example` | **Modify** — update with production value templates |
| `docker-compose.console.yml` | **Delete** — replaced by `docker-compose.yml` |

No application code changes — all pipeline, backend, and frontend code untouched.

---

## Prerequisites on Windows (manual, one-time)

- Docker Desktop with WSL2 backend enabled
- GPU support enabled in Docker Desktop: Settings → Resources → GPU → enable (uses WSL2 GPU passthrough, no separate toolkit install needed)
- GitHub Actions self-hosted runner installed as a service
- Firewall: allow inbound on ports 3000 and 8080 if accessing from Mac browser
