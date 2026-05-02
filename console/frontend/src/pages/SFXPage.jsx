import { useState, useRef, useEffect } from 'react'
import { sfxApi, autofillApi } from '../api/client.js'
import { Card, Button, Input, Select, Modal, EmptyState, Toast } from '../components/index.jsx'

const SOUND_TYPE_SUGGESTIONS = [
  { group: 'RAIN', types: ['rain_heavy', 'rain_light', 'rain_window', 'rain_forest', 'rain_tent'] },
  { group: 'WATER', types: ['ocean_waves', 'stream_river', 'waterfall', 'fountain', 'lake'] },
  { group: 'WEATHER', types: ['thunder', 'wind_gentle', 'wind_strong', 'blizzard', 'hail'] },
  { group: 'FIRE', types: ['fireplace', 'campfire', 'crackling_embers'] },
  { group: 'NATURE', types: ['birds', 'crickets', 'forest_ambience', 'leaves_rustling', 'frogs'] },
  { group: 'URBAN', types: ['cafe_chatter', 'coffee_machine', 'pub_tavern', 'city_traffic', 'train', 'keyboard_typing', 'pages_turning', 'restaurant'] },
  { group: 'NOISE', types: ['pink_noise', 'white_noise', 'brown_noise'] },
  { group: 'SPECIAL', types: ['space_hum', 'magical_ambient', 'underwater', 'crowd_distant'] },
]

const ALL_SUGGESTIONS = SOUND_TYPE_SUGGESTIONS.flatMap(g => g.types)

const SOURCE_COLOR = { import: '#9090a8', freesound: '#34d399' }

function ImportModal({ onClose, onImported }) {
  const [file, setFile] = useState(null)
  const [title, setTitle] = useState('')
  const [soundType, setSoundType] = useState('')
  const [source, setSource] = useState('import')
  const [loading, setLoading] = useState(false)
  const [autofilling, setAutofilling] = useState(false)
  const [toast, setToast] = useState(null)

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  const handleAutofill = async () => {
    if (!file) return
    setAutofilling(true)
    try {
      const metadata = {
        filename: file.name,
        file_size_bytes: file.size,
        mime_type: file.type,
        duration_s: null,
      }
      const form_values = { title, sound_type: soundType }
      const data = await autofillApi.suggest('sfx', metadata, form_values)
      if (data.title      != null) setTitle(data.title)
      if (data.sound_type != null) setSoundType(data.sound_type)
    } catch (e) {
      const msg = e.status === 429
        ? 'AI quota reached — try again later'
        : 'AI suggestion failed — fill in manually'
      showToast(msg)
    } finally {
      setAutofilling(false)
    }
  }

  const handleSubmit = async () => {
    if (!file || !title || !soundType) {
      showToast('Title, sound type, and file are required', 'error')
      return
    }
    setLoading(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('title', title)
      fd.append('sound_type', soundType)
      fd.append('source', source)
      await sfxApi.import(fd)
      onImported()
      onClose()
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Import SFX"
      width="max-w-lg"
      footer={
        <div className="flex items-center gap-2 w-full">
          <Button variant="ghost" disabled={!file || autofilling} loading={autofilling} onClick={handleAutofill}>✨ AI</Button>
          <div className="flex-1" />
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={loading} onClick={handleSubmit}>Import</Button>
        </div>
      }
    >
      {toast && <Toast message={toast.msg} type={toast.type} />}
      <div className="flex flex-col gap-4">
        <Input
          label="Title"
          value={title}
          onChange={e => setTitle(e.target.value)}
          placeholder="e.g. Heavy Rain Stereo"
        />
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Sound Type</label>
          <input
            list="sound-type-list"
            value={soundType}
            onChange={e => setSoundType(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-[#16161a] border border-[#2a2a32] text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7]"
            placeholder="rain_heavy, birds, pink_noise..."
          />
          <datalist id="sound-type-list">
            {ALL_SUGGESTIONS.map(t => <option key={t} value={t} />)}
          </datalist>
        </div>
        <Select label="Source" value={source} onChange={e => setSource(e.target.value)}>
          <option value="import">Manual Import</option>
          <option value="freesound">Freesound.org</option>
        </Select>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">File (WAV / MP3)</label>
          <input
            type="file"
            accept=".wav,.mp3,.m4a,.ogg"
            onChange={e => setFile(e.target.files?.[0] || null)}
            className="text-sm text-[#9090a8] file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:bg-[#2a2a32] file:text-[#e8e8f0] file:text-xs cursor-pointer"
          />
        </div>
      </div>
    </Modal>
  )
}

export default function SFXPage() {
  const [sfxList, setSfxList] = useState([])
  const [soundTypes, setSoundTypes] = useState([])
  const [loading, setLoading] = useState(true)
  const [filterType, setFilterType] = useState('')
  const [search, setSearch] = useState('')
  const [showImport, setShowImport] = useState(false)
  const [playing, setPlaying] = useState(null)
  const [errorToast, setErrorToast] = useState(null)
  const audioRef = useRef(null)

  const showError = (msg) => {
    setErrorToast(msg)
    setTimeout(() => setErrorToast(null), 4000)
  }

  const load = async (signal = { cancelled: false }) => {
    setLoading(true)
    try {
      const [list, types] = await Promise.all([
        sfxApi.list({ sound_type: filterType || undefined, search: search || undefined }),
        sfxApi.listSoundTypes(),
      ])
      if (!signal.cancelled) {
        setSfxList(list)
        setSoundTypes(types)
      }
    } catch (e) {
      console.error('Failed to load SFX:', e)
      if (!signal.cancelled) {
        setSfxList([])
        setSoundTypes([])
      }
    } finally {
      if (!signal.cancelled) setLoading(false)
    }
  }

  useEffect(() => {
    const signal = { cancelled: false }
    load(signal)
    return () => { signal.cancelled = true }
  }, [filterType, search])

  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current = null
      }
    }
  }, [])

  const handlePlay = (sfx) => {
    if (playing === sfx.id) {
      audioRef.current?.pause()
      setPlaying(null)
    } else {
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current.onended = null
        audioRef.current.onerror = null
        audioRef.current.oncanplay = null
        audioRef.current.src = ''  // Clear source to free memory
      }
      
      const audio = new Audio(sfxApi.streamUrl(sfx.id))
      audio.crossOrigin = 'anonymous'  // Allow CORS requests
      audioRef.current = audio
      
      let errorShown = false
      let playAttempted = false
      
      // Wait for audio to be ready before playing
      const handleCanPlay = () => {
        if (!errorShown && !playAttempted && audioRef.current === audio) {
          playAttempted = true
          audio.play().catch((err) => {
            if (!errorShown && err?.name !== 'AbortError') {
              errorShown = true
              setPlaying(null)
              showError(`Could not play audio for "${sfx.title}".`)
            }
          })
        }
      }
      
      audio.onerror = () => {
        if (!errorShown) {
          errorShown = true
          setPlaying(null)
          showError(`Could not load audio for "${sfx.title}". Check that the file exists on disk.`)
        }
      }
      
      audio.onended = () => setPlaying(null)
      audio.oncanplay = handleCanPlay
      
      setPlaying(sfx.id)
      
      // Also try to play immediately in case oncanplay fires before we set the handler
      audio.play().catch((err) => {
        if (!errorShown && err?.name !== 'AbortError' && !playAttempted) {
          playAttempted = true
          // Wait a bit and try again
          setTimeout(() => {
            audio.play().catch((e) => {
              if (!errorShown && e?.name !== 'AbortError') {
                errorShown = true
                setPlaying(null)
                showError(`Could not play audio for "${sfx.title}".`)
              }
            })
          }, 100)
        }
      })
    }
  }

  const handleDelete = async (sfx) => {
    if (!confirm(`Delete "${sfx.title}"?`)) return
    try {
      await sfxApi.delete(sfx.id)
      load()
    } catch (e) {
      alert(`Failed to delete: ${e.message}`)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {errorToast && <Toast message={errorToast} type="error" onClose={() => setErrorToast(null)} />}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#e8e8f0]">SFX Library</h1>
          <p className="text-sm text-[#9090a8] mt-0.5">{sfxList.length} assets</p>
        </div>
        <Button variant="primary" onClick={() => setShowImport(true)}>+ Import SFX</Button>
      </div>

      <div className="flex gap-3">
        <Input
          placeholder="Search..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="max-w-xs"
        />
        <Select value={filterType} onChange={e => setFilterType(e.target.value)} className="max-w-[180px]">
          <option value="">All types</option>
          {soundTypes.map(t => <option key={t} value={t}>{t}</option>)}
        </Select>
      </div>

      {loading ? (
        <div className="text-center text-[#9090a8] py-12">Loading...</div>
      ) : sfxList.length === 0 ? (
        <EmptyState title="No SFX assets" description="Import your first SFX file to get started." />
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {sfxList.map(sfx => (
            <div
              key={sfx.id}
              className="relative bg-[#1c1c22] border border-[#2a2a32] rounded-xl p-3 flex flex-col gap-2 group"
            >
              {/* Delete — visible on hover */}
              <button
                onClick={() => handleDelete(sfx)}
                className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity text-[#5a5a70] hover:text-[#f87171] text-xs leading-none"
                title="Delete"
              >
                ✕
              </button>

              {/* Top row: play button + sound type badge */}
              <div className="flex items-center justify-between gap-2">
                <button
                  onClick={() => handlePlay(sfx)}
                  className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 text-xs transition-colors ${
                    playing === sfx.id
                      ? 'bg-[#f87171] text-white'
                      : 'bg-[#2a2a32] text-[#9090a8] hover:text-[#e8e8f0]'
                  }`}
                >
                  {playing === sfx.id ? '■' : '▶'}
                </button>
                <span className="text-[9px] font-mono text-[#5a5a70] truncate max-w-[80px] text-right">
                  {sfx.sound_type || '—'}
                </span>
              </div>

              {/* Title */}
              <div
                className="text-xs font-medium text-[#e8e8f0] leading-snug"
                style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}
              >
                {sfx.title}
              </div>

              {/* Duration bar + label */}
              <div className="flex items-center gap-2 mt-auto">
                {sfx.duration_s ? (
                  <>
                    <div className="flex-1 h-0.5 rounded-full bg-[#2a2a32]">
                      <div
                        className="h-0.5 rounded-full bg-[#7c6af7]"
                        style={{ width: `${Math.min(100, (sfx.duration_s / 60) * 100)}%` }}
                      />
                    </div>
                    <span className="text-[9px] font-mono text-[#5a5a70] flex-shrink-0">
                      {sfx.duration_s.toFixed(0)}s
                    </span>
                  </>
                ) : (
                  <span className="text-[9px] font-mono text-[#5a5a70]">—</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {showImport && <ImportModal onClose={() => setShowImport(false)} onImported={load} />}
    </div>
  )
}
