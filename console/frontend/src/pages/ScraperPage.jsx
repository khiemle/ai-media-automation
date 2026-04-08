import { useState, useCallback } from 'react'
import { scraperApi, scriptsApi } from '../api/client.js'
import { useApi } from '../hooks/useApi.js'
import { Card, Badge, Button, StatBox, Modal, Select, Input, Textarea, Toast, Spinner, EmptyState } from '../components/index.jsx'

const NICHES   = ['lifestyle', 'fitness', 'finance', 'beauty', 'food', 'tech', 'education']
const REGIONS  = ['VN', 'US', 'UK', 'TH', 'ID']
const TEMPLATES = ['tiktok_viral', 'tiktok_30s', 'youtube_clean', 'shorts_hook']
const SORT_OPTIONS = [
  { value: 'play_count',      label: 'Views ↓' },
  { value: 'engagement_rate', label: 'ER ↓' },
]

// ── Source status dot ─────────────────────────────────────────────────────────
function StatusDot({ status }) {
  const colors = { active: '#34d399', standby: '#fbbf24', planned: '#5a5a70' }
  return <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: colors[status] || '#5a5a70' }} />
}

export default function ScraperPage() {
  // ── Filters ────────────────────────────────────────────────────────────────
  const [sourceFilter, setSourceFilter] = useState('')
  const [nicheFilter,  setNicheFilter]  = useState('')
  const [regionFilter, setRegionFilter] = useState('')
  const [sortBy,       setSortBy]       = useState('play_count')
  const [page]                          = useState(1)

  // ── Data ───────────────────────────────────────────────────────────────────
  const { data: sourcesData, loading: srcLoading, refetch: refetchSources } = useApi(
    () => scraperApi.getSources(), []
  )
  const { data: videosData, loading: vidLoading, refetch: refetchVideos } = useApi(
    () => scraperApi.getVideos({ source: sourceFilter, niche: nicheFilter, region: regionFilter, sort_by: sortBy, page, per_page: 100 }),
    [sourceFilter, nicheFilter, regionFilter, sortBy, page]
  )

  const sources = sourcesData || []
  const videos  = videosData?.items || []
  const total   = videosData?.total || 0

  // ── Selection ──────────────────────────────────────────────────────────────
  const [selectedIds, setSelectedIds] = useState(new Set())
  const toggleSelect = (id) => setSelectedIds(prev => {
    const next = new Set(prev)
    next.has(id) ? next.delete(id) : next.add(id)
    return next
  })
  const selectAll  = () => setSelectedIds(new Set(videos.map(v => v.id)))
  const deselectAll = () => setSelectedIds(new Set())

  // ── Source manager modal ───────────────────────────────────────────────────
  const [srcModalOpen, setSrcModalOpen] = useState(false)
  const [updatingSrc, setUpdatingSrc]   = useState(null)

  const handleUpdateStatus = async (sourceId, status) => {
    setUpdatingSrc(sourceId)
    try {
      await scraperApi.updateSourceStatus(sourceId, status)
      refetchSources()
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setUpdatingSrc(null)
    }
  }

  // ── Manual scrape ──────────────────────────────────────────────────────────
  const [scraping, setScraping] = useState(false)
  const handleRunScrape = async (sourceId) => {
    setScraping(true)
    try {
      const activeSource = sources.find(s => s.status === 'active')
      await scraperApi.triggerScrape(sourceId || activeSource?.id)
      showToast('Scrape queued — results will appear shortly', 'info')
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setScraping(false)
    }
  }

  // ── Index ──────────────────────────────────────────────────────────────────
  const [indexing, setIndexing] = useState(false)
  const handleIndex = async () => {
    if (selectedIds.size === 0) return
    setIndexing(true)
    try {
      const res = await scraperApi.indexVideos([...selectedIds])
      showToast(`${res.indexed} videos indexed to ChromaDB`, 'success')
      refetchVideos()
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setIndexing(false)
    }
  }

  // ── Topic creation modal ───────────────────────────────────────────────────
  const [topicModalOpen, setTopicModalOpen] = useState(false)
  const [newTopic,    setNewTopic]    = useState('')
  const [newNiche,    setNewNiche]    = useState('')
  const [newTemplate, setNewTemplate] = useState('tiktok_viral')
  const [generating,  setGenerating]  = useState(false)

  const handleGenerate = async () => {
    if (!newTopic || !newNiche) return
    setGenerating(true)
    try {
      await scriptsApi.generate({
        topic: newTopic,
        niche: newNiche,
        template: newTemplate,
        source_video_ids: [...selectedIds],
      })
      setTopicModalOpen(false)
      deselectAll()
      setNewTopic('')
      showToast('Script generated — check the Scripts tab', 'success')
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setGenerating(false)
    }
  }

  // ── Toast ──────────────────────────────────────────────────────────────────
  const [toast, setToast] = useState(null)
  const showToast = (message, type = 'success') => {
    setToast({ message, type })
    setTimeout(() => setToast(null), 3500)
  }

  // ── Stats ──────────────────────────────────────────────────────────────────
  const indexed   = videos.filter(v => v.is_indexed).length
  const avgER     = videos.length ? (videos.reduce((s, v) => s + (v.engagement_rate || 0), 0) / videos.length).toFixed(1) : '—'
  const activeSrc = sources.filter(s => s.status === 'active').length

  return (
    <div className="flex flex-col gap-5">
      {/* ── Page header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#e8e8f0]">Scraper</h1>
          <p className="text-sm text-[#9090a8] mt-0.5">Browse and curate scraped trending content</p>
        </div>
        <Button variant="primary" size="md" onClick={() => handleRunScrape()} loading={scraping}>
          ▶ Run Scrape Now
        </Button>
      </div>

      {/* ── Stats row ── */}
      <div className="flex gap-3 flex-wrap">
        <StatBox label="Total Scraped" value={total.toLocaleString()} />
        <StatBox label="Indexed"       value={indexed.toLocaleString()} sub="ChromaDB" />
        <StatBox label="Selected"      value={selectedIds.size} accent />
        <StatBox label="Avg ER"        value={avgER !== '—' ? `${avgER}%` : '—'} />
        <StatBox label="Active Sources" value={activeSrc} />
      </div>

      {/* ── Sources card ── */}
      <Card
        title="Scraper Sources"
        actions={
          <Button variant="ghost" size="sm" onClick={() => setSrcModalOpen(true)}>
            Manage Sources
          </Button>
        }
      >
        {srcLoading ? (
          <Spinner />
        ) : (
          <div className="flex flex-wrap gap-2">
            {sources.map(s => (
              <div key={s.id} className="flex items-center gap-2 bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5">
                <StatusDot status={s.status} />
                <span className="text-sm font-medium text-[#e8e8f0]">{s.name}</span>
                <Badge status={s.status} />
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* ── Videos card ── */}
      <Card
        title="Scraped Videos"
        actions={
          <div className="flex gap-2">
            <Select
              value={sourceFilter}
              onChange={e => setSourceFilter(e.target.value)}
              placeholder="All Sources"
              options={sources.filter(s => s.status !== 'planned').map(s => ({ value: s.id, label: s.name }))}
            />
            <Select
              value={nicheFilter}
              onChange={e => setNicheFilter(e.target.value)}
              placeholder="All Niches"
              options={NICHES.map(n => ({ value: n, label: n }))}
            />
            <Select
              value={regionFilter}
              onChange={e => setRegionFilter(e.target.value)}
              placeholder="All Regions"
              options={REGIONS.map(r => ({ value: r, label: r }))}
            />
            <Select
              value={sortBy}
              onChange={e => setSortBy(e.target.value)}
              options={SORT_OPTIONS}
            />
          </div>
        }
      >
        {/* Action bar */}
        <div className="flex items-center gap-3 mb-3">
          <label className="flex items-center gap-2 cursor-pointer text-sm text-[#9090a8]">
            <input
              type="checkbox"
              checked={selectedIds.size === videos.length && videos.length > 0}
              onChange={e => e.target.checked ? selectAll() : deselectAll()}
              className="accent-[#7c6af7] w-3.5 h-3.5"
            />
            Select All
          </label>
          {selectedIds.size > 0 && (
            <span className="text-sm text-[#7c6af7] font-mono">{selectedIds.size} selected</span>
          )}
          <div className="flex-1" />
          <Button
            variant="accent"
            size="sm"
            disabled={selectedIds.size === 0}
            loading={indexing}
            onClick={handleIndex}
          >
            Index to ChromaDB
          </Button>
          <Button
            variant="primary"
            size="sm"
            disabled={selectedIds.size === 0}
            onClick={() => setTopicModalOpen(true)}
          >
            Generate Script →
          </Button>
        </div>

        {/* Table */}
        {vidLoading ? (
          <div className="flex justify-center py-12"><Spinner size={28} /></div>
        ) : videos.length === 0 ? (
          <EmptyState icon="📭" title="No videos found" description="Try adjusting your filters or run a scrape first." />
        ) : (
          <div className="overflow-y-auto max-h-[440px] rounded-lg border border-[#2a2a32]">
            <table className="w-full text-sm border-collapse">
              <thead className="sticky top-0 bg-[#16161a] z-10">
                <tr className="text-left">
                  <th className="w-8 px-3 py-2" />
                  <th className="px-3 py-2 text-xs text-[#9090a8] font-medium">Hook / Author</th>
                  <th className="w-24 px-3 py-2 text-xs text-[#9090a8] font-medium text-right">Views</th>
                  <th className="w-16 px-3 py-2 text-xs text-[#9090a8] font-medium text-right">ER%</th>
                  <th className="w-24 px-3 py-2 text-xs text-[#9090a8] font-medium">Niche</th>
                  <th className="w-16 px-3 py-2 text-xs text-[#9090a8] font-medium">Region</th>
                  <th className="w-16 px-3 py-2 text-xs text-[#9090a8] font-medium">Indexed</th>
                </tr>
              </thead>
              <tbody>
                {videos.map(v => {
                  const selected = selectedIds.has(v.id)
                  return (
                    <tr
                      key={v.id}
                      onClick={() => toggleSelect(v.id)}
                      className={`border-t border-[#2a2a32] cursor-pointer transition-colors ${
                        selected ? 'bg-[#0f0f2a]' : 'hover:bg-[#1c1c22]'
                      }`}
                    >
                      <td className="px-3 py-2.5" onClick={e => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={() => toggleSelect(v.id)}
                          className="accent-[#7c6af7] w-3.5 h-3.5"
                        />
                      </td>
                      <td className="px-3 py-2.5">
                        <div className="text-[#e8e8f0] text-sm leading-snug line-clamp-1">
                          {v.hook_text || v.script_text?.slice(0, 80) || '—'}
                        </div>
                      </td>
                      <td className="px-3 py-2.5 text-right font-mono text-xs text-[#9090a8]">
                        {v.play_count ? (v.play_count >= 1000000 ? `${(v.play_count/1000000).toFixed(1)}M` : v.play_count >= 1000 ? `${(v.play_count/1000).toFixed(0)}K` : v.play_count) : '—'}
                      </td>
                      <td className="px-3 py-2.5 text-right font-mono text-xs text-[#9090a8]">
                        {v.engagement_rate ? `${v.engagement_rate.toFixed(1)}%` : '—'}
                      </td>
                      <td className="px-3 py-2.5">
                        {v.niche && <Badge status={v.niche} label={v.niche} />}
                      </td>
                      <td className="px-3 py-2.5 text-xs text-[#9090a8] font-mono">{v.region || '—'}</td>
                      <td className="px-3 py-2.5">
                        {v.is_indexed
                          ? <span className="text-[#34d399] text-xs">✓</span>
                          : <span className="text-[#5a5a70] text-xs">—</span>
                        }
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* ── Source Manager Modal ── */}
      <Modal
        open={srcModalOpen}
        onClose={() => setSrcModalOpen(false)}
        title="Manage Scraper Sources"
        footer={<Button variant="ghost" onClick={() => setSrcModalOpen(false)}>Close</Button>}
      >
        <div className="flex flex-col gap-3">
          {sources.map(s => (
            <div key={s.id} className="flex items-center gap-3 bg-[#16161a] border border-[#2a2a32] rounded-xl p-3">
              <StatusDot status={s.status} />
              <div className="flex-1">
                <div className="text-sm font-medium text-[#e8e8f0]">{s.name}</div>
                <div className="text-xs text-[#9090a8] font-mono">{s.type} · {s.module || 'not configured'}</div>
              </div>
              <Select
                value={s.status}
                onChange={e => handleUpdateStatus(s.id, e.target.value)}
                options={['active', 'standby', 'planned'].map(v => ({ value: v, label: v }))}
              />
              {s.status === 'active' && (
                <Button
                  variant="accent"
                  size="sm"
                  loading={updatingSrc === s.id || scraping}
                  onClick={() => handleRunScrape(s.id)}
                >
                  Run
                </Button>
              )}
            </div>
          ))}
          <div className="text-xs text-[#5a5a70] text-center pt-2">
            New source types (YouTube, VnExpress) — coming in future releases
          </div>
        </div>
      </Modal>

      {/* ── Topic Creation Modal ── */}
      <Modal
        open={topicModalOpen}
        onClose={() => setTopicModalOpen(false)}
        title={`Create Script from ${selectedIds.size} Video${selectedIds.size !== 1 ? 's' : ''}`}
        footer={
          <>
            <Button variant="ghost" onClick={() => setTopicModalOpen(false)}>Cancel</Button>
            <Button
              variant="primary"
              loading={generating}
              disabled={!newTopic || !newNiche}
              onClick={handleGenerate}
            >
              Generate Script with LLM
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          {/* Selected video preview */}
          <div>
            <div className="text-xs text-[#9090a8] mb-2 font-medium">Using as RAG context:</div>
            <div className="flex flex-wrap gap-1.5">
              {[...selectedIds].slice(0, 6).map(id => {
                const v = videos.find(x => x.id === id)
                return (
                  <span key={id} className="text-xs bg-[#16161a] border border-[#2a2a32] rounded-md px-2 py-1 text-[#9090a8] max-w-[200px] truncate">
                    {v?.hook_text?.slice(0, 40) || id}
                  </span>
                )
              })}
              {selectedIds.size > 6 && (
                <span className="text-xs text-[#5a5a70]">+{selectedIds.size - 6} more</span>
              )}
            </div>
          </div>

          <Input
            label="Topic *"
            value={newTopic}
            onChange={e => setNewTopic(e.target.value)}
            placeholder="e.g. 5 thói quen buổi sáng lành mạnh"
            autoFocus
          />
          <Select
            label="Niche *"
            value={newNiche}
            onChange={e => setNewNiche(e.target.value)}
            placeholder="Select a niche"
            options={NICHES.map(n => ({ value: n, label: n }))}
          />
          <Select
            label="Template"
            value={newTemplate}
            onChange={e => setNewTemplate(e.target.value)}
            options={TEMPLATES.map(t => ({ value: t, label: t }))}
          />
        </div>
      </Modal>

      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  )
}
