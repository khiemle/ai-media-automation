import { useState, useRef, useEffect } from 'react'
import { musicApi, nichesApi } from '../api/client.js'
import { useApi } from '../hooks/useApi.js'
import { Card, Badge, Button, StatBox, Modal, Input, Select, Spinner, EmptyState, Toast } from '../components/index.jsx'

const MOODS   = ['uplifting', 'calm_focus', 'energetic', 'dramatic', 'neutral']
const GENRES  = ['pop', 'rock', 'electronic', 'jazz', 'classical', 'hip-hop', 'ambient', 'cinematic']

// ── Multi-select pill group ───────────────────────────────────────────────────
function MultiSelect({ label, options, value = [], onChange }) {
  const toggle = (opt) => onChange(value.includes(opt) ? value.filter(v => v !== opt) : [...value, opt])
  return (
    <div className="flex flex-col gap-1">
      {label && <label className="text-xs text-[#9090a8] font-medium">{label}</label>}
      <div className="flex flex-wrap gap-1.5">
        {options.map(opt => (
          <button
            key={opt}
            type="button"
            onClick={() => toggle(opt)}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors ${
              value.includes(opt)
                ? 'bg-[#7c6af7] border-[#7c6af7] text-white'
                : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8] hover:border-[#7c6af7] hover:text-[#e8e8f0]'
            }`}
          >
            {opt}
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Edit Track Modal ──────────────────────────────────────────────────────────
function EditModal({ track, niches, onClose, onSaved }) {
  const [form, setForm] = useState({
    title:         track.title,
    niches:        track.niches || [],
    moods:         track.moods || [],
    genres:        track.genres || [],
    is_vocal:      track.is_vocal,
    is_favorite:   track.is_favorite,
    volume:        track.volume ?? 0.15,
    quality_score: track.quality_score ?? 80,
  })
  const [saving, setSaving] = useState(false)
  const [toast,  setToast]  = useState(null)
  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000) }

  const handleSave = async () => {
    setSaving(true)
    try {
      await musicApi.update(track.id, form)
      onSaved()
      onClose()
    } catch (e) { showToast(e.message, 'error') }
    finally { setSaving(false) }
  }

  return (
    <Modal open onClose={onClose} title={`Edit — ${track.title}`} width="max-w-xl"
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" loading={saving} onClick={handleSave}>Save</Button></>}
    >
      <div className="flex flex-col gap-4">
        <Input label="Title" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} />
        <MultiSelect label="Niches" options={niches.map(n => n.name)} value={form.niches} onChange={v => setForm(f => ({ ...f, niches: v }))} />
        <MultiSelect label="Moods"  options={MOODS}  value={form.moods}  onChange={v => setForm(f => ({ ...f, moods: v }))} />
        <MultiSelect label="Genres" options={GENRES} value={form.genres} onChange={v => setForm(f => ({ ...f, genres: v }))} />
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[#9090a8] font-medium">Volume ({(form.volume * 100).toFixed(0)}%)</label>
            <input type="range" min="0" max="1" step="0.01" value={form.volume}
              onChange={e => setForm(f => ({ ...f, volume: parseFloat(e.target.value) }))}
              className="accent-[#7c6af7]" />
          </div>
          <Input label="Quality Score (0–100)" type="number" value={form.quality_score}
            onChange={e => setForm(f => ({ ...f, quality_score: parseInt(e.target.value) || 0 }))} />
        </div>
        <div className="flex gap-4">
          <label className="flex items-center gap-2 cursor-pointer text-sm text-[#9090a8]">
            <input type="checkbox" checked={form.is_vocal} onChange={e => setForm(f => ({ ...f, is_vocal: e.target.checked }))}
              className="accent-[#7c6af7]" />
            Vocal
          </label>
          <label className="flex items-center gap-2 cursor-pointer text-sm text-[#9090a8]">
            <input type="checkbox" checked={form.is_favorite} onChange={e => setForm(f => ({ ...f, is_favorite: e.target.checked }))}
              className="accent-[#7c6af7]" />
            Favorite ★
          </label>
        </div>
      </div>
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </Modal>
  )
}

// ── Provider / Status badge colors ───────────────────────────────────────────
const PROVIDER_COLORS = {
  suno:        'bg-[#1a0e2e] text-[#7c6af7] border-[#2a1a50]',
  'lyria-clip':'bg-[#001624] text-[#4a9eff] border-[#002840]',
  'lyria-pro': 'bg-[#001e12] text-[#34d399] border-[#003020]',
  import:      'bg-[#1e1e2e] text-[#9090a8] border-[#2a2a42]',
}
const STATUS_COLORS = {
  ready:   'bg-[#001e12] text-[#34d399] border-[#003020]',
  pending: 'bg-[#1e1a00] text-[#fbbf24] border-[#3a3000]',
  failed:  'bg-[#1e0a0a] text-[#f87171] border-[#3a1010]',
}

function ProviderBadge({ provider }) {
  return <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium border ${PROVIDER_COLORS[provider] || PROVIDER_COLORS.import}`}>{(provider || 'import').toUpperCase()}</span>
}
function StatusBadge({ status }) {
  return <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium border ${STATUS_COLORS[status] || STATUS_COLORS.pending}`}>{status}</span>
}

// ── Inline Audio Player ───────────────────────────────────────────────────────
function AudioPlayer({ track, onClose }) {
  const audioRef = useRef(null)
  const [playing, setPlaying] = useState(false)
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    setPlaying(false)
    setProgress(0)
    if (audioRef.current) {
      audioRef.current.load()
      audioRef.current.play().catch(() => {})
      setPlaying(true)
    }
  }, [track?.id])

  const togglePlay = () => {
    if (!audioRef.current) return
    if (playing) { audioRef.current.pause(); setPlaying(false) }
    else { audioRef.current.play(); setPlaying(true) }
  }

  const handleTimeUpdate = () => {
    if (audioRef.current) setProgress((audioRef.current.currentTime / (audioRef.current.duration || 1)) * 100)
  }

  if (!track) return null
  return (
    <div className="fixed bottom-0 left-[200px] right-0 z-40 bg-[#16161a] border-t border-[#2a2a32] px-6 py-3 flex items-center gap-4">
      <audio ref={audioRef} src={musicApi.streamUrl(track.id)} onTimeUpdate={handleTimeUpdate} onEnded={() => setPlaying(false)} />
      <button onClick={togglePlay} className="w-8 h-8 rounded-full bg-[#7c6af7] text-white flex items-center justify-center text-sm hover:bg-[#6a58e5] transition-colors">
        {playing ? '⏸' : '▶'}
      </button>
      <div className="flex-1">
        <div className="text-sm font-medium text-[#e8e8f0] truncate">{track.title}</div>
        <div className="h-1 bg-[#2a2a32] rounded-full mt-1 overflow-hidden">
          <div className="h-full bg-[#7c6af7] rounded-full transition-all" style={{ width: `${progress}%` }} />
        </div>
      </div>
      <span className="text-xs font-mono text-[#5a5a70]">{track.duration_s ? `${track.duration_s.toFixed(0)}s` : '—'}</span>
      <button onClick={onClose} className="text-[#9090a8] hover:text-[#f87171] transition-colors">✕</button>
    </div>
  )
}

// ── Generate Music Modal ──────────────────────────────────────────────────────
function GenerateModal({ niches, onClose, onGenerated, onPollTrack }) {
  const [idea,      setIdea]      = useState('')
  const [selNiches, setSelNiches] = useState([])
  const [selMoods,  setSelMoods]  = useState([])
  const [selGenres, setSelGenres] = useState([])
  const [provider,  setProvider]  = useState('suno')
  const [isVocal,   setIsVocal]   = useState(false)
  const [expanded,  setExpanded]  = useState('')
  const [expanding, setExpanding] = useState(false)
  const [generating,setGenerating]= useState(false)
  const [toast,     setToast]     = useState(null)
  const showToast = (msg, type='error') => { setToast({msg,type}); setTimeout(()=>setToast(null),3000) }

  const handleExpand = async () => {
    if (!idea.trim()) { showToast('Enter an idea first'); return }
    setExpanding(true)
    try {
      const res = await musicApi.generate({
        idea, niches: selNiches, moods: selMoods, genres: selGenres,
        provider, is_vocal: isVocal, expand_only: true,
      })
      setExpanded(res.expanded_prompt || idea)
    } catch (e) { showToast(e.message) }
    finally { setExpanding(false) }
  }

  const handleGenerate = async () => {
    if (!idea.trim() && !expanded.trim()) { showToast('Enter an idea or expand first'); return }
    setGenerating(true)
    try {
      const res = await musicApi.generate({
        idea: expanded || idea, niches: selNiches, moods: selMoods, genres: selGenres,
        provider, is_vocal: isVocal, expand_only: false,
      })
      onPollTrack(res.track_id, res.task_id)
      onGenerated()
      onClose()
    } catch (e) { showToast(e.message) }
    finally { setGenerating(false) }
  }

  return (
    <Modal open onClose={onClose} title="Generate Music" width="max-w-xl"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="default" loading={expanding} onClick={handleExpand}>✨ Expand with Gemini</Button>
          <Button variant="primary" loading={generating} onClick={handleGenerate}>Generate</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">General idea / description</label>
          <textarea
            value={expanded || idea}
            onChange={e => { expanded ? setExpanded(e.target.value) : setIdea(e.target.value) }}
            rows={3}
            placeholder="e.g. upbeat energetic workout music with punchy beats"
            className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] placeholder:text-[#5a5a70] focus:outline-none focus:border-[#7c6af7] resize-y"
          />
          {expanded && <p className="text-xs text-[#34d399]">✓ Expanded by Gemini — edit freely before generating</p>}
        </div>

        <MultiSelect label="Niches" options={niches.map(n => n.name)} value={selNiches} onChange={setSelNiches} />
        <MultiSelect label="Moods"  options={MOODS}  value={selMoods}  onChange={setSelMoods} />
        <MultiSelect label="Genres" options={GENRES} value={selGenres} onChange={setSelGenres} />

        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[#9090a8] font-medium">Provider</label>
            <select value={provider} onChange={e => setProvider(e.target.value)}
              className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7]">
              <option value="suno">Suno</option>
              <option value="lyria-clip">Lyria Clip (30s)</option>
              <option value="lyria-pro">Lyria Pro (full song)</option>
            </select>
          </div>
          <div className="flex flex-col justify-end">
            <label className="flex items-center gap-2 cursor-pointer text-sm text-[#9090a8] pb-1.5">
              <input type="checkbox" checked={isVocal} onChange={e => setIsVocal(e.target.checked)} className="accent-[#7c6af7]" />
              With vocals
            </label>
          </div>
        </div>
      </div>
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </Modal>
  )
}

// ── Import Music Modal ────────────────────────────────────────────────────────
function ImportModal({ niches, onClose, onImported }) {
  const [file,         setFile]         = useState(null)
  const [detectedDur,  setDetectedDur]  = useState(null)
  const [title,        setTitle]        = useState('')
  const [selNiches,    setSelNiches]    = useState([])
  const [selMoods,     setSelMoods]     = useState([])
  const [selGenres,    setSelGenres]    = useState([])
  const [isVocal,      setIsVocal]      = useState(false)
  const [volume,       setVolume]       = useState(0.15)
  const [qualityScore, setQualityScore] = useState(80)
  const [uploading,    setUploading]    = useState(false)
  const [toast,        setToast]        = useState(null)
  const showToast = (msg, type='error') => { setToast({msg,type}); setTimeout(()=>setToast(null),3000) }

  const handleFileChange = (e) => {
    const f = e.target.files?.[0]
    if (!f) return
    setFile(f)
    const baseName = f.name.replace(/\.[^.]+$/, '')
    setTitle(baseName)
    // Detect duration client-side
    const url = URL.createObjectURL(f)
    const audio = new Audio(url)
    audio.onloadedmetadata = () => { setDetectedDur(Math.round(audio.duration)); URL.revokeObjectURL(url) }
  }

  const handleImport = async () => {
    if (!file) { showToast('Choose a file first'); return }
    if (!title.trim()) { showToast('Title is required'); return }
    setUploading(true)
    try {
      await musicApi.upload(file, {
        title, niches: selNiches, moods: selMoods, genres: selGenres,
        is_vocal: isVocal, volume, quality_score: qualityScore,
      })
      onImported()
      onClose()
    } catch (e) { showToast(e.message) }
    finally { setUploading(false) }
  }

  return (
    <Modal open onClose={onClose} title="Import Music File" width="max-w-xl"
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" loading={uploading} onClick={handleImport}>Import</Button></>}
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Audio file (.mp3 / .wav / .m4a / .ogg)</label>
          <input type="file" accept=".mp3,.wav,.m4a,.ogg" onChange={handleFileChange}
            className="text-sm text-[#9090a8] file:mr-3 file:py-1 file:px-3 file:rounded-lg file:border file:border-[#2a2a32] file:bg-[#222228] file:text-[#e8e8f0] file:text-xs hover:file:bg-[#2a2a32]" />
          {detectedDur !== null && <p className="text-xs text-[#34d399]">Detected duration: {detectedDur}s</p>}
        </div>

        <Input label="Title" value={title} onChange={e => setTitle(e.target.value)} placeholder="Track title" />
        <MultiSelect label="Niches" options={niches.map(n => n.name)} value={selNiches} onChange={setSelNiches} />
        <MultiSelect label="Moods"  options={MOODS}  value={selMoods}  onChange={setSelMoods} />
        <MultiSelect label="Genres" options={GENRES} value={selGenres} onChange={setSelGenres} />

        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[#9090a8] font-medium">Volume ({(volume * 100).toFixed(0)}%)</label>
            <input type="range" min="0" max="1" step="0.01" value={volume}
              onChange={e => setVolume(parseFloat(e.target.value))} className="accent-[#7c6af7]" />
          </div>
          <Input label="Quality Score (0–100)" type="number" value={qualityScore}
            onChange={e => setQualityScore(parseInt(e.target.value) || 0)} />
        </div>

        <label className="flex items-center gap-2 cursor-pointer text-sm text-[#9090a8]">
          <input type="checkbox" checked={isVocal} onChange={e => setIsVocal(e.target.checked)} className="accent-[#7c6af7]" />
          With vocals
        </label>
      </div>
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </Modal>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function MusicPage() {
  const [filterNiche,  setFilterNiche]  = useState('')
  const [filterMood,   setFilterMood]   = useState('')
  const [filterGenre,  setFilterGenre]  = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [filterSearch, setFilterSearch] = useState('')
  const [editingTrack, setEditingTrack] = useState(null)
  const [playingTrack, setPlayingTrack] = useState(null)
  const [deletingId,   setDeletingId]   = useState(null)
  const [showGenerate, setShowGenerate] = useState(false)
  const [showImport,   setShowImport]   = useState(false)
  const [toast,        setToast]        = useState(null)
  const [pendingPolls, setPendingPolls] = useState({}) // trackId → celeryTaskId

  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000) }

  const { data: niches = [] } = useApi(() => nichesApi.list(), [])
  const { data: tracks = [], loading, refetch } = useApi(
    () => musicApi.list({ niche: filterNiche, mood: filterMood, genre: filterGenre, status: filterStatus, search: filterSearch }),
    [filterNiche, filterMood, filterGenre, filterStatus, filterSearch]
  )
  
  // Guard against null from useApi hook
  const nicheList = niches || []
  const trackList = tracks || []

  // Poll pending tracks every 10s
  useEffect(() => {
    const pending = trackList.filter(t => t.generation_status === 'pending' && pendingPolls[t.id])
    if (!pending.length) return
    const timer = setInterval(async () => {
      for (const t of pending) {
        try {
          const res = await musicApi.pollTask(pendingPolls[t.id])
          if (res.state === 'SUCCESS' || res.state === 'FAILURE') {
            refetch()
            setPendingPolls(p => { const n = { ...p }; delete n[t.id]; return n })
          }
        } catch { /* ignore */ }
      }
    }, 10000)
    return () => clearInterval(timer)
  }, [tracks, pendingPolls])

  const handleDelete = async (track) => {
    setDeletingId(track.id)
    try {
      await musicApi.delete(track.id)
      if (playingTrack?.id === track.id) setPlayingTrack(null)
      refetch()
      showToast(`Deleted "${track.title}"`)
    } catch (e) { showToast(e.message, 'error') }
    finally { setDeletingId(null) }
  }

  const handleFavoriteToggle = async (track) => {
    try {
      await musicApi.update(track.id, { is_favorite: !track.is_favorite })
      refetch()
    } catch (e) { showToast(e.message, 'error') }
  }

  // Stats
  const totalTracks  = trackList.length
  const sunoCount    = trackList.filter(t => t.provider === 'suno').length
  const lyriaCount   = trackList.filter(t => t.provider?.startsWith('lyria')).length
  const importCount  = trackList.filter(t => t.provider === 'import').length
  const favCount     = trackList.filter(t => t.is_favorite).length

  return (
    <div className="flex flex-col gap-5" style={{ paddingBottom: playingTrack ? 80 : 0 }}>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#e8e8f0]">Music</h1>
          <p className="text-sm text-[#9090a8] mt-0.5">Manage background music tracks for videos</p>
        </div>
        <div className="flex gap-2">
          <Button variant="default" onClick={() => setShowImport(true)}>↑ Import</Button>
          <Button variant="primary" onClick={() => setShowGenerate(true)}>+ Generate</Button>
        </div>
      </div>

      {/* Stats */}
      <div className="flex gap-3 flex-wrap">
        <StatBox label="Total" value={totalTracks} />
        <StatBox label="Suno" value={sunoCount} />
        <StatBox label="Lyria" value={lyriaCount} />
        <StatBox label="Imported" value={importCount} />
        <StatBox label="Favorites" value={favCount} />
      </div>

      {/* Filters */}
      <div className="flex gap-2 flex-wrap">
        <input value={filterSearch} onChange={e => setFilterSearch(e.target.value)} placeholder="Search title…"
          className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] placeholder:text-[#5a5a70] focus:outline-none focus:border-[#7c6af7] w-48" />
        <select value={filterNiche} onChange={e => setFilterNiche(e.target.value)}
          className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7]">
          <option value="">All niches</option>
          {nicheList.map(n => <option key={n.id} value={n.name}>{n.name}</option>)}
        </select>
        <select value={filterMood} onChange={e => setFilterMood(e.target.value)}
          className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7]">
          <option value="">All moods</option>
          {MOODS.map(m => <option key={m} value={m}>{m}</option>)}
        </select>
        <select value={filterGenre} onChange={e => setFilterGenre(e.target.value)}
          className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7]">
          <option value="">All genres</option>
          {GENRES.map(g => <option key={g} value={g}>{g}</option>)}
        </select>
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
          className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7]">
          <option value="">All status</option>
          <option value="ready">Ready</option>
          <option value="pending">Pending</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      {/* Library table */}
      <Card>
        {loading ? (
          <div className="flex justify-center py-10"><Spinner /></div>
        ) : trackList.length === 0 ? (
          <EmptyState icon="🎵" title="No music tracks yet" description="Generate new tracks via Suno or Lyria, or import your own files." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#2a2a32] text-left">
                  {['Title', 'Provider', 'Status', 'Duration', 'Tags', 'Score', '★', 'Uses', ''].map(h => (
                    <th key={h} className="pb-2 pr-4 text-xs font-semibold text-[#9090a8] uppercase tracking-wider whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {trackList.map(t => (
                  <tr key={t.id} className="border-b border-[#2a2a32] hover:bg-[#16161a] transition-colors">
                    <td className="py-2.5 pr-4">
                      <div className="font-medium text-[#e8e8f0] max-w-[180px] truncate">{t.title}</div>
                      <div className="text-xs text-[#5a5a70] font-mono">{t.is_vocal ? 'vocal' : 'instrumental'}</div>
                    </td>
                    <td className="py-2.5 pr-4"><ProviderBadge provider={t.provider} /></td>
                    <td className="py-2.5 pr-4"><StatusBadge status={t.generation_status} /></td>
                    <td className="py-2.5 pr-4 font-mono text-[#9090a8] text-xs whitespace-nowrap">
                      {t.duration_s ? `${t.duration_s.toFixed(0)}s` : '—'}
                    </td>
                    <td className="py-2.5 pr-4">
                      <div className="flex flex-wrap gap-1 max-w-[200px]">
                        {[...(t.niches || []), ...(t.genres || [])].slice(0, 4).map(tag => (
                          <span key={tag} className="text-[10px] bg-[#2a2a32] text-[#9090a8] rounded px-1.5 py-0.5">{tag}</span>
                        ))}
                      </div>
                    </td>
                    <td className="py-2.5 pr-4 font-mono text-[#9090a8] text-xs">{t.quality_score}</td>
                    <td className="py-2.5 pr-4">
                      <button onClick={() => handleFavoriteToggle(t)}
                        className={`text-lg transition-colors ${t.is_favorite ? 'text-[#fbbf24]' : 'text-[#2a2a32] hover:text-[#fbbf24]'}`}>★</button>
                    </td>
                    <td className="py-2.5 pr-4 font-mono text-[#9090a8] text-xs">{t.usage_count}</td>
                    <td className="py-2.5">
                      <div className="flex gap-1">
                        <Button variant="ghost" size="sm"
                          disabled={t.generation_status !== 'ready'}
                          onClick={() => setPlayingTrack(playingTrack?.id === t.id ? null : t)}>▶</Button>
                        <Button variant="ghost" size="sm" onClick={() => setEditingTrack(t)}>✎</Button>
                        <Button variant="danger" size="sm" loading={deletingId === t.id} onClick={() => handleDelete(t)}>✕</Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {editingTrack && (
        <EditModal track={editingTrack} niches={nicheList}
          onClose={() => setEditingTrack(null)} onSaved={refetch} />
      )}

      {showGenerate && (
        <GenerateModal
          niches={nicheList}
          onClose={() => setShowGenerate(false)}
          onGenerated={refetch}
          onPollTrack={(trackId, taskId) => setPendingPolls(p => ({ ...p, [trackId]: taskId }))}
        />
      )}

      {showImport && (
        <ImportModal
          niches={nicheList}
          onClose={() => setShowImport(false)}
          onImported={refetch}
        />
      )}

      <AudioPlayer track={playingTrack} onClose={() => setPlayingTrack(null)} />
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  )
}
