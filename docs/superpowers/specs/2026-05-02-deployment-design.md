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

## Windows Machine Setup Guide

Full step-by-step to go from a fresh Windows machine to a running deployment. Split into manual steps (require UI or browser) and a one-time PowerShell setup script.

---

### Phase 1 — Manual installs (do these first, in order)

**1. Enable WSL2**
Open PowerShell as Administrator:
```powershell
wsl --install
# Reboot when prompted
```

**2. Install Docker Desktop**
- Download from https://www.docker.com/products/docker-desktop/
- During install: select "Use WSL2 instead of Hyper-V"
- After install, open Docker Desktop → Settings:
  - General → check "Use WSL2 based engine"
  - Resources → WSL Integration → enable your WSL distro
  - (GPU) If available: Resources → GPU → enable GPU support

**3. Install Git for Windows**
- Download from https://git-scm.com/download/win
- During install: select "Git from the command line and also from 3rd-party software"

**4. Install GitHub CLI**
```powershell
winget install --id GitHub.cli
# Then authenticate:
gh auth login
```

**5. Install NVIDIA drivers (if not already up to date)**
- Download from https://www.nvidia.com/Download/index.aspx
- Select: GeForce GTX 1660 Super, Windows 11, Game Ready Driver
- Reboot after install

---

### Phase 2 — One-time PowerShell setup script

Save as `setup-windows.ps1` and run as Administrator. This script:
- Creates all required directories
- Clones the repo
- Sets up the GitHub Actions self-hosted runner as a Windows Service
- Opens firewall ports
- Authenticates Docker with GHCR

```powershell
# setup-windows.ps1
# Run as Administrator: Right-click PowerShell → Run as Administrator
# Usage: .\setup-windows.ps1 -GithubRepo "owner/repo-name" -GithubRunnerToken "YOUR_TOKEN"
#
# Get runner token from:
# GitHub repo → Settings → Actions → Runners → New self-hosted runner → Windows → copy the --token value

param(
    [Parameter(Mandatory=$true)]
    [string]$GithubRepo,          # e.g. "jqka-dev/ai-media-automation"

    [Parameter(Mandatory=$true)]
    [string]$GithubRunnerToken,   # from GitHub Settings → Actions → Runners → New runner

    [string]$RepoPath = "C:\ai-media",
    [string]$RenderRoot = "C:\render",
    [string]$RunnerPath = "C:\actions-runner"
)

$ErrorActionPreference = "Stop"

Write-Host "=== AI Media Automation — Windows Setup ===" -ForegroundColor Cyan

# ── 1. Create required directories ──────────────────────────────────────────
Write-Host "`n[1/6] Creating directories..." -ForegroundColor Yellow
$dirs = @(
    "$RenderRoot\output",
    "$RenderRoot\assets\video_db",
    "$RenderRoot\assets\music",
    "$RenderRoot\models",
    "$RepoPath",
    "$RunnerPath"
)
foreach ($dir in $dirs) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    Write-Host "  OK  $dir"
}

# ── 2. Clone the repository ──────────────────────────────────────────────────
Write-Host "`n[2/6] Cloning repository..." -ForegroundColor Yellow
if (Test-Path "$RepoPath\.git") {
    Write-Host "  Repo already cloned — skipping"
} else {
    gh repo clone $GithubRepo $RepoPath
    Write-Host "  Cloned to $RepoPath"
}

# ── 3. Authenticate Docker with GHCR ────────────────────────────────────────
Write-Host "`n[3/6] Authenticating Docker with GitHub Container Registry..." -ForegroundColor Yellow
gh auth token | docker login ghcr.io -u $env:USERNAME --password-stdin
Write-Host "  Docker authenticated with GHCR"

# ── 4. Set up GitHub Actions self-hosted runner ──────────────────────────────
Write-Host "`n[4/6] Setting up GitHub Actions runner..." -ForegroundColor Yellow
Set-Location $RunnerPath

# Download latest runner package
$runnerVersion = "2.316.1"
$runnerUrl = "https://github.com/actions/runner/releases/download/v$runnerVersion/actions-runner-win-x64-$runnerVersion.zip"
$runnerZip = "$RunnerPath\runner.zip"

if (-not (Test-Path "$RunnerPath\run.cmd")) {
    Write-Host "  Downloading runner v$runnerVersion..."
    Invoke-WebRequest -Uri $runnerUrl -OutFile $runnerZip
    Expand-Archive -Path $runnerZip -DestinationPath $RunnerPath -Force
    Remove-Item $runnerZip
}

# Configure runner
$repoUrl = "https://github.com/$GithubRepo"
.\config.cmd --url $repoUrl --token $GithubRunnerToken --name "windows-render" --labels "self-hosted,windows,render" --work "$RunnerPath\_work" --unattended

# Install and start as Windows Service
.\svc.cmd install
.\svc.cmd start
Write-Host "  Runner installed and started as Windows Service"

# ── 5. Configure Windows Firewall ────────────────────────────────────────────
Write-Host "`n[5/6] Opening firewall ports..." -ForegroundColor Yellow
$ports = @(
    @{ Port = 3000; Name = "AI-Media-Frontend" },
    @{ Port = 8080; Name = "AI-Media-API" }
)
foreach ($rule in $ports) {
    $existing = Get-NetFirewallRule -DisplayName $rule.Name -ErrorAction SilentlyContinue
    if (-not $existing) {
        New-NetFirewallRule -DisplayName $rule.Name -Direction Inbound -Protocol TCP -LocalPort $rule.Port -Action Allow | Out-Null
        Write-Host "  Opened port $($rule.Port) ($($rule.Name))"
    } else {
        Write-Host "  Port $($rule.Port) already open — skipping"
    }
}

# ── 6. Verify Docker + GPU ───────────────────────────────────────────────────
Write-Host "`n[6/6] Verifying Docker and GPU..." -ForegroundColor Yellow
docker info | Select-String "Server Version","Runtimes"
docker run --rm --gpus all nvidia/cuda:12.3.2-base-ubuntu22.04 nvidia-smi
Write-Host "  GPU visible to Docker"

# ── Done ─────────────────────────────────────────────────────────────────────
Write-Host "`n=== Setup complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Go to GitHub → Settings → Secrets — run the 'gh secret set' commands from the spec"
Write-Host "  2. Push to main to trigger the first deployment"
Write-Host "  3. Access the console at http://localhost:3000 (or http://<this-machine-ip>:3000 from Mac)"
Write-Host ""
Write-Host "Render output:  $RenderRoot\output"
Write-Host "Asset library:  $RenderRoot\assets"
Write-Host "Models:         $RenderRoot\models"
```

**Run it:**
```powershell
# In PowerShell as Administrator:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\setup-windows.ps1 -GithubRepo "jqka-dev/ai-media-automation" -GithubRunnerToken "YOUR_TOKEN_HERE"
```

---

### Phase 3 — Set GitHub Secrets (run from Mac)

After the Windows script completes, run these from your Mac terminal to populate all secrets:

```bash
# Infrastructure
gh secret set DB_PASSWORD        --body "your-strong-password"
gh secret set JWT_SECRET         --body "your-jwt-secret"
gh secret set FERNET_KEY         --body "your-fernet-key"

# API keys
gh secret set GEMINI_SCRIPT_API_KEY  --body "AIza..."
gh secret set GEMINI_MEDIA_API_KEY   --body "AIza..."
gh secret set ELEVENLABS_API_KEY     --body "5f40..."
gh secret set ELEVENLABS_VOICE_ID_EN --body "RILOU..."
gh secret set ELEVENLABS_VOICE_ID_VI --body "BlZK..."
gh secret set SUNO_API_KEY           --body "282c..."
gh secret set PEXELS_API_KEY         --body "IkVw..."

# Pipeline paths (variables, not secrets)
gh variable set OUTPUT_PATH   --body "C:/render/output"
gh variable set ASSET_DB_PATH --body "C:/render/assets/video_db"
gh variable set MODELS_PATH   --body "C:/render/models"
gh variable set MUSIC_PATH    --body "C:/render/assets/music"
```

---

### Phase 4 — First deployment

Push any change to `main` (or trigger manually in GitHub → Actions → Deploy → Run workflow). The GitHub Actions runner on Windows will:

1. Pull the newly built Docker images from GHCR
2. Write all env/config files from secrets
3. Run database migrations
4. Start all containers

Check status:
```powershell
docker compose ps          # all services should show "running"
docker compose logs api    # look for "Application startup complete"
docker compose logs celery-render  # look for "ready" and GPU in logs
```

Access the console from Mac browser: `http://<windows-machine-ip>:3000`

---

## Prerequisites on Windows (summary checklist)

- [ ] WSL2 enabled and rebooted
- [ ] Docker Desktop installed, WSL2 backend enabled, GPU support on
- [ ] Git for Windows installed
- [ ] GitHub CLI installed and authenticated (`gh auth login`)
- [ ] NVIDIA drivers up to date (GTX 1660 Super)
- [ ] `setup-windows.ps1` run successfully
- [ ] All GitHub Secrets and Variables set via `gh secret set` / `gh variable set`
- [ ] First push to `main` triggered and deployment succeeded
