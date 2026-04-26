# Music API Configuration Guide

The Music Background Feature supports two music generation providers: **Suno** and **Google Lyria**. This guide explains how to configure API keys and choose models.

## Quick Start

```bash
# 1. Set SUNO_API_KEY in root .env
SUNO_API_KEY=your-suno-api-key-here

# 2. Set GEMINI_MEDIA_API_KEY in root .env
GEMINI_MEDIA_API_KEY=your-google-api-key-here

# 3. Restart the console
cd console && ./start.sh
```

---

## Suno API Configuration

### Getting Your API Key

1. Visit **https://sunoapi.org/**
2. Sign in or create an account
3. Navigate to API Settings / Developer Dashboard
4. Generate an API key
5. Copy the key

### Where to Set It

- **File:** `.env` (root directory)
- **Variable:** `SUNO_API_KEY`
- **Example:**
  ```
  SUNO_API_KEY=sk-suno-abc123...
  ```

### How It Works

- **Model:** Suno V4.5 (fixed, latest version)
- **Generation:** Async polling (15s intervals, ~5 min timeout)
- **Capabilities:**
  - Generates 30-second music clips
  - Supports vocal and instrumental modes
  - Optional negative tags for quality control

### API Limits

- **Standard:** Check Suno API dashboard for your quota
- **Polling:** Responses checked every 15 seconds
- **Timeout:** Generation fails after 5 minutes if not complete

---

## Google Lyria API Configuration

### Getting Your API Key

1. Visit **https://aistudio.google.com/app/apikey**
2. Click "Create API Key"
3. Copy the key

### Where to Set It

- **File:** `.env` (root directory)
- **Variable:** `GEMINI_MEDIA_API_KEY`
- **Example:**
  ```
  GEMINI_MEDIA_API_KEY=AIzaSy...
  ```

**Note:** Lyria uses `GEMINI_MEDIA_API_KEY` (the same key used for Veo video generation). This can be the same value as `GEMINI_API_KEY`.

### Model Selection

Lyria has **two model options**:

| Model | ID | Duration | Use Case |
|-------|----|----|----------|
| **Lyria Clip** | `lyria-clip` | ~30 seconds | Short background music, intro/outro |
| **Lyria Pro** | `lyria-pro` | Full song | Complete video background track |

The model is selected when generating music in the console. Default is **Lyria Clip**.

### How It Works

- **Engine:** Google Gemini API with Lyria extension
- **Generation:** Synchronous (returns immediately)
- **Capabilities:**
  - Generates music from text prompts
  - Supports vocal and instrumental modes
  - Gemini can expand short prompts to full descriptions
  - Higher quality than Suno for certain styles

### API Limits

- **Quota:** Check Google AI Studio dashboard
- **Rate Limits:** Standard Gemini API limits apply
- **Model Support:** Requires access to Lyria models (may be limited)

---

## Shared Configuration

### Environment Files

All music API keys live in the **root `.env` file**:

1. **`.env` (root) — ALL API keys go here**
   - `SUNO_API_KEY` — Suno music generation
   - `GEMINI_MEDIA_API_KEY` — Lyria music generation + Veo video generation
   - `GEMINI_API_KEY` — Script generation, prompt expansion
   - Other LLM/pipeline settings

2. **`console/.env`**
   - Database URL, Redis, JWT, Fernet key only
   - Does **not** contain API keys for music or LLM providers

### Loading Order

At startup, the console backend loads:
1. `console/.env` (if present)
2. `.env` (root, referenced as CORE_PIPELINE_PATH)
3. Environment variables (override file settings)

---

## Testing Configuration

### Quick Test: Verify Keys Are Loaded

```bash
# Check keys are set in root .env
grep -E "SUNO_API_KEY|GEMINI_MEDIA_API_KEY" .env
```

### Test Music Generation

1. Open the Music tab in the console (http://localhost:5173)
2. Click **"Generate Music"**
3. Choose provider (Suno or Lyria)
4. Enter a prompt
5. Click **Generate**
6. Monitor the pending status (should update every 10s for Suno, immediate for Lyria)

### Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `SUNO_API_KEY is not set` | Missing env var | Set SUNO_API_KEY in root `.env` |
| `GEMINI_MEDIA_API_KEY is not set` | Missing env var | Set GEMINI_MEDIA_API_KEY in root `.env` |
| `401 Unauthorized` | Invalid key format | Check key is copied completely, no extra spaces |
| `403 Forbidden` | Key has no access | Verify key has Suno API or Gemini API permissions |
| `Lyria returned no audio data` | API error | Try again, check quota, check model availability |
| `Suno generation failed` | Generation timeout or error | Check task status in Suno dashboard |

---

## Production Considerations

### Key Security

- **Never commit** API keys to git (both files should be in .gitignore)
- **Use secrets management** (Docker secrets, environment, vault) in production
- **Rotate keys** regularly in provider dashboards
- **Monitor usage** in Suno and Google AI Studio for cost/quota tracking

### Rate Limiting

- **Suno:** Built-in via API quota
- **Lyria:** Shared Gemini API limits (default 15 RPM, 1500 RPD)
  - Adjust via `GEMINI_RPM` and `GEMINI_RPD` in `.env`

### Fallback Strategy

If one provider is unavailable:
- Music generation will fail for that provider
- User can retry with the other provider
- Existing tracks remain available for assignment

---

## Model Details

### Suno V4.5

- **Latest version** as of April 2026
- **Audio Quality:** High (44.1 kHz stereo MP3)
- **Generation Time:** 30-90 seconds per clip
- **Prompt:** Text description of desired music
- **Style:** Auto-inferred from prompt or specified
- **Limitations:** 30-second clips only

### Lyria Clip (lyria-3-clip-preview)

- **Duration:** ~30 seconds
- **Quality:** High (MP3)
- **Generation:** Instant
- **Prompt:** Text description
- **Features:** Gemini can expand vague prompts
- **Use:** Perfect for short videos or intro/outro

### Lyria Pro (lyria-3-pro-preview)

- **Duration:** Full song (2-5 minutes typical)
- **Quality:** High (MP3)
- **Generation:** 1-2 seconds
- **Prompt:** Text description (same as Clip)
- **Features:** Gemini can expand vague prompts
- **Use:** Full background for longer videos
- **Availability:** May be limited in preview phase

---

## See Also

- [Music Feature Overview](../docs/superpowers/specs/2026-04-26-music-background-design.md)
- [Music Implementation Plan](../docs/superpowers/plans/2026-04-26-music-background.md)
- [Suno API Docs](https://sunoapi.org/docs)
- [Google Lyria Docs](https://ai.google.dev/gemini-api/docs/audio)
