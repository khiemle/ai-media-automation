import { useEffect, useMemo, useState } from 'react'
import { Modal, Button, Input, Select } from './index.jsx'
import { fetchApi } from '../api/client.js'

const unwrap = (r) => Array.isArray(r) ? r : (r?.items || [])

const SOURCES = ['', 'midjourney', 'runway', 'veo', 'manual', 'pexels', 'stock']

/**
 * VisualPickerModal — single-select visual asset picker with thumbnail grid + preview.
 *
 * Props:
 *   open           — boolean
 *   onClose()      — dismiss without choosing
 *   onSelect(asset)— called with the chosen asset { id, file_path, asset_type, source, ... }
 */
export default function VisualPickerModal({ open, onClose, onSelect }) {
  const [assets, setAssets] = useState([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [source, setSource] = useState('')

  useEffect(() => {
    if (!open) return
    setLoading(true)
    const params = new URLSearchParams({ per_page: '200' })
    if (source) params.set('source', source)
    fetchApi(`/api/production/assets?${params}`)
      .then(r => setAssets(unwrap(r)))
      .catch(() => setAssets([]))
      .finally(() => setLoading(false))
  }, [open, source])

  const filtered = useMemo(() => {
    if (!search) return assets
    const q = search.toLowerCase()
    return assets.filter(a =>
      (a.description || '').toLowerCase().includes(q) ||
      (a.keywords || []).some(k => (k || '').toLowerCase().includes(q))
    )
  }, [assets, search])

  return (
    <Modal open={open} onClose={onClose} title="Pick Visual" width="max-w-4xl">
      <div className="flex gap-2 mb-3">
        <Input
          placeholder="Search keywords or description…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="flex-1"
        />
        <Select value={source} onChange={e => setSource(e.target.value)} className="w-40">
          {SOURCES.map(s => (
            <option key={s} value={s}>{s ? s.charAt(0).toUpperCase() + s.slice(1) : 'All Sources'}</option>
          ))}
        </Select>
      </div>
      {loading ? (
        <p className="text-xs text-[#5a5a70] py-6 text-center">Loading…</p>
      ) : filtered.length === 0 ? (
        <p className="text-xs text-[#5a5a70] py-6 text-center">No assets found.</p>
      ) : (
        <div className="grid grid-cols-3 gap-3 max-h-[60vh] overflow-y-auto">
          {filtered.map(a => {
            const isImage = a.asset_type === 'still_image'
            const streamUrl = `/api/production/assets/${a.id}/stream`
            return (
              <div
                key={a.id}
                className="border border-[#2a2a32] rounded-lg overflow-hidden bg-[#0d0d0f] flex flex-col"
              >
                <div className="aspect-video relative bg-black flex items-center justify-center">
                  {isImage ? (
                    <img src={streamUrl} alt="" className="w-full h-full object-cover" />
                  ) : (
                    <video
                      src={streamUrl}
                      preload="metadata"
                      controls
                      className="w-full h-full object-contain bg-black"
                    />
                  )}
                </div>
                <div className="p-2 flex items-center gap-2">
                  <span className="text-xs text-[#9090a8] flex-1 truncate">
                    {a.description || `Asset #${a.id}`}
                    <span className="text-[10px] text-[#5a5a70] ml-1">· {a.source}</span>
                  </span>
                  <Button variant="primary" size="sm" onClick={() => { onSelect(a); onClose() }}>
                    Pick
                  </Button>
                </div>
              </div>
            )
          })}
        </div>
      )}
      <div className="flex justify-end mt-3">
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
      </div>
    </Modal>
  )
}
