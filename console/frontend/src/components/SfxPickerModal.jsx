import { useEffect, useMemo, useState } from 'react'
import { Modal, Button } from './index.jsx'
import { fetchApi } from '../api/client.js'
import PreviewPlayer from './PreviewPlayer.jsx'

const unwrap = (r) => Array.isArray(r) ? r : (r?.items || [])

/**
 * SfxPickerModal — single-select SFX picker with per-row preview.
 *
 * Props:
 *   open           — boolean, controls visibility
 *   onClose()      — close without selection
 *   onSelect(asset)— called with the chosen { id, title, sound_type, ... }
 *   selectedId     — currently selected asset id (highlighted)
 */
export default function SfxPickerModal({ open, onClose, onSelect, selectedId = null }) {
  const [library, setLibrary] = useState([])
  const [search, setSearch] = useState('')

  useEffect(() => {
    if (!open) return
    fetchApi('/api/sfx?per_page=500')
      .then(r => setLibrary(unwrap(r)))
      .catch(() => setLibrary([]))
  }, [open])

  const filtered = useMemo(() => {
    if (!search) return library
    const q = search.toLowerCase()
    return library.filter(s =>
      (s.title || '').toLowerCase().includes(q) ||
      (s.sound_type || '').toLowerCase().includes(q)
    )
  }, [library, search])

  const handlePick = (s) => {
    onSelect(s)
    onClose()
  }

  return (
    <Modal open={open} onClose={onClose} title="Pick SFX">
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
          const active = s.id === selectedId
          return (
            <div
              key={s.id}
              className={`flex items-center gap-2 px-3 py-2 rounded border ${
                active ? 'border-[#7c6af7] bg-[#7c6af7]/10' : 'border-[#2a2a32] hover:bg-[#1c1c22]'
              }`}
            >
              <PreviewPlayer src={`/api/sfx/${s.id}/stream`} kind="audio" />
              <button
                type="button"
                onClick={() => handlePick(s)}
                className="flex-1 text-left min-w-0"
              >
                <div className="text-sm text-[#e8e8f0] truncate">{s.title}</div>
                {s.sound_type && <div className="text-[10px] text-[#5a5a70]">{s.sound_type}</div>}
              </button>
            </div>
          )
        })}
      </div>
      <div className="flex justify-end mt-3">
        <Button variant="ghost" onClick={onClose}>Close</Button>
      </div>
    </Modal>
  )
}
