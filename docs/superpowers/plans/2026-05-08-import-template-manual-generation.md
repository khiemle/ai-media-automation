# Import Template — Manual Generation Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the auto-start Step 3 generation in `ImportFromTemplateModal` with a fully manual UI where users trigger items individually, run all pending at once, or remove items before generation.

**Architecture:** All changes are inside `ImportFromTemplateModal` in `YouTubeVideosPage.jsx`. Remove the `useEffect([step])` auto-start; extract generation logic into callable handlers (`handleGenerateItem`, `handleStartAll`, `handleRemoveItem`); update `renderStep3` with per-item controls; change footer so Step 4 requires a manual "Next →" click.

**Tech Stack:** React 18 (functional component, hooks), existing `musicApi` / `sfxApi` from `client.js`, Tailwind CSS, existing `Button`/`Spinner` components.

---

## File Map

| File | Change |
|---|---|
| `console/frontend/src/pages/YouTubeVideosPage.jsx` | All changes — `ImportFromTemplateModal` only |

---

## Task 1: Replace auto-start effect with manual generation handlers

**Files:**
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx`

The current `useEffect([step])` at the Step 3 section auto-starts generation on entry (lines ~372–442). This task removes it and replaces it with named, callable handlers. It also adds a `genItemsRef` so async handlers can safely check whether items were removed while awaiting API calls.

- [ ] **Step 1: Read the current Step 3 useEffect**

Read lines 371–442 of `console/frontend/src/pages/YouTubeVideosPage.jsx` to confirm the exact text before editing.

- [ ] **Step 2: Add `useRef` to the React import**

Find:
```js
import { useState, useEffect } from 'react'
```
Replace with:
```js
import { useState, useEffect, useRef } from 'react'
```

- [ ] **Step 3: Add `genItemsRef` and its sync effect inside `ImportFromTemplateModal`**

In `ImportFromTemplateModal`, find the Step 3 state block:
```js
  // ── Step 3 ─────────────────────────────────────────────────────────────────
  const [genItems,       setGenItems]       = useState([])
  const [genMusicId,     setGenMusicId]     = useState(null)
  const [genSfxResults,  setGenSfxResults]  = useState([])
```
Replace with:
```js
  // ── Step 3 ─────────────────────────────────────────────────────────────────
  const [genItems,       setGenItems]       = useState([])
  const [genMusicId,     setGenMusicId]     = useState(null)
  const [genSfxResults,  setGenSfxResults]  = useState([])
  const genItemsRef = useRef([])
  useEffect(() => { genItemsRef.current = genItems }, [genItems])
```

- [ ] **Step 4: Add `buildGenItemsList` helper between Step 2 helpers and the Step 3 effect**

Find the comment line:
```js
  // ── Step 3 generation effect ───────────────────────────────────────────────
```
Insert immediately before it:
```js
  // ── Step 3 helpers ─────────────────────────────────────────────────────────
  const buildGenItemsList = () => {
    const items = []
    if (musicJson && planReady) {
      items.push({ key: 'music', type: 'music', title: musicJson.meta?.title || 'Music Track', status: 'pending', error: null })
    }
    if (sfxJson) {
      collectSfxItems(sfxJson).forEach(si => items.push({
        key: si.key, type: 'sfx', title: si.title,
        status: si.automationOnly ? 'skipped' : 'pending',
        error: null, sfxItem: si,
      }))
    }
    return items
  }

  const handleGenerateItem = async (genItem) => {
    setGenItems(prev => prev.map(it => it.key === genItem.key ? { ...it, status: 'generating', error: null } : it))

    if (genItem.type === 'music') {
      try {
        const plan = JSON.parse(planJson)
        const resp = await musicApi.elevenlabsCompose({
          composition_plan: plan,
          title: musicJson?.meta?.title || 'Music Track',
          niches: [], moods: [], genres: [],
        })
        await pollMusicTask(resp.task_id)
        setGenMusicId(resp.track_id)
        setGenItems(prev => prev.map(it => it.key === 'music' ? { ...it, status: 'done' } : it))
      } catch (e) {
        setGenItems(prev => prev.map(it => it.key === 'music' ? { ...it, status: 'failed', error: String(e.message || e).slice(0, 100) } : it))
      }
    } else {
      try {
        const asset = await sfxApi.generate({
          text:  genItem.sfxItem.prompt,
          loop:  genItem.sfxItem.loop,
          title: genItem.title,
        })
        setGenSfxResults(prev => {
          const next = [...prev.filter(r => r.item.key !== genItem.key), { item: genItem.sfxItem, assetId: asset.id }]
          setFinalLayers(assembleSoundLayers(next))
          return next
        })
        setGenItems(prev => prev.map(it => it.key === genItem.key ? { ...it, status: 'done' } : it))
      } catch (e) {
        setGenItems(prev => prev.map(it => it.key === genItem.key ? { ...it, status: 'failed', error: String(e.message || e).slice(0, 100) } : it))
      }
    }
  }

  const handleStartAll = async () => {
    const pending = genItemsRef.current.filter(it => it.status === 'pending')
    const musicItem = pending.find(it => it.type === 'music')
    const sfxItems  = pending.filter(it => it.type === 'sfx')
    if (musicItem) await handleGenerateItem(musicItem)
    for (const item of sfxItems) {
      if (!genItemsRef.current.find(it => it.key === item.key)) continue
      await handleGenerateItem(item)
    }
  }

  const handleRemoveItem = (key) => {
    setGenItems(prev => prev.filter(it => it.key !== key))
  }

```

- [ ] **Step 5: Remove the auto-start `useEffect([step])` and replace with item-building effect**

Find and remove the entire block:
```js
  // ── Step 3 generation effect ───────────────────────────────────────────────
  useEffect(() => {
    if (step !== 3) return
    let cancelled = false

    const upd = (key, patch) =>
      !cancelled && setGenItems(prev => prev.map(it => it.key === key ? { ...it, ...patch } : it))

    const run = async () => {
      // Build item list from current state (captured at effect fire time)
      const items = []
      if (musicJson && planReady) {
        items.push({ key: 'music', type: 'music', title: musicJson.meta?.title || 'Music Track', status: 'pending', error: null })
      }
      if (sfxJson) {
        collectSfxItems(sfxJson).forEach(si => items.push({
          key: si.key, type: 'sfx', title: si.title,
          status: si.automationOnly ? 'skipped' : 'pending',
          error: null, sfxItem: si,
        }))
      }
      if (!cancelled) setGenItems(items)

      let trackId = null
      const sfxRes = []

      // Music
      if (items.find(it => it.type === 'music')) {
        upd('music', { status: 'generating' })
        try {
          const plan = JSON.parse(planJson)
          const resp = await musicApi.elevenlabsCompose({
            composition_plan: plan,
            title: musicJson.meta?.title || 'Music Track',
            niches: [], moods: [], genres: [],
          })
          trackId = resp.track_id
          await pollMusicTask(resp.task_id)
          if (!cancelled) setGenMusicId(trackId)
          upd('music', { status: 'done' })
        } catch (e) {
          upd('music', { status: 'failed', error: String(e.message || e).slice(0, 100) })
        }
      }

      // SFX — sequential
      for (const item of items.filter(it => it.type === 'sfx' && it.status === 'pending')) {
        if (cancelled) break
        upd(item.key, { status: 'generating' })
        try {
          const asset = await sfxApi.generate({
            text:  item.sfxItem.prompt,
            loop:  item.sfxItem.loop,
            title: item.title,
          })
          sfxRes.push({ item: item.sfxItem, assetId: asset.id })
          upd(item.key, { status: 'done' })
        } catch (e) {
          upd(item.key, { status: 'failed', error: String(e.message || e).slice(0, 100) })
        }
      }

      if (!cancelled) {
        setGenSfxResults(sfxRes)
        setFinalLayers(assembleSoundLayers(sfxRes))
        setStep(4)
      }
    }

    run()
    return () => { cancelled = true }
  }, [step]) // eslint-disable-line react-hooks/exhaustive-deps
```

Replace the removed block with nothing — the handlers added in Step 4 replace all of this logic.

- [ ] **Step 6: Update `handleNext1` to populate `genItems` before setting step 3**

Find:
```js
  const handleNext1 = () => {
    if (!canNext1) return
    if (musicJson) {
      setCompPrompt(buildMusicPrompt(musicJson))
      setStep(2)
    } else {
      setStep(3)
    }
  }
```
Replace with:
```js
  const handleNext1 = () => {
    if (!canNext1) return
    if (musicJson) {
      setCompPrompt(buildMusicPrompt(musicJson))
      setStep(2)
    } else {
      setGenItems(buildGenItemsList())
      setStep(3)
    }
  }
```

- [ ] **Step 7: Add `handleNext2` and update the Step 2 footer button to use it**

In the `footer` function, find the Step 2 return:
```js
    if (step === 2) return (
      <>
        <Button variant="ghost" onClick={() => setStep(1)}>← Back</Button>
        <Button variant="primary" disabled={!canNext2} onClick={() => setStep(3)}>
          Next: Generate →
        </Button>
      </>
    )
```
Replace with:
```js
    if (step === 2) return (
      <>
        <Button variant="ghost" onClick={() => setStep(1)}>← Back</Button>
        <Button variant="primary" disabled={!canNext2} onClick={() => { setGenItems(buildGenItemsList()); setStep(3) }}>
          Next: Generate →
        </Button>
      </>
    )
```

- [ ] **Step 8: Build and verify no errors**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/frontend && npm run build
```
Expected: clean build, 0 errors.

- [ ] **Step 9: Commit**

```bash
git add console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "feat: replace auto-start effect with manual generation handlers in Step 3"
```

---

## Task 2: Update `renderStep3` and Step 3 footer

**Files:**
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx`

This task replaces the current Step 3 render (static list + "please wait" message) with the manual UI: a "▶ Start All" header row, per-item ▶ and ✕ buttons, and a footer that progresses from "Generating…" → "▶ Start All" → "Next →" based on item states.

- [ ] **Step 1: Replace `renderStep3`**

Find and replace the entire `renderStep3` function:
```js
  // ── Step 3 render ──────────────────────────────────────────────────────────
  const renderStep3 = () => (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-[#9090a8] mb-1">Generating assets — please wait…</p>
      {genItems.map(item => (
        <div key={item.key} className="flex flex-col py-1.5 border-b border-[#2a2a32]">
          <div className="flex items-center justify-between">
            <span className="text-sm text-[#e8e8f0] truncate flex-1 mr-2">
              {item.type === 'music' ? '🎵' : '🔊'} {item.title}
            </span>
            {statusBadge(item.status, item.error)}
          </div>
          {item.status === 'generating' && item.type === 'music' && (
            <div className="w-32 h-1.5 bg-[#2a2a32] rounded-full overflow-hidden mt-1">
              <div className="h-full bg-[#7c6af7] rounded-full animate-pulse" style={{ width: '60%' }} />
            </div>
          )}
        </div>
      ))}
      {genItems.length === 0 && <span className="text-xs text-[#5a5a70]">Preparing…</span>}
    </div>
  )
```

Replace with:
```jsx
  // ── Step 3 render ──────────────────────────────────────────────────────────
  const renderStep3 = () => {
    const pendingCount   = genItems.filter(it => it.status === 'pending').length
    const anyGenerating  = genItems.some(it => it.status === 'generating')

    return (
      <div className="flex flex-col gap-2">
        {/* Header row */}
        <div className="flex items-center justify-between pb-2 border-b border-[#2a2a32]">
          <span className="text-xs text-[#9090a8]">
            {anyGenerating ? 'Generating…' : pendingCount > 0 ? `${pendingCount} pending` : 'All done'}
          </span>
          {pendingCount > 0 && !anyGenerating && (
            <Button variant="primary" size="sm" onClick={handleStartAll}>
              ▶ Start All
            </Button>
          )}
        </div>

        {/* Item list */}
        {genItems.map(item => {
          const isSkipped    = item.status === 'skipped'
          const isGenerating = item.status === 'generating'
          const isDone       = item.status === 'done'
          const canTrigger   = item.status === 'pending' || item.status === 'failed'
          const canRemove    = item.status === 'pending' || item.status === 'failed'

          return (
            <div key={item.key} className="flex flex-col py-1.5 border-b border-[#2a2a32] last:border-0">
              <div className="flex items-center gap-2">
                <span className="text-sm text-[#e8e8f0] truncate flex-1">
                  {item.type === 'music' ? '🎵' : '🔊'} {item.title}
                </span>
                {statusBadge(item.status, item.error)}
                {!isSkipped && !isDone && (
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={isGenerating}
                    title="Generate"
                    onClick={() => canTrigger && handleGenerateItem(item)}
                  >
                    ▶
                  </Button>
                )}
                {canRemove && (
                  <Button
                    variant="ghost"
                    size="sm"
                    title="Remove"
                    onClick={() => handleRemoveItem(item.key)}
                  >
                    ✕
                  </Button>
                )}
              </div>
              {isGenerating && item.type === 'music' && (
                <div className="w-32 h-1.5 bg-[#2a2a32] rounded-full overflow-hidden mt-1">
                  <div className="h-full bg-[#7c6af7] rounded-full animate-pulse" style={{ width: '60%' }} />
                </div>
              )}
            </div>
          )
        })}

        {genItems.length === 0 && (
          <span className="text-xs text-[#5a5a70]">No items — go back and load a JSON file.</span>
        )}
      </div>
    )
  }
```

- [ ] **Step 2: Update the Step 3 footer**

In the `footer` function, find:
```js
    if (step === 3) return (
      <Button variant="ghost" disabled>Generating… please wait</Button>
    )
```
Replace with:
```js
    if (step === 3) {
      const anyGenerating = genItems.some(it => it.status === 'generating')
      const anyPending    = genItems.some(it => it.status === 'pending')
      if (anyGenerating) return <Button variant="ghost" disabled>Generating… please wait</Button>
      if (anyPending)    return <Button variant="primary" onClick={handleStartAll}>▶ Start All</Button>
      return <Button variant="primary" onClick={() => setStep(4)}>Next →</Button>
    }
```

- [ ] **Step 3: Update the modal `onClose` guard**

Currently, step 3 blocks close with:
```js
  return (
    <Modal open onClose={step === 3 ? undefined : onClose} title={STEP_TITLES[step]} width="max-w-2xl"
```

The guard should now check for any `generating` item rather than blindly blocking all of step 3:
```js
  const blockClose = step === 3 && genItems.some(it => it.status === 'generating')
  return (
    <Modal open onClose={blockClose ? undefined : onClose} title={STEP_TITLES[step]} width="max-w-2xl"
```

- [ ] **Step 4: Build and verify**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/frontend && npm run build
```
Expected: clean build, 0 errors.

- [ ] **Step 5: Manual smoke test**

Start dev server: `npm run dev` in `console/frontend/`.

Open the YouTube Videos page → "New Video" → "↓ Import Template".

**Step 1:** Load a valid SFX JSON (paste mode). Confirm SEO preview appears. Click "Next: Generate →".

**Step 3 — manual mode:**
- Confirm no generation starts automatically
- Header row shows "N pending" and "▶ Start All" button
- Each item shows ▶ and ✕ buttons (except `skipped` items)
- Click ✕ on one SFX item — confirm it disappears from list, pending count decreases
- Click ▶ on one item — confirm it transitions pending → generating → done/failed
- Click "▶ Start All" — confirm remaining pending items run sequentially
- While generating, confirm modal cannot be closed (click backdrop — nothing)
- Once all items resolve, confirm "Next →" appears in footer
- Click "Next →" — confirm Step 4 loads

**Step 3 — empty list:**
- Go back to Step 1, load SFX JSON, go to Step 3, remove all items
- Confirm "No items — go back…" message
- Confirm "Next →" appears immediately (no pending or generating)

- [ ] **Step 6: Commit**

```bash
git add console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "feat: manual Step 3 UI — per-item trigger/remove, Start All, Next → to Step 4"
```

---

## Spec Coverage Check

| Spec requirement | Task |
|---|---|
| Remove auto-start `useEffect([step])` | Task 1 Step 5 |
| `buildGenItemsList()` helper | Task 1 Step 4 |
| `handleGenerateItem(genItem)` — music + SFX | Task 1 Step 4 |
| `handleStartAll()` — sequential, skips removed items | Task 1 Step 4 |
| `handleRemoveItem(key)` | Task 1 Step 4 |
| `genItems` populated before `setStep(3)` (from Step 1 and Step 2) | Task 1 Steps 6–7 |
| Header row: "▶ Start All" + pending count | Task 2 Step 1 |
| Per-item ▶ button (enabled: pending/failed; disabled: generating; hidden: done/skipped) | Task 2 Step 1 |
| Per-item ✕ button (enabled: pending/failed; hidden: done/skipped/generating) | Task 2 Step 1 |
| Footer: disabled while generating | Task 2 Step 2 |
| Footer: "▶ Start All" while pending | Task 2 Step 2 |
| Footer: "Next →" when all resolved | Task 2 Step 2 |
| Modal close blocked only while any item generating | Task 2 Step 3 |
| Step 4 requires manual "Next →" (no auto-advance) | Task 2 Step 2 |
