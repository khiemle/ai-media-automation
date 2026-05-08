# Import Template — Data-Only Apply & Prompt Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an "Apply data only →" shortcut to Step 1 of the Import Template wizard that extracts SEO + prompt data from loaded JSONs and applies them immediately without generating audio; also extract Music/Visual/Midjourney prompts from the JSON and populate renamed prompt fields in `CreationPanel`.

**Architecture:** Three tasks in `ImportFromTemplateModal` and `CreationPanel`, all in `YouTubeVideosPage.jsx`. Task 1 adds the pure helper and updates the Step 4 apply payload. Task 2 adds the shortcut handler and Step 1 footer button. Task 3 wires the payload into `CreationPanel` — new state variable, updated handler, renamed labels, new display block.

**Tech Stack:** React 18 (useState, functional component), Tailwind CSS, existing `Button` component.

---

## File Map

| File | Change |
|---|---|
| `console/frontend/src/pages/YouTubeVideosPage.jsx` | All changes |

---

## Task 1: Add `extractPromptsFromJsons` helper and extend `handleApply` payload

**Files:**
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx`

This task adds the pure helper that extracts prompts from loaded JSON objects, and updates the existing `handleApply` in Step 4 to include `prompts` in the `onImported` call. No UI changes yet.

- [ ] **Step 1: Read the target region**

Read lines 217–247 of `console/frontend/src/pages/YouTubeVideosPage.jsx` to confirm the exact text of `extractSeoFromSfxJson` and the line it ends on before `VideoPreviewModal`.

- [ ] **Step 2: Add `extractPromptsFromJsons` after `extractSeoFromSfxJson`**

Find the closing brace of `extractSeoFromSfxJson` (the block that ends with `}`):
```js
  return {
    theme:             meta.theme              || null,
    target_duration_h: meta.video_length_hours || null,
    seo_title:         meta.title              || null,
    seo_description:   seoDescription,
    seo_tags:          seoTags,
  }
}
```

Insert immediately after it (before `function VideoPreviewModal`):
```js

function extractPromptsFromJsons(musicJson, sfxJson) {
  const result = {}
  if (musicJson)                        result.music      = buildMusicPrompt(musicJson)
  if (sfxJson?.runway?.prompt)          result.visual     = sfxJson.runway.prompt
  if (sfxJson?.midjourney?.full_prompt) result.midjourney = sfxJson.midjourney.full_prompt
  return result
}
```

- [ ] **Step 3: Update `handleApply` in `ImportFromTemplateModal` to include `prompts`**

Find (lines ~444–447):
```js
  const handleApply = () => {
    onImported({ music_track_id: genMusicId, sound_layers: finalLayers, seo: sfxJson ? extractSeoFromSfxJson(sfxJson) : null })
    onClose()
  }
```

Replace with:
```js
  const handleApply = () => {
    const prompts = extractPromptsFromJsons(musicJson, sfxJson)
    onImported({ music_track_id: genMusicId, sound_layers: finalLayers, seo: sfxJson ? extractSeoFromSfxJson(sfxJson) : null, prompts })
    onClose()
  }
```

- [ ] **Step 4: Build and verify**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/frontend && npm run build 2>&1 | tail -10
```

Expected: clean build, 0 errors.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation && git add console/frontend/src/pages/YouTubeVideosPage.jsx && git commit -m "feat: add extractPromptsFromJsons helper and include prompts in handleApply payload"
```

---

## Task 2: Add `handleApplyDataOnly` handler and Step 1 footer button

**Files:**
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx`

This task adds the "Apply data only →" ghost button to Step 1's footer. When clicked it calls `onImported` with SEO + prompts (no music_track_id, empty sound_layers) and closes the wizard immediately.

- [ ] **Step 1: Add `handleApplyDataOnly` inside `ImportFromTemplateModal`**

Find the `handleNext1` function (around line 347):
```js
  const handleNext1 = () => {
```

Insert the following block immediately **before** `handleNext1`:
```js
  const handleApplyDataOnly = () => {
    const seo     = sfxJson ? extractSeoFromSfxJson(sfxJson) : null
    const prompts = extractPromptsFromJsons(musicJson, sfxJson)
    onImported({ music_track_id: null, sound_layers: {}, seo, prompts })
    onClose()
  }

```

- [ ] **Step 2: Update the Step 1 footer to add the ghost button**

In the `footer` function, find:
```js
    if (step === 1) return (
      <>
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button variant="primary" disabled={!canNext1} onClick={handleNext1}>
          {musicJson ? 'Next: Preview Plan →' : 'Next: Generate →'}
        </Button>
      </>
    )
```

Replace with:
```js
    if (step === 1) return (
      <>
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button variant="ghost" disabled={!canNext1} onClick={handleApplyDataOnly}>
          Apply data only →
        </Button>
        <Button variant="primary" disabled={!canNext1} onClick={handleNext1}>
          {musicJson ? 'Next: Preview Plan →' : 'Next: Generate →'}
        </Button>
      </>
    )
```

- [ ] **Step 3: Build and verify**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/frontend && npm run build 2>&1 | tail -10
```

Expected: clean build, 0 errors.

- [ ] **Step 4: Commit**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation && git add console/frontend/src/pages/YouTubeVideosPage.jsx && git commit -m "feat: add Apply data only shortcut to Step 1 footer"
```

---

## Task 3: Wire prompts into CreationPanel — new state, updated handler, renamed labels, Midjourney Prompt field

**Files:**
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx`

This task touches `CreationPanel`. It adds `midjourneyPrompt` state, updates `handleTemplateImported` to receive and apply the new `prompts` payload field, renames the Suno/Runway prompt labels, and inserts a "Midjourney Prompt" read-only display block below the "Midjourney Image" file upload.

- [ ] **Step 1: Add `midjourneyPrompt` state after `autofillRunway`**

Find (around line 840):
```js
  const [autofillSuno, setAutofillSuno] = useState(null)
  const [autofillRunway, setAutofillRunway] = useState(null)
```

Replace with:
```js
  const [autofillSuno, setAutofillSuno] = useState(null)
  const [autofillRunway, setAutofillRunway] = useState(null)
  const [midjourneyPrompt, setMidjourneyPrompt] = useState(null)
```

- [ ] **Step 2: Update `handleTemplateImported` to accept and apply `prompts`**

Find the function signature and closing block (around lines 916–958):
```js
  const handleTemplateImported = ({ music_track_id, sound_layers, seo }) => {
```

Replace the signature line only:
```js
  const handleTemplateImported = ({ music_track_id, sound_layers, seo, prompts }) => {
```

Then find the section just before `setShowImportTemplate(false)`:
```js
    setShowImportTemplate(false)
    showToast('Template imported', 'success')
    sfxApi.list().then(d => setSfxList(d.items || d || []))
  }
```

Replace with:
```js
    if (prompts?.music)      setAutofillSuno(prompts.music)
    if (prompts?.visual)     setAutofillRunway(prompts.visual)
    if (prompts?.midjourney) setMidjourneyPrompt(prompts.midjourney)
    setShowImportTemplate(false)
    showToast('Template imported', 'success')
    sfxApi.list().then(d => setSfxList(d.items || d || []))
  }
```

- [ ] **Step 3: Rename "Suno Prompt" label → "Music Prompt"**

Find (around line 1455–1468):
```js
              {(template?.suno_prompt_template || autofillSuno) && (
                <div className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3 relative">
                  <div className="text-xs text-[#5a5a70] mb-1">
                    Suno Prompt {autofillSuno ? '(AI generated)' : '(reference)'}
                  </div>
                  <p className="text-xs text-[#9090a8] pr-10 leading-relaxed">
                    {autofillSuno || template.suno_prompt_template}
                  </p>
                  <button
                    onClick={() => navigator.clipboard.writeText(autofillSuno || template.suno_prompt_template)}
                    className="absolute top-2 right-2 text-xs text-[#7c6af7] hover:text-[#9d8df8] px-2 py-1 bg-[#16161a] rounded"
                  >
                    Copy
                  </button>
                </div>
              )}
```

Replace with:
```js
              {(template?.suno_prompt_template || autofillSuno) && (
                <div className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3 relative">
                  <div className="text-xs text-[#5a5a70] mb-1">Music Prompt</div>
                  <p className="text-xs text-[#9090a8] pr-10 leading-relaxed">
                    {autofillSuno || template.suno_prompt_template}
                  </p>
                  <button
                    onClick={() => navigator.clipboard.writeText(autofillSuno || template.suno_prompt_template)}
                    className="absolute top-2 right-2 text-xs text-[#7c6af7] hover:text-[#9d8df8] px-2 py-1 bg-[#16161a] rounded"
                  >
                    Copy
                  </button>
                </div>
              )}
```

- [ ] **Step 4: Rename "Runway Prompt" label → "Visual Prompt"**

Find (around line 1557–1571):
```js
              {(template?.runway_prompt_template || autofillRunway) && (
                <div className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3 relative">
                  <div className="text-xs text-[#5a5a70] mb-1">
                    Runway Prompt {autofillRunway ? '(AI generated)' : '(reference)'}
                  </div>
                  <p className="text-xs text-[#9090a8] pr-10 leading-relaxed">
                    {autofillRunway || template.runway_prompt_template}
                  </p>
                  <button
                    onClick={() => navigator.clipboard.writeText(autofillRunway || template.runway_prompt_template)}
                    className="absolute top-2 right-2 text-xs text-[#7c6af7] hover:text-[#9d8df8] px-2 py-1 bg-[#16161a] rounded"
                  >
                    Copy
                  </button>
                </div>
              )}
```

Replace with:
```js
              {(template?.runway_prompt_template || autofillRunway) && (
                <div className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3 relative">
                  <div className="text-xs text-[#5a5a70] mb-1">Visual Prompt</div>
                  <p className="text-xs text-[#9090a8] pr-10 leading-relaxed">
                    {autofillRunway || template.runway_prompt_template}
                  </p>
                  <button
                    onClick={() => navigator.clipboard.writeText(autofillRunway || template.runway_prompt_template)}
                    className="absolute top-2 right-2 text-xs text-[#7c6af7] hover:text-[#9d8df8] px-2 py-1 bg-[#16161a] rounded"
                  >
                    Copy
                  </button>
                </div>
              )}
```

- [ ] **Step 5: Add "Midjourney Prompt" display block below the Midjourney Image file input**

Find the closing `</div>` of the Midjourney Image input group (around lines 1330–1336):
```js
              <div className="flex flex-col gap-1">
                <label className="text-xs text-[#9090a8] font-medium">
                  Midjourney Image (optional)
                </label>
                <input
                  type="file"
                  accept="image/*"
                  onChange={e => setThumbnailFile(e.target.files?.[0] || null)}
                  className="text-sm text-[#9090a8] file:mr-3 file:py-1 file:px-2 file:rounded file:border-0 file:bg-[#2a2a32] file:text-[#e8e8f0] file:text-xs cursor-pointer"
                />
              </div>
```

Replace with:
```js
              <div className="flex flex-col gap-1">
                <label className="text-xs text-[#9090a8] font-medium">
                  Midjourney Image (optional)
                </label>
                <input
                  type="file"
                  accept="image/*"
                  onChange={e => setThumbnailFile(e.target.files?.[0] || null)}
                  className="text-sm text-[#9090a8] file:mr-3 file:py-1 file:px-2 file:rounded file:border-0 file:bg-[#2a2a32] file:text-[#e8e8f0] file:text-xs cursor-pointer"
                />
              </div>
              {midjourneyPrompt && (
                <div className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3 relative">
                  <div className="text-xs text-[#5a5a70] mb-1">Midjourney Prompt</div>
                  <p className="text-xs text-[#9090a8] pr-10 leading-relaxed">{midjourneyPrompt}</p>
                  <button
                    onClick={() => navigator.clipboard.writeText(midjourneyPrompt)}
                    className="absolute top-2 right-2 text-xs text-[#7c6af7] hover:text-[#9d8df8] px-2 py-1 bg-[#16161a] rounded"
                  >
                    Copy
                  </button>
                </div>
              )}
```

- [ ] **Step 6: Build and verify**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/frontend && npm run build 2>&1 | tail -10
```

Expected: clean build, 0 errors.

- [ ] **Step 7: Commit**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation && git add console/frontend/src/pages/YouTubeVideosPage.jsx && git commit -m "feat: wire prompt fields into CreationPanel — Music/Visual/Midjourney Prompt from import"
```

---

## Spec Coverage Check

| Spec requirement | Task |
|---|---|
| `extractPromptsFromJsons(musicJson, sfxJson)` pure helper | Task 1 Step 2 |
| `handleApply` passes `prompts` in payload | Task 1 Step 3 |
| `handleApplyDataOnly()` — SEO + prompts, null music/layers, closes wizard | Task 2 Step 1 |
| Step 1 footer: ghost "Apply data only →" left of "Next →", same enabled condition | Task 2 Step 2 |
| `midjourneyPrompt` state in `CreationPanel` | Task 3 Step 1 |
| `handleTemplateImported` accepts `prompts`, non-destructive patch | Task 3 Step 2 |
| "Suno Prompt ..." → "Music Prompt" label | Task 3 Step 3 |
| "Runway Prompt ..." → "Visual Prompt" label | Task 3 Step 4 |
| "Midjourney Prompt" read-only block below Midjourney Image file input | Task 3 Step 5 |
