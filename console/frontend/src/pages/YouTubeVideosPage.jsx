import { useState, useEffect } from 'react'
import { youtubeVideosApi, musicApi, assetsApi } from '../api/client.js'
import { Card, Badge, Button, Input, Select, Toast, Spinner, EmptyState } from '../components/index.jsx'

const STATUS_COLORS = {
  draft:     '#9090a8',
  rendering: '#fbbf24',
  ready:     '#34d399',
  uploaded:  '#4a9eff',
}

const QUALITY_OPTIONS = ['1080p', '4K']
const DURATION_PRESETS = [
  { label: '1h',     value: 1 },
  { label: '3h',     value: 3 },
  { label: '8h',     value: 8 },
  { label: '10h',    value: 10 },
  { label: 'Custom', value: null },
]

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
  const [loading, setLoading]       = useState(false)
  const [toast, setToast]           = useState(null)

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  useEffect(() => {
    musicApi.list({ status: 'ready' }).then(d => setMusicList(d.items || d)).catch(() => {})
    assetsApi.list({ asset_type: 'video_clip' }).then(d => setAssetList(d.items || d)).catch(() => {})
  }, [])

  useEffect(() => {
    if (form.theme && template) {
      const h = form.isCustomDuration
        ? (parseFloat(form.customDuration) || 8)
        : form.target_duration_h
      setForm(f => ({
        ...f,
        seo_title: (template.seo_title_formula || '{theme} — {duration}h')
          .replace('{theme}', form.theme)
          .replace('{duration}', h),
        seo_description: (template.seo_description_template || '')
          .replace('{theme}', form.theme)
          .replace('{duration}', h),
      }))
    }
  }, [form.theme, form.target_duration_h, form.customDuration])

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
        sfx_overrides: form.sfx_overrides,
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

        <div className="flex-1 overflow-y-auto px-6 py-4 flex flex-col gap-6">
          {toast && <Toast message={toast.msg} type={toast.type} />}

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
            <div className="text-xs font-bold text-[#5a5a70] tracking-widest mb-3">② MUSIC</div>
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
            <div className="text-xs font-bold text-[#5a5a70] tracking-widest mb-3">③ VISUAL</div>
            <div className="flex flex-col gap-3">
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

          {/* ④ RENDER */}
          <section>
            <div className="text-xs font-bold text-[#5a5a70] tracking-widest mb-3">④ RENDER</div>
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

export default function YouTubeVideosPage() {
  const [videos, setVideos]               = useState([])
  const [templates, setTemplates]         = useState([])
  const [loading, setLoading]             = useState(true)
  const [filterStatus, setFilterStatus]   = useState('')
  const [activeTemplate, setActiveTemplate] = useState(null)
  const [toast, setToast]                 = useState(null)

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  const load = async () => {
    setLoading(true)
    try {
      const [vids, tmpl] = await Promise.all([
        youtubeVideosApi.list({ status: filterStatus || undefined }),
        youtubeVideosApi.listTemplates(),
      ])
      setVideos(vids.items || vids)
      setTemplates(tmpl.filter(t => t.output_format === 'landscape_long'))
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [filterStatus])

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
          <option value="rendering">Rendering</option>
          <option value="ready">Ready</option>
          <option value="uploaded">Uploaded</option>
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
    </div>
  )
}
