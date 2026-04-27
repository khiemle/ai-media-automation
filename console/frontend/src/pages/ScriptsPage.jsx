import { useState, useEffect } from 'react'
import { scriptsApi, musicApi, fetchApi } from '../api/client.js'
import { useApi } from '../hooks/useApi.js'
import { Card, Badge, Button, Modal, Tabs, Select, Input, Textarea, StatBox, Toast, Spinner, EmptyState } from '../components/index.jsx'

const STATUS_TABS = [
  { id: '',               label: 'All' },
  { id: 'draft',          label: 'Draft' },
  { id: 'pending_review', label: 'Review' },
  { id: 'approved',       label: 'Approved' },
  { id: 'editing',        label: 'Editing' },
  { id: 'producing',      label: 'Producing' },
  { id: 'completed',      label: 'Done' },
]

const MOODS     = ['uplifting', 'calm_focus', 'energetic', 'dramatic', 'neutral']
const SCENE_TYPES = ['hook', 'body', 'transition', 'cta']
const OVERLAY_STYLES = ['bold_center', 'subtitle_bottom', 'corner_tag', 'full_overlay', 'minimal']
const SUBTITLE_STYLE_OPTIONS = [
  { value: '',              label: 'None' },
  { value: 'bold_center',   label: 'Bold Center' },
  { value: 'tiktok_yellow', label: 'TikTok Yellow' },
  { value: 'tiktok_white',  label: 'TikTok White' },
  { value: 'bold_orange',   label: 'Bold Orange' },
  { value: 'caption_dark',  label: 'Caption Dark' },
  { value: 'minimal',       label: 'Minimal' },
]

// ── Scene Editor Row ──────────────────────────────────────────────────────────
function SceneRow({ scene, index, total, onChange, onMove, onDelete, onRegen, regenLoading }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="border border-[#2a2a32] rounded-xl overflow-hidden">
      {/* Header */}
      <div
        className="flex items-center gap-3 px-4 py-2.5 bg-[#16161a] cursor-pointer hover:bg-[#1c1c22] transition-colors"
        onClick={() => setExpanded(e => !e)}
      >
        <span className="text-xs font-mono text-[#5a5a70] w-5 text-center">{index + 1}</span>
        <Badge status={scene.type || 'body'} label={scene.type || 'body'} />
        <span className="flex-1 text-sm text-[#9090a8] truncate">
          {scene.narration?.slice(0, 80) || '(no narration)'}
        </span>
        <span className="text-xs font-mono text-[#5a5a70]">{scene.duration || 0}s</span>
        <div className="flex gap-1" onClick={e => e.stopPropagation()}>
          <Button variant="ghost" size="sm" disabled={index === 0} onClick={() => onMove(index, 'up')}>↑</Button>
          <Button variant="ghost" size="sm" disabled={index === total - 1} onClick={() => onMove(index, 'down')}>↓</Button>
          <Button variant="ghost" size="sm" loading={regenLoading === index} onClick={() => onRegen(index)}>↺</Button>
          <Button variant="danger" size="sm" onClick={() => onDelete(index)}>✕</Button>
        </div>
        <span className="text-[#5a5a70] text-xs">{expanded ? '▲' : '▼'}</span>
      </div>

      {/* Expanded editor */}
      {expanded && (
        <div className="p-4 grid grid-cols-2 gap-3 bg-[#1c1c22]">
          <Textarea
            label="Narration"
            value={scene.narration || ''}
            onChange={e => onChange(index, 'narration', e.target.value)}
            rows={3}
          />
          <Textarea
            label="Visual Hint"
            value={scene.visual_hint || ''}
            onChange={e => onChange(index, 'visual_hint', e.target.value)}
            rows={3}
          />
          <Input
            label="Text Overlay"
            value={scene.text_overlay || ''}
            onChange={e => onChange(index, 'text_overlay', e.target.value)}
          />
          <Select
            label="Overlay Style"
            value={scene.overlay_style || ''}
            onChange={e => onChange(index, 'overlay_style', e.target.value)}
            placeholder="None"
            options={OVERLAY_STYLES.map(s => ({ value: s, label: s }))}
          />
          <Select
            label="Scene Type"
            value={scene.type || 'body'}
            onChange={e => onChange(index, 'type', e.target.value)}
            options={SCENE_TYPES.map(t => ({ value: t, label: t }))}
          />
          <Input
            label="Duration (seconds)"
            type="number"
            value={scene.duration || ''}
            onChange={e => onChange(index, 'duration', parseFloat(e.target.value) || 0)}
          />
          <Select
            label="Transition Out"
            value={scene.transition_out || ''}
            onChange={e => onChange(index, 'transition_out', e.target.value)}
            placeholder="None"
            options={['fade', 'cut', 'slide_left', 'slide_right', 'zoom_in'].map(t => ({ value: t, label: t }))}
          />
        </div>
      )}
    </div>
  )
}

// ── Script Editor Modal ───────────────────────────────────────────────────────
function ScriptEditorModal({ scriptId, onClose, onSaved }) {
  const { data, loading } = useApi(() => scriptsApi.get(scriptId), [scriptId])
  const [draft, setDraft] = useState(null)
  const [language, setLanguage] = useState('vietnamese')
  const [voices, setVoices] = useState(null)
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [regenLoading, setRegenLoading] = useState(null)
  const [toast, setToast] = useState(null)

  useEffect(() => {
    fetchApi('/api/llm/voices').then(setVoices).catch(() => {})
  }, [])

  useEffect(() => {
    if (data) setLanguage(data.language || 'vietnamese')
  }, [data])

  const showToast = (message, type = 'success') => {
    setToast({ message, type })
    setTimeout(() => setToast(null), 3000)
  }

  // Initialise draft from loaded data
  const scriptJson = draft ?? data?.script_json ?? {}
  const scenes     = scriptJson.scenes || []
  const meta       = scriptJson.meta || {}
  const video      = scriptJson.video || {}

  // Load all ready music tracks (no niche filter — allow manual selection from full library)
  const { data: musicTracks = [] } = useApi(
    () => musicApi.list({ status: 'ready' }),
    []
  )

  const setScriptField = (section, key, value) => {
    setDraft(prev => {
      const current = prev ?? data?.script_json ?? {}
      return { ...current, [section]: { ...(current[section] || {}), [key]: value } }
    })
  }
  const setScenes = (newScenes) => {
    const current = draft ?? data?.script_json ?? {}
    setDraft({ ...current, scenes: newScenes })
  }

  const handleSceneChange = (idx, field, value) => {
    const updated = [...scenes]
    updated[idx] = { ...updated[idx], [field]: value }
    setScenes(updated)
  }
  const handleSceneMove = (idx, dir) => {
    const updated = [...scenes]
    const swapIdx = dir === 'up' ? idx - 1 : idx + 1
    ;[updated[idx], updated[swapIdx]] = [updated[swapIdx], updated[idx]]
    setScenes(updated)
  }
  const handleSceneDelete = (idx) => setScenes(scenes.filter((_, i) => i !== idx))
  const handleSceneAdd = () => setScenes([...scenes, {
    id: `scene_${Date.now()}`, type: 'body', narration: '', visual_hint: '', duration: 5, transition_out: 'cut',
  }])
  const handleSceneRegen = async (idx) => {
    setRegenLoading(idx)
    try {
      const res = await scriptsApi.regenerateScene(scriptId, idx)
      setDraft(res.script_json)
      showToast(`Scene ${idx + 1} regenerated`, 'success')
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setRegenLoading(null)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await scriptsApi.update(scriptId, { script_json: scriptJson, editor_notes: notes, language })
      showToast('Script saved', 'success')
      onSaved?.()
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return (
    <Modal open onClose={onClose} title="Loading script…">
      <div className="flex justify-center py-10"><Spinner size={28} /></div>
    </Modal>
  )

  return (
    <Modal
      open
      onClose={onClose}
      title={`Edit Script — ${data?.topic || ''}`}
      width="max-w-4xl"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={saving} onClick={handleSave}>Save Changes</Button>
        </>
      }
    >
      <div className="flex flex-col gap-5">
        {/* Meta fields */}
        <div>
          <div className="text-xs font-semibold text-[#9090a8] uppercase tracking-wider mb-3">Metadata</div>
          <div className="grid grid-cols-2 gap-3">
            <Input label="Topic"    value={meta.topic    || ''} onChange={e => setScriptField('meta', 'topic', e.target.value)} />
            <Input label="Niche"    value={meta.niche    || ''} onChange={e => setScriptField('meta', 'niche', e.target.value)} />
            <Input label="Template" value={meta.template || ''} onChange={e => setScriptField('meta', 'template', e.target.value)} />
            <Input label="Region"   value={meta.region   || ''} onChange={e => setScriptField('meta', 'region', e.target.value)} />
            <Select
              label="Language"
              value={language}
              onChange={e => {
                setLanguage(e.target.value)
                setScriptField('video', 'tts_service', '')
                setScriptField('video', 'voice', '')
              }}
              options={[
                { value: 'vietnamese', label: 'Vietnamese' },
                { value: 'english',    label: 'English' },
              ]}
            />
          </div>
        </div>

        {/* Video fields */}
        <div>
          <div className="text-xs font-semibold text-[#9090a8] uppercase tracking-wider mb-3">Video</div>
          <div className="grid grid-cols-2 gap-3">
            <Input label="Title"        value={video.title       || ''} onChange={e => setScriptField('video', 'title', e.target.value)} />
            <Textarea label="Description" value={video.description || ''} onChange={e => setScriptField('video', 'description', e.target.value)} rows={2} />
            <Input label="Hashtags (comma-sep)" value={(video.hashtags || []).join(', ')} onChange={e => setScriptField('video', 'hashtags', e.target.value.split(',').map(h => h.trim()).filter(Boolean))} />
            {/* TTS Service */}
            <div>
              <label className="text-xs text-[#9090a8] font-medium block mb-1">TTS Service</label>
              <select
                value={video.tts_service || (language === 'vietnamese' ? 'elevenlabs' : 'kokoro')}
                onChange={e => {
                  setScriptField('video', 'tts_service', e.target.value)
                  setScriptField('video', 'voice', '')
                }}
                disabled={language === 'vietnamese'}
                className="w-full bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7] transition-colors appearance-none cursor-pointer disabled:opacity-50"
              >
                {language === 'english' && <option value="kokoro">Kokoro</option>}
                <option value="elevenlabs">ElevenLabs</option>
              </select>
              {language === 'vietnamese' && (
                <p className="text-[10px] text-[#5a5a70] mt-0.5 font-mono">Vietnamese requires ElevenLabs</p>
              )}
            </div>
            {/* Voice */}
            <div>
              <label className="text-xs text-[#9090a8] font-medium block mb-1">Voice</label>
              <select
                value={video.voice || ''}
                onChange={e => setScriptField('video', 'voice', e.target.value)}
                className="w-full bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7] transition-colors appearance-none cursor-pointer"
              >
                <option value="">— select —</option>
                {voices && (() => {
                  const svc = video.tts_service || (language === 'vietnamese' ? 'elevenlabs' : 'kokoro')
                  if (svc === 'kokoro') {
                    return (
                      <>
                        <optgroup label="American English — Female">
                          {voices.kokoro?.american_english?.female?.map(v => <option key={v.id} value={v.id}>{v.name} ({v.id})</option>)}
                        </optgroup>
                        <optgroup label="American English — Male">
                          {voices.kokoro?.american_english?.male?.map(v => <option key={v.id} value={v.id}>{v.name} ({v.id})</option>)}
                        </optgroup>
                        <optgroup label="British English — Female">
                          {voices.kokoro?.british_english?.female?.map(v => <option key={v.id} value={v.id}>{v.name} ({v.id})</option>)}
                        </optgroup>
                        <optgroup label="British English — Male">
                          {voices.kokoro?.british_english?.male?.map(v => <option key={v.id} value={v.id}>{v.name} ({v.id})</option>)}
                        </optgroup>
                      </>
                    )
                  }
                  const langKey = language === 'vietnamese' ? 'vi' : 'en'
                  return (
                    <>
                      <optgroup label="Male">
                        {voices.elevenlabs?.[langKey]?.male?.map(v => <option key={v.id} value={v.id}>{v.name !== 'Unknown' ? v.name : v.id}</option>)}
                      </optgroup>
                      <optgroup label="Female">
                        {voices.elevenlabs?.[langKey]?.female?.map(v => <option key={v.id} value={v.id}>{v.name !== 'Unknown' ? v.name : v.id}</option>)}
                      </optgroup>
                    </>
                  )
                })()}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-[#9090a8] font-medium">Background Music</label>
              <select
                value={
                  video.music_disabled
                    ? 'none'
                    : video.music_track_id != null
                      ? String(video.music_track_id)
                      : 'auto'
                }
                onChange={e => {
                  const val = e.target.value
                  if (val === 'none') {
                    setScriptField('video', 'music_disabled', true)
                    setScriptField('video', 'music_track_id', null)
                  } else if (val === 'auto') {
                    setScriptField('video', 'music_disabled', false)
                    setScriptField('video', 'music_track_id', null)
                  } else {
                    setScriptField('video', 'music_disabled', false)
                    setScriptField('video', 'music_track_id', parseInt(val))
                  }
                }}
                className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7] transition-colors appearance-none cursor-pointer"
              >
                <option value="auto">Auto (by mood)</option>
                <option value="none">No music (TTS only)</option>
                {musicTracks.map(t => (
                  <option key={t.id} value={String(t.id)}>
                    {t.title} · {t.duration_s ? `${t.duration_s.toFixed(0)}s` : '?'} · {(t.genres || []).join(', ')}
                  </option>
                ))}
              </select>
            </div>
            <Select label="Mood"    value={video.music_mood || ''} onChange={e => setScriptField('video', 'music_mood', e.target.value)} placeholder="Default" options={MOODS.map(m => ({ value: m, label: m }))} />
            <Input label="Voice Speed" type="number" value={video.voice_speed ?? 1} onChange={e => setScriptField('video', 'voice_speed', parseFloat(e.target.value))} />
            <Select
              label="Subtitle Style"
              value={video.subtitle_style ?? 'bold_center'}
              onChange={e => setScriptField('video', 'subtitle_style', e.target.value || null)}
              options={SUBTITLE_STYLE_OPTIONS}
            />
          </div>
        </div>

        {/* Scenes */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <div className="text-xs font-semibold text-[#9090a8] uppercase tracking-wider">
              Scenes ({scenes.length}) · {scenes.reduce((s, sc) => s + (sc.duration || 0), 0)}s total
            </div>
            <Button variant="ghost" size="sm" onClick={handleSceneAdd}>+ Add Scene</Button>
          </div>
          <div className="flex flex-col gap-2">
            {scenes.map((sc, i) => (
              <SceneRow
                key={sc.id || i}
                scene={sc}
                index={i}
                total={scenes.length}
                onChange={handleSceneChange}
                onMove={handleSceneMove}
                onDelete={handleSceneDelete}
                onRegen={handleSceneRegen}
                regenLoading={regenLoading}
              />
            ))}
          </div>
        </div>

        {/* Editor notes */}
        <Textarea
          label="Editor Notes"
          value={notes}
          onChange={e => setNotes(e.target.value)}
          placeholder="Notes for the reviewer..."
          rows={2}
        />
      </div>

      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    </Modal>
  )
}

// ── Scripts Page ──────────────────────────────────────────────────────────────
export default function ScriptsPage() {
  const [statusFilter, setStatusFilter] = useState('')
  const [editingId,    setEditingId]    = useState(null)
  const [bulkSelected, setBulkSelected] = useState(new Set())
  const [toast,        setToast]        = useState(null)
  const [actionLoading, setActionLoading] = useState(null)

  const showToast = (message, type = 'success') => {
    setToast({ message, type })
    setTimeout(() => setToast(null), 3000)
  }

  const { data, loading, refetch } = useApi(
    () => scriptsApi.list({ status: statusFilter, per_page: 50 }),
    [statusFilter]
  )

  const scripts = data?.items || []
  const total   = data?.total || 0

  // ── Counts by status ────────────────────────────────────────────────────────
  const counts = scripts.reduce((acc, s) => {
    acc[s.status] = (acc[s.status] || 0) + 1
    return acc
  }, {})

  const tabsWithCount = STATUS_TABS.map(t => ({
    ...t,
    count: t.id ? counts[t.id] : undefined,
  }))

  // ── Bulk select ─────────────────────────────────────────────────────────────
  const toggleBulk = (id) => setBulkSelected(prev => {
    const next = new Set(prev)
    next.has(id) ? next.delete(id) : next.add(id)
    return next
  })
  const selectAll   = () => setBulkSelected(new Set(scripts.map(s => s.id)))
  const deselectAll = () => setBulkSelected(new Set())

  // ── Actions ─────────────────────────────────────────────────────────────────
  const handleApprove = async (id) => {
    setActionLoading(id + '_approve')
    try {
      await scriptsApi.approve(id)
      refetch()
      showToast('Script approved', 'success')
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setActionLoading(null)
    }
  }

  const handleReject = async (id) => {
    setActionLoading(id + '_reject')
    try {
      await scriptsApi.reject(id)
      refetch()
      showToast('Script sent back to draft', 'info')
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setActionLoading(null)
    }
  }

  const handleRegen = async (id) => {
    setActionLoading(id + '_regen')
    try {
      await scriptsApi.regenerate(id)
      refetch()
      showToast('Script regenerated', 'success')
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setActionLoading(null)
    }
  }

  const handleBulkApprove = async () => {
    for (const id of bulkSelected) await scriptsApi.approve(id).catch(() => {})
    refetch()
    deselectAll()
    showToast(`${bulkSelected.size} scripts approved`, 'success')
  }

  const handleBulkReject = async () => {
    for (const id of bulkSelected) await scriptsApi.reject(id).catch(() => {})
    refetch()
    deselectAll()
    showToast(`${bulkSelected.size} scripts rejected`, 'info')
  }

  return (
    <div className="flex flex-col gap-5">
      {/* ── Page header ── */}
      <div>
        <h1 className="text-xl font-bold text-[#e8e8f0]">Scripts</h1>
        <p className="text-sm text-[#9090a8] mt-0.5">Review and approve LLM-generated scripts</p>
      </div>

      {/* ── Stats ── */}
      <div className="flex gap-3 flex-wrap">
        <StatBox label="Total" value={total} />
        <StatBox label="Pending Review" value={counts.pending_review || 0} accent />
        <StatBox label="Approved" value={counts.approved || 0} />
        <StatBox label="Producing" value={counts.producing || 0} />
        <StatBox label="Completed" value={counts.completed || 0} />
      </div>

      {/* ── List card ── */}
      <Card title="Scripts">
        {/* Status tabs */}
        <Tabs tabs={tabsWithCount} active={statusFilter} onChange={setStatusFilter} />

        {/* Bulk action bar */}
        <div className="flex items-center gap-3 mt-3 mb-2">
          <label className="flex items-center gap-2 cursor-pointer text-sm text-[#9090a8]">
            <input
              type="checkbox"
              checked={bulkSelected.size === scripts.length && scripts.length > 0}
              onChange={e => e.target.checked ? selectAll() : deselectAll()}
              className="accent-[#7c6af7] w-3.5 h-3.5"
            />
            Select All
          </label>
          {bulkSelected.size > 0 && (
            <>
              <span className="text-sm text-[#7c6af7] font-mono">{bulkSelected.size} selected</span>
              <Button variant="success" size="sm" onClick={handleBulkApprove}>✓ Approve</Button>
              <Button variant="danger"  size="sm" onClick={handleBulkReject}>✕ Reject</Button>
            </>
          )}
        </div>

        {/* Script list */}
        {loading ? (
          <div className="flex justify-center py-12"><Spinner size={28} /></div>
        ) : scripts.length === 0 ? (
          <EmptyState
            icon="✍️"
            title="No scripts yet"
            description="Go to the Scraper tab, select some videos, and generate your first script."
          />
        ) : (
          <div className="flex flex-col gap-2 mt-1">
            {scripts.map(s => (
              <div
                key={s.id}
                className={`flex items-center gap-3 bg-[#16161a] border rounded-xl px-4 py-3 transition-colors ${
                  bulkSelected.has(s.id) ? 'border-[#7c6af7]/50 bg-[#0f0f2a]' : 'border-[#2a2a32] hover:border-[#3a3a46]'
                }`}
              >
                {/* Checkbox */}
                <input
                  type="checkbox"
                  checked={bulkSelected.has(s.id)}
                  onChange={() => toggleBulk(s.id)}
                  className="accent-[#7c6af7] w-3.5 h-3.5 flex-shrink-0"
                  onClick={e => e.stopPropagation()}
                />

                {/* Status badge */}
                <Badge status={s.status} />

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-[#e8e8f0] truncate">{s.topic || 'Untitled'}</div>
                  <div className="text-xs text-[#9090a8] font-mono mt-0.5">
                    {s.niche && <span className="mr-2">{s.niche}</span>}
                    {s.template && <span className="mr-2">· {s.template}</span>}
                    {s.performance_score != null && <span>· score: {s.performance_score.toFixed(0)}</span>}
                  </div>
                </div>

                {/* Score bar */}
                {s.performance_score != null && (
                  <div className="w-16">
                    <div className="h-1 bg-[#2a2a32] rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${Math.min(100, s.performance_score)}%`,
                          backgroundColor: s.performance_score >= 70 ? '#34d399' : s.performance_score >= 40 ? '#fbbf24' : '#f87171',
                        }}
                      />
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="flex items-center gap-1.5 flex-shrink-0">
                  <Button variant="ghost" size="sm" onClick={() => setEditingId(s.id)}>Edit</Button>
                  {['draft', 'pending_review', 'editing'].includes(s.status) && (
                    <Button
                      variant="success"
                      size="sm"
                      loading={actionLoading === `${s.id}_approve`}
                      onClick={() => handleApprove(s.id)}
                    >✓</Button>
                  )}
                  {['pending_review', 'approved', 'editing'].includes(s.status) && (
                    <Button
                      variant="danger"
                      size="sm"
                      loading={actionLoading === `${s.id}_reject`}
                      onClick={() => handleReject(s.id)}
                    >✕</Button>
                  )}
                  <Button
                    variant="accent"
                    size="sm"
                    loading={actionLoading === `${s.id}_regen`}
                    onClick={() => handleRegen(s.id)}
                  >↺</Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* ── Script Editor Modal ── */}
      {editingId && (
        <ScriptEditorModal
          scriptId={editingId}
          onClose={() => setEditingId(null)}
          onSaved={() => { refetch(); setEditingId(null) }}
        />
      )}

      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  )
}
