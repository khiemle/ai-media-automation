import { useState, useEffect, useRef } from 'react'
import { nichesApi } from '../api/client.js'

export default function NicheCombobox({ value, onChange, label = 'Niche', placeholder = 'Select or type a niche…' }) {
  const [niches,   setNiches]   = useState([])
  const [input,    setInput]    = useState(value || '')
  const [open,     setOpen]     = useState(false)
  const [creating, setCreating] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    nichesApi.list().then(data => setNiches(data || [])).catch(() => {})
  }, [])

  // Sync controlled value
  useEffect(() => { setInput(value || '') }, [value])

  // Close on outside click
  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const filtered = niches.filter(n => n.name.toLowerCase().includes(input.toLowerCase()))
  const exactMatch = niches.some(n => n.name.toLowerCase() === input.toLowerCase())
  const showAdd = input.trim() && !exactMatch

  const select = (name) => {
    setInput(name)
    onChange(name)
    setOpen(false)
  }

  const handleAdd = async () => {
    const name = input.trim()
    if (!name) return
    setCreating(true)
    try {
      const created = await nichesApi.create(name)
      setNiches(prev => [...prev, created].sort((a, b) => a.name.localeCompare(b.name)))
      select(created.name)
    } catch (e) {
      if (e.message?.includes('already exists')) {
        // Race condition: niche was created concurrently — just select it
        select(name)
      } else {
        // 403 Forbidden, 500, etc. — do not silently accept
        console.error('Could not create niche:', e.message)
      }
    } finally { setCreating(false) }
  }

  return (
    <div className="flex flex-col gap-1" ref={ref}>
      {label && <label className="text-xs font-medium text-[#9090a8]">{label}</label>}
      <div className="relative">
        <input
          type="text"
          value={input}
          onFocus={() => setOpen(true)}
          onChange={e => { setInput(e.target.value); onChange(e.target.value); setOpen(true) }}
          placeholder={placeholder}
          className="w-full bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] placeholder-[#5a5a70] focus:outline-none focus:border-[#7c6af7] transition-colors"
        />
        {open && (filtered.length > 0 || showAdd) && (
          <div className="absolute z-50 w-full mt-1 bg-[#1c1c22] border border-[#2a2a32] rounded-lg shadow-lg overflow-hidden max-h-48 overflow-y-auto">
            {filtered.map(n => (
              <button key={n.id} type="button"
                className="w-full text-left px-3 py-2 text-sm text-[#e8e8f0] hover:bg-[#2a2a32] transition-colors"
                onClick={() => select(n.name)}>
                {n.name}
              </button>
            ))}
            {showAdd && (
              <button type="button"
                className="w-full text-left px-3 py-2 text-sm text-[#7c6af7] hover:bg-[#2a2a32] transition-colors border-t border-[#2a2a32]"
                onClick={handleAdd} disabled={creating}>
                {creating ? 'Adding…' : `+ Add "${input.trim()}"`}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
