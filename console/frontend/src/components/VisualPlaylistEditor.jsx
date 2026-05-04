import { useEffect, useState } from 'react'
import { Button } from './index.jsx'
import { fetchApi } from '../api/client.js'
import VisualPickerModal from './VisualPickerModal.jsx'

/**
 * VisualPlaylistEditor — ordered list of visual assets with per-clip durations.
 *
 * Props:
 *   assetIds      — list of integer asset ids (order matters)
 *   durations     — list of floats parallel to assetIds (0 = native length for videos in concat_loop)
 *   loopMode      — 'concat_loop' | 'per_clip'
 *   onChange({ assetIds, durations }) — emitted on every mutation
 */
export default function VisualPlaylistEditor({ assetIds = [], durations = [], loopMode, onChange }) {
  const [details, setDetails] = useState([])
  const [picker, setPicker] = useState(false)

  useEffect(() => {
    if (assetIds.length === 0) { setDetails([]); return }
    Promise.all(assetIds.map(id =>
      fetchApi(`/api/production/assets/${id}`).catch(() => null)
    )).then(rows => setDetails(rows.filter(Boolean)))
  }, [assetIds.join(',')])

  const detailsById = Object.fromEntries(details.map(a => [a.id, a]))

  const move = (i, dir) => {
    const j = i + dir
    if (j < 0 || j >= assetIds.length) return
    const ids = [...assetIds]
    const durs = [...durations, ...Array(Math.max(0, assetIds.length - durations.length)).fill(0)]
    ;[ids[i], ids[j]] = [ids[j], ids[i]]
    ;[durs[i], durs[j]] = [durs[j], durs[i]]
    onChange({ assetIds: ids, durations: durs })
  }

  const remove = (i) => {
    onChange({
      assetIds: assetIds.filter((_, k) => k !== i),
      durations: durations.filter((_, k) => k !== i),
    })
  }

  const setDuration = (i, value) => {
    const durs = [...durations, ...Array(Math.max(0, assetIds.length - durations.length)).fill(0)]
    durs[i] = value === '' ? 0 : parseFloat(value)
    onChange({ assetIds, durations: durs })
  }

  const add = (asset) => {
    onChange({
      assetIds: [...assetIds, asset.id],
      durations: [...durations, asset.asset_type === 'still_image' ? 3.0 : 0.0],
    })
  }

  return (
    <div className="space-y-2">
      {assetIds.length === 0 && (
        <p className="text-xs text-[#5a5a70]">No visuals selected.</p>
      )}
      {assetIds.map((id, i) => {
        const a = detailsById[id]
        const isImage = a?.asset_type === 'still_image'
        const dur = durations[i] ?? 0
        const placeholder = (loopMode === 'concat_loop' && !isImage)
          ? 'native'
          : '3.0'
        return (
          <div key={`${id}-${i}`} className="flex items-center gap-2 px-2 py-1.5 bg-[#1c1c22] border border-[#2a2a32] rounded">
            <span className="text-xs font-mono text-[#5a5a70] w-6">{i + 1}</span>
            <div className="w-16 h-9 bg-[#0d0d0f] rounded overflow-hidden flex items-center justify-center flex-shrink-0">
              {a ? (
                isImage
                  ? <img src={`/api/production/assets/${id}/stream`} alt="" className="w-full h-full object-cover" />
                  : <video src={`/api/production/assets/${id}/stream`} muted preload="metadata" className="w-full h-full object-cover" />
              ) : (
                <span className="text-[9px] text-[#5a5a70]">…</span>
              )}
            </div>
            <span className="text-sm text-[#e8e8f0] flex-1 truncate">
              {a?.description || `Asset #${id}`}
              {isImage && <span className="text-[10px] text-[#5a5a70] ml-1">[still]</span>}
            </span>
            <input
              type="number"
              min="0"
              step="0.5"
              value={dur || ''}
              onChange={e => setDuration(i, e.target.value)}
              placeholder={placeholder}
              className="w-16 bg-[#0d0d0f] border border-[#2a2a32] rounded px-1.5 py-1 text-xs text-[#e8e8f0] text-right"
              aria-label={`Duration for item ${i + 1} (seconds)`}
            />
            <span className="text-[10px] text-[#5a5a70]">s</span>
            <button type="button" onClick={() => move(i, -1)} disabled={i === 0}
              className="text-xs text-[#9090a8] disabled:opacity-30 px-1" aria-label="Move up">↑</button>
            <button type="button" onClick={() => move(i, +1)} disabled={i === assetIds.length - 1}
              className="text-xs text-[#9090a8] disabled:opacity-30 px-1" aria-label="Move down">↓</button>
            <button type="button" onClick={() => remove(i)}
              className="text-xs text-[#f87171] px-1" aria-label="Remove visual">×</button>
          </div>
        )
      })}
      <Button variant="default" onClick={() => setPicker(true)}>+ Add Visual</Button>
      <VisualPickerModal open={picker} onClose={() => setPicker(false)} onSelect={add} />
    </div>
  )
}
