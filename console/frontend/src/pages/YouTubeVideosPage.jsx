import { useState, useEffect, useRef } from 'react'
import { youtubeVideosApi, musicApi, assetsApi, sfxApi, channelPlansApi } from '../api/client.js'
import { Card, Badge, Button, Input, Select, Toast, Spinner, EmptyState, Modal } from '../components/index.jsx'
import AIAssistantPanel from '../components/AIAssistantPanel.jsx'
import MusicPlaylistEditor from '../components/MusicPlaylistEditor.jsx'
import RenderStatePanel from '../components/RenderStatePanel.jsx'
import PreviewApprovalGate from '../components/PreviewApprovalGate.jsx'
import SoundLayersEditor from '../components/SoundLayersEditor.jsx'
import VisualPlaylistEditor from '../components/VisualPlaylistEditor.jsx'
import { useRenderWebSocket } from '../hooks/useRenderWebSocket.js'
import PreviewPlayer from '../components/PreviewPlayer.jsx'
import { MusicPlaylistPicker } from '../components/MusicPlaylistPicker.jsx'
import { TransitionPanel } from '../components/TransitionPanel.jsx'
import { OverlayStylePicker } from '../components/OverlayStylePicker.jsx'
import { SpectrumPanel } from '../components/SpectrumPanel.jsx'

const ACTIVE_RENDER_STATES = new Set([
  'audio_preview_rendering',
  'video_preview_rendering',
  'rendering',
  'audio_preview_ready',
  'video_preview_ready',
])

function ActiveRenderCard({ video, onUpdate }) {
  const { state: wsState } = useRenderWebSocket(video.id)
  const liveStatus = wsState?.status || video.status
  if (liveStatus === 'audio_preview_ready') {
    return (
      <PreviewApprovalGate
        videoId={video.id}
        kind="audio"
        mediaPath={wsState?.audio_preview_path || video.audio_preview_path}
        onAction={onUpdate}
      />
    )
  }
  if (liveStatus === 'video_preview_ready') {
    return (
      <PreviewApprovalGate
        videoId={video.id}
        kind="video"
        mediaPath={wsState?.video_preview_path || video.video_preview_path}
        onAction={onUpdate}
      />
    )
  }
  return <RenderStatePanel videoId={video.id} state={wsState} onAction={onUpdate} />
}

const STATUS_COLORS = {
  draft:     '#9090a8',
  queued:    '#fbbf24',
  rendering: '#fbbf24',
  done:      '#34d399',
  failed:    '#f87171',
  published: '#4a9eff',
}

const QUALITY_OPTIONS = ['1080p', '4K']
const AI_SOURCES = ['midjourney', 'runway', 'veo']

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
  let parsed
  try { parsed = JSON.parse(text) }
  catch { throw new Error('Invalid JSON — check your pasted text') }
  if (!parsed.composer && !parsed.suno?.style_of_music) {
    throw new Error('Missing required field: composer or suno.style_of_music')
  }
  return parsed
}

function parseSfxJson(text) {
  let parsed
  try { parsed = JSON.parse(text) }
  catch { throw new Error('Invalid JSON — check your pasted text') }
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
      title: item.name_en || item.name_vi || (item.english_prompt || '').slice(0, 60),
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
      title: item.name_en || item.name_vi || (item.english_prompt || '').slice(0, 60),
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
    if (result.state === 'SUCCESS') return result
    if (result.state === 'FAILURE') throw new Error(result.info?.error || 'Music generation failed')
    await new Promise(res => setTimeout(res, 3000))
  }
  throw new Error('Music generation timed out after 5 minutes')
}

function extractSeoFromSfxJson(sfxJson) {
  const meta  = sfxJson.meta  || {}
  const scene = sfxJson.scene || {}

  const descParts = [
    scene.pov,
    [scene.time_of_day, scene.weather].filter(Boolean).join(', '),
    scene.atmosphere,
  ].filter(Boolean)
  const seoDescription = descParts.length
    ? descParts.join('. ').replace(/\.+$/, '') + '.'
    : null

  const tagWords = [
    ...(meta.theme || '').split('-').filter(t => t.length > 2),
    meta.use_case,
    meta.channel,
  ].filter(Boolean).map(t => String(t).toLowerCase().trim())
  const seoTags = [...new Set(tagWords)].join(', ') || null

  return {
    theme:             meta.theme              || null,
    target_duration_h: meta.video_length_hours || null,
    seo_title:         meta.title              || null,
    seo_description:   seoDescription,
    seo_tags:          seoTags,
  }
}

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
    target_duration_h: meta.video_length_hours                     ?? null,
  }
}

function extractPromptsFromJsons(musicJson, sfxJson) {
  const result = {}
  if (musicJson)                        result.music      = buildMusicPrompt(musicJson)
  if (sfxJson?.runway?.prompt)          result.visual     = sfxJson.runway.prompt
  if (sfxJson?.midjourney?.full_prompt) result.midjourney = sfxJson.midjourney.full_prompt
  return result
}

function VideoPreviewModal({ video, onClose }) {
  if (!video) return null
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
      onClick={onClose}
    >
      <div
        className="bg-[#1c1c22] border border-[#2a2a32] rounded-xl p-4 flex flex-col gap-3"
        style={{ width: '80vw', maxWidth: '1200px' }}
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="text-sm font-medium text-[#e8e8f0] leading-snug">{video.title}</div>
          <button onClick={onClose} className="text-[#9090a8] hover:text-[#f87171] flex-shrink-0 transition-colors text-lg leading-none">
            ✕
          </button>
        </div>
        <video
          controls
          autoPlay
          src={youtubeVideosApi.streamUrl(video.id)}
          className="w-full rounded-lg bg-black"
          style={{ aspectRatio: '16/9', maxHeight: '70vh', objectFit: 'contain' }}
        />
      </div>
    </div>
  )
}

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
  const [seoJson,        setSeoJson]        = useState(null)
  const [seoJsonError,   setSeoJsonError]   = useState(null)
  const [seoMode,        setSeoMode]        = useState('file')
  const [seoPaste,       setSeoPaste]       = useState('')

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
  const genItemsRef = useRef([])
  useEffect(() => { genItemsRef.current = genItems }, [genItems])

  // ── Step 4 ─────────────────────────────────────────────────────────────────
  const [finalLayers, setFinalLayers] = useState({})
  const [regenStatus, setRegenStatus] = useState({})   // key → 'regenerating'

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

  const handleSeoFile = (e) => {
    const file = e.target.files?.[0]; if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      try { setSeoJson(parseSeoJson(ev.target.result)); setSeoJsonError(null) }
      catch (e) { setSeoJson(null); setSeoJsonError(e.message) }
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
    const total = bg + mid + fg + rsfx + skip
    return `${total} sounds (${bg} bg, ${mid} mid, ${fg} fg, ${rsfx} random${skip > 0 ? `, ${skip} skipped` : ''})`
  })() : null

  const canNext1 = musicJson !== null || sfxJson !== null || seoJson !== null

  const handleApplyDataOnly = () => {
    const seo     = seoJson ? extractSeoFromSeoJson(seoJson) : sfxJson ? extractSeoFromSfxJson(sfxJson) : null
    const prompts = extractPromptsFromJsons(musicJson, sfxJson)
    onImported({ music_track_id: null, sound_layers: {}, seo, prompts })
    onClose()
  }

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

  // ── Step 4 helpers ─────────────────────────────────────────────────────────
  const canApply = genMusicId !== null || genSfxResults.length > 0

  const handleApply = () => {
    const prompts = extractPromptsFromJsons(musicJson, sfxJson)
    const seo     = seoJson ? extractSeoFromSeoJson(seoJson) : sfxJson ? extractSeoFromSfxJson(sfxJson) : null
    onImported({ music_track_id: genMusicId, sound_layers: finalLayers, seo, prompts })
    onClose()
  }

  const handleRegenSfx = async (genItem) => {
    setRegenStatus(s => ({ ...s, [genItem.key]: 'regenerating' }))
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
      setGenItems(prev => prev.map(it => it.key === genItem.key ? { ...it, status: 'done', error: null } : it))
      setRegenStatus(s => { const n = { ...s }; delete n[genItem.key]; return n })
    } catch (e) {
      setGenItems(prev => prev.map(it => it.key === genItem.key ? { ...it, status: 'failed', error: String(e.message || e).slice(0, 100) } : it))
      setRegenStatus(s => { const n = { ...s }; delete n[genItem.key]; return n })
    }
  }

  const handleRegenMusic = async () => {
    setRegenStatus(s => ({ ...s, music: 'regenerating' }))
    try {
      const plan = JSON.parse(planJson)
      const resp = await musicApi.elevenlabsCompose({
        composition_plan: plan,
        title: musicJson?.meta?.title || 'Music Track',
        niches: [], moods: [], genres: [],
      })
      await pollMusicTask(resp.task_id)
      setGenMusicId(resp.track_id)
      setGenItems(prev => prev.map(it => it.type === 'music' ? { ...it, status: 'done', error: null } : it))
      setRegenStatus(s => { const n = { ...s }; delete n.music; return n })
    } catch (e) {
      setGenItems(prev => prev.map(it => it.type === 'music' ? { ...it, status: 'failed', error: String(e.message || e).slice(0, 100) } : it))
      setRegenStatus(s => { const n = { ...s }; delete n.music; return n })
    }
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
        Provide any combination of JSON template files. Each is optional — music, SFX, and SEO are all independent.
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
        {sfxJson && (
          <>
            <span className="text-xs text-[#34d399]">🔊 {sfxJson.meta?.title || 'SFX JSON loaded'} — {sfxBadge}</span>
            {(() => {
              const seo = extractSeoFromSfxJson(sfxJson)
              return (
                <div className="pl-2 border-l-2 border-[#2a2a32] flex flex-col gap-0.5 mt-0.5">
                  {seo.theme && (
                    <span className="text-xs text-[#9090a8]">Theme: <span className="text-[#e8e8f0] font-mono">{seo.theme}</span></span>
                  )}
                  {seo.target_duration_h && (
                    <span className="text-xs text-[#9090a8]">Duration: <span className="text-[#e8e8f0]">{seo.target_duration_h}h</span></span>
                  )}
                  {seo.seo_title && (
                    <span className="text-xs text-[#9090a8]">Title: <span className="text-[#e8e8f0]">{seo.seo_title}</span></span>
                  )}
                  {seo.seo_tags && (
                    <span className="text-xs text-[#9090a8]">Tags: <span className="text-[#5a5a70] font-mono">{seo.seo_tags}</span></span>
                  )}
                </div>
              )
            })()}
          </>
        )}
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

  // ── Step 2 render ──────────────────────────────────────────────────────────
  const renderStep2 = () => (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <label className="text-xs text-[#9090a8] font-medium">Extracted Composition Prompt</label>
        <textarea
          value={compPrompt}
          readOnly
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
                    onClick={() => handleGenerateItem(item)}
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

  // ── Step 4 render ──────────────────────────────────────────────────────────
  const renderStep4 = () => {
    const sfxSkipped = genItems.filter(it => it.status === 'skipped').length
    const sfxFailed  = genItems.filter(it => it.type === 'sfx' && it.status === 'failed').length
    const sfxDone    = genSfxResults.length

    return (
      <div className="flex flex-col gap-2">
        {/* Summary strip */}
        <div className="flex flex-wrap gap-3 pb-2 mb-1 border-b border-[#2a2a32] text-xs">
          {genItems.find(it => it.type === 'music') && (
            <span className={genMusicId ? 'text-[#34d399]' : 'text-[#f87171]'}>
              {genMusicId ? '✓ Music saved' : '✗ Music failed'}
            </span>
          )}
          {(sfxDone > 0 || sfxFailed > 0) && (
            <span className="text-[#34d399]">✓ {sfxDone} / {sfxDone + sfxFailed} SFX saved</span>
          )}
          {sfxFailed > 0 && <span className="text-[#f87171]">✗ {sfxFailed} failed</span>}
          {sfxSkipped > 0 && <span className="text-[#5a5a70]">⊘ {sfxSkipped} skipped</span>}
          {!canApply && <span className="text-[#f87171]">Nothing to apply — all items failed.</span>}
        </div>

        {/* Per-item rows */}
        {genItems.map(item => {
          const isRegen   = regenStatus[item.key] === 'regenerating'
          const sfxAssetId = item.type === 'sfx'
            ? genSfxResults.find(r => r.item.key === item.key)?.assetId
            : null
          const audioSrc  = item.type === 'music' && genMusicId
            ? musicApi.streamUrl(genMusicId)
            : sfxAssetId != null
            ? sfxApi.streamUrl(sfxAssetId)
            : null
          const canRegen  = item.status !== 'skipped'

          return (
            <div key={item.key} className="flex items-center gap-2 py-1.5 border-b border-[#2a2a32] last:border-0">
              <span className="text-sm text-[#e8e8f0] truncate flex-1">
                {item.type === 'music' ? '🎵' : '🔊'} {item.title}
              </span>
              {audioSrc && !isRegen && <PreviewPlayer src={audioSrc} kind="audio" />}
              {isRegen ? <Spinner size={14} /> : statusBadge(item.status, item.error)}
              {canRegen && (
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={isRegen}
                  title="Regenerate"
                  onClick={() => item.type === 'music' ? handleRegenMusic() : handleRegenSfx(item)}
                >
                  ↺
                </Button>
              )}
            </div>
          )
        })}
      </div>
    )
  }

  // ── Modal ──────────────────────────────────────────────────────────────────
  const STEP_TITLES = ['', 'Import Template — Select Files', 'Music Plan Preview', 'Generating…', 'Done']

  const footer = () => {
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
    if (step === 2) return (
      <>
        <Button variant="ghost" onClick={() => setStep(1)}>← Back</Button>
        <Button variant="primary" disabled={!canNext2} onClick={() => { setGenItems(buildGenItemsList()); setStep(3) }}>
          Next: Generate →
        </Button>
      </>
    )
    if (step === 3) {
      const anyGenerating = genItems.some(it => it.status === 'generating')
      const anyPending    = genItems.some(it => it.status === 'pending')
      if (anyGenerating) return <Button variant="ghost" disabled>Generating… please wait</Button>
      if (anyPending)    return <Button variant="primary" onClick={handleStartAll}>▶ Start All</Button>
      return <Button variant="primary" onClick={() => setStep(4)}>Next →</Button>
    }
    return (
      <>
        <Button variant="ghost" onClick={onClose}>Close</Button>
        {canApply && <Button variant="primary" onClick={handleApply}>Apply to Video →</Button>}
      </>
    )
  }

  const blockClose = step === 3 && genItems.some(it => it.status === 'generating')
  return (
    <Modal open onClose={blockClose ? undefined : onClose} title={STEP_TITLES[step]} width="max-w-2xl"
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

function CreationPanel({ template, channelPlan, channelPlans = [], onClose, onCreated, mode = 'create', existingVideo = null }) {
  const isEdit = mode === 'edit' && existingVideo
  const [selectedPlan, setSelectedPlan] = useState(channelPlan)
  const [form, setForm] = useState({
    theme:                 isEdit ? (existingVideo.theme || '')                  : '',
    target_duration_h:     isEdit ? (existingVideo.target_duration_h || 8)       : (template?.target_duration_h || 8),
    customDuration:        '',
    isCustomDuration:      false,
    music_track_id:        isEdit ? existingVideo.music_track_id                 : null,
    visual_asset_id:       isEdit ? existingVideo.visual_asset_id                : null,
    sfx_overrides:         null,
    seo_title:             isEdit ? (existingVideo.seo_title || '')              : '',
    seo_description:       isEdit ? (existingVideo.seo_description || '')        : '',
    seo_tags:              isEdit ? (existingVideo.seo_tags || []).join(', ')    : '',
    output_quality:        isEdit ? (existingVideo.output_quality || '1080p')    : '1080p',
  })
  const [musicList, setMusicList]   = useState([])
  const [assetList, setAssetList]   = useState([])
  const [sfxList,   setSfxList]     = useState([])
  const [loading, setLoading]       = useState(false)
  const [toast, setToast]           = useState(null)
  const [autofilling, setAutofilling] = useState(false)
  const [autofillError, setAutofillError] = useState(null)
  const [autofillSuno, setAutofillSuno] = useState(null)
  const [autofillRunway, setAutofillRunway] = useState(null)
  const [midjourneyPrompt, setMidjourneyPrompt] = useState(null)

  const [soundLayers, setSoundLayers] = useState(() => {
    const sl = isEdit ? (existingVideo.sound_layers || {}) : {}
    return {
      background: {
        asset_id: sl.background?.asset_id ? String(sl.background.asset_id) : '',
        volume: sl.background?.volume ?? 0.4,
      },
      midground: {
        pool: sl.midground?.pool || [],
        volume: sl.midground?.volume ?? 0.5,
        interval_min_s: sl.midground?.interval_min_s ?? 10,
        interval_max_s: sl.midground?.interval_max_s ?? 25,
      },
      foreground: {
        pool: sl.foreground?.pool || [],
        volume: sl.foreground?.volume ?? 0.7,
        interval_min_s: sl.foreground?.interval_min_s ?? 45,
        interval_max_s: sl.foreground?.interval_max_s ?? 60,
      },
      random_sfx: {
        pool: sl.random_sfx?.pool || [],
        volume: sl.random_sfx?.volume ?? 0.6,
        interval_min_s: sl.random_sfx?.interval_min_s ?? 60,
        interval_max_s: sl.random_sfx?.interval_max_s ?? 100,
      },
    }
  })

  // ASMR / Soundscape extras
  const [musicTrackIds, setMusicTrackIds]       = useState(isEdit ? (existingVideo.music_track_ids || []) : [])
  const [blackFromSeconds, setBlackFromSeconds] = useState(isEdit && existingVideo.black_from_seconds != null ? String(existingVideo.black_from_seconds) : '')
  const [skipPreviews, setSkipPreviews]         = useState(isEdit ? !!existingVideo.skip_previews : false)
  const isAsmrLike = ['asmr', 'soundscape'].includes(template?.slug)
  const isMusic = template?.slug === 'music'
  // Generic feature gating driven by template.ui_features array from the backend.
  // music template has ui_features=[] so all panels below will be hidden.
  // asmr/soundscape templates have ui_features=['sfx_panel','duration_picker','blackout'].
  const uiFeatures = new Set(template?.ui_features ?? [])

  // Music-template-only state
  const [trackTransition,        setTrackTransition]        = useState(isEdit ? (existingVideo.track_transition        ?? 'gapless') : 'gapless')
  const [trackTransitionSeconds, setTrackTransitionSeconds] = useState(isEdit ? (existingVideo.track_transition_seconds ?? 2.0)      : 2.0)
  const [playlistOverlayStyle,   setPlaylistOverlayStyle]   = useState(isEdit ? (existingVideo.playlist_overlay_style  ?? null)      : null)
  const [spectrumEnabled,        setSpectrumEnabled]        = useState(isEdit ? !!existingVideo.spectrum_enabled                     : false)
  const [spectrumHeightPct,      setSpectrumHeightPct]      = useState(isEdit ? (existingVideo.spectrum_height_pct      ?? 0.12)      : 0.12)
  const [spectrumColor,          setSpectrumColor]          = useState(isEdit ? (existingVideo.spectrum_color           ?? '#ffffff') : '#ffffff')
  const [spectrumOpacity,        setSpectrumOpacity]        = useState(isEdit ? (existingVideo.spectrum_opacity         ?? 0.6)      : 0.6)
  const [spectrumStyle,          setSpectrumStyle]          = useState(isEdit ? (existingVideo.spectrum_style           ?? 'classic') : 'classic')
  const [spectrumBarWidthPx,     setSpectrumBarWidthPx]     = useState(isEdit ? (existingVideo.spectrum_bar_width_px    ?? 10)        : 10)
  const [spectrumBarCount,       setSpectrumBarCount]       = useState(isEdit ? (existingVideo.spectrum_bar_count       ?? 50)        : 50)
  const [spectrumAlignH,         setSpectrumAlignH]         = useState(isEdit ? (existingVideo.spectrum_align_horizontal ?? 'center')  : 'center')
  const [spectrumAlignV,         setSpectrumAlignV]         = useState(isEdit ? (existingVideo.spectrum_align_vertical   ?? 'bottom')  : 'bottom')

  // Visual playlist — fall back to legacy single visual_asset_id when array is empty
  // so editing a pre-feature video doesn't drop the existing visual.
  const [visualAssetIds, setVisualAssetIds]   = useState(() => {
    if (!isEdit) return []
    if (existingVideo.visual_asset_ids?.length > 0) return existingVideo.visual_asset_ids
    if (existingVideo.visual_asset_id) return [existingVideo.visual_asset_id]
    return []
  })
  const [visualDurations, setVisualDurations] = useState(() => {
    if (!isEdit) return []
    if (existingVideo.visual_clip_durations_s?.length > 0) return existingVideo.visual_clip_durations_s
    if (existingVideo.visual_asset_id) return [0.0]  // 0 = use native length in concat_loop
    return []
  })
  const [visualLoopMode, setVisualLoopMode]   = useState(isEdit ? (existingVideo.visual_loop_mode || 'concat_loop') : 'concat_loop')

  const [thumbnailFile, setThumbnailFile] = useState(null)
  const [thumbnailText, setThumbnailText] = useState(isEdit ? (existingVideo?.thumbnail_text || '') : '')
  const [thumbnailPreviewKey, setThumbnailPreviewKey] = useState(0)
  const [hasThumbnail, setHasThumbnail] = useState(isEdit ? !!existingVideo?.thumbnail_path : false)
  const [thumbnailGenerating, setThumbnailGenerating] = useState(false)

  const [showImportTemplate, setShowImportTemplate] = useState(false)
  const [showMusicUpload, setShowMusicUpload] = useState(false)
  const [musicUploadFile, setMusicUploadFile] = useState(null)
  const [musicUploadTitle, setMusicUploadTitle] = useState('')
  const [musicUploading, setMusicUploading] = useState(false)

  const [showVisualUpload, setShowVisualUpload] = useState(false)
  const [visualUploadFile, setVisualUploadFile] = useState(null)
  const [visualUploadDesc, setVisualUploadDesc] = useState('')
  const [visualUploadSource, setVisualUploadSource] = useState('manual')
  const [visualUploading, setVisualUploading] = useState(false)

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  const handleTemplateImported = ({ music_track_id, sound_layers, seo, prompts }) => {
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
    if (seo) {
      setForm(f => {
        const patch = {}
        if (seo.theme)           patch.theme           = seo.theme
        if (seo.seo_title)       patch.seo_title       = seo.seo_title
        if (seo.seo_description) patch.seo_description = seo.seo_description
        if (seo.seo_tags)        patch.seo_tags        = seo.seo_tags
        if (seo.target_duration_h != null) {
          const preset = DURATION_PRESETS.find(p => p.value === seo.target_duration_h)
          if (preset && preset.value !== null) {
            patch.target_duration_h = seo.target_duration_h
            patch.isCustomDuration  = false
          } else {
            patch.customDuration   = String(seo.target_duration_h)
            patch.isCustomDuration = true
          }
        }
        return { ...f, ...patch }
      })
    }
    if (prompts?.music)      setAutofillSuno(prompts.music)
    if (prompts?.visual)     setAutofillRunway(prompts.visual)
    if (prompts?.midjourney) setMidjourneyPrompt(prompts.midjourney)
    setShowImportTemplate(false)
    showToast('Template imported', 'success')
    sfxApi.list().then(d => setSfxList(d.items || d || []))
  }

  const handleMusicUpload = async () => {
    if (!musicUploadFile) { showToast('Select a file', 'error'); return }
    if (!musicUploadTitle.trim()) { showToast('Title is required', 'error'); return }
    setMusicUploading(true)
    try {
      const newTrack = await musicApi.upload(musicUploadFile, {
        title: musicUploadTitle.trim(),
        niches: [],
        moods: [],
        genres: [],
        is_vocal: false,
        volume: 0.15,
        quality_score: 80,
      })
      setMusicList(prev => [...prev, newTrack])
      if (isAsmrLike) {
        setMusicTrackIds(prev => [...prev, newTrack.id])
      } else {
        setForm(f => ({ ...f, music_track_id: String(newTrack.id) }))
      }
      setShowMusicUpload(false)
      setMusicUploadFile(null)
      setMusicUploadTitle('')
      showToast('Track uploaded', 'success')
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setMusicUploading(false)
    }
  }

  const handleVisualUpload = async () => {
    if (!visualUploadFile) { showToast('Select a file', 'error'); return }
    setVisualUploading(true)
    try {
      const ext = (visualUploadFile.name.split('.').pop() || '').toLowerCase()
      const asset_type = ['mp4', 'mov', 'webm'].includes(ext) ? 'video_clip' : 'still_image'
      const newAsset = await assetsApi.upload(visualUploadFile, {
        source: visualUploadSource,
        description: visualUploadDesc,
        asset_type,
      })
      setAssetList(prev => [...prev, newAsset])
      setVisualAssetIds(prev => [...prev, newAsset.id])
      setVisualDurations(prev => [...prev, asset_type === 'still_image' ? 3.0 : 0.0])
      setShowVisualUpload(false)
      setVisualUploadFile(null)
      setVisualUploadDesc('')
      setVisualUploadSource('manual')
      showToast('Asset uploaded', 'success')
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setVisualUploading(false)
    }
  }

  const handleGenerateThumbnail = async () => {
    if (!thumbnailFile && !hasThumbnail) return
    const wordCount = thumbnailText.trim()
      ? thumbnailText.trim().split(/\s+/).filter(Boolean).length
      : 0
    if (wordCount > 5) { showToast('Thumbnail text must be 5 words or fewer', 'error'); return }
    const id = existingVideo?.id
    if (!id) { showToast('Save the video first before generating a thumbnail preview', 'info'); return }
    setThumbnailGenerating(true)
    try {
      if (thumbnailFile) {
        await youtubeVideosApi.uploadThumbnailImage(id, thumbnailFile)
        setThumbnailFile(null)
        setHasThumbnail(true)
      }
      await youtubeVideosApi.generateThumbnail(id, thumbnailText.trim() || null)
      setThumbnailPreviewKey(k => k + 1)
      showToast('Thumbnail generated', 'success')
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setThumbnailGenerating(false)
    }
  }

  useEffect(() => {
    let mounted = true
    musicApi.list({ status: 'ready' })
      .then(d => { if (mounted) setMusicList(d.items || d || []) })
      .catch(() => {})
    assetsApi.list({ asset_type: 'video_clip', per_page: 200 })
      .then(d => {
        if (mounted) setAssetList((d.items || d || []).filter(a => AI_SOURCES.includes(a.source)))
      })
      .catch(() => {})
    sfxApi.list()
      .then(d => { if (mounted) setSfxList(d.items || d || []) })
      .catch(() => {})
    return () => { mounted = false }
  }, [])


  const handleAutofill = async () => {
    if (!selectedPlan || !form.theme) return
    setAutofilling(true)
    setAutofillError(null)
    try {
      const result = await channelPlansApi.aiAutofill(selectedPlan.id, form.theme)
      setForm(f => ({
        ...f,
        seo_title:       result.title       || f.seo_title,
        seo_description: result.description || f.seo_description,
        seo_tags:        result.tags        || f.seo_tags,
        ...(result.target_duration_h
          ? (() => {
              const preset = DURATION_PRESETS.find(p => p.value === result.target_duration_h)
              return preset
                ? { target_duration_h: result.target_duration_h, isCustomDuration: false }
                : { customDuration: String(result.target_duration_h), isCustomDuration: true }
            })()
          : {}),
      }))
      if (result.suno_prompt) setAutofillSuno(result.suno_prompt)
      if (result.runway_prompt) setAutofillRunway(result.runway_prompt)
      showToast('AI autofill complete', 'success')
    } catch (e) {
      setAutofillError(e.message)
    } finally {
      setAutofilling(false)
    }
  }

  const handleSubmit = async () => {
    if (!form.theme) { showToast('Theme is required', 'error'); return }
    const duration = form.isCustomDuration
      ? parseFloat(form.customDuration)
      : form.target_duration_h
    if (!isMusic && (!duration || duration <= 0)) {
      showToast('Valid duration is required', 'error'); return
    }
    if (isMusic && musicTrackIds.length === 0) {
      showToast('Music template requires at least 1 music track', 'error'); return
    }
    setLoading(true)
    try {
      const title = form.seo_title || `${template.label} — ${form.theme}`
      const body = {
        title,
        template_id: template.id,
        theme: form.theme,
        ...(isMusic ? {} : { target_duration_h: duration }),
        music_track_id: form.music_track_id || null,
        visual_asset_id: null,
        visual_asset_ids: visualAssetIds,
        visual_clip_durations_s: visualDurations,
        visual_loop_mode: visualLoopMode,
        sound_layers: (() => {
          const result = {}
          if (soundLayers.background.asset_id)
            result.background = { asset_id: parseInt(soundLayers.background.asset_id), volume: soundLayers.background.volume }
          for (const key of ['midground', 'foreground', 'random_sfx']) {
            if (soundLayers[key].pool.length > 0)
              result[key] = { ...soundLayers[key] }
          }
          return Object.keys(result).length > 0 ? result : null
        })(),
        seo_title: form.seo_title,
        seo_description: form.seo_description,
        seo_tags: form.seo_tags
          ? form.seo_tags.split(',').map(t => t.trim()).filter(Boolean)
          : [],
        output_quality: form.output_quality,
        ...(isAsmrLike ? {
          music_track_ids: musicTrackIds,
          black_from_seconds: blackFromSeconds ? parseInt(blackFromSeconds, 10) : null,
          skip_previews: skipPreviews,
        } : {}),
        ...(isMusic ? {
          music_track_ids: musicTrackIds,
          track_transition: trackTransition,
          track_transition_seconds: trackTransitionSeconds,
          playlist_overlay_style: playlistOverlayStyle,
          spectrum_enabled: spectrumEnabled,
          spectrum_height_pct: spectrumHeightPct,
          spectrum_color: spectrumColor,
          spectrum_opacity: spectrumOpacity,
          spectrum_style: spectrumStyle,
          spectrum_bar_width_px: spectrumBarWidthPx,
          spectrum_bar_count: spectrumBarCount,
          spectrum_align_horizontal: spectrumAlignH,
          spectrum_align_vertical: spectrumAlignV,
        } : {}),
      }
      let videoId = existingVideo?.id
      if (isEdit) {
        await youtubeVideosApi.update(videoId, body)
      } else {
        const created = await youtubeVideosApi.create(body)
        videoId = created.id
      }
      let thumbnailError = null
      if (!isEdit && thumbnailFile && videoId) {
        try {
          await youtubeVideosApi.uploadThumbnailImage(videoId, thumbnailFile)
          await youtubeVideosApi.generateThumbnail(videoId, thumbnailText.trim() || null)
        } catch (e) {
          thumbnailError = e.message
        }
      }
      onCreated()
      onClose()
      if (thumbnailError) {
        showToast(`Thumbnail could not be generated — retry from the edit form. (${thumbnailError})`, 'warning')
      }
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative w-[480px] h-full bg-[#16161a] border-l border-[#2a2a32] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#2a2a32]">
          <div className="flex flex-col gap-0.5 min-w-0">
            <h2 className="text-base font-semibold text-[#e8e8f0]">
              {isEdit ? 'Edit' : 'New'} {template?.label}
            </h2>
            {selectedPlan && (
              <span className="text-xs text-[#7c6af7] font-mono">{selectedPlan.name}</span>
            )}
          </div>
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
        </div>

        {/* Toast — outside scroll area so it doesn't shift layout */}
        {toast && (
          <div className="absolute top-16 left-0 right-0 z-10 px-6">
            <Toast message={toast.msg} type={toast.type} />
          </div>
        )}
        <div className="flex-1 overflow-y-auto px-6 py-4 flex flex-col gap-6">
          {autofillError && (
            <div className="pt-2">
              <p className="text-xs text-[#f87171]">{autofillError}</p>
            </div>
          )}

          {/* Channel plan picker — shown when opened from header (no pre-selected plan) */}
          {!channelPlan && channelPlans.length > 0 && (
            <section>
              <div className="text-xs font-bold text-[#5a5a70] tracking-widest mb-3">CHANNEL PLAN</div>
              <Select
                value={selectedPlan?.id ?? ''}
                onChange={e => {
                  const id = parseInt(e.target.value, 10)
                  setSelectedPlan(channelPlans.find(p => p.id === id) || null)
                }}
              >
                <option value="">— Select a channel plan (optional) —</option>
                {channelPlans.map(p => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </Select>
            </section>
          )}

          {/* ① THEME & SEO */}
          <section>
            <div className="text-xs font-bold text-[#5a5a70] tracking-widest mb-3">① THEME &amp; SEO</div>
            <div className="flex flex-col gap-3">
              <Input
                label="Theme"
                value={form.theme}
                onChange={e => setForm(f => ({ ...f, theme: e.target.value }))}
                placeholder="e.g. Heavy Rain Window"
              />

              {uiFeatures.has('duration_picker') && (
              <div className="flex flex-col gap-1">
                <label className="text-xs text-[#9090a8] font-medium">Duration</label>
                <div className="flex flex-wrap gap-2">
                  {DURATION_PRESETS.map(p => (
                    <button
                      key={p.label}
                      onClick={() => setForm(f => ({
                        ...f,
                        isCustomDuration: p.value === null,
                        target_duration_h: p.value ?? f.target_duration_h,
                      }))}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                        (p.value === null
                          ? form.isCustomDuration
                          : !form.isCustomDuration && form.target_duration_h === p.value)
                          ? 'bg-[#7c6af7] border-[#7c6af7] text-white'
                          : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8] hover:text-[#e8e8f0]'
                      }`}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
                {form.isCustomDuration && (
                  <Input
                    value={form.customDuration}
                    onChange={e => setForm(f => ({ ...f, customDuration: e.target.value }))}
                    placeholder="Hours (e.g. 6.5)"
                    type="number"
                    min="0.5"
                    step="0.5"
                  />
                )}
                {template?.target_duration_h && (
                  <p className="text-xs text-[#5a5a70]">
                    💡 {template.label} recommended: {template.target_duration_h}h
                  </p>
                )}
              </div>
              )}

              <Input
                label="SEO Title"
                value={form.seo_title}
                onChange={e => setForm(f => ({ ...f, seo_title: e.target.value }))}
              />
              <div className="flex flex-col gap-1">
                <label className="text-xs text-[#9090a8] font-medium">SEO Description</label>
                <textarea
                  value={form.seo_description || ''}
                  onChange={e => setForm(f => ({ ...f, seo_description: e.target.value }))}
                  placeholder="YouTube description..."
                  rows={4}
                  className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] placeholder:text-[#5a5a70] focus:outline-none focus:border-[#7c6af7] transition-colors resize-none"
                />
              </div>
              <Input
                label="SEO Tags (comma-separated)"
                value={form.seo_tags}
                onChange={e => setForm(f => ({ ...f, seo_tags: e.target.value }))}
                placeholder="asmr, rain, sleep, relaxing"
              />
            </div>
          </section>

          {/* THUMBNAIL */}
          <section>
            <div className="text-xs font-bold text-[#5a5a70] tracking-widest mb-3">THUMBNAIL</div>
            <div className="flex flex-col gap-3">
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
              <div className="flex flex-col gap-1">
                <div className="flex items-center justify-between">
                  <label className="text-xs text-[#9090a8] font-medium">
                    Thumbnail Text (optional, ≤5 words)
                  </label>
                  <span className={`text-xs font-mono ${
                    thumbnailText.trim().split(/\s+/).filter(Boolean).length > 5
                      ? 'text-[#f87171]'
                      : 'text-[#5a5a70]'
                  }`}>
                    {thumbnailText.trim() ? thumbnailText.trim().split(/\s+/).filter(Boolean).length : 0}/5
                  </span>
                </div>
                <Input
                  value={thumbnailText}
                  onChange={e => setThumbnailText(e.target.value)}
                  placeholder="e.g. DEEP FOCUS"
                />
              </div>
              {isEdit && (
                <Button
                  variant="secondary"
                  size="sm"
                  loading={thumbnailGenerating}
                  disabled={
                    (!thumbnailFile && !hasThumbnail) ||
                    thumbnailText.trim().split(/\s+/).filter(Boolean).length > 5
                  }
                  onClick={handleGenerateThumbnail}
                >
                  Generate Preview
                </Button>
              )}
              {isEdit && hasThumbnail && (
                <img
                  key={thumbnailPreviewKey}
                  src={`${youtubeVideosApi.thumbnailUrl(existingVideo.id)}?t=${thumbnailPreviewKey}`}
                  alt="Thumbnail preview"
                  className="w-full rounded-lg border border-[#2a2a32]"
                  style={{ aspectRatio: '16/9', objectFit: 'cover' }}
                  onError={() => setHasThumbnail(false)}
                />
              )}
            </div>
          </section>

          {/* ② MUSIC */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs font-bold text-[#5a5a70] tracking-widest">② MUSIC</div>
              <button
                type="button"
                onClick={() => setShowMusicUpload(v => !v)}
                className={`text-xs px-2 py-1 rounded border transition-colors ${
                  showMusicUpload
                    ? 'bg-[#7c6af7] border-[#7c6af7] text-white'
                    : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8] hover:text-[#e8e8f0]'
                }`}
              >
                ↑ Upload
              </button>
            </div>
            <div className="flex flex-col gap-3">
              {isAsmrLike ? (
                <div className="flex flex-col gap-1">
                  <div className="text-xs text-[#9090a8] font-medium">
                    Music Playlist <span className="text-[#5a5a70]">(reorder with ↑↓ — looped in order)</span>
                  </div>
                  <MusicPlaylistEditor trackIds={musicTrackIds} onChange={setMusicTrackIds} />
                </div>
              ) : isMusic ? (
                <MusicPlaylistPicker
                  value={musicTrackIds}
                  onChange={setMusicTrackIds}
                  transition={trackTransition}
                  transitionSeconds={trackTransitionSeconds}
                />
              ) : (
                <Select
                  label="Music Track"
                  value={form.music_track_id || ''}
                  onChange={e => setForm(f => ({ ...f, music_track_id: e.target.value || null }))}
                >
                  <option value="">— Select from library —</option>
                  {musicList.map(m => (
                    <option key={m.id} value={m.id}>{m.title} ({m.provider})</option>
                  ))}
                </Select>
              )}
              {showMusicUpload && (
                <div className="flex flex-col gap-2 bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3">
                  <div className="text-xs text-[#5a5a70] font-medium">Upload Music Track</div>
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-[#9090a8] font-medium">File (.mp3 / .wav / .m4a / .ogg)</label>
                    <input
                      type="file"
                      accept=".mp3,.wav,.m4a,.ogg"
                      onChange={e => {
                        const f = e.target.files?.[0] || null
                        setMusicUploadFile(f)
                        if (f && !musicUploadTitle) setMusicUploadTitle(f.name.replace(/\.[^.]+$/, ''))
                      }}
                      className="text-sm text-[#9090a8] file:mr-3 file:py-1 file:px-2 file:rounded file:border-0 file:bg-[#2a2a32] file:text-[#e8e8f0] file:text-xs cursor-pointer"
                    />
                  </div>
                  <Input
                    label="Title"
                    value={musicUploadTitle}
                    onChange={e => setMusicUploadTitle(e.target.value)}
                    placeholder="Track title"
                  />
                  <div className="flex gap-2 justify-end">
                    <Button variant="ghost" size="sm" onClick={() => {
                      setShowMusicUpload(false)
                      setMusicUploadFile(null)
                      setMusicUploadTitle('')
                    }}>
                      Cancel
                    </Button>
                    <Button variant="primary" size="sm" loading={musicUploading} onClick={handleMusicUpload}>
                      Upload
                    </Button>
                  </div>
                </div>
              )}
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
            </div>
          </section>

          {/* ③ VISUAL */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs font-bold text-[#5a5a70] tracking-widest">③ VISUAL</div>
              <button
                type="button"
                onClick={() => setShowVisualUpload(v => !v)}
                className={`text-xs px-2 py-1 rounded border transition-colors ${
                  showVisualUpload
                    ? 'bg-[#7c6af7] border-[#7c6af7] text-white'
                    : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8] hover:text-[#e8e8f0]'
                }`}
              >
                ↑ Upload
              </button>
            </div>
            <div className="flex flex-col gap-3">
              <div className="flex gap-2">
                {[
                  { value: 'concat_loop', label: 'Concat-then-loop' },
                  { value: 'per_clip',    label: 'Per-clip duration' },
                ].map(opt => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setVisualLoopMode(opt.value)}
                    className={`flex-1 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                      visualLoopMode === opt.value
                        ? 'bg-[#7c6af7] border-[#7c6af7] text-white'
                        : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8] hover:text-[#e8e8f0]'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
              <VisualPlaylistEditor
                assetIds={visualAssetIds}
                durations={visualDurations}
                loopMode={visualLoopMode}
                onChange={({ assetIds, durations }) => {
                  setVisualAssetIds(assetIds)
                  setVisualDurations(durations)
                }}
              />
              {showVisualUpload && (
                <div className="flex flex-col gap-2 bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3">
                  <div className="text-xs text-[#5a5a70] font-medium">Upload Visual Asset</div>
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-[#9090a8] font-medium">File (image or video)</label>
                    <input
                      type="file"
                      accept=".jpg,.jpeg,.png,.webp,.mp4,.mov,.webm"
                      onChange={e => setVisualUploadFile(e.target.files?.[0] || null)}
                      className="text-sm text-[#9090a8] file:mr-3 file:py-1 file:px-2 file:rounded file:border-0 file:bg-[#2a2a32] file:text-[#e8e8f0] file:text-xs cursor-pointer"
                    />
                  </div>
                  <Select label="Source" value={visualUploadSource} onChange={e => setVisualUploadSource(e.target.value)}>
                    {['manual', 'midjourney', 'runway', 'pexels', 'veo', 'stock'].map(s => (
                      <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                    ))}
                  </Select>
                  <Input
                    label="Description (optional)"
                    value={visualUploadDesc}
                    onChange={e => setVisualUploadDesc(e.target.value)}
                    placeholder="e.g. Rainy window close-up"
                  />
                  <div className="flex gap-2 justify-end">
                    <Button variant="ghost" size="sm" onClick={() => {
                      setShowVisualUpload(false)
                      setVisualUploadFile(null)
                      setVisualUploadDesc('')
                      setVisualUploadSource('manual')
                    }}>
                      Cancel
                    </Button>
                    <Button variant="primary" size="sm" loading={visualUploading} onClick={handleVisualUpload}>
                      Upload
                    </Button>
                  </div>
                </div>
              )}
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
            </div>
          </section>

          {/* ④ SOUND LAYERS — hidden for templates that don't declare sfx_panel */}
          {uiFeatures.has('sfx_panel') && (
          <section>
            <div className="text-xs font-bold text-[#5a5a70] tracking-widest mb-3">④ SOUND LAYERS</div>
            <SoundLayersEditor
              soundLayers={soundLayers}
              sfxList={sfxList}
              onChange={setSoundLayers}
            />
          </section>
          )}

          {/* ④b EXTRAS — asmr/soundscape only; blackout input also requires ui_features flag */}
          {isAsmrLike && (
            <section>
              <div className="text-xs font-bold text-[#5a5a70] tracking-widest mb-3">④b EXTRAS</div>
              <div className="flex flex-col gap-3">
                {uiFeatures.has('blackout') && (
                <Input
                  label="Black-out from (seconds — visual fades to black, audio continues)"
                  type="number"
                  min="0"
                  value={blackFromSeconds}
                  onChange={e => setBlackFromSeconds(e.target.value)}
                  placeholder="leave blank for no blackout"
                />
                )}
                <label className="flex items-center gap-2 text-xs text-[#9090a8]">
                  <input
                    type="checkbox"
                    checked={skipPreviews}
                    onChange={e => setSkipPreviews(e.target.checked)}
                    className="accent-[#7c6af7]"
                  />
                  Skip preview gates (render straight to final, still chunked)
                </label>
              </div>
            </section>
          )}

          {/* ④c MUSIC OPTIONS — music template only */}
          {isMusic && (
            <section>
              <div className="text-xs font-bold text-[#5a5a70] tracking-widest mb-3">④c MUSIC OPTIONS</div>
              <div className="flex flex-col gap-4">
                <TransitionPanel
                  transition={trackTransition}
                  transitionSeconds={trackTransitionSeconds}
                  onChange={({ transition, transitionSeconds }) => {
                    setTrackTransition(transition)
                    setTrackTransitionSeconds(transitionSeconds)
                  }}
                />
                <OverlayStylePicker
                  value={playlistOverlayStyle}
                  onChange={setPlaylistOverlayStyle}
                  trackCount={musicTrackIds.length}
                />
                <SpectrumPanel
                  value={{
                    spectrum_enabled:           spectrumEnabled,
                    spectrum_height_pct:        spectrumHeightPct,
                    spectrum_color:             spectrumColor,
                    spectrum_opacity:           spectrumOpacity,
                    spectrum_style:             spectrumStyle,
                    spectrum_bar_width_px:      spectrumBarWidthPx,
                    spectrum_bar_count:         spectrumBarCount,
                    spectrum_align_horizontal:  spectrumAlignH,
                    spectrum_align_vertical:    spectrumAlignV,
                  }}
                  onChange={patch => {
                    if ('spectrum_enabled'           in patch) setSpectrumEnabled(patch.spectrum_enabled)
                    if ('spectrum_height_pct'        in patch) setSpectrumHeightPct(patch.spectrum_height_pct)
                    if ('spectrum_color'             in patch) setSpectrumColor(patch.spectrum_color)
                    if ('spectrum_opacity'           in patch) setSpectrumOpacity(patch.spectrum_opacity)
                    if ('spectrum_style'             in patch) setSpectrumStyle(patch.spectrum_style)
                    if ('spectrum_bar_width_px'      in patch) setSpectrumBarWidthPx(patch.spectrum_bar_width_px)
                    if ('spectrum_bar_count'         in patch) setSpectrumBarCount(patch.spectrum_bar_count)
                    if ('spectrum_align_horizontal'  in patch) setSpectrumAlignH(patch.spectrum_align_horizontal)
                    if ('spectrum_align_vertical'    in patch) setSpectrumAlignV(patch.spectrum_align_vertical)
                  }}
                />
              </div>
            </section>
          )}

          {/* ⑤ RENDER */}
          <section>
            <div className="text-xs font-bold text-[#5a5a70] tracking-widest mb-3">⑤ RENDER</div>
            <Select
              label="Output Quality"
              value={form.output_quality}
              onChange={e => setForm(f => ({ ...f, output_quality: e.target.value }))}
            >
              {QUALITY_OPTIONS.map(q => (
                <option key={q} value={q}>{q}</option>
              ))}
            </Select>
          </section>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-[#2a2a32] flex gap-3 justify-end">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={loading} onClick={handleSubmit}>
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

function MakeShortModal({ video, shortTemplates, onClose, onCreated }) {
  const shortTemplate = shortTemplates[0]
  const [form, setForm] = useState({
    sameMusic: true,
    sameVisual: true,
    ctaText: shortTemplate?.short_cta_text || `Full ${video.target_duration_h ? video.target_duration_h + 'h' : ''} version on channel ↑`,
    ctaPosition: 'last_10s',
  })
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState(null)
  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000) }

  const handleSubmit = async () => {
    if (loading) return
    if (!shortTemplate) { showToast('No short template found', 'error'); return }
    setLoading(true)
    try {
      await youtubeVideosApi.create({
        title: `${video.title} — Short`,
        template_id: shortTemplate.id,
        theme: video.theme,
        target_duration_h: (shortTemplate?.short_duration_s ?? 58) / 3600,
        music_track_id: form.sameMusic
          ? (video.music_track_id ?? video.music_track_ids?.[0] ?? null)
          : null,
        visual_asset_id: form.sameVisual
          ? (video.visual_asset_id ?? video.visual_asset_ids?.[0] ?? null)
          : null,
        parent_youtube_video_id: video.id,
        sfx_overrides: { ...(video.sfx_overrides || {}), cta: { text: form.ctaText, position: form.ctaPosition } },
      })
      onCreated()
      onClose()
    } catch (e) { showToast(e.message, 'error') }
    finally { setLoading(false) }
  }

  return (
    <Modal open onClose={onClose} title={`New ${shortTemplate?.label || 'Viral Short'}`} width="max-w-md"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={loading} onClick={handleSubmit}>Queue Render →</Button>
        </>
      }
    >
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
      <div className="flex flex-col gap-4">
        <div className="bg-[#0d0d0f] rounded-lg p-3">
          <div className="text-xs text-[#5a5a70] mb-1">Parent Video</div>
          <div className="text-sm text-[#e8e8f0]">{video.title}</div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[#9090a8] font-medium">Music</label>
            <div className="flex gap-2">
              <button onClick={() => setForm(f => ({ ...f, sameMusic: true }))}
                className={`flex-1 py-2 rounded-lg text-xs border transition-colors ${form.sameMusic ? 'bg-[#7c6af7] border-[#7c6af7] text-white' : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8]'}`}>
                Same as parent
              </button>
              <button onClick={() => setForm(f => ({ ...f, sameMusic: false }))}
                className={`flex-1 py-2 rounded-lg text-xs border transition-colors ${!form.sameMusic ? 'bg-[#7c6af7] border-[#7c6af7] text-white' : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8]'}`}>
                Pick different
              </button>
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[#9090a8] font-medium">Visual</label>
            <div className="flex gap-2">
              <button onClick={() => setForm(f => ({ ...f, sameVisual: true }))}
                className={`flex-1 py-2 rounded-lg text-xs border transition-colors ${form.sameVisual ? 'bg-[#7c6af7] border-[#7c6af7] text-white' : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8]'}`}>
                9:16 crop
              </button>
              <button onClick={() => setForm(f => ({ ...f, sameVisual: false }))}
                className={`flex-1 py-2 rounded-lg text-xs border transition-colors ${!form.sameVisual ? 'bg-[#7c6af7] border-[#7c6af7] text-white' : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8]'}`}>
                Pick different
              </button>
            </div>
          </div>
        </div>
        <div className="text-xs text-[#9090a8]">Duration: <strong className="text-[#e8e8f0]">{shortTemplate?.short_duration_s ?? 58} seconds</strong> (fixed)</div>
        <Input label="CTA Overlay Text" value={form.ctaText} onChange={e => setForm(f => ({ ...f, ctaText: e.target.value }))} />
        <Select label="CTA Position" value={form.ctaPosition} onChange={e => setForm(f => ({ ...f, ctaPosition: e.target.value }))}>
          <option value="last_10s">Last 10 seconds</option>
          <option value="throughout">Throughout</option>
        </Select>
      </div>
    </Modal>
  )
}

function RegenerateThumbnailModal({ video, onClose, onDone }) {
  const [file, setFile]             = useState(null)
  const [text, setText]             = useState(video?.thumbnail_text || '')
  const [previewKey, setPreviewKey] = useState(0)
  const [hasThumbnail, setHasThumbnail] = useState(!!video?.thumbnail_path)
  const [generating, setGenerating] = useState(false)
  const [toast, setToast]           = useState(null)

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  const wordCount = text.trim() ? text.trim().split(/\s+/).filter(Boolean).length : 0
  const canGenerate = (file || hasThumbnail) && wordCount <= 5

  const handleGenerate = async () => {
    if (!canGenerate) return
    setGenerating(true)
    try {
      if (file) {
        await youtubeVideosApi.uploadThumbnailImage(video.id, file)
        setFile(null)
        setHasThumbnail(true)
      }
      await youtubeVideosApi.generateThumbnail(video.id, text.trim() || null)
      setPreviewKey(k => k + 1)
      showToast('Thumbnail generated', 'success')
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setGenerating(false)
    }
  }

  return (
    <Modal open title="Regenerate Thumbnail" onClose={onClose}>
      {toast && (
        <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />
      )}
      <div className="flex flex-col gap-4 px-1">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Midjourney Image</label>
          <input
            type="file"
            accept="image/*"
            onChange={e => setFile(e.target.files?.[0] || null)}
            className="text-sm text-[#9090a8] file:mr-3 file:py-1 file:px-2 file:rounded file:border-0 file:bg-[#2a2a32] file:text-[#e8e8f0] file:text-xs cursor-pointer"
          />
          {!file && !hasThumbnail && (
            <p className="text-xs text-[#5a5a70]">No source image — upload one above.</p>
          )}
        </div>

        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <label className="text-xs text-[#9090a8] font-medium">
              Thumbnail Text (optional, ≤5 words)
            </label>
            <span className={`text-xs font-mono ${wordCount > 5 ? 'text-[#f87171]' : 'text-[#5a5a70]'}`}>
              {wordCount}/5
            </span>
          </div>
          <Input
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder="e.g. DEEP FOCUS"
          />
        </div>

        <Button
          variant="secondary"
          size="sm"
          loading={generating}
          disabled={!canGenerate}
          onClick={handleGenerate}
        >
          Generate Preview
        </Button>

        {hasThumbnail && (
          <img
            key={previewKey}
            src={`${youtubeVideosApi.thumbnailUrl(video.id)}?t=${previewKey}`}
            alt="Thumbnail preview"
            className="w-full rounded-lg border border-[#2a2a32]"
            style={{ aspectRatio: '16/9', objectFit: 'cover' }}
            onError={() => setHasThumbnail(false)}
          />
        )}

        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" size="sm" onClick={onClose}>Cancel</Button>
          <Button
            size="sm"
            disabled={!hasThumbnail}
            onClick={() => { onDone?.(); onClose() }}
          >
            Done
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export default function YouTubeVideosPage() {
  const [videos, setVideos]               = useState([])
  const [templates, setTemplates]         = useState([])
  const [loading, setLoading]             = useState(true)
  const [filterStatus, setFilterStatus]   = useState('')
  const [activeTemplate, setActiveTemplate] = useState(null)
  const [makeShortVideo, setMakeShortVideo] = useState(null)
  const [previewVideo, setPreviewVideo] = useState(null)
  const [editingVideo, setEditingVideo] = useState(null)
  const [regenThumbnailVideo, setRegenThumbnailVideo] = useState(null)
  const [toast, setToast]                 = useState(null)
  const [channelPlans, setChannelPlans]     = useState([])
  const [accordionOpen, setAccordionOpen]   = useState(false)
  const [expandedPlanId, setExpandedPlanId] = useState(null)
  const [activeChannelPlan, setActiveChannelPlan] = useState(null)
  const [templateMenuOpen, setTemplateMenuOpen] = useState(null)  // 'header' | `plan-${id}` | null

  const landscapeTemplates = templates.filter(t => t.output_format === 'landscape_long')

  const openCreateForTemplate = (template, plan = null) => {
    setActiveTemplate(template)
    setActiveChannelPlan(plan)
    setTemplateMenuOpen(null)
  }

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  const load = async (signal = { cancelled: false }) => {
    setLoading(true)
    try {
      const vids = await youtubeVideosApi.list({ status: filterStatus || undefined })
      if (!signal.cancelled) setVideos(vids.items || vids)
    } catch (e) {
      if (!signal.cancelled) showToast(e.message, 'error')
    }
    try {
      const tmpl = await youtubeVideosApi.listTemplates()
      if (!signal.cancelled) setTemplates(tmpl)
    } catch (e) {
      if (!signal.cancelled) console.warn('Failed to load templates:', e)
    }
    try {
      const plans = await channelPlansApi.list()
      if (!signal.cancelled) setChannelPlans(plans)
    } catch (e) {
      if (!signal.cancelled) console.warn('Failed to load channel plans:', e)
    }
    if (!signal.cancelled) setLoading(false)
  }

  useEffect(() => {
    const signal = { cancelled: false }
    load(signal)
    return () => { signal.cancelled = true }
  }, [filterStatus])

  const handleRender = async (video) => {
    try {
      await youtubeVideosApi.render(video.id)
      showToast('Render queued', 'success')
      load()
    } catch (e) {
      showToast(e.message, 'error')
    }
  }

  const handleDelete = async (video) => {
    if (!confirm(`Delete "${video.title}"?`)) return
    try {
      await youtubeVideosApi.delete(video.id)
      load()
    } catch (e) {
      showToast(e.message, 'error')
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {toast && <Toast message={toast.msg} type={toast.type} />}

      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#e8e8f0]">YouTube Videos</h1>
          <p className="text-sm text-[#9090a8] mt-0.5">{videos.length} videos</p>
        </div>
        <div className="flex gap-2 relative">
          <Button
            variant="primary"
            onClick={() => {
              if (!landscapeTemplates.length) { showToast('No landscape template configured', 'error'); return }
              setTemplateMenuOpen(o => o === 'header' ? null : 'header')
            }}
          >
            + New Video {landscapeTemplates.length > 1 ? '▾' : ''}
          </Button>
          {templateMenuOpen === 'header' && (
            <div
              className="absolute right-0 top-full mt-1 z-10 min-w-[180px] bg-[#1c1c22] border border-[#2a2a32] rounded-md shadow-lg py-1"
              onMouseLeave={() => setTemplateMenuOpen(null)}
            >
              {landscapeTemplates.map(t => (
                <button
                  key={t.id}
                  onClick={() => openCreateForTemplate(t, null)}
                  className="w-full text-left px-3 py-2 text-sm text-[#e8e8f0] hover:bg-[#2a2a32]"
                >
                  {t.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Channel Plans accordion */}
      <div className="border border-[#2a2a32] rounded-xl overflow-hidden">
        <button
          onClick={() => setAccordionOpen(v => {
            if (v) setExpandedPlanId(null)
            return !v
          })}
          className="w-full flex items-center justify-between px-5 py-3 bg-[#1c1c22] hover:bg-[#222228] transition-colors"
        >
          <span className="text-sm font-semibold text-[#e8e8f0]">
            Channel Plans <span className="text-[#5a5a70] font-normal">({channelPlans.length})</span>
          </span>
          <span className="text-[#9090a8] text-xs">{accordionOpen ? '▲' : '▼'}</span>
        </button>

        {accordionOpen && (
          <div className="divide-y divide-[#2a2a32]">
            {channelPlans.length === 0 ? (
              <p className="px-5 py-4 text-xs text-[#5a5a70]">
                No channel plans yet. Visit <strong className="text-[#7c6af7]">Channel Plans</strong> to import one.
              </p>
            ) : channelPlans.map(plan => (
              <div key={plan.id} className="bg-[#16161a]">
                <button
                  onClick={() => setExpandedPlanId(id => id === plan.id ? null : plan.id)}
                  className="w-full flex items-center gap-3 px-5 py-3 hover:bg-[#1c1c22] transition-colors text-left"
                >
                  <span className="text-sm font-medium text-[#e8e8f0] flex-1">{plan.name}</span>
                  {plan.focus && (
                    <span className="text-[10px] font-mono bg-[#1c1c22] border border-[#2a2a32] px-2 py-0.5 rounded text-[#9090a8] hidden sm:inline">
                      {plan.focus.split(',')[0].trim()}
                    </span>
                  )}
                  {plan.rpm_estimate && (
                    <span className="text-[10px] font-mono text-[#34d399]">{plan.rpm_estimate}</span>
                  )}
                  <span className="text-[#9090a8] text-xs">{expandedPlanId === plan.id ? '▲' : '▼'}</span>
                </button>

                {expandedPlanId === plan.id && (
                  <div className="px-5 pb-5 flex flex-col gap-4">
                    <div className="flex flex-wrap gap-2">
                      {plan.focus && (
                        <span className="text-[10px] font-mono bg-[#1c1c22] border border-[#2a2a32] px-2 py-0.5 rounded text-[#9090a8]">
                          {plan.focus}
                        </span>
                      )}
                      {plan.upload_frequency && (
                        <span className="text-[10px] font-mono bg-[#1c1c22] border border-[#2a2a32] px-2 py-0.5 rounded text-[#9090a8]">
                          {plan.upload_frequency}
                        </span>
                      )}
                      {plan.rpm_estimate && (
                        <span className="text-[10px] font-mono bg-[#1c1c22] border border-[#2a2a32] px-2 py-0.5 rounded text-[#34d399]">
                          RPM {plan.rpm_estimate}
                        </span>
                      )}
                    </div>

                    <AIAssistantPanel key={plan.id} planId={plan.id} />

                    <div className="flex justify-end relative">
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => {
                          if (!landscapeTemplates.length) { showToast('No landscape template configured', 'error'); return }
                          const key = `plan-${plan.id}`
                          setTemplateMenuOpen(o => o === key ? null : key)
                        }}
                      >
                        + New Video for this channel {landscapeTemplates.length > 1 ? '▾' : ''}
                      </Button>
                      {templateMenuOpen === `plan-${plan.id}` && (
                        <div
                          className="absolute right-0 top-full mt-1 z-10 min-w-[180px] bg-[#1c1c22] border border-[#2a2a32] rounded-md shadow-lg py-1"
                          onMouseLeave={() => setTemplateMenuOpen(null)}
                        >
                          {landscapeTemplates.map(t => (
                            <button
                              key={t.id}
                              onClick={() => openCreateForTemplate(t, plan)}
                              className="w-full text-left px-3 py-2 text-sm text-[#e8e8f0] hover:bg-[#2a2a32]"
                            >
                              {t.label}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <Select
          value={filterStatus}
          onChange={e => setFilterStatus(e.target.value)}
          className="max-w-[160px]"
        >
          <option value="">All Status</option>
          <option value="draft">Draft</option>
          <option value="queued">Queued</option>
          <option value="rendering">Rendering</option>
          <option value="done">Done</option>
          <option value="failed">Failed</option>
          <option value="published">Published</option>
        </Select>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex justify-center py-12"><Spinner /></div>
      ) : videos.length === 0 ? (
        <EmptyState
          title="No YouTube videos"
          description="Create your first video — pick a template (ASMR, Soundscape, or Music Video)."
        />
      ) : (
        <div className="flex flex-col gap-3">
          {videos.map(v => {
            const tmpl = templates.find(t => t.id === v.template_id)
            const isActive = ACTIVE_RENDER_STATES.has(v.status)
            return (
              <Card key={v.id} className="px-5 py-4">
                <div className="flex items-start gap-4">
                {v.thumbnail_path && (
                  <img
                    src={youtubeVideosApi.thumbnailUrl(v.id)}
                    alt="thumbnail"
                    className="rounded flex-shrink-0 object-cover"
                    style={{ height: 128, aspectRatio: '16/9' }}
                    onError={e => { e.target.style.display = 'none' }}
                  />
                )}
                <div className="flex items-start justify-between gap-4 flex-1 min-w-0">
                  <div className="flex items-start gap-3 min-w-0">
                    {/* Template label chip */}
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-[#2a2a32] text-[#9090a8] flex-shrink-0">
                      {tmpl?.label || 'UNKNOWN'}
                    </span>
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-[#e8e8f0] truncate">{v.title}</div>
                      <div className="flex items-center gap-3 mt-1">
                        <span className="text-xs text-[#9090a8]">
                          {v.target_duration_h ? `${v.target_duration_h}h` : '—'}
                        </span>
                        {v.music_track_id  && <span className="text-xs text-[#5a5a70]">🎵 music linked</span>}
                        {v.visual_asset_id && <span className="text-xs text-[#5a5a70]">🖼 visual linked</span>}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="text-xs font-medium" style={{ color: STATUS_COLORS[v.status] }}>
                      ● {v.status}
                    </span>
                    {['draft', 'failed', 'audio_preview_ready', 'video_preview_ready'].includes(v.status) && (
                      <Button variant="ghost" size="sm" onClick={() => setEditingVideo(v)}>
                        ✎ Edit
                      </Button>
                    )}
                    {v.status === 'draft' && (
                      <Button variant="ghost" size="sm" onClick={() => handleRender(v)}>
                        Render →
                      </Button>
                    )}
                    {v.status === 'done' && (
                      <>
                        <Button variant="ghost" size="sm" onClick={() => setPreviewVideo(v)}>
                          ▶ Preview
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setMakeShortVideo(v)}>
                          + Make Short
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setRegenThumbnailVideo(v)}>
                          Thumbnail
                        </Button>
                      </>
                    )}
                    <button
                      onClick={() => handleDelete(v)}
                      className="text-[#5a5a70] hover:text-[#f87171] text-xs ml-1"
                    >
                      ✕
                    </button>
                  </div>
                </div>
                </div>
                {isActive && (
                  <div className="mt-4">
                    <ActiveRenderCard video={v} onUpdate={load} />
                  </div>
                )}
              </Card>
            )
          })}
        </div>
      )}

      {/* Creation slide-over */}
      {activeTemplate && (
        <CreationPanel
          template={activeTemplate}
          channelPlan={activeChannelPlan}
          channelPlans={activeChannelPlan ? [] : channelPlans}
          onClose={() => { setActiveTemplate(null); setActiveChannelPlan(null) }}
          onCreated={() => { setActiveTemplate(null); setActiveChannelPlan(null); load() }}
        />
      )}

      {/* Edit slide-over */}
      {editingVideo && (() => {
        const tmpl = templates.find(t => t.id === editingVideo.template_id)
        return (
          <CreationPanel
            template={tmpl}
            channelPlan={null}
            channelPlans={[]}
            mode="edit"
            existingVideo={editingVideo}
            onClose={() => setEditingVideo(null)}
            onCreated={() => { setEditingVideo(null); load() }}
          />
        )
      })()}

      {previewVideo && (
        <VideoPreviewModal video={previewVideo} onClose={() => setPreviewVideo(null)} />
      )}

      {/* Make Short Modal */}
      {makeShortVideo && (
        <MakeShortModal
          video={makeShortVideo}
          shortTemplates={templates.filter(t => t.output_format === 'portrait_short')}
          onClose={() => setMakeShortVideo(null)}
          onCreated={() => { setMakeShortVideo(null); load() }}
        />
      )}

      {/* Regenerate Thumbnail Modal */}
      {regenThumbnailVideo && (
        <RegenerateThumbnailModal
          video={regenThumbnailVideo}
          onClose={() => setRegenThumbnailVideo(null)}
          onDone={load}
        />
      )}
    </div>
  )
}
