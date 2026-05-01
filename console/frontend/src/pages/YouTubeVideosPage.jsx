import { useState, useEffect } from 'react'
import { youtubeVideosApi, musicApi, assetsApi, sfxApi } from '../api/client.js'
import { Card, Badge, Button, Input, Select, Toast, Spinner, EmptyState, Modal } from '../components/index.jsx'

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

function CreationPanel({ template, onClose, onCreated }) {
  const [form, setForm] = useState({
    theme: '',
    target_duration_h: template?.target_duration_h || 8,
    customDuration: '',
    isCustomDuration: false,
    music_track_id: null,
    visual_asset_id: null,
    sfx_overrides: null,
    seo_title: '',
    seo_description: '',
    seo_tags: '',
    output_quality: '1080p',
  })
  const [musicList, setMusicList]   = useState([])
  const [assetList, setAssetList]   = useState([])
  const [sfxList,   setSfxList]     = useState([])
  const [loading, setLoading]       = useState(false)
  const [toast, setToast]           = useState(null)

  const [sfxLayers, setSfxLayers] = useState({
    foreground: { asset_id: '', volume: 0.6 },
    midground:  { asset_id: '', volume: 0.3 },
    background: { asset_id: '', volume: 0.1 },
  })

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
      setForm(f => ({ ...f, music_track_id: String(newTrack.id) }))
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
      setForm(f => ({ ...f, visual_asset_id: String(newAsset.id) }))
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

  useEffect(() => {
    let mounted = true
    musicApi.list({ status: 'ready' })
      .then(d => { if (mounted) setMusicList(d.items || d || []) })
      .catch(() => {})
    assetsApi.list({ asset_type: 'video_clip' })
      .then(d => {
        if (mounted) setAssetList((d.items || d || []).filter(a => AI_SOURCES.includes(a.source)))
      })
      .catch(() => {})
    sfxApi.list()
      .then(d => { if (mounted) setSfxList(d.items || d || []) })
      .catch(() => {})
    return () => { mounted = false }
  }, [])

  useEffect(() => {
    if (form.theme && template) {
      const h = form.isCustomDuration
        ? (parseFloat(form.customDuration) || 8)
        : form.target_duration_h
      const durationDisplay = h < 1 ? `${Math.round(h * 60)}min` : h
      setForm(f => ({
        ...f,
        seo_title: (template.seo_title_formula || '{theme} — {duration}h')
          .replace('{theme}', form.theme)
          .replace('{duration}', durationDisplay),
        seo_description: (template.seo_description_template || '')
          .replace('{theme}', form.theme)
          .replace('{duration}', durationDisplay),
      }))
    }
  }, [form.theme, form.target_duration_h, form.customDuration, form.isCustomDuration])

  const handleSubmit = async () => {
    if (!form.theme) { showToast('Theme is required', 'error'); return }
    const duration = form.isCustomDuration
      ? parseFloat(form.customDuration)
      : form.target_duration_h
    if (!duration || duration <= 0) { showToast('Valid duration is required', 'error'); return }
    setLoading(true)
    try {
      const title = form.seo_title || `${template.label} — ${form.theme}`
      await youtubeVideosApi.create({
        title,
        template_id: template.id,
        theme: form.theme,
        target_duration_h: duration,
        music_track_id: form.music_track_id || null,
        visual_asset_id: form.visual_asset_id || null,
        sfx_overrides: (sfxLayers.foreground.asset_id || sfxLayers.midground.asset_id || sfxLayers.background.asset_id)
          ? {
              foreground: sfxLayers.foreground.asset_id ? sfxLayers.foreground : null,
              midground:  sfxLayers.midground.asset_id  ? sfxLayers.midground  : null,
              background: sfxLayers.background.asset_id ? sfxLayers.background : null,
            }
          : null,
        seo_title: form.seo_title,
        seo_description: form.seo_description,
        seo_tags: form.seo_tags
          ? form.seo_tags.split(',').map(t => t.trim()).filter(Boolean)
          : [],
        output_quality: form.output_quality,
      })
      onCreated()
      onClose()
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
          <h2 className="text-base font-semibold text-[#e8e8f0]">New {template?.label}</h2>
          <button onClick={onClose} className="text-[#9090a8] hover:text-[#e8e8f0]">✕</button>
        </div>

        {/* Toast — outside scroll area so it doesn't shift layout */}
        {toast && (
          <div className="absolute top-16 left-0 right-0 z-10 px-6">
            <Toast message={toast.msg} type={toast.type} />
          </div>
        )}
        <div className="flex-1 overflow-y-auto px-6 py-4 flex flex-col gap-6">

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

              <Input
                label="SEO Title"
                value={form.seo_title}
                onChange={e => setForm(f => ({ ...f, seo_title: e.target.value }))}
              />
              <Input
                label="SEO Tags (comma-separated)"
                value={form.seo_tags}
                onChange={e => setForm(f => ({ ...f, seo_tags: e.target.value }))}
                placeholder="asmr, rain, sleep, relaxing"
              />
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
              {template?.suno_prompt_template && (
                <div className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3 relative">
                  <div className="text-xs text-[#5a5a70] mb-1">Suno Prompt (reference)</div>
                  <p className="text-xs text-[#9090a8] pr-10 leading-relaxed">
                    {template.suno_prompt_template}
                  </p>
                  <button
                    onClick={() => navigator.clipboard.writeText(template.suno_prompt_template)}
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
              <p className="text-xs text-[#5a5a70]">Showing AI-generated clips only (Midjourney · Runway · Veo)</p>
              <Select
                label="Visual Loop"
                value={form.visual_asset_id || ''}
                onChange={e => setForm(f => ({ ...f, visual_asset_id: e.target.value || null }))}
              >
                <option value="">— Select from library —</option>
                {assetList.map(a => (
                  <option key={a.id} value={a.id}>
                    {a.description || `Asset #${a.id}`} ({a.source})
                  </option>
                ))}
              </Select>
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
              {template?.runway_prompt_template && (
                <div className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3 relative">
                  <div className="text-xs text-[#5a5a70] mb-1">Runway Prompt (reference)</div>
                  <p className="text-xs text-[#9090a8] pr-10 leading-relaxed">
                    {template.runway_prompt_template}
                  </p>
                  <button
                    onClick={() => navigator.clipboard.writeText(template.runway_prompt_template)}
                    className="absolute top-2 right-2 text-xs text-[#7c6af7] hover:text-[#9d8df8] px-2 py-1 bg-[#16161a] rounded"
                  >
                    Copy
                  </button>
                </div>
              )}
            </div>
          </section>

          {/* ④ SFX LAYERS */}
          <section>
            <div className="text-xs font-bold text-[#5a5a70] tracking-widest mb-3">④ SFX LAYERS</div>
            <div className="flex flex-col gap-3">
              {[
                { key: 'foreground', label: 'Foreground', defaultVol: 0.6 },
                { key: 'midground',  label: 'Midground',  defaultVol: 0.3 },
                { key: 'background', label: 'Background', defaultVol: 0.1 },
              ].map(({ key, label, defaultVol }) => {
                const sfxPack = template?.sfx_pack?.[key]
                const layerDefault = sfxList.find(s => s.id === sfxPack?.asset_id)
                return (
                  <div key={key} className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3 flex flex-col gap-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-[#9090a8]">{label}</span>
                      {layerDefault && !sfxLayers[key].asset_id && (
                        <span className="text-[10px] text-[#5a5a70] font-mono">template default: {layerDefault.title}</span>
                      )}
                    </div>
                    <select
                      value={sfxLayers[key].asset_id}
                      onChange={e => setSfxLayers(prev => ({
                        ...prev,
                        [key]: { ...prev[key], asset_id: e.target.value },
                      }))}
                      className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7] transition-colors w-full"
                    >
                      <option value="">— {layerDefault ? `${layerDefault.title} (template default)` : 'No SFX'} —</option>
                      {sfxList.map(s => (
                        <option key={s.id} value={String(s.id)}>{s.title} ({s.category || 'sfx'})</option>
                      ))}
                    </select>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-[#5a5a70] w-16 shrink-0">Volume</span>
                      <input
                        type="range"
                        min={0} max={1} step={0.05}
                        value={sfxLayers[key].volume}
                        onChange={e => setSfxLayers(prev => ({
                          ...prev,
                          [key]: { ...prev[key], volume: parseFloat(e.target.value) },
                        }))}
                        className="flex-1 accent-[#7c6af7]"
                      />
                      <span className="text-xs text-[#9090a8] font-mono w-8 text-right">
                        {Math.round(sfxLayers[key].volume * 100)}%
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          </section>

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
          <Button variant="primary" loading={loading} onClick={handleSubmit}>Queue Render →</Button>
        </div>
      </div>
    </div>
  )
}

function MakeShortModal({ video, shortTemplates, onClose, onCreated }) {
  const [form, setForm] = useState({
    sameMusic: true,
    sameVisual: true,
    ctaText: `Full ${video.target_duration_h ? video.target_duration_h + 'h' : ''} version on channel ↑`,
    ctaPosition: 'last_10s',
  })
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState(null)
  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000) }

  const shortTemplate = shortTemplates[0]

  const handleSubmit = async () => {
    if (loading) return
    if (!shortTemplate) { showToast('No short template found', 'error'); return }
    setLoading(true)
    try {
      await youtubeVideosApi.create({
        title: `${video.title} — Short`,
        template_id: shortTemplate.id,
        theme: video.theme,
        target_duration_h: 58 / 3600,
        music_track_id: form.sameMusic ? video.music_track_id : null,
        visual_asset_id: form.sameVisual ? video.visual_asset_id : null,
        sfx_overrides: { parent_youtube_video_id: video.id, cta_text: form.ctaText, cta_position: form.ctaPosition },
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
        <div className="text-xs text-[#9090a8]">Duration: <strong className="text-[#e8e8f0]">58 seconds</strong> (fixed)</div>
        <Input label="CTA Overlay Text" value={form.ctaText} onChange={e => setForm(f => ({ ...f, ctaText: e.target.value }))} />
        <Select label="CTA Position" value={form.ctaPosition} onChange={e => setForm(f => ({ ...f, ctaPosition: e.target.value }))}>
          <option value="last_10s">Last 10 seconds</option>
          <option value="throughout">Throughout</option>
        </Select>
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
  const [toast, setToast]                 = useState(null)

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
      if (!signal.cancelled) setTemplates(tmpl.filter(t => t.output_format === 'landscape_long'))
    } catch (e) {
      if (!signal.cancelled) console.warn('Failed to load templates:', e)
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
        <div className="flex gap-2">
          {templates.map(t => (
            <Button key={t.slug} variant="primary" onClick={() => setActiveTemplate(t)}>
              + New {t.label}
            </Button>
          ))}
        </div>
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
          description="Create your first ASMR or Soundscape video."
        />
      ) : (
        <div className="flex flex-col gap-3">
          {videos.map(v => {
            const tmpl = templates.find(t => t.id === v.template_id)
            return (
              <Card key={v.id} className="px-5 py-4">
                <div className="flex items-start justify-between gap-4">
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
              </Card>
            )
          })}
        </div>
      )}

      {/* Creation slide-over */}
      {activeTemplate && (
        <CreationPanel
          template={activeTemplate}
          onClose={() => setActiveTemplate(null)}
          onCreated={() => { setActiveTemplate(null); load() }}
        />
      )}

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
    </div>
  )
}
