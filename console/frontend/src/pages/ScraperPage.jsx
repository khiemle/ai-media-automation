import { useState, useRef, useEffect } from 'react'
import { scraperApi, scriptsApi } from '../api/client.js'
import { useApi } from '../hooks/useApi.js'
import { Card, Badge, Button, StatBox, Modal, Select, Input, Toast, Spinner, EmptyState } from '../components/index.jsx'
import NicheCombobox from '../components/NicheCombobox.jsx'

const REGIONS   = ['VN', 'US', 'UK', 'TH', 'ID']
const TEMPLATES = ['tiktok_viral', 'tiktok_30s', 'youtube_clean', 'shorts_hook']
const LANGUAGES = ['vietnamese', 'english']
const NEWS_SOURCES = ['news_vnexpress', 'news_tinhte', 'news_cnn']

function StatusDot({ status }) {
  const colors = { active: '#34d399', standby: '#fbbf24', planned: '#5a5a70' }
  return <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: colors[status] || '#5a5a70' }} />
}

export default function ScraperPage() {
  const [artSourceFilter, setArtSourceFilter] = useState('')
  const [artLangFilter,   setArtLangFilter]   = useState('')
  const [expandedArticle, setExpandedArticle] = useState(null)

  const { data: sourcesData, loading: srcLoading, refetch: refetchSources } = useApi(
    () => scraperApi.getSources(), []
  )
  const { data: articlesData, loading: artLoading, refetch: refetchArticles } = useApi(
    () => scraperApi.getArticles({ source: artSourceFilter, language: artLangFilter, per_page: 100 }),
    [artSourceFilter, artLangFilter]
  )

  const sources  = sourcesData || []
  const articles = articlesData?.items || []
  const totalArt = articlesData?.total || 0
  const activeSrc = sources.filter(s => s.status === 'active').length

  // ── Source manager modal ───────────────────────────────────────────────────
  const [srcModalOpen, setSrcModalOpen] = useState(false)
  const [updatingSrc,  setUpdatingSrc]  = useState(null)

  const handleUpdateStatus = async (sourceId, status) => {
    setUpdatingSrc(sourceId)
    try {
      await scraperApi.updateSourceStatus(sourceId, status)
      refetchSources()
    } catch (e) { showToast(e.message, 'error') }
    finally { setUpdatingSrc(null) }
  }

  // ── Manual scrape + live log panel ────────────────────────────────────────
  const [scraping,   setScraping]   = useState(false)
  const [scrapingId, setScrapingId] = useState(null)
  const [activeTask, setActiveTask] = useState(null)
  const pollRef   = useRef(null)
  const logBoxRef = useRef(null)

  useEffect(() => {
    if (logBoxRef.current) logBoxRef.current.scrollTop = logBoxRef.current.scrollHeight
  }, [activeTask?.logs?.length])

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  const _stopPolling = () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null } }

  const _startPolling = (task_id, sourceId) => {
    _stopPolling()
    setActiveTask({ task_id, source_id: sourceId, state: 'PENDING', step: null, logs: [], count: null, error: null })
    pollRef.current = setInterval(async () => {
      try {
        const status = await scraperApi.getTaskStatus(task_id)
        setActiveTask(prev => ({ ...prev, ...status }))
        if (status.state === 'SUCCESS') {
          _stopPolling()
          showToast(`Scraped ${status.count ?? 0} item(s) saved`, 'success')
          refetchSources()
          setTimeout(() => refetchArticles(), 800)
        } else if (status.state === 'FAILURE') {
          _stopPolling()
          showToast(`Scrape failed: ${status.error}`, 'error')
        }
      } catch (_) {}
    }, 2000)
  }

  const handleRunScrape = async (sourceId) => {
    setScraping(true); setScrapingId(sourceId)
    try {
      const res = await scraperApi.triggerScrape(sourceId)
      _startPolling(res.task_id, sourceId)
      showToast('Scrape queued — watching logs below', 'info')
    } catch (e) { showToast(e.message, 'error') }
    finally { setScraping(false); setScrapingId(null) }
  }

  // ── Scrape from URL modal ─────────────────────────────────────────────────
  const [urlModalOpen, setUrlModalOpen] = useState(false)
  const [scrapeUrl,    setScrapeUrl]    = useState('')
  const [scrapingUrl,  setScrapingUrl]  = useState(false)

  const handleScrapeUrl = async () => {
    if (!scrapeUrl.trim()) return
    setScrapingUrl(true)
    try {
      const article = await scraperApi.scrapeFromUrl(scrapeUrl.trim())
      showToast(`Article saved: "${article.title.slice(0, 50)}..."`, 'success')
      setUrlModalOpen(false); setScrapeUrl('')
      refetchArticles()
    } catch (e) { showToast(e.message, 'error') }
    finally { setScrapingUrl(false) }
  }

  // ── Script generation modal ───────────────────────────────────────────────
  const [genModalOpen, setGenModalOpen] = useState(false)
  const [genArticle,   setGenArticle]   = useState(null)
  const [newTopic,     setNewTopic]     = useState('')
  const [newNiche,     setNewNiche]     = useState('')
  const [newTemplate,  setNewTemplate]  = useState('tiktok_viral')
  const [newLanguage,  setNewLanguage]  = useState('vietnamese')
  const [generating,   setGenerating]   = useState(false)

  const openGenFromArticle = (article) => {
    setGenArticle(article)
    setNewTopic(article.title)
    setNewLanguage(article.language || 'vietnamese')
    setGenModalOpen(true)
  }

  const handleGenerate = async () => {
    if (!newTopic || !newNiche) return
    setGenerating(true)
    try {
      await scriptsApi.generate({
        topic: newTopic,
        niche: newNiche,
        template: newTemplate,
        language: newLanguage,
        source_article_id: genArticle ? genArticle.id : null,
      })
      setGenModalOpen(false); setGenArticle(null); setNewTopic('')
      showToast('Script queued — check the Scripts tab', 'success')
    } catch (e) { showToast(e.message, 'error') }
    finally { setGenerating(false) }
  }

  // ── Toast ──────────────────────────────────────────────────────────────────
  const [toast, setToast] = useState(null)
  const showToast = (msg, type = 'success') => { setToast({ message: msg, type }); setTimeout(() => setToast(null), 3500) }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#e8e8f0]">Scraper</h1>
          <p className="text-sm text-[#9090a8] mt-0.5">Browse and curate scraped news articles</p>
        </div>
        <Button variant="ghost" size="md" onClick={() => setSrcModalOpen(true)}>Manage Sources</Button>
      </div>

      <div className="flex gap-3 flex-wrap">
        <StatBox label="Articles"       value={totalArt.toLocaleString()} />
        <StatBox label="Active Sources" value={activeSrc} />
      </div>

      <Card
        title="News Articles"
        actions={
          <div className="flex gap-2">
            <Select value={artSourceFilter} onChange={e => setArtSourceFilter(e.target.value)} placeholder="All Sources"
              options={sources.filter(s => s.type === 'news').map(s => ({ value: s.id, label: s.name }))} />
            <Select value={artLangFilter} onChange={e => setArtLangFilter(e.target.value)} placeholder="All Languages"
              options={LANGUAGES.map(l => ({ value: l, label: l }))} />
            <Button variant="ghost" size="sm" onClick={() => setUrlModalOpen(true)}>+ Scrape URL</Button>
          </div>
        }
      >
        {artLoading ? (
          <div className="flex justify-center py-12"><Spinner size={28} /></div>
        ) : articles.length === 0 ? (
          <EmptyState icon="📰" title="No articles yet"
            description="Run a news scrape from Manage Sources, or paste a URL with + Scrape URL." />
        ) : (
          <div className="overflow-y-auto max-h-[500px] rounded-lg border border-[#2a2a32]">
            <table className="w-full text-sm border-collapse">
              <thead className="sticky top-0 bg-[#16161a] z-10">
                <tr className="text-left">
                  <th className="px-3 py-2 text-xs text-[#9090a8] font-medium">Title</th>
                  <th className="w-28 px-3 py-2 text-xs text-[#9090a8] font-medium">Source</th>
                  <th className="w-24 px-3 py-2 text-xs text-[#9090a8] font-medium">Language</th>
                  <th className="w-32 px-3 py-2 text-xs text-[#9090a8] font-medium">Date</th>
                  <th className="w-28 px-3 py-2 text-xs text-[#9090a8] font-medium text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {articles.map(a => {
                  const isExpanded = expandedArticle === a.id
                  return (
                    <>
                      <tr key={a.id} onClick={() => setExpandedArticle(isExpanded ? null : a.id)}
                        className="border-t border-[#2a2a32] hover:bg-[#1c1c22] transition-colors cursor-pointer">
                        <td className="px-3 py-2.5">
                          <div className="flex items-center gap-1.5">
                            <span className="text-[#5a5a70] text-xs w-3 flex-shrink-0">{isExpanded ? '▾' : '▸'}</span>
                            <div>
                              <div className="text-[#e8e8f0] text-sm line-clamp-1">{a.title}</div>
                              {a.author && <div className="text-xs text-[#5a5a70] mt-0.5">{a.author}</div>}
                            </div>
                          </div>
                        </td>
                        <td className="px-3 py-2.5"><span className="text-xs font-mono text-[#9090a8]">{a.source}</span></td>
                        <td className="px-3 py-2.5">
                          <Badge label={a.language === 'english' ? 'EN' : 'VI'} status={a.language === 'english' ? 'info' : 'success'} />
                        </td>
                        <td className="px-3 py-2.5 text-xs text-[#5a5a70] font-mono">
                          {a.published_at ? new Date(a.published_at).toLocaleDateString() : new Date(a.scraped_at).toLocaleDateString()}
                        </td>
                        <td className="px-3 py-2.5 text-right" onClick={e => e.stopPropagation()}>
                          <Button variant="primary" size="sm" onClick={() => openGenFromArticle(a)}>→ Script</Button>
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr key={`${a.id}-content`} className="border-t border-[#2a2a32] bg-[#111116]">
                          <td colSpan={5} className="px-4 py-3">
                            {a.tags?.length > 0 && (
                              <div className="flex flex-wrap gap-1 mb-2">
                                {a.tags.map(t => (
                                  <span key={t} className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-[#1c1c22] text-[#9090a8] border border-[#2a2a32]">{t}</span>
                                ))}
                              </div>
                            )}
                            {a.main_content
                              ? <p className="text-xs text-[#9090a8] leading-relaxed whitespace-pre-wrap">{a.main_content}</p>
                              : <p className="text-xs text-[#5a5a70] italic">No content available</p>}
                            {a.url && (
                              <a href={a.url} target="_blank" rel="noopener noreferrer"
                                className="inline-block mt-2 text-[10px] font-mono text-[#7c6af7] hover:underline"
                                onClick={e => e.stopPropagation()}>{a.url}</a>
                            )}
                          </td>
                        </tr>
                      )}
                    </>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Source Manager Modal */}
      <Modal open={srcModalOpen} onClose={() => setSrcModalOpen(false)} title="Manage Scraper Sources"
        footer={<Button variant="ghost" onClick={() => setSrcModalOpen(false)}>Close</Button>}>
        <div className="flex flex-col gap-3">
          {sources.map(s => (
            <div key={s.id} className="flex items-center gap-3 bg-[#16161a] border border-[#2a2a32] rounded-xl p-3">
              <StatusDot status={s.status} />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-[#e8e8f0]">{s.name}</div>
                <div className="text-xs text-[#9090a8] font-mono truncate">{s.type} · {s.language || '—'} · {s.module || 'not configured'}</div>
              </div>
              <Select value={s.status} onChange={e => handleUpdateStatus(s.id, e.target.value)}
                options={['active', 'standby', 'planned'].map(v => ({ value: v, label: v }))} />
              {s.status !== 'planned' && s.module && (
                <Button variant="accent" size="sm"
                  loading={scrapingId === s.id && scraping}
                  disabled={activeTask && ['PENDING','PROGRESS'].includes(activeTask.state)}
                  onClick={() => handleRunScrape(s.id)}>Run</Button>
              )}
            </div>
          ))}
          {activeTask && (
            <div className="mt-1 border border-[#2a2a32] rounded-xl overflow-hidden">
              <div className="flex items-center justify-between px-3 py-2 bg-[#1c1c22] border-b border-[#2a2a32]">
                <div className="flex items-center gap-2 min-w-0">
                  {['PENDING','PROGRESS'].includes(activeTask.state) && <Spinner size={13} />}
                  {activeTask.state === 'SUCCESS' && <span className="text-[#34d399] text-xs">✓</span>}
                  {activeTask.state === 'FAILURE' && <span className="text-[#f87171] text-xs">✕</span>}
                  <span className="text-xs font-mono text-[#9090a8] truncate">{activeTask.source_id || '…'} · {activeTask.step || activeTask.state}</span>
                  {activeTask.count != null && <span className="text-xs font-mono text-[#34d399] ml-1">{activeTask.count} saved</span>}
                  {activeTask.state === 'FAILURE' && activeTask.error && <span className="text-xs text-[#f87171] truncate ml-1">{activeTask.error}</span>}
                </div>
                <button onClick={() => { _stopPolling(); setActiveTask(null) }}
                  className="text-[#5a5a70] hover:text-[#9090a8] text-sm leading-none ml-2 flex-shrink-0">✕</button>
              </div>
              <div ref={logBoxRef} className="bg-[#0d0d0f] px-3 py-2.5 max-h-52 overflow-y-auto font-mono text-xs leading-5 space-y-0.5">
                {activeTask.logs.length === 0
                  ? <span className="text-[#5a5a70]">Waiting for worker…</span>
                  : activeTask.logs.map((l, i) => (
                    <div key={i} className="flex gap-1.5">
                      <span className="text-[#5a5a70] flex-shrink-0">{l.ts ? l.ts.slice(11, 19) : ''}</span>
                      <span className={`flex-shrink-0 ${l.level === 'ERROR' ? 'text-[#f87171]' : l.level === 'WARNING' ? 'text-[#fbbf24]' : 'text-[#34d399]'}`}>[{l.level}]</span>
                      <span className={l.level === 'ERROR' ? 'text-[#f87171]' : l.level === 'WARNING' ? 'text-[#fbbf24]' : 'text-[#9090a8]'}>{l.msg}</span>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>
      </Modal>

      {/* Scrape URL Modal */}
      <Modal open={urlModalOpen} onClose={() => { setUrlModalOpen(false); setScrapeUrl('') }} title="Scrape Article from URL"
        footer={
          <>
            <Button variant="ghost" onClick={() => { setUrlModalOpen(false); setScrapeUrl('') }}>Cancel</Button>
            <Button variant="primary" loading={scrapingUrl} disabled={!scrapeUrl.trim()} onClick={handleScrapeUrl}>Scrape & Save</Button>
          </>
        }>
        <div className="flex flex-col gap-3">
          <p className="text-sm text-[#9090a8]">Paste a URL from vnexpress.net, tinhte.vn, or edition.cnn.com.</p>
          <Input label="Article URL" value={scrapeUrl} onChange={e => setScrapeUrl(e.target.value)}
            placeholder="https://vnexpress.net/..." autoFocus />
        </div>
      </Modal>

      {/* Generate Script Modal */}
      <Modal open={genModalOpen} onClose={() => { setGenModalOpen(false); setGenArticle(null) }}
        title="Generate Script from Article"
        footer={
          <>
            <Button variant="ghost" onClick={() => { setGenModalOpen(false); setGenArticle(null) }}>Cancel</Button>
            <Button variant="primary" loading={generating} disabled={!newTopic || !newNiche} onClick={handleGenerate}>Generate with LLM</Button>
          </>
        }>
        <div className="flex flex-col gap-4">
          {genArticle && (
            <div className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-2 text-xs text-[#9090a8]">
              <span className="font-medium text-[#e8e8f0]">Source: </span>{genArticle.source} · {genArticle.language}
              <div className="mt-1 line-clamp-2 text-[#5a5a70]">{genArticle.title}</div>
            </div>
          )}
          <Input label="Topic *" value={newTopic} onChange={e => setNewTopic(e.target.value)}
            placeholder="e.g. Article headline or custom topic" autoFocus />
          <NicheCombobox label="Niche *" value={newNiche} onChange={setNewNiche} />
          <Select label="Template" value={newTemplate} onChange={e => setNewTemplate(e.target.value)}
            options={TEMPLATES.map(t => ({ value: t, label: t }))} />
          <Select label="Language" value={newLanguage} onChange={e => setNewLanguage(e.target.value)}
            options={LANGUAGES.map(l => ({ value: l, label: l }))} />
        </div>
      </Modal>

      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  )
}
