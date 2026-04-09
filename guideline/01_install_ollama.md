# Install Ollama + Local LLM (Qwen2.5)

> **Purpose:** Run LLM script generation locally — free, offline, no API quota.
> **Model for testing:** `qwen2.5:3b` (~2 GB, fast)
> **Model for production:** `qwen2.5:7b` (~4.4 GB, better quality)

---

## macOS

### Step 1 — Install Ollama

**Option A: Direct installer (recommended)**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Option B: Homebrew**
```bash
brew install ollama
```

---

### Step 2 — Start Ollama

```bash
# Run in background (keep terminal open or use & )
ollama serve
```

Ollama listens on `http://localhost:11434` by default.

**Auto-start on login:**
```bash
# Homebrew install
brew services start ollama

# Or if installed via direct installer (already registered as launchd service)
launchctl start com.ollama.ollama
```

---

### Step 3 — Pull the model

```bash
# Testing (fast, ~2 GB)
ollama pull qwen2.5:3b

# Production (better quality, ~4.4 GB)
ollama pull qwen2.5:7b
```

Progress bar will show download status. Takes a few minutes depending on connection.

---

### Step 4 — Verify

```bash
# Check Ollama API is responding
curl http://localhost:11434/api/tags

# Quick Vietnamese language test
ollama run qwen2.5:3b "Xin chào, bạn có thể viết tiếng Việt không?"
```

Expected response: Ollama replies in Vietnamese.

---

### Step 5 — Verify from the pipeline

```bash
cd /Volumes/SSD/Workspace/ai-media-automation

python3 -c "
from rag.llm_router import LLMRouter
r = LLMRouter(mode='local')
print('Ollama up:  ', r.is_ollama_available())
print('Model:      ', r.status()['ollama_model'])
print('Gemini key: ', r.status()['gemini_key_set'])
"
```

Expected output:
```
Ollama up:   True
Model:       qwen2.5:3b
Gemini key:  True
```

---

### Step 6 — Test script generation

```bash
cd /Volumes/SSD/Workspace/ai-media-automation

python3 -c "
from rag.script_writer import generate_script
import json

script = generate_script(
    topic='5 thói quen buổi sáng giúp bạn thành công',
    niche='lifestyle',
    template='tiktok_viral',
)
print(json.dumps(script, ensure_ascii=False, indent=2)[:1000])
"
```

Expected: Valid JSON with `meta`, `video`, `scenes` keys and Vietnamese narration text.

---

## Ubuntu / Debian (Linux)

```bash
# Install
curl -fsSL https://ollama.com/install.sh | sh

# Start as systemd service
sudo systemctl start ollama
sudo systemctl enable ollama    # auto-start on boot

# Pull model
ollama pull qwen2.5:3b
```

---

## Configuration

Set in `pipeline.env`:

```bash
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b     # testing
# OLLAMA_MODEL=qwen2.5:7b   # production
LLM_MODE=auto               # local | gemini | auto | hybrid
```

| `LLM_MODE` | Behavior |
|------------|----------|
| `local`    | Qwen2.5 only — always offline, no Gemini |
| `gemini`   | Gemini only — requires `GEMINI_API_KEY` |
| `auto`     | Gemini if quota available, Ollama as fallback |
| `hybrid`   | Per-template routing (hook/cta → Gemini, body → local) |

---

## Switching models

```bash
# Switch to 7B for better quality
ollama pull qwen2.5:7b

# Update pipeline.env
OLLAMA_MODEL=qwen2.5:7b
```

No code changes needed — the router reads `OLLAMA_MODEL` from env at runtime.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `connection refused` on port 11434 | `ollama serve` is not running — start it |
| `model not found` | Run `ollama pull qwen2.5:3b` |
| Slow generation | Normal for 3B on CPU — 7B is slower, use Gemini for speed |
| Out of memory | Use `qwen2.5:3b` instead of 7B, or add swap space |
| `Ollama up: False` from pipeline | Ollama not started — run `ollama serve` first |

---

## Model storage location

```
macOS:  ~/.ollama/models/
Linux:  ~/.ollama/models/
```

---

*Guide version: April 2026 — AI Media Automation Project*
