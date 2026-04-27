# LLM & Integrations Management — Design Spec

**Date:** 2026-04-27  
**Status:** Approved  
**Scope:** Replace env-var-based API key management with a JSON config file editable from the web UI. Extend the LLM page to cover all external service providers.

---

## Goals

1. Move all external API keys out of `pipeline.env` into a structured, UI-editable JSON file.
2. Expose two separate Gemini keys (script, media, music) with per-use-case model selection.
3. Add ElevenLabs, Suno, and Pexels key management with usage summaries to the LLM page.
4. Support hot-reload: key changes take effect within 30 seconds without restarting workers.

---

## 1. JSON Config File

**Path:** `config/api_keys.json`  
**Committed:** No — added to `.gitignore`  
**Example template committed:** `config/api_keys.json.example` (all values empty)

```json
{
  "gemini": {
    "script": {
      "api_key": "",
      "model": "gemini-2.5-flash"
    },
    "media": {
      "api_key": "",
      "model": "gemini-2.0-flash-exp"
    },
    "music": {
      "api_key": "",
      "model": "lyria-3-clip-preview"
    }
  },
  "elevenlabs": {
    "api_key": "",
    "voice_id_en": "",
    "voice_id_vi": "",
    "model": "eleven_multilingual_v2"
  },
  "suno": {
    "api_key": "",
    "model": "V4_5"
  },
  "pexels": {
    "api_key": ""
  }
}
```

**Key rules:**
- Plaintext (same security posture as `pipeline.env` — keep file out of version control).
- `gemini.media.api_key` and `gemini.music.api_key` are independent keys; they may be the same value or different billing accounts.
- `gemini.music` has no quota tracking locally — Lyria quota is managed by Google AI Studio.

---

## 2. Shared Config Module

**Path:** `config/api_config.py`

Single reader/writer used by all pipeline code and the console backend.

```python
def get_config() -> dict      # returns full config dict, cached for 30s
def save_config(data: dict) -> None  # atomically writes JSON, busts cache immediately
```

**Cache:** 30-second in-process TTL. Multiple Celery workers each hold their own cache — changes propagate within 30 seconds without restart.

**File not found:** If `api_keys.json` does not exist, `get_config()` returns all empty strings and logs a warning (does not raise — lets the app start without keys configured).

---

## 3. Pipeline Code Migration

All pipeline files that currently call `os.environ.get(...)` for API keys are updated to call `get_config()`. No env-var fallback is kept — `pipeline.env` stops being the source for these keys.

| File | Old env var(s) | New config path |
|---|---|---|
| `rag/llm_router.py` | `GEMINI_API_KEY`, `GEMINI_MODEL` | `gemini.script.api_key`, `gemini.script.model` |
| `pipeline/veo_client.py` | `GEMINI_MEDIA_API_KEY` | `gemini.media.api_key` |
| `pipeline/music_providers/lyria_provider.py` | `GEMINI_MEDIA_API_KEY` | `gemini.music.api_key` |
| `pipeline/elevenlabs_tts.py` | `ELEVENLABS_API_KEY` | `elevenlabs.api_key` |
| `pipeline/tts_router.py` | `ELEVENLABS_VOICE_ID_EN`, `ELEVENLABS_VOICE_ID_VI` | `elevenlabs.voice_id_en`, `elevenlabs.voice_id_vi` |
| `pipeline/pexels_client.py` | `PEXELS_API_KEY` | `pexels.api_key` |
| `pipeline/music_providers/suno_provider.py` | `SUNO_API_KEY` | `suno.api_key` |

`ELEVENLABS_MODEL` constant in `elevenlabs_tts.py` is replaced by `get_config()["elevenlabs"]["model"]`.  
`SUNO_MODEL` constant in `suno_provider.py` is replaced by `get_config()["suno"]["model"]`.

---

## 4. Backend API

### New endpoints (added to `routers/llm.py`)

```
GET  /api/llm/config       → returns config with keys masked (last 4 chars visible, rest "••••")
PUT  /api/llm/config       → saves full config to JSON (admin only)
```

**Masking rule:** any non-empty key value is returned as `"••••" + last_4_chars`. Empty string stays `""`. The frontend sends back the full unmasked value on save; if the user has not changed a masked field, the frontend re-submits the current value as-is (the `GET` returns the real value to the frontend only in a `_raw` field used internally — see Section 5).

**Simpler alternative:** `GET /api/llm/config` returns masked values for display; a separate `GET /api/llm/config/raw` (admin only) returns unmasked values used to pre-fill the edit form. The `PUT` always expects unmasked values.

### Extended existing endpoints

**`GET /api/llm/status`** — extended to return per-use-case Gemini status:
```json
{
  "gemini": {
    "script":  { "api_key_set": true, "model": "gemini-2.5-flash", "available": true },
    "media":   { "api_key_set": true, "model": "gemini-2.0-flash-exp", "available": true },
    "music":   { "api_key_set": false, "model": "lyria-3-clip-preview", "available": false }
  },
  "elevenlabs": { "api_key_set": true, "available": true },
  "suno":       { "api_key_set": true, "available": true },
  "pexels":     { "api_key_set": true, "available": true }
}
```

**`GET /api/llm/quota`** — extended to include all providers:
```json
{
  "gemini_script": { "rpm": 12, "rpm_limit": 60, "rpd": 340, "rpd_limit": 1500 },
  "elevenlabs":    { "characters_used": 42000, "characters_limit": 100000 },
  "suno":          { "tracks_generated": 17 },
  "pexels":        { "status": "ok" }
}
```

- **ElevenLabs quota:** fetched from `GET https://api.elevenlabs.io/v1/user/subscription`.
- **Suno usage:** DB count of `music_tracks` rows with `provider = "suno"`.
- **Pexels status:** lightweight `GET https://api.pexels.com/v1/search?query=test&per_page=1` — checks key validity, returns `"ok"` or error string.
- **Gemini media/music:** key status only, no quota tracking. Cards show note: *"Quota managed by Google AI Studio."*

### Auth

- `GET /api/llm/config` — admin only
- `PUT /api/llm/config` — admin only
- `GET /api/llm/status` — editor or admin (unchanged)
- `GET /api/llm/quota` — editor or admin (unchanged)

---

## 5. Frontend UI

**Page:** `LLMPage.jsx` (name unchanged in nav)

**Layout:** vertical stack of provider cards. Each card is self-contained with its own **Save** button. Saving calls `PUT /api/llm/config` with the full merged config (the card reads existing config state and patches only its own fields before submitting).

### Cards

#### Gemini — Script
- Status dot (green/red based on `gemini.script.available`)
- API key input (masked, reveal toggle)
- Model selector (fetches available models from Gemini API, same as current behavior)
- Usage row: RPM `12 / 60` · RPD `340 / 1500`
- Save button

#### Gemini — Media (Veo)
- Status dot
- API key input (masked, reveal toggle)
- Model selector (static list of known Veo models)
- Note: *"Quota managed by Google AI Studio"*
- Save button

#### Gemini — Music (Lyria)
- Status dot
- API key input (masked, reveal toggle)
- Model selector (static list: `lyria-3-clip-preview`, etc.)
- Note: *"Quota managed by Google AI Studio"*
- Save button

#### ElevenLabs
- Status dot
- API key input (masked, reveal toggle)
- Voice ID (EN) text input
- Voice ID (VI) text input
- Model selector (static list: `eleven_multilingual_v2`, `eleven_turbo_v2`, etc.)
- Usage row: `42,000 / 100,000 characters this month` (progress bar)
- Save button

#### Suno
- Status dot
- API key input (masked, reveal toggle)
- Model selector (static list: `V4_5`, `V4`, `V3_5`)
- Usage row: `17 tracks generated`
- Save button

#### Pexels
- Status dot
- API key input (masked, reveal toggle)
- Usage row: `Connected ✓` or error string from ping
- Save button

### Key masking in the form

On load, `GET /api/llm/config/raw` (admin endpoint) returns the actual key values to pre-fill the inputs. The user sees the real key when editing. On save, the full value is submitted. This avoids the complexity of tracking "did this field change" in the UI.

### Model selectors

- **Gemini Script:** dynamic — fetched from Gemini API (existing behavior).
- **Gemini Media / Music / ElevenLabs / Suno:** static option lists hardcoded in the frontend (these APIs don't have a "list models" endpoint, or the list rarely changes).

---

## 6. What Is Not Changing

- The LLM tab name in the nav stays "LLM".
- Role gate stays admin-only.
- The `rag/llm_router.py` internal routing logic (local/gemini/auto/hybrid) is unchanged — only the key/model source moves from env to JSON.
- `pipeline.env` continues to hold non-key config (TikTok scraper settings, `MUSIC_PATH`, `ASSET_DB_PATH`, etc.).

---

## Out of Scope

- Ollama / local LLM key management (Ollama has no API key).
- YouTube / TikTok OAuth tokens (managed separately in the Credentials tab).
- Encryption of the JSON file (plaintext, `.gitignored`, same as current `pipeline.env`).
