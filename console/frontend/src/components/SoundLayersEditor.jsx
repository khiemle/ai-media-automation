import { useEffect, useMemo, useState } from 'react'
import { Button, Modal } from './index.jsx'
import { fetchApi } from '../api/client.js'
import PreviewPlayer from './PreviewPlayer.jsx'
import SfxPickerModal from './SfxPickerModal.jsx'

const unwrap = (r) => Array.isArray(r) ? r : (r?.items || [])

function PoolLayerCard({ label, layer, sfxList, onChange }) {
  const [picker, setPicker] = useState(false)
  const [library, setLibrary] = useState([])
  const [search, setSearch] = useState('')

  const poolIds = layer.pool || []

  const sfxById = useMemo(
    () => Object.fromEntries(sfxList.map(s => [s.id, s])),
    [sfxList]
  )

  useEffect(() => {
    if (!picker) return
    fetchApi('/api/sfx?per_page=500')
      .then(r => setLibrary(unwrap(r)))
      .catch(() => setLibrary([]))
  }, [picker])

  const filtered = search
    ? library.filter(s =>
        (s.title || '').toLowerCase().includes(search.toLowerCase()) ||
        (s.sound_type || '').toLowerCase().includes(search.toLowerCase())
      )
    : library

  const togglePick = (id) => {
    const newPool = poolIds.includes(id) ? poolIds.filter(p => p !== id) : [...poolIds, id]
    onChange({ ...layer, pool: newPool })
  }

  const remove = (id) => onChange({ ...layer, pool: poolIds.filter(p => p !== id) })

  return (
    <div className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3 flex flex-col gap-2">
      <span className="text-xs font-medium text-[#9090a8]">{label}</span>

      <div>
        <label className="text-xs text-[#5a5a70] mb-1 block">Pool</label>
        <div className="flex flex-col gap-1.5">
          {poolIds.length === 0 && (
            <p className="text-xs text-[#5a5a70]">No files — layer disabled.</p>
          )}
          {poolIds.map(id => {
            const s = sfxById[id]
            return (
              <div key={id} className="flex items-center gap-2 px-2 py-1.5 bg-[#1c1c22] border border-[#2a2a32] rounded">
                <PreviewPlayer src={`/api/sfx/${id}/stream`} kind="audio" />
                <span className="text-sm text-[#e8e8f0] flex-1 truncate">{s?.title || `SFX #${id}`}</span>
                <button
                  type="button"
                  onClick={() => remove(id)}
                  className="text-[#f87171] text-xs px-1"
                  aria-label={`Remove ${s?.title || 'SFX'}`}
                >×</button>
              </div>
            )
          })}
          <div>
            <Button variant="default" onClick={() => setPicker(true)}>+ Pick SFX</Button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-xs text-[#5a5a70] mb-1 block">Min interval (s)</label>
          <input
            type="number" min="1" step="1"
            value={layer.interval_min_s ?? ''}
            onChange={e => onChange({ ...layer, interval_min_s: parseFloat(e.target.value) || 0 })}
            className="w-full bg-[#16161a] border border-[#2a2a32] rounded px-2 py-1 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7]"
          />
        </div>
        <div>
          <label className="text-xs text-[#5a5a70] mb-1 block">Max interval (s)</label>
          <input
            type="number" min="1" step="1"
            value={layer.interval_max_s ?? ''}
            onChange={e => onChange({ ...layer, interval_max_s: parseFloat(e.target.value) || 0 })}
            className="w-full bg-[#16161a] border border-[#2a2a32] rounded px-2 py-1 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7]"
          />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <span className="text-xs text-[#5a5a70] w-16 shrink-0">Volume</span>
        <input
          type="range" min={0} max={1} step={0.05}
          value={layer.volume ?? 0.5}
          onChange={e => onChange({ ...layer, volume: parseFloat(e.target.value) })}
          className="flex-1 accent-[#7c6af7]"
        />
        <span className="text-xs text-[#9090a8] font-mono w-8 text-right">
          {Math.round((layer.volume ?? 0.5) * 100)}%
        </span>
      </div>

      <Modal open={picker} onClose={() => { setPicker(false); setSearch('') }} title={`Pick SFX — ${label}`}>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search by title or sound type…"
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
                <button type="button" onClick={() => togglePick(s.id)} className="flex-1 text-left min-w-0">
                  <div className="text-sm text-[#e8e8f0] truncate">{s.title}</div>
                  {s.sound_type && <div className="text-[10px] text-[#5a5a70]">{s.sound_type}</div>}
                </button>
              </div>
            )
          })}
        </div>
        <div className="text-xs text-[#9090a8] mt-2">
          {poolIds.length} selected — click any to toggle
        </div>
      </Modal>
    </div>
  )
}

export default function SoundLayersEditor({ soundLayers, sfxList = [], onChange }) {
  const [bgPickerOpen, setBgPickerOpen] = useState(false)

  const bg = soundLayers.background || { asset_id: '', volume: 0.4 }
  const pickedBgSfx = sfxList.find(s => String(s.id) === String(bg.asset_id))

  const setLayer = (key, val) => onChange({ ...soundLayers, [key]: val })

  return (
    <div className="flex flex-col gap-3">
      {/* Background — single loopable file */}
      <div className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3 flex flex-col gap-2">
        <span className="text-xs font-medium text-[#9090a8]">Background (loops for full duration)</span>
        {bg.asset_id ? (
          <div className="flex items-center gap-2 px-2 py-1.5 bg-[#1c1c22] border border-[#2a2a32] rounded">
            <PreviewPlayer src={`/api/sfx/${bg.asset_id}/stream`} kind="audio" />
            <button
              type="button"
              onClick={() => setBgPickerOpen(true)}
              className="flex-1 text-left text-sm text-[#e8e8f0] truncate"
            >
              {pickedBgSfx?.title || `SFX #${bg.asset_id}`}
            </button>
            <button
              type="button"
              onClick={() => setLayer('background', { ...bg, asset_id: '' })}
              className="text-[#f87171] text-xs px-1"
              aria-label="Clear background"
            >×</button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setBgPickerOpen(true)}
            className="px-3 py-1.5 rounded border border-dashed border-[#2a2a32] text-xs text-[#9090a8] hover:text-[#e8e8f0] hover:border-[#7c6af7] transition-colors"
          >
            + Pick loopable SFX
          </button>
        )}
        <div className="flex items-center gap-3">
          <span className="text-xs text-[#5a5a70] w-16 shrink-0">Volume</span>
          <input
            type="range" min={0} max={1} step={0.05}
            value={bg.volume ?? 0.4}
            onChange={e => setLayer('background', { ...bg, volume: parseFloat(e.target.value) })}
            className="flex-1 accent-[#7c6af7]"
          />
          <span className="text-xs text-[#9090a8] font-mono w-8 text-right">
            {Math.round((bg.volume ?? 0.4) * 100)}%
          </span>
        </div>
        <SfxPickerModal
          open={bgPickerOpen}
          onClose={() => setBgPickerOpen(false)}
          selectedId={bg.asset_id ? parseInt(bg.asset_id) : null}
          onSelect={s => setLayer('background', { ...bg, asset_id: String(s.id) })}
        />
      </div>

      {/* Midground */}
      <PoolLayerCard
        label="Midground — random every interval_min–max s"
        layer={soundLayers.midground || { pool: [], volume: 0.5, interval_min_s: 10, interval_max_s: 25 }}
        sfxList={sfxList}
        onChange={val => setLayer('midground', val)}
      />

      {/* Foreground */}
      <PoolLayerCard
        label="Foreground — random every interval_min–max s"
        layer={soundLayers.foreground || { pool: [], volume: 0.7, interval_min_s: 45, interval_max_s: 60 }}
        sfxList={sfxList}
        onChange={val => setLayer('foreground', val)}
      />

      {/* Random SFX */}
      <PoolLayerCard
        label="Random SFX — random every interval_min–max s"
        layer={soundLayers.random_sfx || { pool: [], volume: 0.6, interval_min_s: 60, interval_max_s: 100 }}
        sfxList={sfxList}
        onChange={val => setLayer('random_sfx', val)}
      />
    </div>
  )
}
