# AI Media Automation

A fully automated AI media pipeline with a web-based Management Console for orchestrating video generation, curation, and publishing to YouTube and TikTok.

---

## Getting Started

See the detailed setup guides below for installation and running the system.

### Quick Start

```bash
# Install dependencies
pip install -r requirements.pipeline.txt
cd console && npm install

# Start everything (migrations + Redis + Celery + FastAPI + frontend)
./start.sh

# Frontend dev server (separate terminal)
cd console/frontend && npm run dev
```

For full setup details, see [CLAUDE.md](CLAUDE.md).

---

## Viewing Logs

### Celery Worker Logs

To monitor Celery tasks in real-time:

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
.venv/bin/celery -A console.backend.celery_app worker \
  -Q scrape_q,script_q,render_q,upload_q \
  --concurrency=4 \
  --loglevel=info
```

**Log levels:**
- `debug` — Verbose output for troubleshooting
- `info` — Normal operation (recommended)
- `warning` — Warnings and errors only

**Output includes:**
- Task start/completion times
- Queue processing status
- Error tracebacks (if any)

### FastAPI Logs

The FastAPI server logs appear in the terminal where you ran `./start.sh` or:

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
uvicorn console.backend.main:app --port 8080 --reload
```

Watch for:
- Request/response timings
- Database query logs (if enabled)
- Import errors or startup issues

### Pipeline Batch Job Logs

When running the daily pipeline or batch operations:

```bash
python3 batch_runner.py --run-now --verbose
```

Or dry-run mode to test without executing:

```bash
python3 batch_runner.py --run-now --dry-run
```

### Frontend (Vite) Logs

Frontend dev server logs appear in the terminal running `npm run dev`:

```bash
cd console/frontend && npm run dev
```

Watch for:
- Hot module reload confirmations
- Build warnings/errors
- Missing imports or type errors

### Redis Logs

If running Redis locally, monitor the Redis server:

```bash
redis-cli monitor  # Watch all Redis commands in real-time
redis-cli INFO     # Server info and stats
```

### PostgreSQL Logs

Check database connection issues:

```bash
# On macOS with Homebrew
tail -f /usr/local/var/log/postgresql@16.log

# Or use psql directly
psql -U postgres -c "SELECT pg_sleep(0);"  # Test connection
```

---

## Architecture Overview

| Component | Purpose | Port |
|-----------|---------|------|
| **FastAPI Backend** | REST API, auth, job orchestration | 8080 |
| **React Frontend** | Management console | 5173 (dev) |
| **Celery Worker** | Async task execution | N/A (queues via Redis) |
| **Redis** | Message broker, cache | 6379 |
| **PostgreSQL** | Main database | 5432 |
| **ChromaDB** | Vector embeddings (RAG) | Embedded |

---

## Common Tasks

### Run Scraper Only

```bash
python3 batch_runner.py --scrape-only
```

### Generate a Script from Curator Review

Go to **Scripts** tab in console → Click "Generate" → Set context parameters.

### Render a Video

Go to **Production** tab → Select script → Configure scenes → Click "Render".

### Upload to YouTube/TikTok

Go to **Uploads** tab → Select video and channel → Click "Upload".

### Check System Health

Go to **System** tab in console for CPU, memory, GPU, and disk status.

---

## Troubleshooting

### Task Stuck in Queue

Check Celery logs for errors. If worker crashed, restart it:

```bash
pkill -f "celery.*worker"
# Then restart
.venv/bin/celery -A console.backend.celery_app worker \
  -Q scrape_q,script_q,render_q,upload_q \
  --concurrency=4 --loglevel=info
```

### Database Connection Issues

```bash
# Test PostgreSQL connection
psql postgresql://user:password@localhost:5432/ai_media

# Check migrations
cd console/backend && alembic current
alembic upgrade head
```

### Missing Ollama (Local LLM)

See [guideline/01_install_ollama.md](guideline/01_install_ollama.md) for setup.

### Scraper Not Finding Videos

Check browser scraper logs:

```bash
python3 -c "
from scraper.tiktok_playwright import TikTokPlaywright
scraper = TikTokPlaywright()
videos = scraper.scrape('trending', limit=5)
print(videos)
"
```

---

## Documentation

- [CLAUDE.md](CLAUDE.md) — Full project context and architecture
- [01_product_spec.md](01_product_spec.md) — Feature specifications (all 8 modules)
- [02_architecture_design.md](02_architecture_design.md) — System design and data model
- [guideline/01_install_ollama.md](guideline/01_install_ollama.md) — Local LLM setup
- [docs/guides/youtube-channel-setup.md](docs/guides/youtube-channel-setup.md) — YouTube channel onboarding

---

## Project Status

**Sprint 1 (Complete):** Management console with 8 core tabs (Scraper, Scripts, Production, Uploads, Pipeline, LLM, Performance, System).

**Sprint 2–4 (In Progress):** Full pipeline integration, upload automation, performance optimization, and deployment.

---

## Contributing

All code changes follow the conventions in [CLAUDE.md](CLAUDE.md). Before submitting:

1. Run linters and tests
2. Verify log output is clean (no unhandled exceptions)
3. Update relevant documentation
4. Include proper commit message with co-authored-by trailer

---

## Support

For issues, questions, or contributions, see the issue tracker or contact the development team.

**Last updated:** May 2026
