# Import from Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an "↓ Import Template" button to the YouTube create modal that opens a 4-step wizard for generating a music track and/or SFX assets from JSON template files, then pre-fills the modal with the results.

**Architecture:** Single frontend file change (`YouTubeVideosPage.jsx`). Pure helper functions + a new `ImportFromTemplateModal` component wired into the existing `CreationPanel`. Reuses existing API endpoints — no backend changes.

**Tech Stack:** React 18, existing `musicApi` + `sfxApi` from `client.js`, existing `Modal`/`Button`/`Toast` components from `components/index.jsx`.

---

## File Map

| File | Change |
|---|---|
| `console/frontend/src/pages/YouTubeVideosPage.jsx` | Add 7 helper functions, `ImportFromTemplateModal` component (~320 lines), `showImportTemplate` state + "↓ Import Template" button + `handleTemplateImported` handler inside `CreationPanel` |

---

## Task 1: Add pure helper functions

**Files:**
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx` (insert after line 66, after the closing `]` of `DURATION_PRESETS`)

These seven functions have no side effects and can be verified in the browser console before the UI is built.

- [ ] **Step 1: Insert the helper functions**

In `YouTubeVideosPage.jsx`, find:

```js
const DURATION_PRESETS = [
  { label: '10min', value: 10 / 60 },
  { label: '1h',    value: 1 },
  { label: '3h',    value: 3 },
  { label: '8h',    value: 8 },
  { label: '10h',   value: 10 },
  { label: 'Custom', value: null },
]
```

Replace with:

```js
const DURATION_PRESETS = [
  { label: '10min', value: 10 / 60 },
  { label: '1h',    value: 1 },
  { label: '3h',    value: 3 },
  { label: '8h',    value: 8 },
  { label: '10h',   value: 10 },
  { label: 'Custom', value: null },
]

// ── Import-from-template helpers ───────────────────────────────────────────────

function parseMusicJson(text) {
  const parsed = JSON.parse(text)
  if (!parsed.composer && !parsed.suno?.style_of_music) {
    throw new Error('Missing required fields: composer or suno.style_of_music')
  }
  return parsed
}

function parseSfxJson(text) {
  const parsed = JSON.parse(text)
  if (!parsed.sfx) throw new Error('Missing required field: sfx')
  return parsed
}

function buildMusicPrompt(json) {
  const c = json.composer
  if (c) {
    return [
      c.function_tag, c.key_mode,
      c.bpm ? `${c.bpm} BPM` : null,
      c.primary_instrument, c.harmonic_bed, c.textural_layer,
      c.dynamic_rule, c.reverb, c.timbre,
      'instrumental', 'no vocals',
    ].filter(Boolean).join(', ')
  }
  return json.suno?.style_of_music || ''
}

function parseInterval(str) {
  const parts = String(str || '').split('-').map(Number)
  if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
    return { min: parts[0], max: parts[1] }
  }
  return { min: 10, max: 25 }
}

function collectSfxItems(sfxJson) {
  const { sfx } = sfxJson
  const items = []
  if (sfx.background) {
    items.push({
      key: 'bg',
      layer: 'background',
      title: sfx.background.name_en || sfx.background.name_vi || 'Background Ambience',
      prompt: sfx.background.english_prompt,
      loop: true,
      automationOnly: false,
      intervalSeconds: null,
      triggerInterval: null,
    })
  }
  ;(sfx.midground || []).forEach((item, i) => {
    items.push({
      key: `mid_${i}`,
      layer: 'midground',
      title: item.name_en || item.name_vi || item.english_prompt.slice(0, 60),
      prompt: item.english_prompt,
      loop: false,
      automationOnly: false,
      intervalSeconds: item.interval_seconds || null,
      triggerInterval: null,
    })
  })
  ;(sfx.foreground || []).forEach((item, i) => {
    items.push({
      key: `fg_${i}`,
      layer: 'foreground',
      title: item.name_en || item.name_vi || item.english_prompt.slice(0, 60),
      prompt: item.english_prompt,
      loop: false,
      automationOnly: false,
      intervalSeconds: item.interval_seconds || null,
      triggerInterval: null,
    })
  })
  const rsfx = sfx.random_sfx || {}
  const triggerInterval = rsfx.trigger_interval_seconds || '60-100'
  ;(rsfx.items || []).forEach((item, i) => {
    items.push({
      key: `rsfx_${i}`,
      layer: 'random_sfx',
      title: item.name_en || item.name_vi || (item.english_prompt || '').slice(0, 60) || 'SFX',
      prompt: item.english_prompt || '',
      loop: false,
      automationOnly: !!item.automation_only,
      intervalSeconds: null,
      triggerInterval,
    })
  })
  return items
}

function assembleSoundLayers(sfxResults) {
  const layers = {}
  const bg = sfxResults.find(r => r.item.layer === 'background')
  if (bg) layers.background = { asset_id: bg.assetId, volume: 0.4 }

  const mids = sfxResults.filter(r => r.item.layer === 'midground')
  if (mids.length > 0) {
    const ivs = mids.filter(r => r.item.intervalSeconds).map(r => parseInterval(r.item.intervalSeconds))
    layers.midground = {
      pool: mids.map(r => r.assetId),
      volume: 0.5,
      interval_min_s: ivs.length ? Math.min(...ivs.map(i => i.min)) : 10,
      interval_max_s: ivs.length ? Math.max(...ivs.map(i => i.max)) : 25,
    }
  }

  const fgs = sfxResults.filter(r => r.item.layer === 'foreground')
  if (fgs.length > 0) {
    const ivs = fgs.filter(r => r.item.intervalSeconds).map(r => parseInterval(r.item.intervalSeconds))
    layers.foreground = {
      pool: fgs.map(r => r.assetId),
      volume: 0.7,
      interval_min_s: ivs.length ? Math.min(...ivs.map(i => i.min)) : 45,
      interval_max_s: ivs.length ? Math.max(...ivs.map(i => i.max)) : 60,
    }
  }

  const rsfxs = sfxResults.filter(r => r.item.layer === 'random_sfx')
  if (rsfxs.length > 0) {
    const tv = parseInterval(rsfxs[0].item.triggerInterval)
    layers.random_sfx = {
      pool: rsfxs.map(r => r.assetId),
      volume: 0.6,
      interval_min_s: tv.min,
      interval_max_s: tv.max,
    }
  }
  return layers
}

async function pollMusicTask(taskId, maxMs = 300000) {
  const start = Date.now()
  while (Date.now() - start < maxMs) {
    const result = await musicApi.pollTask(taskId)
    if (result.generation_status === 'ready') return result
    if (result.generation_status === 'failed') throw new Error(result.error || 'Music generation failed')
    await new Promise(res => setTimeout(res, 3000))
  }
  throw new Error('Music generation timed out after 5 minutes')
}
```

- [ ] **Step 2: Verify helpers load without errors**

Start (or hot-reload) the dev server:
```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/frontend
npm run dev
```

Open `http://localhost:5173`, navigate to the YouTube Videos page. Open the browser console. No red errors should appear (the helpers are module-level functions that don't execute until called).

- [ ] **Step 3: Smoke-test helpers in browser console**

Paste into the browser console:

```js
// parseMusicJson
const mj = {composer:{function_tag:'study music',key_mode:'D Dorian',bpm:70,primary_instrument:'koto',harmonic_bed:'warm pad',textural_layer:'wind',dynamic_rule:'no crescendo',reverb:'warm reverb',timbre:'lush'}}
console.assert(buildMusicPrompt(mj).includes('70 BPM'), 'bpm ok')
console.assert(buildMusicPrompt(mj).includes('no vocals'), 'no vocals ok')

// parseInterval
console.assert(parseInterval('10-18').min === 10, 'min ok')
console.assert(parseInterval('60-100').max === 100, 'max ok')
console.assert(parseInterval('').min === 10, 'fallback ok')

// assembleSoundLayers — background only
const res = [{item:{layer:'background',intervalSeconds:null,triggerInterval:null},assetId:42}]
const sl = assembleSoundLayers(res)
console.assert(sl.background.asset_id === 42, 'bg asset_id ok')
console.assert(sl.background.volume === 0.4, 'bg volume ok')
console.assert(!sl.midground, 'no mid ok')

console.log('All helpers OK')
```

Expected output: `All helpers OK`

- [ ] **Step 4: Commit**

```bash
git add console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "feat: add import-from-template helper functions"
```

---

## Task 2: ImportFromTemplateModal — scaffold + Step 1 (Input)

**Files:**
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx` (insert new component between `VideoPreviewModal` and `CreationPanel`, i.e. after line 95)

- [ ] **Step 1: Insert the ImportFromTemplateModal component**

In `YouTubeVideosPage.jsx`, find the exact line:

```js
function CreationPanel({ template, channelPlan, channelPlans = [], onClose, onCreated, mode = 'create', existingVideo = null }) {
```

Insert the following **before** that line (leave a blank line between them):

```jsx
function ImportFromTemplateModal({ onClose, onImported }) {
  const [step, setStep] = useState(1)

  // ── Step 1 ─────────────────────────────────────────────────────────────────
  const [musicJson,      setMusicJson]      = useState(null)
  const [musicJsonError, setMusicJsonError] = useState(null)
  const [musicMode,      setMusicMode]      = useState('file')
  const [musicPaste,     setMusicPaste]     = useState('')
  const [sfxJson,        setSfxJson]        = useState(null)
  const [sfxJsonError,   setSfxJsonError]   = useState(null)
  const [sfxMode,        setSfxMode]        = useState('file')
  const [sfxPaste,       setSfxPaste]       = useState('')

  // ── Step 2 ─────────────────────────────────────────────────────────────────
  const [compPrompt,  setCompPrompt]  = useState('')
  const [planJson,    setPlanJson]    = useState('')
  const [planLoading, setPlanLoading] = useState(false)
  const [planError,   setPlanError]   = useState(null)
  const [planReady,   setPlanReady]   = useState(false)

  // ── Step 3 ─────────────────────────────────────────────────────────────────
  const [genItems,       setGenItems]       = useState([])
  const [genMusicId,     setGenMusicId]     = useState(null)
  const [genSfxResults,  setGenSfxResults]  = useState([])

  // ── Step 4 ─────────────────────────────────────────────────────────────────
  const [finalLayers, setFinalLayers] = useState({})

  // ── Step 1 helpers ─────────────────────────────────────────────────────────
  const loadJsonFromText = (text, parser, setJson, setError) => {
    if (!text.trim()) { setJson(null); setError(null); return }
    try { setJson(parser(text)); setError(null) }
    catch (e) { setJson(null); setError(e.message) }
  }

  const handleMusicFile = (e) => {
    const file = e.target.files?.[0]; if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      try { setMusicJson(parseMusicJson(ev.target.result)); setMusicJsonError(null) }
      catch (e) { setMusicJson(null); setMusicJsonError(e.message) }
    }
    reader.readAsText(file)
  }

  const handleSfxFile = (e) => {
    const file = e.target.files?.[0]; if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      try { setSfxJson(parseSfxJson(ev.target.result)); setSfxJsonError(null) }
      catch (e) { setSfxJson(null); setSfxJsonError(e.message) }
    }
    reader.readAsText(file)
  }

  const sfxBadge = sfxJson ? (() => {
    const items = collectSfxItems(sfxJson)
    const bg  = items.filter(i => i.layer === 'background').length
    const mid = items.filter(i => i.layer === 'midground').length
    const fg  = items.filter(i => i.layer === 'foreground').length
    const rsfx = items.filter(i => i.layer === 'random_sfx' && !i.automationOnly).length
    const skip = items.filter(i => i.automationOnly).length
    return `${bg} bg, ${mid} mid, ${fg} fg, ${rsfx} random${skip ? `, ${skip} skipped` : ''}`
  })() : null

  const canNext1 = musicJson !== null || sfxJson !== null

  const handleNext1 = () => {
    if (!canNext1) return
    if (musicJson) {
      setCompPrompt(buildMusicPrompt(musicJson))
      setStep(2)
    } else {
      setStep(3)
    }
  }

  // ── Step 2 helpers ─────────────────────────────────────────────────────────
  const handleGeneratePlan = async () => {
    if (!compPrompt.trim()) return
    setPlanLoading(true); setPlanError(null)
    try {
      const res = await musicApi.elevenlabsPlan(compPrompt.trim(), 600000)
      setPlanJson(JSON.stringify(res.composition_plan, null, 2))
      setPlanReady(true)
    } catch (e) {
      setPlanError(e.message || 'Failed to generate plan')
    } finally { setPlanLoading(false) }
  }

  const isPlanValid = () => { try { JSON.parse(planJson); return true } catch { return false } }
  const canNext2 = planReady && isPlanValid()

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

  // ── Step 4 helpers ─────────────────────────────────────────────────────────
  const canApply = genMusicId !== null || genSfxResults.length > 0

  const handleApply = () => {
    onImported({ music_track_id: genMusicId, sound_layers: finalLayers })
  }

  // ── Status badge helper ────────────────────────────────────────────────────
  const statusBadge = (status, error) => {
    if (status === 'pending')    return <span className="text-xs text-[#5a5a70]">pending</span>
    if (status === 'generating') return <span className="text-xs text-[#fbbf24] animate-pulse">generating…</span>
    if (status === 'done')       return <span className="text-xs text-[#34d399]">done</span>
    if (status === 'skipped')    return <span className="text-xs text-[#5a5a70]">skipped</span>
    if (status === 'failed')     return <span className="text-xs text-[#f87171]" title={error}>failed</span>
    return null
  }

  // ── Step 1 render ──────────────────────────────────────────────────────────
  const renderStep1 = () => (
    <div className="flex flex-col gap-5">
      <p className="text-xs text-[#9090a8]">
        Provide one or both JSON template files. Each is optional — you can import just music, just SFX, or both.
      </p>

      {/* Music JSON */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-[#5a5a70] tracking-widest">MUSIC JSON</span>
          <div className="flex gap-1">
            <button onClick={() => setMusicMode('file')}
              className={`text-xs px-2 py-0.5 rounded border transition-colors ${musicMode==='file' ? 'bg-[#7c6af7] border-[#7c6af7] text-white' : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8]'}`}>
              File
            </button>
            <button onClick={() => setMusicMode('paste')}
              className={`text-xs px-2 py-0.5 rounded border transition-colors ${musicMode==='paste' ? 'bg-[#7c6af7] border-[#7c6af7] text-white' : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8]'}`}>
              Paste
            </button>
          </div>
        </div>
        {musicMode === 'file' ? (
          <input type="file" accept=".json"
            onChange={handleMusicFile}
            className="text-sm text-[#9090a8] file:mr-3 file:py-1 file:px-2 file:rounded file:border-0 file:bg-[#2a2a32] file:text-[#e8e8f0] file:text-xs cursor-pointer"
          />
        ) : (
          <textarea
            value={musicPaste}
            onChange={e => { setMusicPaste(e.target.value); loadJsonFromText(e.target.value, parseMusicJson, setMusicJson, setMusicJsonError) }}
            rows={4}
            placeholder='Paste Suno prompt JSON here…'
            className="w-full px-3 py-2 rounded-lg bg-[#16161a] border border-[#2a2a32] text-xs text-[#e8e8f0] font-mono resize-none focus:outline-none focus:border-[#7c6af7]"
          />
        )}
        {musicJson && <span className="text-xs text-[#34d399]">🎵 {musicJson.meta?.title || 'Music JSON loaded'}</span>}
        {musicJsonError && <span className="text-xs text-[#f87171]">{musicJsonError}</span>}
      </div>

      {/* SFX JSON */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-[#5a5a70] tracking-widest">SFX JSON</span>
          <div className="flex gap-1">
            <button onClick={() => setSfxMode('file')}
              className={`text-xs px-2 py-0.5 rounded border transition-colors ${sfxMode==='file' ? 'bg-[#7c6af7] border-[#7c6af7] text-white' : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8]'}`}>
              File
            </button>
            <button onClick={() => setSfxMode('paste')}
              className={`text-xs px-2 py-0.5 rounded border transition-colors ${sfxMode==='paste' ? 'bg-[#7c6af7] border-[#7c6af7] text-white' : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8]'}`}>
              Paste
            </button>
          </div>
        </div>
        {sfxMode === 'file' ? (
          <input type="file" accept=".json"
            onChange={handleSfxFile}
            className="text-sm text-[#9090a8] file:mr-3 file:py-1 file:px-2 file:rounded file:border-0 file:bg-[#2a2a32] file:text-[#e8e8f0] file:text-xs cursor-pointer"
          />
        ) : (
          <textarea
            value={sfxPaste}
            onChange={e => { setSfxPaste(e.target.value); loadJsonFromText(e.target.value, parseSfxJson, setSfxJson, setSfxJsonError) }}
            rows={4}
            placeholder='Paste soundscape SFX JSON here…'
            className="w-full px-3 py-2 rounded-lg bg-[#16161a] border border-[#2a2a32] text-xs text-[#e8e8f0] font-mono resize-none focus:outline-none focus:border-[#7c6af7]"
          />
        )}
        {sfxJson && <span className="text-xs text-[#34d399]">🔊 {sfxJson.meta?.title || 'SFX JSON loaded'} — {sfxBadge}</span>}
        {sfxJsonError && <span className="text-xs text-[#f87171]">{sfxJsonError}</span>}
      </div>
    </div>
  )

  // ── Step 2 render ──────────────────────────────────────────────────────────
  const renderStep2 = () => (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <label className="text-xs text-[#9090a8] font-medium">Extracted Composition Prompt</label>
        <textarea
          value={compPrompt}
          onChange={e => { setCompPrompt(e.target.value); setPlanReady(false); setPlanJson('') }}
          rows={3}
          className="w-full px-3 py-2 rounded-lg bg-[#16161a] border border-[#2a2a32] text-sm text-[#e8e8f0] resize-none focus:outline-none focus:border-[#7c6af7]"
        />
      </div>
      <Button variant="accent" loading={planLoading} disabled={!compPrompt.trim()} onClick={handleGeneratePlan}>
        Generate Composition Plan →
      </Button>
      {planError && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-[#f87171] flex-1">{planError}</span>
          <Button variant="ghost" size="sm" onClick={handleGeneratePlan}>Retry</Button>
        </div>
      )}
      {planReady && (
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Composition Plan JSON <span className="text-[#5a5a70]">(editable)</span></label>
          <textarea
            value={planJson}
            onChange={e => setPlanJson(e.target.value)}
            rows={14}
            spellCheck={false}
            className="w-full px-3 py-2 rounded-lg bg-[#0d0d0f] border border-[#2a2a32] text-xs text-[#e8e8f0] font-mono resize-none focus:outline-none focus:border-[#7c6af7]"
          />
          {!isPlanValid() && <span className="text-xs text-[#f87171]">Invalid JSON — fix syntax before continuing</span>}
        </div>
      )}
    </div>
  )

  // ── Step 3 render ──────────────────────────────────────────────────────────
  const renderStep3 = () => (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-[#9090a8] mb-1">Generating assets — please wait…</p>
      {genItems.map(item => (
        <div key={item.key} className="flex items-center justify-between py-1.5 border-b border-[#2a2a32]">
          <span className="text-sm text-[#e8e8f0] truncate flex-1 mr-2">
            {item.type === 'music' ? '🎵' : '🔊'} {item.title}
          </span>
          {statusBadge(item.status, item.error)}
        </div>
      ))}
      {genItems.length === 0 && <span className="text-xs text-[#5a5a70]">Preparing…</span>}
    </div>
  )

  // ── Step 4 render ──────────────────────────────────────────────────────────
  const renderStep4 = () => {
    const musicItem = genItems.find(it => it.type === 'music')
    const sfxDone   = genSfxResults.length
    const sfxFailed = genItems.filter(it => it.type === 'sfx' && it.status === 'failed').length
    const sfxSkipped = genItems.filter(it => it.status === 'skipped').length
    return (
      <div className="flex flex-col gap-3">
        {musicItem && (
          <div className={`text-sm ${musicItem.status === 'done' ? 'text-[#34d399]' : 'text-[#f87171]'}`}>
            {musicItem.status === 'done' ? '✓' : '✗'} Music: {musicItem.title}
          </div>
        )}
        {(sfxDone > 0 || sfxFailed > 0) && (
          <div className="text-sm text-[#e8e8f0]">
            <span className="text-[#34d399]">✓ {sfxDone} SFX saved</span>
            {sfxFailed > 0 && <span className="text-[#f87171] ml-2">✗ {sfxFailed} failed</span>}
            {sfxSkipped > 0 && <span className="text-[#5a5a70] ml-2">⊘ {sfxSkipped} skipped</span>}
          </div>
        )}
        {!canApply && (
          <p className="text-sm text-[#f87171]">Nothing to apply — all items failed.</p>
        )}
      </div>
    )
  }

  // ── Modal ──────────────────────────────────────────────────────────────────
  const STEP_TITLES = ['', 'Import Template — Select Files', 'Music Plan Preview', 'Generating…', 'Done']

  const footer = () => {
    if (step === 1) return (
      <>
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button variant="primary" disabled={!canNext1} onClick={handleNext1}>
          {musicJson ? 'Next: Preview Plan →' : 'Next: Generate →'}
        </Button>
      </>
    )
    if (step === 2) return (
      <>
        <Button variant="ghost" onClick={() => setStep(1)}>← Back</Button>
        <Button variant="primary" disabled={!canNext2} onClick={() => setStep(3)}>
          Next: Generate →
        </Button>
      </>
    )
    if (step === 3) return (
      <Button variant="ghost" disabled>Generating… please wait</Button>
    )
    return (
      <>
        <Button variant="ghost" onClick={onClose}>Close</Button>
        {canApply && <Button variant="primary" onClick={handleApply}>Apply to Video →</Button>}
      </>
    )
  }

  return (
    <Modal open onClose={step === 3 ? undefined : onClose} title={STEP_TITLES[step]} width="max-w-2xl"
      footer={footer()}
    >
      <div className="py-1 max-h-[60vh] overflow-y-auto">
        {step === 1 && renderStep1()}
        {step === 2 && renderStep2()}
        {step === 3 && renderStep3()}
        {step === 4 && renderStep4()}
      </div>
    </Modal>
  )
}

```

- [ ] **Step 2: Verify no parse errors**

Hot-reload should work; if not, restart dev server. Open the YouTube Videos page. No red console errors.

- [ ] **Step 3: Commit**

```bash
git add console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "feat: add ImportFromTemplateModal component (steps 1-4)"
```

---

## Task 3: Wire ImportFromTemplateModal into CreationPanel

**Files:**
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx` (three changes inside `CreationPanel`)

- [ ] **Step 1: Add showImportTemplate state to CreationPanel**

In `CreationPanel`, find:

```js
  const [showMusicUpload, setShowMusicUpload] = useState(false)
```

Replace with:

```js
  const [showImportTemplate, setShowImportTemplate] = useState(false)
  const [showMusicUpload, setShowMusicUpload] = useState(false)
```

- [ ] **Step 2: Add handleTemplateImported function to CreationPanel**

In `CreationPanel`, find:

```js
  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }
```

Replace with:

```js
  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  const handleTemplateImported = ({ music_track_id, sound_layers }) => {
    if (music_track_id) {
      if (isAsmrLike) {
        setMusicTrackIds(prev => prev.includes(music_track_id) ? prev : [...prev, music_track_id])
      } else {
        setForm(f => ({ ...f, music_track_id: String(music_track_id) }))
      }
    }
    if (sound_layers && Object.keys(sound_layers).length > 0) {
      setSoundLayers(prev => ({
        ...prev,
        background: sound_layers.background
          ? { asset_id: String(sound_layers.background.asset_id), volume: sound_layers.background.volume }
          : prev.background,
        midground:  sound_layers.midground  || prev.midground,
        foreground: sound_layers.foreground || prev.foreground,
        random_sfx: sound_layers.random_sfx || prev.random_sfx,
      }))
    }
    setShowImportTemplate(false)
    showToast('Template imported', 'success')
  }
```

- [ ] **Step 3: Add "↓ Import Template" button to the CreationPanel header**

In `CreationPanel`, find:

```jsx
          <div className="flex items-center gap-2 flex-shrink-0">
            {!isEdit && (selectedPlan || channelPlans.length > 0) && (
              <Button
                variant="accent"
                size="sm"
                loading={autofilling}
                disabled={!selectedPlan || !form.theme?.trim()}
                onClick={handleAutofill}
                title={!selectedPlan ? 'Select a channel plan first' : !form.theme?.trim() ? 'Enter a theme first' : 'AI Autofill from channel plan'}
              >
                ✦ AI Autofill
              </Button>
            )}
            <button onClick={onClose} className="text-[#9090a8] hover:text-[#e8e8f0]">✕</button>
          </div>
```

Replace with:

```jsx
          <div className="flex items-center gap-2 flex-shrink-0">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowImportTemplate(true)}
            >
              ↓ Import Template
            </Button>
            {!isEdit && (selectedPlan || channelPlans.length > 0) && (
              <Button
                variant="accent"
                size="sm"
                loading={autofilling}
                disabled={!selectedPlan || !form.theme?.trim()}
                onClick={handleAutofill}
                title={!selectedPlan ? 'Select a channel plan first' : !form.theme?.trim() ? 'Enter a theme first' : 'AI Autofill from channel plan'}
              >
                ✦ AI Autofill
              </Button>
            )}
            <button onClick={onClose} className="text-[#9090a8] hover:text-[#e8e8f0]">✕</button>
          </div>
```

- [ ] **Step 4: Render ImportFromTemplateModal at the bottom of CreationPanel's return**

In `CreationPanel`, find the very last lines of the return statement:

```jsx
        {/* Submit */}
        <div className="px-6 py-4 border-t border-[#2a2a32]">
          <Button variant="primary" className="w-full" loading={loading} onClick={handleSubmit}>
            {isEdit ? 'Save changes →' : 'Queue Render →'}
          </Button>
        </div>
      </div>
    </div>
  )
}
```

Replace with:

```jsx
        {/* Submit */}
        <div className="px-6 py-4 border-t border-[#2a2a32]">
          <Button variant="primary" className="w-full" loading={loading} onClick={handleSubmit}>
            {isEdit ? 'Save changes →' : 'Queue Render →'}
          </Button>
        </div>
      </div>
      {showImportTemplate && (
        <ImportFromTemplateModal
          onClose={() => setShowImportTemplate(false)}
          onImported={handleTemplateImported}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 5: Verify in browser — Step 1 (Input)**

Open the YouTube Videos page, click "New Video" on any template to open `CreationPanel`. Verify:
- "↓ Import Template" ghost button appears in the header
- Clicking it opens the modal titled "Import Template — Select Files"
- Two sections: MUSIC JSON and SFX JSON, each with File / Paste toggle
- "Next" button is disabled when neither JSON is loaded
- In Paste mode: pasting the content of `suno-prompt_20260506-0158_study-focus_d-dorian_koto.json` shows `🎵 Study Focus · D Dorian · Koto & Wind` in green
- In Paste mode: pasting the content of `2026-05-07_soundscapes_amazon-rainforest-cabin-morning-rain.json` shows `🔊 Amazon Rainforest — Cabin Morning Rain — X bg, Y mid…` in green
- Pasting invalid JSON shows a red error
- "Next" enables when at least one is valid
- With only SFX JSON loaded (no music): clicking "Next" shows "Next: Generate →", clicking it opens step 3 immediately (skipping step 2)

- [ ] **Step 6: Verify Step 2 (Music Plan Preview)**

Load both JSONs in step 1. Click "Next: Preview Plan →". Verify:
- Step 2 shows "Extracted Composition Prompt" pre-filled with the `composer`-derived string
- The prompt textarea is editable
- Clicking "Generate Composition Plan →" calls the API (needs backend running) and shows a spinner, then fills the plan JSON textarea
- Plan textarea is editable (14 rows, monospace)
- "Next: Generate →" is disabled until the plan is loaded and valid JSON
- Editing the plan to invalid JSON shows the "Invalid JSON" error and disables Next
- "← Back" returns to step 1

- [ ] **Step 7: Verify Step 3 (Generation) and Step 4 (Done)**

With both JSONs loaded and plan generated, click "Next: Generate →". Verify:
- Step 3 shows the list of items with `pending`/`generating`/`done` badges updating in real time
- Music item uses `🎵` prefix, SFX items use `🔊`
- `automation_only` items show `skipped` badge
- After all generation completes, step 4 shows automatically
- Step 4 summary shows music title and SFX counts
- "Apply to Video →" is visible; clicking it closes the modal and shows "Template imported" toast
- `CreationPanel` music track is now set (check the Music Track select or playlist)
- `SoundLayersEditor` in the ASMR/soundscape section reflects the imported `sound_layers`

- [ ] **Step 8: Verify error path**

Open the modal with an SFX JSON only (no music). Click "Next: Generate →" (jumps to step 3). If ElevenLabs returns an error on one item, that item shows `failed` in red but others continue. Step 4 still shows "Apply to Video →" if any succeeded.

- [ ] **Step 9: Commit**

```bash
git add console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "feat: wire ImportFromTemplateModal into CreationPanel with apply handler"
```

---

## Spec Coverage Check

| Spec requirement | Task |
|---|---|
| "↓ Import Template" button in CreationPanel header | Task 3 Step 3 |
| Modal opens on button click | Task 3 Step 4 |
| Step 1: file picker + paste toggle for music JSON | Task 2 Step 1 |
| Step 1: file picker + paste toggle for SFX JSON | Task 2 Step 1 |
| Step 1: green badge with title on valid JSON | Task 2 Step 1 |
| Step 1: SFX badge shows item counts | Task 2 Step 1 (`sfxBadge`) |
| Step 1: inline red error on invalid JSON | Task 2 Step 1 |
| Step 1: Next disabled until at least one JSON valid | Task 2 Step 1 (`canNext1`) |
| Step 1 → Step 3 skip when no music JSON | Task 2 Step 1 (`handleNext1`) |
| Step 2: extracted prompt from `composer` fields | Task 1 (`buildMusicPrompt`) + Task 2 (`handleNext1`) |
| Step 2: `suno.style_of_music` fallback | Task 1 (`buildMusicPrompt`) |
| Step 2: editable prompt textarea | Task 2 Step 1 (`renderStep2`) |
| Step 2: Generate Plan button calls `/music/elevenlabs/plan` | Task 2 Step 1 (`handleGeneratePlan`) |
| Step 2: `music_length_ms = 600000` | Task 2 Step 1 (`handleGeneratePlan`) |
| Step 2: editable plan JSON textarea | Task 2 Step 1 (`renderStep2`) |
| Step 2: plan JSON validation before Next | Task 2 Step 1 (`isPlanValid`, `canNext2`) |
| Step 2: Retry button on plan API error | Task 2 Step 1 (`renderStep2`) |
| Step 3: items list with status badges | Task 2 Step 1 (`renderStep3`, `statusBadge`) |
| Step 3: music first, then SFX sequential | Task 2 Step 1 (`run()` in `useEffect`) |
| Step 3: music polls `GET /music/tasks/{task_id}` | Task 1 (`pollMusicTask`) + Task 2 |
| Step 3: poll interval 3s | Task 1 (`pollMusicTask`) |
| Step 3: 5-minute timeout | Task 1 (`pollMusicTask`) |
| Step 3: `automation_only` items skipped | Task 1 (`collectSfxItems`) |
| Step 3: failed items show error, generation continues | Task 2 Step 1 (`run()`) |
| Step 3: no user interaction during generation | Task 2 Step 1 (footer disabled) |
| Step 4: summary of music + SFX counts | Task 2 Step 1 (`renderStep4`) |
| Step 4: "Apply to Video →" hidden when all failed | Task 2 Step 1 (`canApply`) |
| Step 4: "Close" always visible | Task 2 Step 1 (footer step 4) |
| `onImported({ music_track_id, sound_layers })` | Task 2 Step 1 (`handleApply`) |
| Parent fills `musicTrackIds` for ASMR | Task 3 Step 2 (`handleTemplateImported`) |
| Parent fills `form.music_track_id` for non-ASMR | Task 3 Step 2 (`handleTemplateImported`) |
| Parent fills `soundLayers` state | Task 3 Step 2 (`handleTemplateImported`) |
| `background.asset_id` as String (UI format) | Task 3 Step 2 (`handleTemplateImported`) |
| `sound_layers` volumes: 0.4/0.5/0.7/0.6 defaults | Task 1 (`assembleSoundLayers`) |
| Interval from JSON strings e.g. `"10-18"` | Task 1 (`parseInterval`, `assembleSoundLayers`) |
| `loop: true` for background SFX only | Task 1 (`collectSfxItems`) |
| `music_track_id: null` when music failed | Task 2 Step 1 (`genMusicId` stays null on failure) |
| `sound_layers: {}` when no SFX or all SFX failed | Task 2 Step 1 (`assembleSoundLayers([])` returns `{}`) |
