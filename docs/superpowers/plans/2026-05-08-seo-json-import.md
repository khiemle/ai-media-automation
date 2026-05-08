# SEO JSON Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a third "SEO JSON" file-picker section to the Import Template modal in `YouTubeVideosPage.jsx` so that SEO data (title, description, tags) is sourced from a dedicated `*_seo.json` file instead of being extracted from the SFX JSON.

**Architecture:** Two new pure functions (`parseSeoJson`, `extractSeoFromSeoJson`) handle parsing and field-mapping. The existing `ImportFromTemplateModal` gains a third state slot and handler. SEO resolution uses priority: seoJson → sfxJson → null. All changes are in one file; no backend work.

**Tech Stack:** React 18, Vite, Vitest (added for pure-function tests), Tailwind CSS

---

## File Map

| Action | Path |
|--------|------|
| Modify | `console/frontend/src/pages/YouTubeVideosPage.jsx` |
| Create | `console/frontend/src/__tests__/seoJsonUtils.test.js` |
| Modify | `console/frontend/package.json` (add vitest) |
| Modify | `console/frontend/vite.config.js` (add test config) |

---

### Task 1: Add Vitest and write failing tests for the two pure functions

**Files:**
- Modify: `console/frontend/package.json`
- Modify: `console/frontend/vite.config.js`
- Create: `console/frontend/src/__tests__/seoJsonUtils.test.js`

- [ ] **Step 1: Install Vitest**

Run from `console/frontend/`:
```bash
cd console/frontend && npm install --save-dev vitest
```

- [ ] **Step 2: Add test script and vitest config to `package.json`**

Open `console/frontend/package.json`. Add `"test": "vitest run"` to the `scripts` block:

```json
{
  "name": "ai-media-console",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test": "vitest run"
  },
  "dependencies": {
    "marked": "^18.0.3",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.30.3"
  },
  "devDependencies": {
    "@types/react": "^18.3.1",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.1",
    "autoprefixer": "^10.4.19",
    "postcss": "^8.4.38",
    "tailwindcss": "^3.4.4",
    "vite": "^5.3.1",
    "vitest": "latest"
  }
}
```

- [ ] **Step 3: Add test config block to `vite.config.js`**

Open `console/frontend/vite.config.js`. Add a `test` key inside the `defineConfig` object. The existing file likely looks like:

```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://localhost:8080', '/ws': { target: 'ws://localhost:8080', ws: true } } }
})
```

Change it to:

```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://localhost:8080', '/ws': { target: 'ws://localhost:8080', ws: true } } },
  test: {
    environment: 'node',
  },
})
```

- [ ] **Step 4: Write the failing tests**

Create `console/frontend/src/__tests__/seoJsonUtils.test.js`:

```js
import { describe, it, expect } from 'vitest'

// We'll import these after implementing them in Task 2.
// For now define inline copies so the tests can be written first.
function parseSeoJson(text) {
  throw new Error('not implemented')
}

function extractSeoFromSeoJson(seoJson) {
  throw new Error('not implemented')
}

const VALID_SEO_JSON = {
  meta: { video_title_slug: 'bamboo-engawa-rain', channel: 'soundscapes', video_length_hours: 8 },
  titles: {
    recommended: 'Bamboo Forest Rain · Japanese Koto Music for Studying · 8 Hours',
    alternatives: ['Japanese Study Music · Bamboo Rain & Koto Ambience · 8 Hours'],
  },
  description: {
    full: 'Bamboo forest rain ambience with Japanese koto music — designed for studying.',
  },
  tags: {
    all: ['study music', 'bamboo forest', 'koto music'],
  },
}

describe('parseSeoJson', () => {
  it('parses valid SEO JSON text', () => {
    const result = parseSeoJson(JSON.stringify(VALID_SEO_JSON))
    expect(result).toEqual(VALID_SEO_JSON)
  })

  it('throws on invalid JSON syntax', () => {
    expect(() => parseSeoJson('not json')).toThrow()
  })

  it('throws when titles.recommended and description.full are both absent', () => {
    const bad = { meta: { channel: 'soundscapes' } }
    expect(() => parseSeoJson(JSON.stringify(bad))).toThrow('Not a valid SEO JSON')
  })

  it('accepts JSON that has description.full even without titles.recommended', () => {
    const partial = { description: { full: 'Some description' } }
    expect(() => parseSeoJson(JSON.stringify(partial))).not.toThrow()
  })
})

describe('extractSeoFromSeoJson', () => {
  it('maps titles.recommended to seo_title', () => {
    const result = extractSeoFromSeoJson(VALID_SEO_JSON)
    expect(result.seo_title).toBe('Bamboo Forest Rain · Japanese Koto Music for Studying · 8 Hours')
  })

  it('maps description.full to seo_description', () => {
    const result = extractSeoFromSeoJson(VALID_SEO_JSON)
    expect(result.seo_description).toBe('Bamboo forest rain ambience with Japanese koto music — designed for studying.')
  })

  it('joins tags.all as comma-separated string into seo_tags', () => {
    const result = extractSeoFromSeoJson(VALID_SEO_JSON)
    expect(result.seo_tags).toBe('study music, bamboo forest, koto music')
  })

  it('maps meta.video_length_hours to target_duration_h', () => {
    const result = extractSeoFromSeoJson(VALID_SEO_JSON)
    expect(result.target_duration_h).toBe(8)
  })

  it('returns null for missing optional fields', () => {
    const minimal = { titles: { recommended: 'Some Title' } }
    const result = extractSeoFromSeoJson(minimal)
    expect(result.seo_description).toBeNull()
    expect(result.seo_tags).toBeNull()
    expect(result.target_duration_h).toBeNull()
  })
})
```

- [ ] **Step 5: Run tests — verify they fail**

```bash
cd console/frontend && npm test
```

Expected: all tests FAIL with `Error: not implemented` (or similar). If Vitest itself errors, check the config. The tests should be *found and run*, just failing.

- [ ] **Step 6: Commit the test scaffolding**

```bash
git add console/frontend/package.json console/frontend/vite.config.js console/frontend/src/__tests__/seoJsonUtils.test.js
git commit -m "test: add vitest + failing tests for parseSeoJson and extractSeoFromSeoJson"
```

---

### Task 2: Implement `parseSeoJson` and `extractSeoFromSeoJson`

**Files:**
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx` (add two functions near line 244)
- Modify: `console/frontend/src/__tests__/seoJsonUtils.test.js` (swap inline stubs for real imports)

- [ ] **Step 1: Add the two functions to `YouTubeVideosPage.jsx`**

Open `console/frontend/src/pages/YouTubeVideosPage.jsx`. Find line 244 (end of `extractSeoFromSfxJson`). Insert the two new functions immediately after line 244, before `function extractPromptsFromJsons`:

```js
export function parseSeoJson(text) {
  const data = JSON.parse(text)
  if (!data.titles?.recommended && !data.description?.full) {
    throw new Error('Not a valid SEO JSON — missing titles.recommended or description.full')
  }
  return data
}

export function extractSeoFromSeoJson(seoJson) {
  const titles = seoJson.titles      || {}
  const desc   = seoJson.description || {}
  const tags   = seoJson.tags        || {}
  const meta   = seoJson.meta        || {}
  return {
    seo_title:         titles.recommended                          || null,
    seo_description:   desc.full                                   || null,
    seo_tags:          Array.isArray(tags.all) ? tags.all.join(', ') : null,
    target_duration_h: meta.video_length_hours                     || null,
  }
}
```

Note: the `export` keyword is added so the test file can import them. All other functions in this file are module-internal — only these two need exports.

- [ ] **Step 2: Update the test file to import from the real source**

Open `console/frontend/src/__tests__/seoJsonUtils.test.js`. Replace the two inline stub functions at the top with real imports:

```js
import { describe, it, expect } from 'vitest'
import { parseSeoJson, extractSeoFromSeoJson } from '../pages/YouTubeVideosPage.jsx'
```

Remove (delete) these lines from the file:
```js
function parseSeoJson(text) {
  throw new Error('not implemented')
}

function extractSeoFromSeoJson(seoJson) {
  throw new Error('not implemented')
}
```

- [ ] **Step 3: Run tests — verify they pass**

```bash
cd console/frontend && npm test
```

Expected output (all green):
```
✓ parseSeoJson > parses valid SEO JSON text
✓ parseSeoJson > throws on invalid JSON syntax
✓ parseSeoJson > throws when titles.recommended and description.full are both absent
✓ parseSeoJson > accepts JSON that has description.full even without titles.recommended
✓ extractSeoFromSeoJson > maps titles.recommended to seo_title
✓ extractSeoFromSeoJson > maps description.full to seo_description
✓ extractSeoFromSeoJson > joins tags.all as comma-separated string into seo_tags
✓ extractSeoFromSeoJson > maps meta.video_length_hours to target_duration_h
✓ extractSeoFromSeoJson > returns null for missing optional fields

Test Files  1 passed (1)
Tests       9 passed (9)
```

If Vitest fails to resolve the JSX import, add this to `vite.config.js` under `test`:
```js
test: {
  environment: 'node',
  resolve: { extensions: ['.js', '.jsx'] },
},
```

- [ ] **Step 4: Commit**

```bash
git add console/frontend/src/pages/YouTubeVideosPage.jsx console/frontend/src/__tests__/seoJsonUtils.test.js
git commit -m "feat: add parseSeoJson and extractSeoFromSeoJson pure functions"
```

---

### Task 3: Add state, handler, and update SEO resolution in `ImportFromTemplateModal`

**Files:**
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx` (lines 292–295, 353, 355–360, 459–463)

- [ ] **Step 1: Add four state variables after line 295**

Find this block (lines 292–295):
```js
  const [sfxJson,        setSfxJson]        = useState(null)
  const [sfxJsonError,   setSfxJsonError]   = useState(null)
  const [sfxMode,        setSfxMode]        = useState('file')
  const [sfxPaste,       setSfxPaste]       = useState('')
```

Add four lines immediately after it:
```js
  const [seoJson,        setSeoJson]        = useState(null)
  const [seoJsonError,   setSeoJsonError]   = useState(null)
  const [seoMode,        setSeoMode]        = useState('file')
  const [seoPaste,       setSeoPaste]       = useState('')
```

- [ ] **Step 2: Add `handleSeoFile` after `handleSfxFile` (around line 340)**

Find `handleSfxFile` (lines 332–340):
```js
  const handleSfxFile = (e) => {
    const file = e.target.files?.[0]; if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      try { setSfxJson(parseSfxJson(ev.target.result)); setSfxJsonError(null) }
      catch (e) { setSfxJson(null); setSfxJsonError(e.message) }
    }
    reader.readAsText(file)
  }
```

Add the following immediately after it:
```js
  const handleSeoFile = (e) => {
    const file = e.target.files?.[0]; if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      try { setSeoJson(parseSeoJson(ev.target.result)); setSeoJsonError(null) }
      catch (e) { setSeoJson(null); setSeoJsonError(e.message) }
    }
    reader.readAsText(file)
  }
```

- [ ] **Step 3: Update `canNext1` (line 353)**

Find:
```js
  const canNext1 = musicJson !== null || sfxJson !== null
```

Replace with:
```js
  const canNext1 = musicJson !== null || sfxJson !== null || seoJson !== null
```

- [ ] **Step 4: Update `handleApplyDataOnly` (lines 355–360)**

Find:
```js
  const handleApplyDataOnly = () => {
    const seo     = sfxJson ? extractSeoFromSfxJson(sfxJson) : null
    const prompts = extractPromptsFromJsons(musicJson, sfxJson)
    onImported({ music_track_id: null, sound_layers: {}, seo, prompts })
    onClose()
  }
```

Replace with:
```js
  const handleApplyDataOnly = () => {
    const seo     = seoJson ? extractSeoFromSeoJson(seoJson) : sfxJson ? extractSeoFromSfxJson(sfxJson) : null
    const prompts = extractPromptsFromJsons(musicJson, sfxJson)
    onImported({ music_track_id: null, sound_layers: {}, seo, prompts })
    onClose()
  }
```

- [ ] **Step 5: Update `handleApply` (lines 459–463)**

Find:
```js
  const handleApply = () => {
    const prompts = extractPromptsFromJsons(musicJson, sfxJson)
    onImported({ music_track_id: genMusicId, sound_layers: finalLayers, seo: sfxJson ? extractSeoFromSfxJson(sfxJson) : null, prompts })
    onClose()
  }
```

Replace with:
```js
  const handleApply = () => {
    const prompts = extractPromptsFromJsons(musicJson, sfxJson)
    const seo     = seoJson ? extractSeoFromSeoJson(seoJson) : sfxJson ? extractSeoFromSfxJson(sfxJson) : null
    onImported({ music_track_id: genMusicId, sound_layers: finalLayers, seo, prompts })
    onClose()
  }
```

- [ ] **Step 6: Run tests to make sure nothing broke**

```bash
cd console/frontend && npm test
```

Expected: all 9 tests still pass.

- [ ] **Step 7: Commit**

```bash
git add console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "feat: wire seoJson state and SEO priority resolution into ImportFromTemplateModal"
```

---

### Task 4: Add the SEO JSON section to `renderStep1`

**Files:**
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx` (lines 516–611)

- [ ] **Step 1: Update the intro text**

Find (line 518–520):
```jsx
      <p className="text-xs text-[#9090a8]">
        Provide one or both JSON template files. Each is optional — you can import just music, just SFX, or both.
      </p>
```

Replace with:
```jsx
      <p className="text-xs text-[#9090a8]">
        Provide any combination of JSON template files. Each is optional — music, SFX, and SEO are all independent.
      </p>
```

- [ ] **Step 2: Add the SEO JSON section after the closing `</div>` of the SFX JSON block**

Find the closing of the SFX JSON block (line 609):
```jsx
        {sfxJsonError && <span className="text-xs text-[#f87171]">{sfxJsonError}</span>}
      </div>
    </div>
  )
```

Insert the new SEO JSON section between `</div>` (end of SFX block) and `</div>` (end of outer flex):

```jsx
        {sfxJsonError && <span className="text-xs text-[#f87171]">{sfxJsonError}</span>}
      </div>

      {/* SEO JSON */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-[#5a5a70] tracking-widest">SEO JSON</span>
          <div className="flex gap-1">
            <button onClick={() => setSeoMode('file')}
              className={`text-xs px-2 py-0.5 rounded border transition-colors ${seoMode==='file' ? 'bg-[#7c6af7] border-[#7c6af7] text-white' : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8]'}`}>
              File
            </button>
            <button onClick={() => setSeoMode('paste')}
              className={`text-xs px-2 py-0.5 rounded border transition-colors ${seoMode==='paste' ? 'bg-[#7c6af7] border-[#7c6af7] text-white' : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8]'}`}>
              Paste
            </button>
          </div>
        </div>
        {seoMode === 'file' ? (
          <input type="file" accept=".json"
            onChange={handleSeoFile}
            className="text-sm text-[#9090a8] file:mr-3 file:py-1 file:px-2 file:rounded file:border-0 file:bg-[#2a2a32] file:text-[#e8e8f0] file:text-xs cursor-pointer"
          />
        ) : (
          <textarea
            value={seoPaste}
            onChange={e => { setSeoPaste(e.target.value); loadJsonFromText(e.target.value, parseSeoJson, setSeoJson, setSeoJsonError) }}
            rows={4}
            placeholder='Paste SEO JSON here…'
            className="w-full px-3 py-2 rounded-lg bg-[#16161a] border border-[#2a2a32] text-xs text-[#e8e8f0] font-mono resize-none focus:outline-none focus:border-[#7c6af7]"
          />
        )}
        {seoJson && (() => {
          const seo = extractSeoFromSeoJson(seoJson)
          const tagCount = seoJson.tags?.all?.length || 0
          const titlePreview = (seo.seo_title || '').slice(0, 60) + ((seo.seo_title || '').length > 60 ? '…' : '')
          return (
            <>
              <span className="text-xs text-[#34d399]">🔍 {titlePreview || 'SEO JSON loaded'}</span>
              <div className="pl-2 border-l-2 border-[#2a2a32] flex flex-col gap-0.5 mt-0.5">
                {seo.target_duration_h && (
                  <span className="text-xs text-[#9090a8]">Duration: <span className="text-[#e8e8f0]">{seo.target_duration_h}h</span></span>
                )}
                {tagCount > 0 && (
                  <span className="text-xs text-[#9090a8]">Tags: <span className="text-[#e8e8f0]">{tagCount} tags loaded</span></span>
                )}
              </div>
            </>
          )
        })()}
        {seoJsonError && <span className="text-xs text-[#f87171]">{seoJsonError}</span>}
      </div>
    </div>
  )
```

- [ ] **Step 2: Run tests**

```bash
cd console/frontend && npm test
```

Expected: all 9 tests still pass.

- [ ] **Step 3: Commit**

```bash
git add console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "feat: add SEO JSON section to Import Template modal Step 1"
```

---

### Task 5: Manual smoke test

**No files to change — verification only.**

- [ ] **Step 1: Start the dev server**

```bash
cd console/frontend && npm run dev
```

Open `http://localhost:5173` in a browser. Log in.

- [ ] **Step 2: Open the Import Template modal**

Navigate to the YouTube Videos page. Click "↓ Import Template". Verify Step 1 now shows three sections: `MUSIC JSON`, `SFX JSON`, `SEO JSON` — each with File/Paste toggle.

- [ ] **Step 3: Test SEO JSON file upload**

Click "File" under `SEO JSON`. Select the file:
`/Volumes/SSD/Workspace/ai-media-automation/output/seo/2026-05-06_soundscapes_bamboo-engawa-rain_seo.json`

Expected:
- Green badge: `🔍 Bamboo Forest Rain · Japanese Koto Music for Studyin…`
- Sub-line: `Duration: 8h`
- Sub-line: `Tags: 40 tags loaded`
- "Apply data only →" button becomes enabled

- [ ] **Step 4: Test Apply data only — verify SEO fields populated**

Click "Apply data only →". The modal closes. Check the form fields on the video:
- `SEO Title` = `Bamboo Forest Rain · Japanese Koto Music for Studying · 8 Hours`
- `SEO Description` = full description text (starts with "Bamboo forest rain ambience…")
- `SEO Tags` = `study music, bamboo forest, bamboo rain, japanese study music, koto music, …` (40 tags comma-separated)

- [ ] **Step 5: Verify fallback — SFX JSON still provides SEO when no SEO JSON loaded**

Open the modal again. Load only an SFX JSON file (no SEO JSON). Click "Apply data only →". Verify that SEO fields are still populated from the SFX JSON (existing behaviour unchanged).

- [ ] **Step 6: Test paste mode**

Open the modal. Click "Paste" under `SEO JSON`. Paste the contents of the SEO JSON file. Verify the same green badge and sub-lines appear.

- [ ] **Step 7: Test invalid JSON**

In paste mode, type `{bad`. Verify a red error message appears: `Not a valid SEO JSON — missing titles.recommended or description.full` or a JSON parse error.
