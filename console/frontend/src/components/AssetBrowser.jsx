import { useState, useEffect, useCallback } from 'react'
import { Modal, Button, Input, Select, Spinner, EmptyState } from './index.jsx'
import { fetchApi } from '../api/client.js'

const SOURCES  = ['All Sources', 'pexels', 'veo', 'manual', 'stock']
const NICHES   = ['All Niches', 'finance', 'health', 'tech', 'lifestyle', 'education', 'entertainment', 'news']

export default function AssetBrowser({ open, onClose, onSelect, title = 'Select Asset' }) {
  const [assets,   setAssets]   = useState([])
  const [loading,  setLoading]  = useState(false)
  const [selected, setSelected] = useState(null)

  const [keywords, setKeywords] = useState('')
  const [niche,    setNiche]    = useState('All Niches')
  const [source,   setSource]   = useState('All Sources')
  const [page,     setPage]     = useState(1)
  const [total,    setTotal]    = useState(0)

  const PER_PAGE = 20

  const fetch = useCallback(async (p = 1) => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ page: p, per_page: PER_PAGE })
      if (keywords) params.set('keywords', keywords)
      if (niche   !== 'All Niches')   params.set('niche',  niche)
      if (source  !== 'All Sources')  params.set('source', source)

      const res = await fetchApi(`/api/production/assets?${params}`)
      setAssets(res.items || [])
      setTotal(res.total || 0)
      setPage(p)
    } catch {
      setAssets([])
    } finally {
      setLoading(false)
    }
  }, [keywords, niche, source])

  useEffect(() => {
    if (open) { setSelected(null); fetch(1) }
  }, [open, fetch])

  const handleConfirm = () => {
    if (selected) { onSelect(selected); onClose() }
  }

  const pages = Math.ceil(total / PER_PAGE)

  return (
    <Modal open={open} onClose={onClose} title={title} width="max-w-4xl">
      {/* Filters */}
      <div className="flex gap-2 mb-4 flex-wrap">
        <Input
          placeholder="Search keywords…"
          value={keywords}
          onChange={e => setKeywords(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && fetch(1)}
          className="flex-1 min-w-[160px]"
        />
        <Select value={source} onChange={e => setSource(e.target.value)} className="w-36">
          {SOURCES.map(s => <option key={s}>{s}</option>)}
        </Select>
        <Select value={niche} onChange={e => setNiche(e.target.value)} className="w-36">
          {NICHES.map(n => <option key={n}>{n}</option>)}
        </Select>
        <Button onClick={() => fetch(1)} variant="primary">Search</Button>
      </div>

      {/* Grid */}
      <div className="min-h-[320px]">
        {loading ? (
          <div className="flex items-center justify-center h-64"><Spinner /></div>
        ) : assets.length === 0 ? (
          <EmptyState title="No assets found. Try different keywords." />
        ) : (
          <div className="grid grid-cols-4 gap-3">
            {assets.map(asset => (
              <button
                key={asset.id}
                onClick={() => setSelected(asset)}
                className={`relative rounded-lg overflow-hidden border-2 transition-all text-left group ${
                  selected?.id === asset.id
                    ? 'border-[#7c6af7] ring-2 ring-[#7c6af7]/40'
                    : 'border-[#2a2a32] hover:border-[#5a5a70]'
                }`}
              >
                {/* Thumbnail */}
                <div className="bg-[#0d0d0f] aspect-[9/16] flex items-center justify-center">
                  {asset.thumbnail_url ? (
                    <img
                      src={asset.thumbnail_url}
                      alt={asset.keywords?.join(', ')}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="text-[#5a5a70] text-xs font-mono p-2 text-center">
                      {asset.source || 'asset'}
                    </div>
                  )}
                </div>

                {/* Metadata overlay */}
                <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 to-transparent p-2">
                  <div className="text-[10px] text-[#e8e8f0] font-mono truncate">
                    {asset.keywords?.slice(0, 2).join(', ') || '—'}
                  </div>
                  <div className="text-[9px] text-[#9090a8] flex justify-between mt-0.5">
                    <span>{asset.duration_s ? `${asset.duration_s.toFixed(1)}s` : '—'}</span>
                    <span>{asset.source}</span>
                  </div>
                </div>

                {/* Selected checkmark */}
                {selected?.id === asset.id && (
                  <div className="absolute top-1.5 right-1.5 w-5 h-5 rounded-full bg-[#7c6af7] flex items-center justify-center">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3">
                      <polyline points="20 6 9 17 4 12"/>
                    </svg>
                  </div>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-4">
          <Button variant="ghost" disabled={page <= 1} onClick={() => fetch(page - 1)}>‹ Prev</Button>
          <span className="text-xs text-[#9090a8] font-mono">{page} / {pages}</span>
          <Button variant="ghost" disabled={page >= pages} onClick={() => fetch(page + 1)}>Next ›</Button>
        </div>
      )}

      {/* Footer */}
      <div className="flex justify-between items-center mt-4 pt-4 border-t border-[#2a2a32]">
        <span className="text-xs text-[#9090a8]">
          {selected ? `Selected: ${selected.keywords?.slice(0, 2).join(', ') || `Asset #${selected.id}`}` : `${total} asset(s) found`}
        </span>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" disabled={!selected} onClick={handleConfirm}>Use Asset</Button>
        </div>
      </div>
    </Modal>
  )
}
