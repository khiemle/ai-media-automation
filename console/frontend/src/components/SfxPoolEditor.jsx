import { useEffect, useMemo, useState } from 'react'
import { Button, Modal } from './index.jsx'
import { fetchApi } from '../api/client.js'
import PreviewPlayer from './PreviewPlayer.jsx'

// Music + SFX list endpoints return raw arrays (not {items: [...]} envelopes).
// Tolerate both shapes so this component keeps working if the API ever switches.
const unwrap = (r) => Array.isArray(r) ? r : (r?.items || [])

/**
 * SfxPoolEditor
 * pool: list of `{asset_id, volume}` objects (the new ASMR sfx_pool JSONB shape).
 * onChange({ pool, densitySeconds }): emits the updated pool + density.
 */
export default function SfxPoolEditor({ pool = [], densitySeconds, onChange }) {
  const [picker, setPicker] = useState(false)
  const [library, setLibrary] = useState([])
  const [poolDetails, setPoolDetails] = useState([])
  const [search, setSearch] = useState('')

  const poolIds = useMemo(() => pool.map(p => p.asset_id), [pool])
  const idsKey = poolIds.join(',')

  useEffect(() => {
    if (poolIds.length === 0) { setPoolDetails([]); return }
    fetchApi(`/api/sfx?ids=${idsKey}`)
      .then(r => setPoolDetails(unwrap(r)))
      .catch(() => setPoolDetails([]))
  }, [idsKey])

  useEffect(() => {
    if (!picker) return
    fetchApi('/api/sfx?per_page=500')
      .then(r => setLibrary(unwrap(r)))
      .catch(() => setLibrary([]))
  }, [picker])

  const togglePick = (id) => {
    if (poolIds.includes(id)) {
      onChange({
        pool: pool.filter(p => p.asset_id !== id),
        densitySeconds,
      })
    } else {
      onChange({
        pool: [...pool, { asset_id: id, volume: 1.0 }],
        densitySeconds,
      })
    }
  }
  const remove = (id) => onChange({
    pool: pool.filter(p => p.asset_id !== id),
    densitySeconds,
  })
  const setVolume = (id, vol) => onChange({
    pool: pool.map(p => p.asset_id === id ? { ...p, volume: vol } : p),
    densitySeconds,
  })

  const detailsById = useMemo(
    () => Object.fromEntries(poolDetails.map(s => [s.id, s])),
    [poolDetails]
  )

  const filtered = search
    ? library.filter(s =>
        (s.title || '').toLowerCase().includes(search.toLowerCase()) ||
        (s.sound_type || '').toLowerCase().includes(search.toLowerCase())
      )
    : library

  return (
    <div className="space-y-3">
      <div>
        <label className="text-xs text-[#9090a8] mb-1 block">SFX Pool</label>
        <div className="flex flex-col gap-1.5">
          {pool.length === 0 && (
            <p className="text-xs text-[#5a5a70]">No SFX selected.</p>
          )}
          {pool.map(({ asset_id, volume }) => {
            const s = detailsById[asset_id]
            return (
              <div
                key={asset_id}
                className="flex items-center gap-2 px-2 py-1.5 bg-[#1c1c22] border border-[#2a2a32] rounded"
              >
                <PreviewPlayer src={`/api/sfx/${asset_id}/stream`} kind="audio" />
                <span className="text-sm text-[#e8e8f0] flex-1 truncate">
                  {s?.title || `SFX #${asset_id}`}
                </span>
                <input
                  type="range"
                  min={0} max={1} step={0.05}
                  value={volume ?? 1.0}
                  onChange={e => setVolume(asset_id, parseFloat(e.target.value))}
                  className="w-24 accent-[#7c6af7]"
                  aria-label={`Volume for ${s?.title || `SFX ${asset_id}`}`}
                />
                <span className="text-xs font-mono text-[#9090a8] w-10 text-right">
                  {Math.round((volume ?? 1.0) * 100)}%
                </span>
                <button
                  type="button"
                  onClick={() => remove(asset_id)}
                  className="text-[#f87171] text-xs px-1"
                  aria-label={`Remove ${s?.title || `SFX ${asset_id}`}`}
                >×</button>
              </div>
            )
          })}
          <div>
            <Button variant="default" onClick={() => setPicker(true)}>+ Pick SFX</Button>
          </div>
        </div>
      </div>
      <div>
        <label className="text-xs text-[#9090a8] mb-1 block">
          Density: one SFX every <span className="font-mono text-[#fbbf24]">{densitySeconds || '—'}s</span> (±50% jitter)
        </label>
        <input
          type="range" min="5" max="300" step="5"
          value={densitySeconds || 60}
          onChange={e => onChange({ pool, densitySeconds: parseInt(e.target.value, 10) })}
          className="w-full accent-[#7c6af7]"
          disabled={pool.length === 0}
        />
      </div>
      <Modal open={picker} onClose={() => setPicker(false)} title="Pick SFX">
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search by title or sound type..."
          className="w-full mb-3 bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] placeholder:text-[#5a5a70] focus:outline-none focus:border-[#7c6af7] transition-colors"
        />
        <div className="grid grid-cols-2 gap-2 max-h-96 overflow-y-auto">
          {filtered.length === 0 && (
            <p className="col-span-2 text-xs text-[#5a5a70] px-2 py-3">No SFX assets.</p>
          )}
          {filtered.map(s => {
            const active = poolIds.includes(s.id)
            return (
              <div
                key={s.id}
                className={`flex items-stretch gap-2 px-3 py-2 rounded border ${
                  active ? 'border-[#7c6af7] bg-[#7c6af7]/10' : 'border-[#2a2a32] hover:bg-[#1c1c22]'
                }`}
              >
                <PreviewPlayer src={`/api/sfx/${s.id}/stream`} kind="audio" />
                <button
                  type="button"
                  onClick={() => togglePick(s.id)}
                  className="flex-1 text-left min-w-0"
                >
                  <div className="text-sm text-[#e8e8f0] truncate">{s.title}</div>
                  {s.sound_type && <div className="text-[10px] text-[#5a5a70]">{s.sound_type}</div>}
                </button>
              </div>
            )
          })}
        </div>
        <div className="text-xs text-[#9090a8] mt-2">
          {pool.length} selected — click any to toggle
        </div>
      </Modal>
    </div>
  )
}
