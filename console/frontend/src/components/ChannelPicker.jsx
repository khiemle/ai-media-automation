import { useRef, useEffect, useState } from 'react'

const PLATFORM_COLORS = {
  youtube:   { bg: 'bg-[#1e0808]', text: 'text-[#ff6060]', dot: '#ff6060' },
  tiktok:    { bg: 'bg-[#001624]', text: 'text-[#22d3ee]', dot: '#22d3ee' },
  instagram: { bg: 'bg-[#1a0820]', text: 'text-[#c084fc]', dot: '#c084fc' },
}

const PlatformIcon = ({ platform, size = 14 }) => {
  const color = PLATFORM_COLORS[platform]?.dot || '#9090a8'
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={color}>
      {platform === 'youtube'   && <path d="M19.59 6.69a4.83 4.83 0 01-3.77-2.73 12.86 12.86 0 00-4.82 0A4.83 4.83 0 017.23 6.69 30.11 30.11 0 006 12a30.11 30.11 0 001.23 5.31 4.83 4.83 0 003.77 2.73 12.86 12.86 0 004.82 0 4.83 4.83 0 003.77-2.73A30.11 30.11 0 0021 12a30.11 30.11 0 00-1.41-5.31zM10 15V9l5 3z"/>}
      {platform === 'tiktok'   && <path d="M19.59 6.69a4.83 4.83 0 01-3.77-2.73V3h-3v13a2.5 2.5 0 11-2.5-2.5V10.5A6 6 0 1016 16V9.66a8.08 8.08 0 004.59 1.42V7.74a4.84 4.84 0 01-1-.05z"/>}
      {platform === 'instagram' && <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/>}
    </svg>
  )
}

export default function ChannelPicker({ channels = [], selected = [], onChange, onDone }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const toggle = (id) => {
    const next = selected.includes(id) ? selected.filter(i => i !== id) : [...selected, id]
    onChange(next)
  }

  const handleDone = () => {
    setOpen(false)
    onDone?.(selected)
  }

  const activeChannels = channels.filter(c => c.status === 'active')

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1.5 px-2 py-1 rounded text-xs text-[#9090a8] hover:text-[#e8e8f0] hover:bg-[#222228] border border-transparent hover:border-[#2a2a32] transition-all"
      >
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
        </svg>
        Target
        {selected.length > 0 && (
          <span className="ml-0.5 bg-[#7c6af7] text-white rounded-full w-4 h-4 flex items-center justify-center text-[9px] font-bold">
            {selected.length}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute z-50 top-full left-0 mt-1 w-56 bg-[#1c1c22] border border-[#2a2a32] rounded-xl shadow-2xl overflow-hidden">
          <div className="px-3 py-2 border-b border-[#2a2a32]">
            <span className="text-[10px] font-semibold text-[#5a5a70] uppercase tracking-wider">
              Select Target Channels
            </span>
          </div>

          <div className="max-h-48 overflow-y-auto py-1">
            {activeChannels.length === 0 ? (
              <div className="px-3 py-3 text-xs text-[#5a5a70]">No active channels</div>
            ) : activeChannels.map(ch => (
              <button
                key={ch.id}
                onClick={() => toggle(ch.id)}
                className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-[#222228] transition-colors text-left"
              >
                <div className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 ${
                  selected.includes(ch.id)
                    ? 'bg-[#7c6af7] border-[#7c6af7]'
                    : 'border-[#2a2a32]'
                }`}>
                  {selected.includes(ch.id) && (
                    <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3">
                      <polyline points="20 6 9 17 4 12"/>
                    </svg>
                  )}
                </div>
                <PlatformIcon platform={ch.platform} size={13} />
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium text-[#e8e8f0] truncate">{ch.name}</div>
                  <div className="text-[10px] text-[#5a5a70]">
                    {ch.platform} · {ch.subscriber_count?.toLocaleString() || 0} subs
                  </div>
                </div>
              </button>
            ))}
          </div>

          <div className="flex gap-1 px-3 py-2 border-t border-[#2a2a32]">
            <button
              onClick={() => onChange(activeChannels.map(c => c.id))}
              className="flex-1 text-[10px] text-[#9090a8] hover:text-[#e8e8f0] py-1 rounded hover:bg-[#222228] transition-colors"
            >All</button>
            <button
              onClick={() => onChange([])}
              className="flex-1 text-[10px] text-[#9090a8] hover:text-[#e8e8f0] py-1 rounded hover:bg-[#222228] transition-colors"
            >None</button>
            <button
              onClick={handleDone}
              className="flex-1 text-[10px] text-[#7c6af7] font-semibold py-1 rounded hover:bg-[#7c6af7]/10 transition-colors"
            >Done</button>
          </div>
        </div>
      )}
    </div>
  )
}
