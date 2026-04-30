import { useState } from 'react'
import { assetsApi, nichesApi } from '../api/client.js'
import { useApi } from '../hooks/useApi.js'
import { Card, Button, StatBox, Modal, Input, Select, Spinner, EmptyState, Toast } from '../components/index.jsx'

// ── Source badge ──────────────────────────────────────────────────────────────
const SOURCE_COLORS = {
  pexels:     'bg-[#001624] text-[#4a9eff] border-[#002840]',
  veo:        'bg-[#001e12] text-[#34d399] border-[#003020]',
  manual:     'bg-[#1e1e2e] text-[#9090a8] border-[#2a2a42]',
  stock:      'bg-[#1e1e2e] text-[#9090a8] border-[#2a2a42]',
  midjourney: 'bg-[#1f0d00] text-[#f97316] border-[#2e1500]',
  runway:     'bg-[#0a1e1e] text-[#14b8a6] border-[#0d2e2e]',
}

function SourceBadge({ source, runwayStatus }) {
  const cls = SOURCE_COLORS[source] || 'bg-[#1e1e2e] text-[#9090a8] border-[#2a2a42]'
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium border ${cls}`}>
        {(source || 'manual').toUpperCase()}
      </span>
      {runwayStatus === 'pending' && (
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#14b8a6] bg-opacity-20 text-[#14b8a6] font-mono animate-pulse">RUNWAY ●</span>
      )}
    </span>
  )
}

// ── Niche multi-select pills ──────────────────────────────────────────────────
function NicheSelect({ options, value = [], onChange }) {
  const toggle = (opt) =>
    onChange(value.includes(opt) ? value.filter(v => v !== opt) : [...value, opt])
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs text-[#9090a8] font-medium">Niches</label>
      <div className="flex flex-wrap gap-1.5">
        {options.map(opt => (
          <button
            key={opt}
            type="button"
            onClick={() => toggle(opt)}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors ${
              value.includes(opt)
                ? 'bg-[#7c6af7] border-[#7c6af7] text-white'
                : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8] hover:border-[#7c6af7] hover:text-[#e8e8f0]'
            }`}
          >
            {opt}
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Preview Modal ─────────────────────────────────────────────────────────────
function PreviewModal({ asset, onClose }) {
  return (
    <Modal open onClose={onClose} title="Preview" width="max-w-xs">
      <div className="flex flex-col gap-3">
        <div className="aspect-[9/16] bg-[#0d0d0f] rounded-lg overflow-hidden">
          <video
            controls
            autoPlay
            src={assetsApi.streamUrl(asset.id)}
            className="w-full h-full object-contain"
          />
        </div>
        {asset.keywords?.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {asset.keywords.map(kw => (
              <span
                key={kw}
                className="text-[10px] bg-[#2a2a32] text-[#9090a8] rounded px-2 py-0.5"
              >
                {kw}
              </span>
            ))}
          </div>
        )}
      </div>
    </Modal>
  )
}

// ── Edit Modal ────────────────────────────────────────────────────────────────
function EditModal({ asset, niches, onClose, onSaved }) {
  const [description,   setDescription]   = useState(asset.description || '')
  const [keywordsRaw,   setKeywordsRaw]   = useState((asset.keywords || []).join(', '))
  const [selectedNiches,setSelectedNiches]= useState(asset.niche || [])
  const [qualityScore,  setQualityScore]  = useState(asset.quality_score ?? 0)
  const [saving,        setSaving]        = useState(false)
  const [toast,         setToast]         = useState(null)

  const showToast = (msg, type = 'error') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const keywords = keywordsRaw.split(',').map(k => k.trim()).filter(Boolean)
      await assetsApi.update(asset.id, {
        description: description || null,
        keywords,
        niche: selectedNiches,
        quality_score: qualityScore,
      })
      onSaved()
      onClose()
    } catch (e) {
      showToast(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`Edit Asset — ${asset.id}`}
      width="max-w-xl"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={saving} onClick={handleSave}>Save</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Description</label>
          <textarea
            value={description}
            onChange={e => setDescription(e.target.value)}
            rows={3}
            placeholder="Describe the video clip…"
            className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] placeholder:text-[#5a5a70] focus:outline-none focus:border-[#7c6af7] resize-y transition-colors"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Keywords <span className="text-[#5a5a70]">(comma-separated)</span></label>
          <input
            value={keywordsRaw}
            onChange={e => setKeywordsRaw(e.target.value)}
            placeholder="fitness, outdoor, running"
            className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] placeholder:text-[#5a5a70] focus:outline-none focus:border-[#7c6af7] transition-colors"
          />
        </div>

        <NicheSelect
          options={niches.map(n => n.name)}
          value={selectedNiches}
          onChange={setSelectedNiches}
        />

        <Input
          label="Quality Score (0–100)"
          type="number"
          value={qualityScore}
          onChange={e => setQualityScore(parseFloat(e.target.value) || 0)}
        />
      </div>
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </Modal>
  )
}

// ── Animate Modal ─────────────────────────────────────────────────────────────
function AnimateModal({ asset, onClose, onAnimated }) {
  const [prompt, setPrompt] = useState('')
  const [intensity, setIntensity] = useState(2)
  const [duration, setDuration] = useState(5)
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState(null)
  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000) }

  const handleGenerate = async () => {
    if (!prompt) { showToast('Runway prompt is required', 'error'); return }
    setLoading(true)
    try {
      await assetsApi.animateWithRunway(asset.id, { prompt, motion_intensity: intensity, duration })
      showToast('Animation queued — check back in a few minutes', 'success')
      onAnimated()
      onClose()
    } catch (e) { showToast(e.message, 'error') }
    finally { setLoading(false) }
  }

  return (
    <Modal open onClose={onClose} title="Animate with Runway →" width="max-w-lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={loading} onClick={handleGenerate}>Animate →</Button>
        </>
      }
    >
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
      <div className="flex flex-col gap-4">
        {asset.thumbnail_url && (
          <img src={assetsApi.thumbnailUrl(asset.id)} alt={asset.description} className="w-full h-32 object-cover rounded-lg" />
        )}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Runway Prompt</label>
          <textarea
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            rows={3}
            className="w-full px-3 py-2 rounded-lg bg-[#16161a] border border-[#2a2a32] text-sm text-[#e8e8f0] resize-none focus:outline-none focus:border-[#7c6af7]"
            placeholder="Slow rain droplets running down glass. No camera movement. Hypnotic loop."
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[#9090a8] font-medium">Motion Intensity ({intensity}/10)</label>
            <input type="range" min={1} max={10} value={intensity} onChange={e => setIntensity(Number(e.target.value))}
              className="w-full accent-[#7c6af7]" />
          </div>
          <Select label="Duration" value={duration} onChange={e => setDuration(Number(e.target.value))}>
            <option value={5}>5s</option>
            <option value={10}>10s</option>
          </Select>
        </div>
      </div>
    </Modal>
  )
}

// ── Import Modal ──────────────────────────────────────────────────────────────
const IMPORT_SOURCES = ['manual', 'midjourney', 'runway', 'pexels', 'veo', 'stock']
const IMAGE_EXTS = new Set(['.jpg', '.jpeg', '.png', '.webp'])
const VIDEO_EXTS = new Set(['.mp4', '.mov', '.webm'])

function detectAssetType(filename) {
  const ext = filename.slice(filename.lastIndexOf('.')).toLowerCase()
  if (IMAGE_EXTS.has(ext)) return 'still_image'
  if (VIDEO_EXTS.has(ext)) return 'video_clip'
  return ''
}

function ImportAssetModal({ onClose, onImported }) {
  const [file, setFile] = useState(null)
  const [source, setSource] = useState('manual')
  const [description, setDescription] = useState('')
  const [keywords, setKeywords] = useState('')
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState(null)

  const showToast = (msg, type = 'error') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  const detectedType = file ? detectAssetType(file.name) : ''

  const handleSubmit = async () => {
    if (!file) { showToast('Please select a file'); return }
    setLoading(true)
    try {
      await assetsApi.upload(file, {
        source,
        description: description || undefined,
        keywords: keywords || undefined,
        asset_type: detectedType || undefined,
      })
      onImported()
      onClose()
    } catch (e) {
      showToast(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Import Asset"
      width="max-w-lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={loading} onClick={handleSubmit}>Import</Button>
        </>
      }
    >
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">File (Image or Video)</label>
          <input
            type="file"
            accept=".jpg,.jpeg,.png,.webp,.mp4,.mov,.webm"
            onChange={e => setFile(e.target.files?.[0] || null)}
            className="text-sm text-[#9090a8] file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:bg-[#2a2a32] file:text-[#e8e8f0] file:text-xs cursor-pointer"
          />
          {detectedType && (
            <span className="text-xs text-[#5a5a70] mt-0.5">
              Type: <span className="text-[#9090a8] font-mono">{detectedType}</span>
            </span>
          )}
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Source</label>
          <select
            value={source}
            onChange={e => setSource(e.target.value)}
            className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7] transition-colors"
          >
            {IMPORT_SOURCES.map(s => (
              <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Description <span className="text-[#5a5a70]">(optional)</span></label>
          <input
            value={description}
            onChange={e => setDescription(e.target.value)}
            placeholder="e.g. Rainy window close-up"
            className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] placeholder:text-[#5a5a70] focus:outline-none focus:border-[#7c6af7] transition-colors"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Keywords <span className="text-[#5a5a70]">(comma-separated, optional)</span></label>
          <input
            value={keywords}
            onChange={e => setKeywords(e.target.value)}
            placeholder="rain, dark, window"
            className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] placeholder:text-[#5a5a70] focus:outline-none focus:border-[#7c6af7] transition-colors"
          />
        </div>
      </div>
    </Modal>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function VideoAssetsPage() {
  const [filterKeywords,  setFilterKeywords]  = useState('')
  const [filterSource,    setFilterSource]    = useState('')
  const [filterNiches,    setFilterNiches]    = useState([])
  const [filterMinDur,    setFilterMinDur]    = useState('')
  const [filterAssetType, setFilterAssetType] = useState('')
  const [previewAsset,    setPreviewAsset]    = useState(null)
  const [editingAsset,    setEditingAsset]    = useState(null)
  const [animateTarget,   setAnimateTarget]   = useState(null)
  const [deletingId,      setDeletingId]      = useState(null)
  const [toast,           setToast]           = useState(null)
  const [showImport,      setShowImport]      = useState(false)

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  const { data: niches = [] } = useApi(() => nichesApi.list(), [])
  const nichesKey = filterNiches.join(',')
  const { data: result, loading, refetch } = useApi(
    () => assetsApi.list({
      keywords:    filterKeywords || undefined,
      source:      filterSource   || undefined,
      niche:       nichesKey || undefined,
      min_duration: filterMinDur  || undefined,
      asset_type:  filterAssetType || undefined,
    }),
    [filterKeywords, filterSource, nichesKey, filterMinDur, filterAssetType]
  )

  const nicheList  = niches  || []
  const assetList  = result?.items || result || []
  const totalCount = result?.total ?? assetList.length

  // Derived counts from visible results
  const pexelsCount = assetList.filter(a => a.source === 'pexels').length
  const veoCount    = assetList.filter(a => a.source === 'veo').length
  const otherCount  = assetList.filter(a => a.source !== 'pexels' && a.source !== 'veo').length

  const handleDelete = async (asset) => {
    if (!window.confirm(`Delete this asset? This cannot be undone.`)) return
    setDeletingId(asset.id)
    try {
      await assetsApi.delete(asset.id)
      refetch()
      showToast('Asset deleted')
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setDeletingId(null)
    }
  }

  const toggleNicheFilter = (niche) => {
    setFilterNiches(prev =>
      prev.includes(niche) ? prev.filter(n => n !== niche) : [...prev, niche]
    )
  }

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#e8e8f0]">Video Assets</h1>
          <p className="text-sm text-[#9090a8] mt-0.5">
            Manage video clips downloaded from Pexels or generated by Veo
          </p>
        </div>
        <Button variant="primary" onClick={() => setShowImport(true)}>+ Import Asset</Button>
      </div>

      {/* Stats */}
      <div className="flex gap-3 flex-wrap">
        <StatBox label="Total"  value={totalCount} />
        <StatBox label="Pexels" value={pexelsCount} />
        <StatBox label="Veo"    value={veoCount} />
        <StatBox label="Other"  value={otherCount} />
      </div>

      {/* Filters */}
      <div className="flex gap-2 flex-wrap items-end">
        {/* Keyword search */}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Keywords</label>
          <input
            value={filterKeywords}
            onChange={e => setFilterKeywords(e.target.value)}
            placeholder="Search keywords…"
            className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] placeholder:text-[#5a5a70] focus:outline-none focus:border-[#7c6af7] w-44 transition-colors"
          />
        </div>

        {/* Source filter */}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Source</label>
          <select
            value={filterSource}
            onChange={e => setFilterSource(e.target.value)}
            className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7] transition-colors"
          >
            <option value="">All sources</option>
            <option value="pexels">Pexels</option>
            <option value="veo">Veo</option>
            <option value="manual">Manual</option>
            <option value="midjourney">MidJourney</option>
            <option value="runway">Runway</option>
          </select>
        </div>

        {/* Min duration */}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Min Duration (s)</label>
          <input
            type="number"
            value={filterMinDur}
            onChange={e => setFilterMinDur(e.target.value)}
            placeholder="e.g. 5"
            className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] placeholder:text-[#5a5a70] focus:outline-none focus:border-[#7c6af7] w-32 transition-colors"
          />
        </div>

        {/* Niche filter pills */}
        {nicheList.length > 0 && (
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[#9090a8] font-medium">Niches</label>
            <div className="flex flex-wrap gap-1.5">
              {nicheList.map(n => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => toggleNicheFilter(n.name)}
                  className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors ${
                    filterNiches.includes(n.name)
                      ? 'bg-[#7c6af7] border-[#7c6af7] text-white'
                      : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8] hover:border-[#7c6af7] hover:text-[#e8e8f0]'
                  }`}
                >
                  {n.name}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Asset type toggle */}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Type</label>
          <div className="flex items-center gap-1 bg-[#16161a] border border-[#2a2a32] rounded-lg p-1">
            {['all', 'video_clip', 'still_image'].map(t => (
              <button
                key={t}
                onClick={() => setFilterAssetType(t === 'all' ? '' : t)}
                className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                  (filterAssetType || 'all') === t
                    ? 'bg-[#7c6af7] text-white'
                    : 'text-[#9090a8] hover:text-[#e8e8f0]'
                }`}
              >
                {t === 'all' ? 'All' : t === 'video_clip' ? 'Video Clips' : 'Stills'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Asset table */}
      <Card>
        {loading ? (
          <div className="flex justify-center py-10"><Spinner /></div>
        ) : assetList.length === 0 ? (
          <EmptyState
            icon="🎬"
            title="No video assets found"
            description="Video clips are downloaded from Pexels or generated by Veo during the production pipeline."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#2a2a32] text-left">
                  {['Thumbnail', 'Description / Keywords', 'Source', 'Duration', 'Resolution', 'Niches', 'Score', 'Uses', ''].map(h => (
                    <th key={h} className="pb-2 pr-4 text-xs font-semibold text-[#9090a8] uppercase tracking-wider whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {assetList.map(asset => (
                  <tr key={asset.id} className="border-b border-[#2a2a32] hover:bg-[#16161a] transition-colors">
                    {/* Thumbnail */}
                    <td className="py-2.5 pr-4">
                      {asset.thumbnail_url ? (
                        <img
                          src={asset.thumbnail_url}
                          alt="thumbnail"
                          className="w-16 h-9 object-cover rounded bg-[#0d0d0f]"
                        />
                      ) : (
                        <div className="w-16 h-9 flex items-center justify-center bg-[#0d0d0f] rounded text-xl">
                          🎬
                        </div>
                      )}
                    </td>

                    {/* Description + keywords */}
                    <td className="py-2.5 pr-4 max-w-[220px]">
                      <div className="text-[#e8e8f0] text-sm truncate">
                        {asset.description || <span className="text-[#5a5a70] italic">No description</span>}
                      </div>
                      {asset.keywords?.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {asset.keywords.slice(0, 4).map(kw => (
                            <span key={kw} className="text-[10px] bg-[#2a2a32] text-[#9090a8] rounded px-1.5 py-0.5">
                              {kw}
                            </span>
                          ))}
                          {asset.keywords.length > 4 && (
                            <span className="text-[10px] text-[#5a5a70]">+{asset.keywords.length - 4}</span>
                          )}
                        </div>
                      )}
                    </td>

                    {/* Source badge */}
                    <td className="py-2.5 pr-4 whitespace-nowrap">
                      <SourceBadge source={asset.source} runwayStatus={asset.runway_status} />
                    </td>

                    {/* Duration */}
                    <td className="py-2.5 pr-4 font-mono text-[#9090a8] text-xs whitespace-nowrap">
                      {asset.duration_s != null ? `${Number(asset.duration_s).toFixed(1)}s` : '—'}
                    </td>

                    {/* Resolution */}
                    <td className="py-2.5 pr-4 font-mono text-[#9090a8] text-xs whitespace-nowrap">
                      {asset.resolution || '—'}
                    </td>

                    {/* Niches */}
                    <td className="py-2.5 pr-4">
                      <div className="flex flex-wrap gap-1 max-w-[160px]">
                        {(asset.niche || []).slice(0, 3).map(n => (
                          <span key={n} className="text-[10px] bg-[#1a0e2e] text-[#7c6af7] border border-[#2a1a50] rounded px-1.5 py-0.5">
                            {n}
                          </span>
                        ))}
                        {(asset.niche || []).length > 3 && (
                          <span className="text-[10px] text-[#5a5a70]">+{asset.niche.length - 3}</span>
                        )}
                      </div>
                    </td>

                    {/* Quality score */}
                    <td className="py-2.5 pr-4 font-mono text-[#9090a8] text-xs">
                      {asset.quality_score ?? '—'}
                    </td>

                    {/* Usage count */}
                    <td className="py-2.5 pr-4 font-mono text-[#9090a8] text-xs">
                      {asset.usage_count ?? 0}
                    </td>

                    {/* Actions */}
                    <td className="py-2.5 whitespace-nowrap">
                      <div className="flex gap-1">
                        <Button variant="ghost" size="sm" onClick={() => setPreviewAsset(asset)} title="Preview">
                          ▶
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setEditingAsset(asset)} title="Edit">
                          ✎
                        </Button>
                        {asset.asset_type === 'still_image' && (
                          <Button variant="ghost" size="sm" onClick={() => setAnimateTarget(asset)}>Animate →</Button>
                        )}
                        <Button
                          variant="danger"
                          size="sm"
                          loading={deletingId === asset.id}
                          onClick={() => handleDelete(asset)}
                          title="Delete"
                        >
                          ✕
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Modals */}
      {previewAsset && (
        <PreviewModal asset={previewAsset} onClose={() => setPreviewAsset(null)} />
      )}

      {editingAsset && (
        <EditModal
          asset={editingAsset}
          niches={nicheList}
          onClose={() => setEditingAsset(null)}
          onSaved={refetch}
        />
      )}

      {animateTarget && (
        <AnimateModal
          asset={animateTarget}
          onClose={() => setAnimateTarget(null)}
          onAnimated={refetch}
        />
      )}

      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}

      {showImport && (
        <ImportAssetModal
          onClose={() => setShowImport(false)}
          onImported={refetch}
        />
      )}
    </div>
  )
}
