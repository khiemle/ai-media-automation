# Windows Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Containerise the full AI Media Automation stack into Docker images deployed to a Windows machine (GTX 1660S) via GitHub Actions CI/CD, with a one-time PowerShell setup script for the Windows machine.

**Architecture:** Three Docker images (`api`, `render`, `frontend`) are built on GitHub-hosted runners and pushed to GHCR on every push to `main`. A self-hosted GitHub Actions runner on the Windows machine pulls those images and runs `docker compose up -d`. The render worker uses a CUDA-based image and claims the NVIDIA GPU; all other services use the slim Python API image.

**Tech Stack:** Docker, Docker Compose v2, GitHub Actions, GHCR (`ghcr.io/khiemle/ai-media-automation`), Nginx, NVIDIA CUDA 12.3.2, Python 3.11, PowerShell 7, `gh` CLI

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| Modify | `Dockerfile.api` | Remove alembic from CMD; migrations run as a deploy step |
| Create | `Dockerfile.render` | CUDA base + pipeline deps for render worker |
| Create | `docker-compose.yml` | All services for Windows; replaces `docker-compose.console.yml` |
| Delete | `docker-compose.console.yml` | Superseded by `docker-compose.yml` |
| Modify | `nginx.conf` | Already correct — no change needed |
| Create | `.github/workflows/deploy.yml` | Build images → push GHCR → deploy on Windows runner |
| Modify | `.gitignore` | Add `pipeline.env` |
| Modify | `console/.env.example` | Add production Docker values, document every key |
| Create | `scripts/setup-windows.ps1` | One-time Windows machine bootstrap |

---

## Task 1: Housekeeping

**Files:**
- Modify: `Dockerfile.api`
- Modify: `.gitignore`
- Modify: `console/.env.example`
- Delete: `docker-compose.console.yml`

- [ ] **Step 1.1: Remove alembic from Dockerfile.api CMD**

Open `Dockerfile.api`. Replace the CMD line:

```dockerfile
# Before
CMD ["sh", "-c", "cd /app/console/backend && alembic upgrade head && cd /app && uvicorn console.backend.main:app --host 0.0.0.0 --port 8080"]

# After
CMD ["uvicorn", "console.backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

Migrations will run as a one-off container step in the deploy workflow instead.

- [ ] **Step 1.2: Add pipeline.env to .gitignore**

Open `.gitignore`. Under the `# Environment` section, add `pipeline.env`:

```
# Environment
.env
*.env.local
config/api_keys.json
pipeline.env
```

- [ ] **Step 1.3: Update console/.env.example**

Replace the entire contents of `console/.env.example` with:

```bash
# ─────────────────────────────────────────────
#  AI Media Management Console — Environment
# ─────────────────────────────────────────────
# Copy this file to console/.env and fill in values.
# In Docker: DATABASE_URL and REDIS_URL use service names, not localhost.

# Database — in Docker use service name "postgres", not "localhost"
DATABASE_URL=postgresql://admin:CHANGE_ME_DB_PASSWORD@postgres:5432/ai_media

# Redis — in Docker use service name "redis"
REDIS_URL=redis://redis:6379/0

# JWT Authentication
JWT_SECRET=CHANGE_ME_use_a_long_random_string
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# Fernet encryption key for OAuth secrets
# Generate: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FERNET_KEY=CHANGE_ME_generate_with_command_above

# Path to project root inside the Docker container
CORE_PIPELINE_PATH=/app

# Console server
CONSOLE_PORT=8080

# In production (Docker): set to the machine's IP or hostname on port 3000
# In dev (local): http://localhost:5173
FRONTEND_ORIGIN=http://localhost:3000

# production | development
ENV=production

# Runway ML (optional)
RUNWAY_API_KEY=
```

- [ ] **Step 1.4: Delete the old compose file**

```bash
git rm docker-compose.console.yml
```

- [ ] **Step 1.5: Commit**

```bash
git add Dockerfile.api .gitignore console/.env.example
git commit -m "chore: prep dockerfiles and env for Windows deployment"
```

---

## Task 2: Create Dockerfile.render

**Files:**
- Create: `Dockerfile.render`

- [ ] **Step 2.1: Verify requirements files exist**

```bash
ls requirements.pipeline.txt console/requirements.txt
```

Expected output:
```
requirements.pipeline.txt   console/requirements.txt
```

- [ ] **Step 2.2: Create Dockerfile.render**

Create `Dockerfile.render` at project root:

```dockerfile
FROM nvidia/cuda:12.3.2-runtime-ubuntu22.04

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

# System deps + Python 3.11 (Ubuntu 22.04 ships 3.10; deadsnakes gives us 3.11)
RUN apt-get update && apt-get install -y --no-install-recommends \
        software-properties-common curl \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y --no-install-recommends \
        python3.11 python3.11-dev python3.11-distutils \
        ffmpeg libsndfile1 libgomp1 \
        postgresql-client \
    && curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11 \
    && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
    && ln -sf /usr/bin/python3.11 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/*

# Python deps — console first (Celery, SQLAlchemy, etc.), then pipeline
COPY console/requirements.txt /app/console/requirements.txt
COPY requirements.pipeline.txt /app/requirements.pipeline.txt
RUN pip install --no-cache-dir \
        -r /app/console/requirements.txt \
        -r /app/requirements.pipeline.txt

# App code
COPY . /app

CMD ["celery", "-A", "console.backend.celery_app", "worker", \
     "-Q", "render_q", "--concurrency=2", "--loglevel=info"]
```

- [ ] **Step 2.3: Verify the file was created correctly**

```bash
head -5 Dockerfile.render
```

Expected:
```
FROM nvidia/cuda:12.3.2-runtime-ubuntu22.04
```

- [ ] **Step 2.4: Commit**

```bash
git add Dockerfile.render
git commit -m "feat: add Dockerfile.render with CUDA base for render worker"
```

---

## Task 3: Create docker-compose.yml

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 3.1: Create docker-compose.yml**

Create `docker-compose.yml` at project root:

```yaml
version: "3.9"

# Docker Compose for Windows production deployment.
# All services run on a single Windows machine with NVIDIA GTX 1660S.
# Images are pulled from GHCR — run "docker compose pull" to update.

services:

  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: ai_media
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    ports:
      - "6379:6379"

  api:
    image: ghcr.io/khiemle/ai-media-automation/api:latest
    restart: unless-stopped
    ports:
      - "8080:8080"
    env_file:
      - ./console/.env
    depends_on:
      - postgres
      - redis
    volumes:
      - ./config:/app/config:ro
      - render_output:/app/assets/output

  celery-worker:
    image: ghcr.io/khiemle/ai-media-automation/api:latest
    restart: unless-stopped
    command: >
      celery -A console.backend.celery_app worker
      -Q scrape_q,script_q,upload_q
      --concurrency=4 --loglevel=info
    env_file:
      - ./console/.env
    depends_on:
      - postgres
      - redis
    volumes:
      - ./config:/app/config:ro
      - render_output:/app/assets/output

  celery-beat:
    image: ghcr.io/khiemle/ai-media-automation/api:latest
    restart: unless-stopped
    command: >
      celery -A console.backend.celery_app beat
      --loglevel=info
    env_file:
      - ./console/.env
    depends_on:
      - redis

  celery-render:
    image: ghcr.io/khiemle/ai-media-automation/render:latest
    restart: unless-stopped
    command: >
      celery -A console.backend.celery_app worker
      -Q render_q
      --concurrency=2 --loglevel=info
    env_file:
      - ./console/.env
      - ./pipeline.env
    depends_on:
      - postgres
      - redis
    volumes:
      - ./config:/app/config:ro
      - render_output:/app/assets/output
      - ${ASSET_DB_PATH:-C:/render/assets/video_db}:/app/assets/video_db
      - ${MODELS_PATH:-C:/render/models}:/app/models
      - ${MUSIC_PATH:-C:/render/assets/music}:/app/assets/music
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  frontend:
    image: ghcr.io/khiemle/ai-media-automation/frontend:latest
    restart: unless-stopped
    ports:
      - "3000:80"
    depends_on:
      - api

volumes:
  postgres_data:
  render_output:
```

- [ ] **Step 3.2: Validate compose file syntax**

```bash
docker compose config --quiet && echo "VALID"
```

Expected output: `VALID`

If `docker compose` isn't available locally (Mac dev machine), install Docker Desktop or validate with:
```bash
python3 -c "import yaml; yaml.safe_load(open('docker-compose.yml'))" && echo "YAML OK"
```

- [ ] **Step 3.3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add docker-compose.yml for Windows single-machine deployment"
```

---

## Task 4: Create GitHub Actions deploy workflow

**Files:**
- Create: `.github/workflows/deploy.yml`

- [ ] **Step 4.1: Create .github/workflows directory**

```bash
mkdir -p .github/workflows
```

- [ ] **Step 4.2: Create deploy.yml**

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  packages: write

jobs:

  # ── Build all three images in parallel ──────────────────────────────────
  build-api:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - uses: docker/build-push-action@v5
        with:
          context: .
          file: Dockerfile.api
          push: true
          tags: ghcr.io/khiemle/ai-media-automation/api:latest

  build-render:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - uses: docker/build-push-action@v5
        with:
          context: .
          file: Dockerfile.render
          push: true
          tags: ghcr.io/khiemle/ai-media-automation/render:latest

  build-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - uses: docker/build-push-action@v5
        with:
          context: .
          file: Dockerfile.frontend
          push: true
          tags: ghcr.io/khiemle/ai-media-automation/frontend:latest

  # ── Deploy on Windows self-hosted runner ────────────────────────────────
  deploy:
    needs: [build-api, build-render, build-frontend]
    runs-on: [self-hosted, windows, render]

    steps:
      - uses: actions/checkout@v4

      # Write console/.env from secrets
      - name: Write console/.env
        shell: pwsh
        run: |
          $content = @"
          DATABASE_URL=postgresql://admin:${{ secrets.DB_PASSWORD }}@postgres:5432/ai_media
          REDIS_URL=redis://redis:6379/0
          JWT_SECRET=${{ secrets.JWT_SECRET }}
          JWT_ALGORITHM=HS256
          JWT_EXPIRE_MINUTES=1440
          FERNET_KEY=${{ secrets.FERNET_KEY }}
          CORE_PIPELINE_PATH=/app
          CONSOLE_PORT=8080
          FRONTEND_ORIGIN=http://localhost:3000
          ENV=production
          RUNWAY_API_KEY=${{ secrets.RUNWAY_API_KEY }}
          "@
          New-Item -ItemType Directory -Force -Path "console" | Out-Null
          $content | Out-File -FilePath "console\.env" -Encoding utf8NoBOM

      # Write config/api_keys.json from secrets
      - name: Write config/api_keys.json
        shell: pwsh
        run: |
          $json = @"
          {
            "gemini": {
              "script": { "api_key": "${{ secrets.GEMINI_SCRIPT_API_KEY }}", "model": "gemini-2.5-flash" },
              "media":  { "api_key": "${{ secrets.GEMINI_MEDIA_API_KEY }}",  "model": "veo-3.1-lite-generate-preview" },
              "music":  { "api_key": "${{ secrets.GEMINI_MEDIA_API_KEY }}",  "model": "lyria-3-clip-preview" }
            },
            "elevenlabs": {
              "api_key":     "${{ secrets.ELEVENLABS_API_KEY }}",
              "voice_id_en": "${{ secrets.ELEVENLABS_VOICE_ID_EN }}",
              "voice_id_vi": "${{ secrets.ELEVENLABS_VOICE_ID_VI }}",
              "model":       "eleven_flash_v2_5"
            },
            "suno":    { "api_key": "${{ secrets.SUNO_API_KEY }}", "model": "V4_5" },
            "sunoapi": { "api_key": "${{ secrets.SUNO_API_KEY }}" },
            "pexels":  { "api_key": "${{ secrets.PEXELS_API_KEY }}" }
          }
          "@
          New-Item -ItemType Directory -Force -Path "config" | Out-Null
          $json | Out-File -FilePath "config\api_keys.json" -Encoding utf8NoBOM

      # Write pipeline.env from variables (non-sensitive) + secrets
      - name: Write pipeline.env
        shell: pwsh
        run: |
          $content = @"
          OUTPUT_PATH=${{ vars.OUTPUT_PATH }}
          ASSET_DB_PATH=${{ vars.ASSET_DB_PATH }}
          MODELS_PATH=${{ vars.MODELS_PATH }}
          MUSIC_PATH=${{ vars.MUSIC_PATH }}
          TTS_ENGINE=auto
          TIKTOK_SCRAPER_ENGINE=auto
          TIKTOK_BROWSER_HEADLESS=true
          TIKTOK_BROWSER_HEADFUL_RETRY_ON_EMPTY=true
          TIKTOK_SELENIUM_FALLBACK=true
          "@
          $content | Out-File -FilePath "pipeline.env" -Encoding utf8NoBOM

      # Write DB_PASSWORD for docker-compose postgres service
      - name: Write .env for compose
        shell: pwsh
        run: |
          "DB_PASSWORD=${{ secrets.DB_PASSWORD }}" | Out-File -FilePath ".env" -Encoding utf8NoBOM

      # Pull latest images from GHCR
      - name: Pull images
        shell: pwsh
        run: docker compose pull

      # Run database migrations (one-off container, runs before services restart)
      - name: Run migrations
        shell: pwsh
        run: |
          docker run --rm `
            --env-file console\.env `
            --network ai-media-automation_default `
            ghcr.io/khiemle/ai-media-automation/api:latest `
            sh -c "cd /app/console/backend && alembic upgrade head"

      # Restart all services
      - name: Start services
        shell: pwsh
        run: docker compose up -d --remove-orphans
```

- [ ] **Step 4.3: Validate workflow YAML syntax**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yml')); print('YAML OK')"
```

Expected: `YAML OK`

- [ ] **Step 4.4: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "feat: add GitHub Actions deploy workflow for Windows self-hosted runner"
```

---

## Task 5: Create Windows setup script

**Files:**
- Create: `scripts/setup-windows.ps1`

- [ ] **Step 5.1: Create scripts directory**

```bash
mkdir -p scripts
```

- [ ] **Step 5.2: Create scripts/setup-windows.ps1**

Create `scripts/setup-windows.ps1`:

```powershell
# setup-windows.ps1
# One-time bootstrap for the Windows render machine.
# Run as Administrator in PowerShell 7+.
#
# Usage:
#   .\scripts\setup-windows.ps1 `
#     -GithubRepo "khiemle/ai-media-automation" `
#     -GithubRunnerToken "YOUR_TOKEN"
#
# Get the runner token from:
#   GitHub repo → Settings → Actions → Runners → New self-hosted runner → Windows
#   Copy the value after --token in the config step.

param(
    [Parameter(Mandatory=$true)]
    [string]$GithubRepo,

    [Parameter(Mandatory=$true)]
    [string]$GithubRunnerToken,

    [string]$RepoPath    = "C:\ai-media",
    [string]$RenderRoot  = "C:\render",
    [string]$RunnerPath  = "C:\actions-runner",
    [string]$RunnerVersion = "2.316.1"
)

$ErrorActionPreference = "Stop"
$ProgressPreference    = "SilentlyContinue"   # speeds up Invoke-WebRequest

Write-Host "`n=== AI Media Automation — Windows Setup ===" -ForegroundColor Cyan

# ── 1. Verify prerequisites ──────────────────────────────────────────────────
Write-Host "`n[1/6] Checking prerequisites..." -ForegroundColor Yellow

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker is not installed or not in PATH. Install Docker Desktop first."
    exit 1
}
docker info | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker Desktop is not running. Start it and re-run this script."
    exit 1
}
Write-Host "  Docker OK"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Error "GitHub CLI (gh) is not installed. Run: winget install --id GitHub.cli"
    exit 1
}
Write-Host "  GitHub CLI OK"

# ── 2. Create required directories ──────────────────────────────────────────
Write-Host "`n[2/6] Creating directories..." -ForegroundColor Yellow
$dirs = @(
    "$RenderRoot\output",
    "$RenderRoot\assets\video_db",
    "$RenderRoot\assets\music",
    "$RenderRoot\models",
    $RepoPath,
    $RunnerPath
)
foreach ($dir in $dirs) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    Write-Host "  OK  $dir"
}

# ── 3. Clone the repository ──────────────────────────────────────────────────
Write-Host "`n[3/6] Cloning repository..." -ForegroundColor Yellow
if (Test-Path "$RepoPath\.git") {
    Write-Host "  Already cloned at $RepoPath — skipping"
} else {
    gh repo clone $GithubRepo $RepoPath
    Write-Host "  Cloned → $RepoPath"
}

# ── 4. Authenticate Docker with GHCR ────────────────────────────────────────
Write-Host "`n[4/6] Authenticating Docker with GHCR..." -ForegroundColor Yellow
gh auth token | docker login ghcr.io -u (gh api user --jq .login) --password-stdin
Write-Host "  Docker authenticated with ghcr.io"

# ── 5. Set up GitHub Actions self-hosted runner ──────────────────────────────
Write-Host "`n[5/6] Setting up GitHub Actions runner..." -ForegroundColor Yellow
Set-Location $RunnerPath

if (-not (Test-Path "$RunnerPath\run.cmd")) {
    $zipUrl  = "https://github.com/actions/runner/releases/download/v$RunnerVersion/actions-runner-win-x64-$RunnerVersion.zip"
    $zipPath = "$RunnerPath\runner.zip"
    Write-Host "  Downloading runner v$RunnerVersion..."
    Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath
    Expand-Archive -Path $zipPath -DestinationPath $RunnerPath -Force
    Remove-Item $zipPath
    Write-Host "  Extracted"
}

$repoUrl = "https://github.com/$GithubRepo"
.\config.cmd `
    --url   $repoUrl `
    --token $GithubRunnerToken `
    --name  "windows-render" `
    --labels "self-hosted,windows,render" `
    --work  "$RunnerPath\_work" `
    --unattended

.\svc.cmd install
.\svc.cmd start
Write-Host "  Runner installed and started as Windows Service"

# ── 6. Open firewall ports ───────────────────────────────────────────────────
Write-Host "`n[6/6] Opening firewall ports..." -ForegroundColor Yellow
@(
    @{ Port = 3000; Name = "AI-Media-Frontend" },
    @{ Port = 8080; Name = "AI-Media-API" }
) | ForEach-Object {
    if (-not (Get-NetFirewallRule -DisplayName $_.Name -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -DisplayName $_.Name -Direction Inbound `
            -Protocol TCP -LocalPort $_.Port -Action Allow | Out-Null
        Write-Host "  Opened port $($_.Port)"
    } else {
        Write-Host "  Port $($_.Port) already open"
    }
}

# ── Verify GPU visibility ────────────────────────────────────────────────────
Write-Host "`nVerifying GPU in Docker..." -ForegroundColor Yellow
docker run --rm --gpus all nvidia/cuda:12.3.2-base-ubuntu22.04 nvidia-smi
if ($LASTEXITCODE -ne 0) {
    Write-Warning "GPU not visible to Docker. Check Docker Desktop → Settings → Resources → GPU."
} else {
    Write-Host "  GPU OK"
}

# ── Done ─────────────────────────────────────────────────────────────────────
Write-Host "`n=== Setup complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. From your Mac terminal, run the 'gh secret set' commands in the spec"
Write-Host "  2. Push to main (or run the Deploy workflow manually in GitHub Actions)"
Write-Host "  3. Open http://localhost:3000 in a browser on this machine"
Write-Host "     Or http://<this-machine-ip>:3000 from your Mac"
Write-Host ""
Write-Host "Render output : $RenderRoot\output"
Write-Host "Asset library : $RenderRoot\assets"
Write-Host "Models        : $RenderRoot\models"
Write-Host "Runner logs   : $RunnerPath\_diag"
```

- [ ] **Step 5.3: Commit**

```bash
git add scripts/setup-windows.ps1
git commit -m "feat: add one-time Windows machine setup script"
```

---

## Task 6: Set GitHub Secrets and trigger first deploy

**Files:** none — CLI commands only

- [ ] **Step 6.1: Verify you are authenticated with gh CLI**

```bash
gh auth status
```

Expected: shows `khiemle` account as active and authenticated.

- [ ] **Step 6.2: Set infrastructure secrets**

Run each command and paste the secret value when prompted (no `--body` flag so the value never appears in shell history):

```bash
gh secret set DB_PASSWORD
gh secret set JWT_SECRET
gh secret set FERNET_KEY
```

- [ ] **Step 6.3: Set API key secrets**

```bash
gh secret set GEMINI_SCRIPT_API_KEY
gh secret set GEMINI_MEDIA_API_KEY
gh secret set ELEVENLABS_API_KEY
gh secret set ELEVENLABS_VOICE_ID_EN
gh secret set ELEVENLABS_VOICE_ID_VI
gh secret set SUNO_API_KEY
gh secret set PEXELS_API_KEY
```

Optional (leave blank if not used):
```bash
gh secret set RUNWAY_API_KEY
```

- [ ] **Step 6.4: Set pipeline path variables**

```bash
gh variable set OUTPUT_PATH   --body "C:/render/output"
gh variable set ASSET_DB_PATH --body "C:/render/assets/video_db"
gh variable set MODELS_PATH   --body "C:/render/models"
gh variable set MUSIC_PATH    --body "C:/render/assets/music"
```

- [ ] **Step 6.5: Verify secrets were saved**

```bash
gh secret list
gh variable list
```

Expected — secrets list shows (values hidden):
```
DB_PASSWORD
ELEVENLABS_API_KEY
ELEVENLABS_VOICE_ID_EN
ELEVENLABS_VOICE_ID_VI
FERNET_KEY
GEMINI_MEDIA_API_KEY
GEMINI_SCRIPT_API_KEY
JWT_SECRET
PEXELS_API_KEY
SUNO_API_KEY
```

Variables list shows with their values:
```
ASSET_DB_PATH   C:/render/assets/video_db
MODELS_PATH     C:/render/models
MUSIC_PATH      C:/render/assets/music
OUTPUT_PATH     C:/render/output
```

- [ ] **Step 6.6: Push to trigger first build**

```bash
git push origin main
```

Then watch the workflow at:
```
https://github.com/khiemle/ai-media-automation/actions
```

Build jobs (`build-api`, `build-render`, `build-frontend`) run in parallel (~5-10 min each). The `deploy` job starts after all three pass and runs on the Windows self-hosted runner.

- [ ] **Step 6.7: Verify deployment on Windows machine**

On the Windows machine, open PowerShell and run:

```powershell
cd C:\ai-media
docker compose ps
```

Expected output — all services `running`:
```
NAME              IMAGE                                       STATUS
ai-media-api      ghcr.io/khiemle/ai-media-automation/api    running
ai-media-celery   ghcr.io/khiemle/ai-media-automation/api    running
ai-media-render   ghcr.io/khiemle/ai-media-automation/render running
ai-media-frontend ghcr.io/khiemle/ai-media-automation/front  running
ai-media-postgres postgres:16-alpine                          running
ai-media-redis    redis:7-alpine                              running
```

Check API startup:
```powershell
docker compose logs api --tail=20
```

Expected: `Application startup complete.`

Check render worker GPU:
```powershell
docker compose logs celery-render --tail=20
```

Expected: lines mentioning `celery@... ready` and no CUDA errors.

Open browser on Windows: `http://localhost:3000` — should show the login page.

---

## Self-Review Notes

- **Spec coverage:** All 8 file changes from the spec are covered. Windows setup guide (4 phases) maps to Tasks 1-5 + Task 6. GitHub Secrets map to Task 6.
- **Migration network:** The migration one-off container uses `ai-media-automation_default` as the Docker network name — Docker Compose names the default network `<project-name>_default`. The project name defaults to the directory name on the Windows machine (`ai-media`). The workflow checks out to `_work/ai-media-automation/ai-media-automation` — network name will be `ai-media-automation_default`. This is already correct in the workflow step.
- **DB_PASSWORD in compose:** `docker-compose.yml` uses `${DB_PASSWORD}` for the postgres password — this requires a root-level `.env` file (written by the deploy workflow's "Write .env for compose" step).
- **nginx.conf:** Already exists and is correct. No task needed.
- **No placeholder steps:** All code blocks are complete.
