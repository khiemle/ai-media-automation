import { useEffect, useState } from 'react'
import { Button, Modal } from './index.jsx'
import { fetchApi } from '../api/client.js'
import PreviewPlayer from './PreviewPlayer.jsx'

// Music + SFX list endpoints return raw arrays (not {items: [...]} envelopes).
// Tolerate both shapes so this component keeps working if the API ever switches.
const unwrap = (r) => Array.isArray(r) ? r : (r?.items || [])

export default function MusicPlaylistEditor({ trackIds = [], onChange }) {
  const [tracks, setTracks] = useState([])
  const [picker, setPicker] = useState(false)
  const [library, setLibrary] = useState([])
  const [search, setSearch] = useState('')

  useEffect(() => {
    if (trackIds.length === 0) { setTracks([]); return }
    fetchApi(`/api/music?ids=${trackIds.join(',')}`)
      .then(r => {
        const items = unwrap(r)
        const byId = Object.fromEntries(items.map(t => [t.id, t]))
        // Preserve playlist order even though the server orders by created_at desc
        setTracks(trackIds.map(id => byId[id]).filter(Boolean))
      })
      .catch(() => setTracks([]))
  }, [trackIds.join(',')])

  useEffect(() => {
    if (!picker) return
    fetchApi('/api/music?per_page=200&generation_status=ready')
      .then(r => setLibrary(unwrap(r)))
      .catch(() => setLibrary([]))
  }, [picker])

  const move = (i, dir) => {
    const next = [...trackIds]
    const j = i + dir
    if (j < 0 || j >= next.length) return
    ;[next[i], next[j]] = [next[j], next[i]]
    onChange(next)
  }
  const remove = (i) => onChange(trackIds.filter((_, k) => k !== i))
  const add = (id) => { onChange([...trackIds, id]); setPicker(false) }

  const filtered = search
    ? library.filter(t => (t.title || '').toLowerCase().includes(search.toLowerCase()))
    : library

  return (
    <div className="space-y-2">
      {tracks.length === 0 && <p className="text-xs text-[#5a5a70]">No tracks selected.</p>}
      {tracks.map((t, i) => (
        <div key={`${t.id}-${i}`} className="flex items-center gap-2 px-2 py-1.5 bg-[#1c1c22] border border-[#2a2a32] rounded">
          <span className="text-xs font-mono text-[#5a5a70] w-6">{i + 1}</span>
          <PreviewPlayer src={`/api/music/${t.id}/stream`} kind="audio" />
          <span className="text-sm text-[#e8e8f0] flex-1 truncate">{t.title}</span>
          <span className="text-xs font-mono text-[#9090a8]">{Math.round(t.duration_s || 0)}s</span>
          <button
            type="button"
            onClick={() => move(i, -1)}
            disabled={i === 0}
            className="text-xs text-[#9090a8] disabled:opacity-30 px-1"
            aria-label="Move up"
          >↑</button>
          <button
            type="button"
            onClick={() => move(i, +1)}
            disabled={i === tracks.length - 1}
            className="text-xs text-[#9090a8] disabled:opacity-30 px-1"
            aria-label="Move down"
          >↓</button>
          <button
            type="button"
            onClick={() => remove(i)}
            className="text-xs text-[#f87171] px-1"
            aria-label="Remove track"
          >×</button>
        </div>
      ))}
      <Button variant="default" onClick={() => setPicker(true)}>+ Add Track</Button>
      <Modal open={picker} onClose={() => setPicker(false)} title="Select Music Track">
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search tracks..."
          className="w-full mb-3 bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] placeholder:text-[#5a5a70] focus:outline-none focus:border-[#7c6af7] transition-colors"
        />
        <div className="max-h-96 overflow-y-auto space-y-1">
          {filtered.length === 0 && (
            <p className="text-xs text-[#5a5a70] px-2 py-3">No ready music tracks.</p>
          )}
          {filtered.map(t => {
            const already = trackIds.includes(t.id)
            return (
              <div
                key={t.id}
                className="flex items-center gap-2 px-3 py-2 hover:bg-[#1c1c22] rounded"
              >
                <PreviewPlayer src={`/api/music/${t.id}/stream`} kind="audio" />
                <button
                  type="button"
                  onClick={() => add(t.id)}
                  className="flex-1 text-left text-sm text-[#e8e8f0] flex items-center justify-between gap-2"
                >
                  <span className="truncate">
                    {t.title}{' '}
                    <span className="text-[#5a5a70] text-xs">({Math.round(t.duration_s || 0)}s)</span>
                  </span>
                  {already && <span className="text-[10px] text-[#7c6af7]">in playlist</span>}
                </button>
              </div>
            )
          })}
        </div>
      </Modal>
    </div>
  )
}
