# Console Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the management console: remove obsolete Videos/TikTok features, add Niches tab, add Composer page, enrich Production + Pipeline pages, simplify LLM tab to Gemini-only.

**Architecture:** Thin FastAPI backend + React 18 SPA. New features follow existing patterns: SQLAlchemy `Mapped` models, Alembic migrations, dependency-injected routers, Tailwind dark-theme components. All heavy work goes via Celery; lightweight Gemini calls (expand) run inline.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 · Alembic · Celery + Redis · React 18 + Vite · Tailwind CSS · `google-genai` SDK

---

## Task 1: Remove scraper videos — backend

**Files:**
- Modify: `console/backend/routers/scraper.py`
- Modify: `console/backend/services/scraper_service.py`
- Modify: `console/backend/schemas/scraper.py`

- [ ] **Step 1: Delete the `/videos` endpoint from the router**

In `console/backend/routers/scraper.py`, remove the entire `list_videos` function (lines 66–86 in the current file). Also remove `ScrapedVideoResponse` from the import block at the top.

The import block should become:
```python
from console.backend.schemas.scraper import (
    ScraperSourceResponse,
    ScraperSourceStatusUpdate,
    ScrapedArticleResponse,
    ScrapeUrlRequest,
    TriggerScrapeRequest,
    ScraperTaskStatus,
)
```

- [ ] **Step 2: Remove `list_videos` from ScraperService**

In `console/backend/services/scraper_service.py`, find and delete the `list_videos()` method. Also remove `ScrapedVideoResponse` from the import at the top of the file.

- [ ] **Step 3: Verify the server still starts**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
uvicorn console.backend.main:app --port 8080 --reload &
sleep 3
curl -s http://localhost:8080/api/health | python3 -m json.tool
kill %1
```
Expected: `{"status": "ok", ...}`

- [ ] **Step 4: Commit**

```bash
git add console/backend/routers/scraper.py console/backend/services/scraper_service.py console/backend/schemas/scraper.py
git commit -m "feat: remove scraper videos endpoint (videos no longer available)"
```

---

## Task 2: Remove scraper videos — frontend

**Files:**
- Modify: `console/frontend/src/api/client.js`
- Modify: `console/frontend/src/pages/ScraperPage.jsx`

- [ ] **Step 1: Remove video API methods from client.js**

In `console/frontend/src/api/client.js`, inside `scraperApi`, delete the `getVideos` and `indexVideos` entries. The `scraperApi` object should be:
```js
export const scraperApi = {
  getSources: () => fetchApi('/api/scraper/sources'),
  updateSourceStatus: (id, status) =>
    fetchApi(`/api/scraper/sources/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  triggerScrape: (source_id) =>
    fetchApi('/api/scraper/run', { method: 'POST', body: JSON.stringify({ source_id }) }),
  getTaskStatus: (task_id) => fetchApi(`/api/scraper/tasks/${task_id}`),
  getArticles: (params = {}) => {
    const q = new URLSearchParams(Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== '')))
    return fetchApi(`/api/scraper/articles?${q}`)
  },
  scrapeFromUrl: (url) =>
    fetchApi('/api/scraper/articles/from-url', { method: 'POST', body: JSON.stringify({ url }) }),
}
```

- [ ] **Step 2: Rewrite ScraperPage.jsx — remove Videos tab entirely**

Replace the full contents of `console/frontend/src/pages/ScraperPage.jsx` with:

```jsx
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
```

- [ ] **Step 3: Verify frontend compiles**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/frontend
npm run build 2>&1 | tail -20
```
Expected: no errors (NicheCombobox import will fail until Task 6 — that's OK, fix after Task 6).

- [ ] **Step 4: Commit**

```bash
git add console/frontend/src/api/client.js console/frontend/src/pages/ScraperPage.jsx
git commit -m "feat: scraper page articles-only, remove videos tab and ChromaDB UI"
```

---

## Task 3: Remove TikTok/YouTube scraper files + YAML

**Files:**
- Modify: `config/scraper_sources.yaml`
- Delete: `scraper/tiktok_research_api.py`, `scraper/tiktok_playwright.py`, `scraper/tiktok_selenium.py`, `scraper/tiktok_browser_common.py`, `scraper/apify_scraper.py`

- [ ] **Step 1: Update scraper_sources.yaml**

Replace the full contents of `config/scraper_sources.yaml` with:
```yaml
sources:
- function: scrape_homepage
  id: news_vnexpress
  language: vietnamese
  module: scraper.vnexpress_scraper
  name: VnExpress News
  status: standby
  type: news
- function: scrape_homepage
  id: news_tinhte
  language: vietnamese
  module: scraper.tinhte_scraper
  name: Tinhte News
  status: standby
  type: news
- function: scrape_homepage
  id: news_cnn
  language: english
  module: scraper.cnn_scraper
  name: CNN News
  status: active
  type: news
```

- [ ] **Step 2: Delete TikTok/Apify scraper files**

```bash
rm /Volumes/SSD/Workspace/ai-media-automation/scraper/tiktok_research_api.py
rm /Volumes/SSD/Workspace/ai-media-automation/scraper/tiktok_playwright.py
rm /Volumes/SSD/Workspace/ai-media-automation/scraper/tiktok_selenium.py
rm /Volumes/SSD/Workspace/ai-media-automation/scraper/tiktok_browser_common.py
rm /Volumes/SSD/Workspace/ai-media-automation/scraper/apify_scraper.py
```

- [ ] **Step 3: Check scraper/main.py for any TikTok imports to clean up**

```bash
grep -n "tiktok\|apify\|playwright\|selenium" /Volumes/SSD/Workspace/ai-media-automation/scraper/main.py
```

Remove any lines that import the deleted modules. If `scraper/main.py` imports them, replace those imports with pass or remove the import blocks.

- [ ] **Step 4: Commit**

```bash
git add config/scraper_sources.yaml scraper/
git commit -m "feat: remove TikTok/YouTube scraper sources and files"
```

---

## Task 4: Niches — DB migration + SQLAlchemy model

**Files:**
- Create: `console/backend/models/niche.py`
- Create: `console/backend/alembic/versions/005_niches.py`

- [ ] **Step 1: Create the SQLAlchemy model**

Create `console/backend/models/niche.py`:
```python
from datetime import datetime
from sqlalchemy import Integer, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from console.backend.database import Base


class Niche(Base):
    __tablename__ = "niches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: Create the Alembic migration**

Create `console/backend/alembic/versions/005_niches.py`:
```python
"""Add niches table

Revision ID: 005
Revises: 004
Create Date: 2026-04-26
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEED_NICHES = ["beauty", "education", "finance", "fitness", "food", "lifestyle", "tech"]


def upgrade() -> None:
    op.create_table(
        "niches",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_niches_name", "niches", ["name"])

    # Seed default niches
    op.execute(
        sa.text("INSERT INTO niches (name) VALUES " +
                ", ".join(f"('{n}')" for n in SEED_NICHES))
    )


def downgrade() -> None:
    op.drop_index("idx_niches_name", table_name="niches")
    op.drop_table("niches")
```

- [ ] **Step 3: Run the migration**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/backend
alembic upgrade head
```
Expected: `Running upgrade 004 -> 005, Add niches table`

- [ ] **Step 4: Verify seeded data**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/backend
python3 -c "
from database_check import *
" 2>/dev/null || python3 -c "
import sys; sys.path.insert(0, '../../')
from console.backend.database import SessionLocal
from console.backend.models.niche import Niche
db = SessionLocal()
niches = db.query(Niche).order_by(Niche.name).all()
print([n.name for n in niches])
db.close()
"
```
Expected: `['beauty', 'education', 'finance', 'fitness', 'food', 'lifestyle', 'tech']`

- [ ] **Step 5: Commit**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
git add console/backend/models/niche.py console/backend/alembic/versions/005_niches.py
git commit -m "feat: add niches table with seeded defaults"
```

---

## Task 5: Niches — service, router, main.py, client.js

**Files:**
- Create: `console/backend/services/niche_service.py`
- Create: `console/backend/routers/niches.py`
- Modify: `console/backend/main.py`
- Modify: `console/frontend/src/api/client.js`

- [ ] **Step 1: Create niche_service.py**

Create `console/backend/services/niche_service.py`:
```python
"""NicheService — CRUD for the niches table."""
import math
from sqlalchemy.orm import Session
from console.backend.models.niche import Niche
from console.backend.models.audit_log import AuditLog


def _audit(db, user_id, action, name):
    db.add(AuditLog(user_id=user_id, action=action, target_type="niche", target_id=name))


class NicheService:
    def __init__(self, db: Session):
        self.db = db

    def list_niches(self) -> list[dict]:
        """Return all niches with script_count."""
        try:
            from database.models import GeneratedScript
            rows = self.db.query(Niche).order_by(Niche.name).all()
            result = []
            for n in rows:
                count = self.db.query(GeneratedScript).filter(GeneratedScript.niche == n.name).count()
                result.append({"id": n.id, "name": n.name, "script_count": count, "created_at": n.created_at.isoformat() if n.created_at else None})
            return result
        except Exception:
            rows = self.db.query(Niche).order_by(Niche.name).all()
            return [{"id": n.id, "name": n.name, "script_count": 0, "created_at": n.created_at.isoformat() if n.created_at else None} for n in rows]

    def create_niche(self, name: str, user_id: int) -> dict:
        name = name.strip()
        if not name:
            raise ValueError("Niche name cannot be empty")
        existing = self.db.query(Niche).filter(Niche.name == name).first()
        if existing:
            raise ValueError(f"Niche '{name}' already exists")
        niche = Niche(name=name)
        self.db.add(niche)
        _audit(self.db, user_id, "create_niche", name)
        self.db.commit()
        self.db.refresh(niche)
        return {"id": niche.id, "name": niche.name, "script_count": 0, "created_at": niche.created_at.isoformat() if niche.created_at else None}

    def delete_niche(self, niche_id: int, user_id: int) -> None:
        niche = self.db.query(Niche).filter(Niche.id == niche_id).first()
        if not niche:
            raise KeyError(f"Niche {niche_id} not found")
        try:
            from database.models import GeneratedScript
            count = self.db.query(GeneratedScript).filter(GeneratedScript.niche == niche.name).count()
            if count > 0:
                raise ValueError(f"Cannot delete '{niche.name}' — used by {count} script(s)")
        except ImportError:
            pass
        _audit(self.db, user_id, "delete_niche", niche.name)
        self.db.delete(niche)
        self.db.commit()

    def get_or_create(self, name: str, user_id: int) -> dict:
        name = name.strip()
        existing = self.db.query(Niche).filter(Niche.name == name).first()
        if existing:
            return {"id": existing.id, "name": existing.name}
        return self.create_niche(name, user_id)
```

- [ ] **Step 2: Create niches router**

Create `console/backend/routers/niches.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from console.backend.auth import require_admin, require_editor_or_admin, get_current_user
from console.backend.database import get_db
from console.backend.services.niche_service import NicheService

router = APIRouter(prefix="/niches", tags=["niches"])


class CreateNicheBody(BaseModel):
    name: str


@router.get("")
def list_niches(
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return NicheService(db).list_niches()


@router.post("", status_code=201)
def create_niche(
    body: CreateNicheBody,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    try:
        return NicheService(db).create_niche(body.name, user.id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/{niche_id}", status_code=204)
def delete_niche(
    niche_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    try:
        NicheService(db).delete_niche(niche_id, user.id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
```

- [ ] **Step 3: Register niches router in main.py**

In `console/backend/main.py`, inside `register_routers()`, add after `app.include_router(scripts.router, prefix="/api")`:
```python
    try:
        from console.backend.routers import niches
        app.include_router(niches.router, prefix="/api")
    except ImportError:
        pass
```

- [ ] **Step 4: Add nichesApi to client.js**

In `console/frontend/src/api/client.js`, add after the `scriptsApi` block:
```js
// ── Niches ─────────────────────────────────────────────────────────────────────
export const nichesApi = {
  list: () => fetchApi('/api/niches'),
  create: (name) => fetchApi('/api/niches', { method: 'POST', body: JSON.stringify({ name }) }),
  remove: (id) => fetchApi(`/api/niches/${id}`, { method: 'DELETE' }),
}
```

- [ ] **Step 5: Verify endpoint works**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
uvicorn console.backend.main:app --port 8080 &
sleep 3
# Login first to get a token, then:
TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null || echo "")
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/niches | python3 -m json.tool | head -20
kill %1
```
Expected: JSON array with `beauty`, `education`, etc.

- [ ] **Step 6: Commit**

```bash
git add console/backend/services/niche_service.py console/backend/routers/niches.py console/backend/main.py console/frontend/src/api/client.js
git commit -m "feat: niches CRUD backend (service, router, client)"
```

---

## Task 6: NicheCombobox shared component

**Files:**
- Create: `console/frontend/src/components/NicheCombobox.jsx`

- [ ] **Step 1: Create NicheCombobox.jsx**

Create `console/frontend/src/components/NicheCombobox.jsx`:
```jsx
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
      // If already exists (race), just select it
      select(name)
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
```

- [ ] **Step 2: Verify frontend builds (NicheCombobox is now available)**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/frontend
npm run build 2>&1 | grep -E "error|warning|built" | tail -10
```
Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add console/frontend/src/components/NicheCombobox.jsx
git commit -m "feat: NicheCombobox shared component with inline add"
```

---

## Task 7: NichesPage

**Files:**
- Create: `console/frontend/src/pages/NichesPage.jsx`

- [ ] **Step 1: Create NichesPage.jsx**

Create `console/frontend/src/pages/NichesPage.jsx`:
```jsx
import { useState } from 'react'
import { nichesApi } from '../api/client.js'
import { useApi } from '../hooks/useApi.js'
import { Card, Button, StatBox, Modal, Input, Toast, Spinner, EmptyState } from '../components/index.jsx'

export default function NichesPage() {
  const { data, loading, refetch } = useApi(() => nichesApi.list(), [])
  const niches = data || []

  const [addOpen,   setAddOpen]   = useState(false)
  const [newName,   setNewName]   = useState('')
  const [saving,    setSaving]    = useState(false)
  const [deletingId,setDeletingId]= useState(null)
  const [toast,     setToast]     = useState(null)

  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000) }

  const handleAdd = async () => {
    const name = newName.trim()
    if (!name) return
    if (niches.some(n => n.name.toLowerCase() === name.toLowerCase())) {
      showToast('Niche already exists', 'error'); return
    }
    setSaving(true)
    try {
      await nichesApi.create(name)
      refetch()
      setAddOpen(false); setNewName('')
      showToast(`Niche "${name}" added`)
    } catch (e) { showToast(e.message, 'error') }
    finally { setSaving(false) }
  }

  const handleDelete = async (niche) => {
    if (niche.script_count > 0) return
    setDeletingId(niche.id)
    try {
      await nichesApi.remove(niche.id)
      refetch()
      showToast(`Niche "${niche.name}" deleted`)
    } catch (e) { showToast(e.message, 'error') }
    finally { setDeletingId(null) }
  }

  const mostUsed = niches.length ? niches.reduce((a, b) => a.script_count > b.script_count ? a : b) : null

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#e8e8f0]">Niches</h1>
          <p className="text-sm text-[#9090a8] mt-0.5">Manage content niches used across scripts</p>
        </div>
        <Button variant="primary" onClick={() => setAddOpen(true)}>+ Add Niche</Button>
      </div>

      <div className="flex gap-3 flex-wrap">
        <StatBox label="Total Niches" value={niches.length} />
        <StatBox label="Most Used" value={mostUsed?.name || '—'} sub={mostUsed ? `${mostUsed.script_count} scripts` : ''} />
      </div>

      <Card title="All Niches">
        {loading ? (
          <div className="flex justify-center py-12"><Spinner size={28} /></div>
        ) : niches.length === 0 ? (
          <EmptyState icon="🏷️" title="No niches yet" description="Add your first niche above." />
        ) : (
          <div className="rounded-lg border border-[#2a2a32] overflow-hidden">
            <table className="w-full text-sm border-collapse">
              <thead className="bg-[#16161a]">
                <tr className="text-left">
                  <th className="px-4 py-2 text-xs text-[#9090a8] font-medium">Name</th>
                  <th className="w-32 px-4 py-2 text-xs text-[#9090a8] font-medium text-right">Scripts</th>
                  <th className="w-24 px-4 py-2 text-xs text-[#9090a8] font-medium text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {niches.map(n => (
                  <tr key={n.id} className="border-t border-[#2a2a32] hover:bg-[#1c1c22] transition-colors">
                    <td className="px-4 py-3">
                      <span className="text-[#e8e8f0] font-medium">{n.name}</span>
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-xs text-[#9090a8]">{n.script_count}</td>
                    <td className="px-4 py-3 text-right">
                      <Button
                        variant="danger" size="sm"
                        disabled={n.script_count > 0 || deletingId === n.id}
                        loading={deletingId === n.id}
                        onClick={() => handleDelete(n)}
                        title={n.script_count > 0 ? `Used by ${n.script_count} script(s)` : 'Delete'}
                      >
                        Delete
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Modal open={addOpen} onClose={() => { setAddOpen(false); setNewName('') }} title="Add Niche"
        footer={
          <>
            <Button variant="ghost" onClick={() => { setAddOpen(false); setNewName('') }}>Cancel</Button>
            <Button variant="primary" loading={saving} disabled={!newName.trim()} onClick={handleAdd}>Save</Button>
          </>
        }>
        <Input label="Niche Name" value={newName} onChange={e => setNewName(e.target.value)}
          placeholder="e.g. gaming" autoFocus
          onKeyDown={e => e.key === 'Enter' && handleAdd()} />
      </Modal>

      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add console/frontend/src/pages/NichesPage.jsx
git commit -m "feat: NichesPage — list, add, delete niches"
```

---

## Task 8: App.jsx — add Niches + Composer tabs

**Files:**
- Modify: `console/frontend/src/App.jsx`

- [ ] **Step 1: Add imports and tab definitions**

In `console/frontend/src/App.jsx`:

1. Add imports at the top (after existing page imports):
```js
import NichesPage from './pages/NichesPage.jsx'
import ComposerPage from './pages/ComposerPage.jsx'
```

2. Add icons to the `Icons` object (after the existing icon definitions):
```js
  Niches: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/>
    </svg>
  ),
  Composer: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
    </svg>
  ),
```

3. Replace `ALL_TABS` with:
```js
const ALL_TABS = [
  { id: 'niches',     label: 'Niches',     Icon: Icons.Niches,     roles: ['admin', 'editor'] },
  { id: 'composer',   label: 'Composer',   Icon: Icons.Composer,   roles: ['admin', 'editor'] },
  { id: 'scraper',    label: 'Scraper',    Icon: Icons.Scraper,    roles: ['admin', 'editor'] },
  { id: 'scripts',    label: 'Scripts',    Icon: Icons.Scripts,    roles: ['admin', 'editor'] },
  { id: 'production', label: 'Production', Icon: Icons.Production, roles: ['admin', 'editor'] },
  { id: 'uploads',    label: 'Uploads',    Icon: Icons.Uploads,    roles: ['admin', 'editor'] },
  { id: 'pipeline',   label: 'Pipeline',   Icon: Icons.Pipeline,   roles: ['admin', 'editor'] },
  { id: 'llm',        label: 'LLM',        Icon: Icons.LLM,        roles: ['admin'] },
  { id: 'performance',label: 'Performance',Icon: Icons.Performance,roles: ['admin', 'editor'] },
  { id: 'system',     label: 'System',     Icon: Icons.System,     roles: ['admin'] },
]
```

4. Also update the default active tab state to `'niches'`:
```js
const [activeTab, setTab] = useState('niches')
```

5. Add cases to `renderPage()`:
```js
      case 'niches':   return <NichesPage />
      case 'composer': return <ComposerPage />
```

- [ ] **Step 2: Verify build**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/frontend
npm run build 2>&1 | grep -E "error|built" | tail -5
```
Expected: builds OK (ComposerPage import fails until Task 10 — add a stub file first if needed).

- [ ] **Step 2a: Stub ComposerPage if Task 10 not yet done**

If the build fails because `ComposerPage.jsx` doesn't exist yet, create a stub:
```bash
cat > /Volumes/SSD/Workspace/ai-media-automation/console/frontend/src/pages/ComposerPage.jsx << 'EOF'
export default function ComposerPage() {
  return <div className="text-[#9090a8] p-6">Composer — coming soon</div>
}
EOF
```

- [ ] **Step 3: Commit**

```bash
git add console/frontend/src/App.jsx console/frontend/src/pages/ComposerPage.jsx
git commit -m "feat: add Niches and Composer tabs to navigation"
```

---

## Task 9: Composer — backend (schema + /expand endpoint + raw_content in service)

**Files:**
- Modify: `console/backend/schemas/script.py`
- Modify: `console/backend/services/script_service.py`
- Modify: `console/backend/routers/scripts.py`

- [ ] **Step 1: Extend ScriptGenerateRequest schema**

In `console/backend/schemas/script.py`, update `ScriptGenerateRequest`:
```python
class ScriptGenerateRequest(BaseModel):
    topic: str
    niche: str
    template: str
    language: str = "vietnamese"
    source_video_ids: list[str] | None = None
    source_article_id: int | None = None
    raw_content: str | None = None   # free-form text from Composer


class ExpandRequest(BaseModel):
    content: str


class ExpandResponse(BaseModel):
    expanded_outline: str
```

- [ ] **Step 2: Update generate_script in script_service.py to handle raw_content**

In `console/backend/services/script_service.py`, update the `generate_script` method signature and the content-fetching block:

Change the method signature to:
```python
    def generate_script(
        self,
        topic: str,
        niche: str,
        template: str,
        source_video_ids: list[str] | None,
        user_id: int,
        language: str = "vietnamese",
        source_article_id: int | None = None,
        raw_content: str | None = None,
    ) -> ScriptDetail:
```

After the `article_content` block (around line 191 in current file), add:
```python
        # Composer raw content overrides article lookup
        if raw_content and not article_content:
            article_content = raw_content
```

Also update the `_audit` call to include raw_content flag:
```python
        _audit(self.db, user_id, "generate_script", "script", "new", {
            "topic": topic,
            "source_article_id": source_article_id,
            "from_composer": bool(raw_content),
        })
```

- [ ] **Step 3: Add /expand endpoint and update /generate in scripts router**

In `console/backend/routers/scripts.py`:

Add to the import block:
```python
from console.backend.schemas.script import (
    ScriptListItem,
    ScriptDetail,
    ScriptUpdate,
    ScriptGenerateRequest,
    ExpandRequest,
    ExpandResponse,
)
```

Update the `generate_script` endpoint to pass `raw_content`:
```python
@router.post("/generate", response_model=ScriptDetail, status_code=201)
def generate_script(
    body: ScriptGenerateRequest,
    db: Session = Depends(get_db),
    user=Depends(require_editor_or_admin),
):
    try:
        return ScriptService(db).generate_script(
            topic=body.topic,
            niche=body.niche,
            template=body.template,
            source_video_ids=body.source_video_ids,
            user_id=user.id,
            language=body.language,
            source_article_id=body.source_article_id,
            raw_content=body.raw_content,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

Add the `/expand` endpoint (before the `/{script_id}` routes to avoid path conflicts):
```python
@router.post("/expand", response_model=ExpandResponse)
def expand_content(
    body: ExpandRequest,
    _user=Depends(require_editor_or_admin),
):
    """Inline Gemini call — expands a short idea into a detailed outline. Not queued."""
    try:
        from rag.llm_router import get_router
        router_instance = get_router()
        prompt = (
            "You are a video script planner. Expand the following idea into a detailed "
            "video script outline. Include: a strong hook, 3-5 key points with supporting "
            "details, and a clear call to action. Write in prose, not JSON.\n\n"
            f"Idea: {body.content}"
        )
        result = router_instance.generate(prompt, expect_json=False)
        return ExpandResponse(expanded_outline=str(result))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 4: Test /expand endpoint**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
uvicorn console.backend.main:app --port 8080 &
sleep 3
TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))" 2>/dev/null)
curl -s -X POST http://localhost:8080/api/scripts/expand \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"content": "5 morning habits that change your life"}' | python3 -m json.tool | head -10
kill %1
```
Expected: JSON with `expanded_outline` key containing non-empty text.

- [ ] **Step 5: Commit**

```bash
git add console/backend/schemas/script.py console/backend/services/script_service.py console/backend/routers/scripts.py
git commit -m "feat: composer backend — raw_content on generate, /expand endpoint"
```

---

## Task 10: ComposerPage frontend

**Files:**
- Create/Replace: `console/frontend/src/pages/ComposerPage.jsx`

- [ ] **Step 1: Write ComposerPage.jsx**

Replace the stub (or create) `console/frontend/src/pages/ComposerPage.jsx`:
```jsx
import { useState } from 'react'
import { scriptsApi, fetchApi } from '../api/client.js'
import { Card, Button, Select, Toast, Spinner } from '../components/index.jsx'
import NicheCombobox from '../components/NicheCombobox.jsx'

const TEMPLATES = ['tiktok_viral', 'tiktok_30s', 'youtube_clean', 'shorts_hook']
const LANGUAGES = ['vietnamese', 'english']

export default function ComposerPage() {
  const [content,   setContent]   = useState('')
  const [expandFirst,setExpandFirst]=useState(false)
  const [niche,     setNiche]     = useState('')
  const [template,  setTemplate]  = useState('tiktok_viral')
  const [language,  setLanguage]  = useState('vietnamese')

  const [expanding,   setExpanding]   = useState(false)
  const [outline,     setOutline]     = useState('')   // after expand step
  const [outlineReady,setOutlineReady]= useState(false)

  const [generating, setGenerating] = useState(false)
  const [toast,      setToast]      = useState(null)

  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3500) }

  const handleExpand = async () => {
    if (!content.trim()) return
    setExpanding(true)
    try {
      const res = await fetchApi('/api/scripts/expand', {
        method: 'POST',
        body: JSON.stringify({ content: content.trim() }),
      })
      setOutline(res.expanded_outline || '')
      setOutlineReady(true)
    } catch (e) { showToast(e.message, 'error') }
    finally { setExpanding(false) }
  }

  const handleGenerate = async () => {
    const finalContent = outlineReady ? outline : content
    if (!finalContent.trim() || !niche) return
    const topic = finalContent.trim().split('\n')[0].slice(0, 120)
    setGenerating(true)
    try {
      await scriptsApi.generate({
        topic,
        niche,
        template,
        language,
        raw_content: finalContent.trim(),
      })
      showToast('Script queued — check the Scripts tab', 'success')
      // Reset
      setContent(''); setOutline(''); setOutlineReady(false); setNiche('')
    } catch (e) { showToast(e.message, 'error') }
    finally { setGenerating(false) }
  }

  const canGenerate = (outlineReady ? outline.trim() : content.trim()) && niche

  return (
    <div className="flex flex-col gap-5 max-w-3xl">
      <div>
        <h1 className="text-xl font-bold text-[#e8e8f0]">Composer</h1>
        <p className="text-sm text-[#9090a8] mt-0.5">Write or paste content, generate a script with Gemini</p>
      </div>

      <Card title="Content">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-[#9090a8]">Content / Idea</label>
            <textarea
              value={content}
              onChange={e => { setContent(e.target.value); if (outlineReady) setOutlineReady(false) }}
              rows={10}
              placeholder="Paste a full article, write a topic sentence, or describe a general idea…"
              className="w-full bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-2 text-sm text-[#e8e8f0] placeholder-[#5a5a70] focus:outline-none focus:border-[#7c6af7] resize-y transition-colors"
            />
          </div>

          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={expandFirst}
              onChange={e => { setExpandFirst(e.target.checked); setOutlineReady(false); setOutline('') }}
              className="accent-[#7c6af7] w-3.5 h-3.5"
            />
            <span className="text-sm text-[#9090a8]">Expand idea first — Gemini writes a detailed outline for you to review</span>
          </label>

          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-1">
              <NicheCombobox label="Niche *" value={niche} onChange={setNiche} />
            </div>
            <Select label="Template" value={template} onChange={e => setTemplate(e.target.value)}
              options={TEMPLATES.map(t => ({ value: t, label: t }))} />
            <Select label="Language" value={language} onChange={e => setLanguage(e.target.value)}
              options={LANGUAGES.map(l => ({ value: l, label: l }))} />
          </div>

          {!expandFirst && (
            <Button variant="primary" disabled={!canGenerate} loading={generating} onClick={handleGenerate}>
              Generate Script
            </Button>
          )}

          {expandFirst && !outlineReady && (
            <Button variant="default" disabled={!content.trim()} loading={expanding} onClick={handleExpand}>
              Expand & Preview
            </Button>
          )}
        </div>
      </Card>

      {outlineReady && (
        <Card title="Expanded Outline">
          <div className="flex flex-col gap-4">
            <p className="text-xs text-[#9090a8]">Review and edit the outline before generating the script.</p>
            <textarea
              value={outline}
              onChange={e => setOutline(e.target.value)}
              rows={12}
              className="w-full bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-2 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7] resize-y transition-colors font-mono"
            />
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setOutlineReady(false)}>← Back</Button>
              <Button variant="primary" disabled={!canGenerate} loading={generating} onClick={handleGenerate}>
                Generate Script from Outline
              </Button>
            </div>
          </div>
        </Card>
      )}

      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  )
}
```

- [ ] **Step 2: Verify build**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/frontend
npm run build 2>&1 | grep -E "error|built" | tail -5
```
Expected: clean build.

- [ ] **Step 3: Commit**

```bash
git add console/frontend/src/pages/ComposerPage.jsx
git commit -m "feat: ComposerPage with expand-first two-step flow"
```

---

## Task 11: Production page enrichment

**Files:**
- Modify: `console/frontend/src/pages/ProductionPage.jsx`

- [ ] **Step 1: Update SceneCard header row with readiness dots**

In `ProductionPage.jsx`, find the `SceneCard` component's header `<button>` row. Replace the existing inner JSX:

```jsx
      <button
        className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-[#1c1c22] transition-colors text-left"
        onClick={() => setExpanded(e => !e)}
      >
        <span className="text-xs font-mono text-[#5a5a70] w-6">{String(index + 1).padStart(2, '0')}</span>
        <span className="text-xs font-mono text-[#fbbf24] w-12">{scene.type || 'scene'}</span>
        {/* Readiness dots */}
        <span title={scene.asset_id ? 'Asset assigned' : 'No asset'}
          className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${scene.asset_id ? 'bg-[#34d399]' : 'bg-[#5a5a70]'}`} />
        <span title={scene.tts_audio_url ? 'Audio ready' : 'No audio'}
          className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${scene.tts_audio_url ? 'bg-[#34d399]' : 'bg-[#5a5a70]'}`} />
        <span className="text-sm text-[#e8e8f0] flex-1 truncate">{scene.narration?.slice(0, 80) || '—'}</span>
        <span className="text-xs font-mono text-[#9090a8]">{scene.duration || 0}s</span>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          className={`text-[#5a5a70] transition-transform ${expanded ? 'rotate-180' : ''}`}>
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </button>
```

- [ ] **Step 2: Enrich left column of expanded SceneCard**

Replace the left column visual section in the expanded grid:
```jsx
          {/* Left — visual asset */}
          <div className="space-y-3">
            <div className="text-xs font-semibold text-[#9090a8] uppercase tracking-wider">Visual Asset</div>
            <div className="aspect-[9/16] max-h-48 bg-[#0d0d0f] rounded-lg border border-[#2a2a32] flex items-center justify-center overflow-hidden">
              {scene.asset_thumbnail_url ? (
                <img src={scene.asset_thumbnail_url} alt="asset thumbnail"
                  className="w-full h-full object-cover" />
              ) : scene.asset_id ? (
                <div className="text-xs text-[#7c6af7] font-mono">Asset #{scene.asset_id}</div>
              ) : (
                <div className="text-xs text-[#5a5a70]">No asset</div>
              )}
            </div>
            <div className="flex items-center gap-2 text-xs font-mono text-[#9090a8]">
              {scene.asset_source && (
                <span className="px-1.5 py-0.5 rounded bg-[#1c1c22] border border-[#2a2a32]">{scene.asset_source}</span>
              )}
              {scene.asset_duration && <span>{scene.asset_duration}s clip</span>}
            </div>
            <Input label="Visual hint" value={visualHint} onChange={e => setVisualHint(e.target.value)}
              placeholder="Describe the visual…" />
            <div className="flex gap-2">
              <Button variant="default" className="flex-1 justify-center text-xs" onClick={() => setAssetBrowser(true)}>Replace</Button>
              <Button variant="ghost" className="flex-1 justify-center text-xs" onClick={handleVeoGen} loading={veoLoading}>Veo Gen</Button>
            </div>
          </div>
```

- [ ] **Step 3: Add TTS audio player to right column**

In the right column (Audio section), add the audio player after the `<div>Audio</div>` label:
```jsx
            <div className="text-xs font-semibold text-[#9090a8] uppercase tracking-wider">Audio</div>
            {scene.tts_audio_url ? (
              <audio controls src={scene.tts_audio_url}
                className="w-full h-8 accent-[#7c6af7]" />
            ) : (
              <div className="text-xs text-[#5a5a70] py-2 border border-dashed border-[#2a2a32] rounded text-center">No audio yet</div>
            )}
```

- [ ] **Step 4: Enrich the script header card**

In the `ProductionPage` main render, find the header `<Card>` and extend the metadata row to include hook text and render status:
```jsx
            <Card
              title={script.topic || `Script #${script.id}`}
              actions={
                <div className="flex gap-2 items-center">
                  <Badge status={script.status} />
                  <Button variant="primary" onClick={handleStartRender} loading={rendering}
                    disabled={!['approved', 'editing'].includes(script.status)}>
                    Start Render
                  </Button>
                </div>
              }
            >
              <div className="flex gap-6 text-xs text-[#9090a8] flex-wrap">
                <span><span className="text-[#5a5a70]">Template </span>{script.template || '—'}</span>
                <span><span className="text-[#5a5a70]">Niche </span>{script.niche || '—'}</span>
                <span><span className="text-[#5a5a70]">Voice </span>{vidMeta.voice || '—'}</span>
                <span><span className="text-[#5a5a70]">Duration </span>{vidMeta.total_duration || totalDur}s</span>
                <span><span className="text-[#5a5a70]">Scenes </span>{scenes.length}</span>
              </div>
              {vidMeta.hook && (
                <div className="mt-2 text-xs text-[#9090a8]">
                  <span className="text-[#5a5a70]">Hook </span>
                  <span className="text-[#e8e8f0] italic">"{vidMeta.hook}"</span>
                </div>
              )}
            </Card>
```

- [ ] **Step 5: Add readiness indicator to sidebar**

In the scripts sidebar `<Card>`, update the per-script button to show readiness:
```jsx
                  const scenes_list = []  // will be populated on load — use script.scene_count if available
                  // Readiness can only be shown for the loaded script
                  const isActive = activeId === s.id
                  const readyCount = isActive && script
                    ? (script.script_json?.scenes || []).filter(sc => sc.asset_id && sc.tts_audio_url).length
                    : null
                  const totalCount = isActive && script
                    ? (script.script_json?.scenes || []).length
                    : null
```

Add below the `<Badge>` in the sidebar button:
```jsx
                  {isActive && readyCount !== null && (
                    <span className="text-[#5a5a70] font-mono text-[10px]">{readyCount}/{totalCount} ready</span>
                  )}
```

- [ ] **Step 6: Verify build**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/frontend
npm run build 2>&1 | grep -E "error|built" | tail -5
```

- [ ] **Step 7: Commit**

```bash
git add console/frontend/src/pages/ProductionPage.jsx
git commit -m "feat: production page — scene readiness dots, asset thumbnails, TTS player, hook text"
```

---

## Task 12: Pipeline — backend logs (emit_log + /logs endpoint + WS update)

**Files:**
- Modify: `console/backend/services/pipeline_service.py`
- Modify: `console/backend/routers/pipeline.py`
- Modify: `console/backend/ws/pipeline_ws.py`

- [ ] **Step 1: Add emit_log helper to pipeline_service.py**

At the top of `console/backend/services/pipeline_service.py`, add after the `logger` line:

```python
import json
from datetime import datetime, timezone


def emit_log(job_id: int, level: str, msg: str) -> None:
    """Push a log line to Redis for the given job. Fails silently if Redis unavailable."""
    try:
        import redis as _redis
        import os
        r = _redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"), socket_connect_timeout=1)
        entry = json.dumps({"ts": datetime.now(timezone.utc).isoformat(), "level": level, "msg": msg})
        key = f"pipeline:job:{job_id}:logs"
        r.lpush(key, entry)
        r.ltrim(key, 0, 199)
        r.expire(key, 86400)  # 24h TTL
    except Exception:
        logger.debug(f"[emit_log] job={job_id} {level}: {msg}")
```

Also add a `get_job_logs` method to `PipelineService`:
```python
    def get_job_logs(self, job_id: int) -> list[dict]:
        """Read accumulated logs from Redis for a job."""
        try:
            import redis as _redis
            import os
            r = _redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"), socket_connect_timeout=1)
            key = f"pipeline:job:{job_id}:logs"
            raw = r.lrange(key, 0, -1)
            # Redis LPUSH prepends, so reverse to get chronological order
            entries = []
            for item in reversed(raw):
                try:
                    entries.append(json.loads(item))
                except Exception:
                    pass
            return entries
        except Exception:
            return []
```

- [ ] **Step 2: Add /logs endpoint to pipeline router**

In `console/backend/routers/pipeline.py`, add after the existing `get_job` endpoint:

```python
@router.get("/jobs/{job_id}/logs")
def get_job_logs(
    job_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        PipelineService(db).get_job(job_id)  # validates job exists
        logs = PipelineService(db).get_job_logs(job_id)
        return {"job_id": job_id, "logs": logs}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

- [ ] **Step 3: Update WS broadcaster to include job_logs**

In `console/backend/ws/pipeline_ws.py`, update `_get_stats()` to also fetch logs for running jobs:

Replace the function body with:
```python
def _get_stats() -> dict:
    try:
        from console.backend.database import SessionLocal
        from console.backend.models.pipeline_job import PipelineJob
        from console.backend.services.pipeline_service import PipelineService
        from sqlalchemy import func

        db = SessionLocal()
        try:
            rows = (
                db.query(PipelineJob.status, func.count(PipelineJob.id))
                .group_by(PipelineJob.status)
                .all()
            )
            counts = {r[0]: r[1] for r in rows}
            recent = (
                db.query(PipelineJob)
                .order_by(PipelineJob.created_at.desc())
                .limit(10)
                .all()
            )
            jobs = [
                {
                    "id":         j.id,
                    "job_type":   j.job_type,
                    "status":     j.status,
                    "progress":   j.progress,
                    "script_id":  j.script_id,
                    "error":      j.error,
                    "created_at": j.created_at.isoformat() if j.created_at else None,
                }
                for j in recent
            ]

            # Fetch live logs only for running jobs
            svc = PipelineService(db)
            job_logs = {}
            for j in recent:
                if j.status == "running":
                    job_logs[j.id] = svc.get_job_logs(j.id)

            return {
                "stats": {
                    "queued":    counts.get("queued", 0),
                    "running":   counts.get("running", 0),
                    "completed": counts.get("completed", 0),
                    "failed":    counts.get("failed", 0),
                    "total":     sum(counts.values()),
                },
                "recent_jobs": jobs,
                "job_logs": job_logs,
            }
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"WS stats fetch failed: {e}")
        return {"stats": {}, "recent_jobs": [], "job_logs": {}}
```

- [ ] **Step 4: Commit**

```bash
git add console/backend/services/pipeline_service.py console/backend/routers/pipeline.py console/backend/ws/pipeline_ws.py
git commit -m "feat: pipeline live logs via Redis + WS broadcast + /logs endpoint"
```

---

## Task 13: Pipeline — frontend live log panel

**Files:**
- Modify: `console/frontend/src/pages/PipelinePage.jsx`

- [ ] **Step 1: Update JobRow to show live logs and View Logs button**

Replace the `JobRow` component in `PipelinePage.jsx` with:

```jsx
function LogPanel({ logs }) {
  const ref = useRef(null)
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight
  }, [logs?.length])

  return (
    <div ref={ref} className="bg-[#0d0d0f] px-3 py-2.5 max-h-52 overflow-y-auto font-mono text-xs leading-5 space-y-0.5 mt-2 rounded-lg border border-[#2a2a32]">
      {!logs || logs.length === 0
        ? <span className="text-[#5a5a70]">No logs yet…</span>
        : logs.map((l, i) => (
          <div key={i} className="flex gap-1.5">
            <span className="text-[#5a5a70] flex-shrink-0">{l.ts ? l.ts.slice(11, 19) : ''}</span>
            <span className={`flex-shrink-0 ${l.level === 'ERROR' ? 'text-[#f87171]' : l.level === 'WARNING' ? 'text-[#fbbf24]' : 'text-[#34d399]'}`}>[{l.level}]</span>
            <span className={l.level === 'ERROR' ? 'text-[#f87171]' : l.level === 'WARNING' ? 'text-[#fbbf24]' : 'text-[#9090a8]'}>{l.msg}</span>
          </div>
        ))}
    </div>
  )
}

function JobRow({ job, onRetry, onCancel }) {
  const [expanded,  setExpanded]  = useState(false)
  const [staticLogs,setStaticLogs]= useState(null)
  const [loadingLog,setLoadingLog]= useState(false)

  const handleViewLogs = async () => {
    setLoadingLog(true)
    try {
      const res = await fetchApi(`/api/pipeline/jobs/${job.id}/logs`)
      setStaticLogs(res.logs || [])
    } catch (_) { setStaticLogs([]) }
    finally { setLoadingLog(false) }
  }

  const liveLogs = job.live_logs  // populated from WS when status === 'running'

  return (
    <div className="border border-[#2a2a32] rounded-lg overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-2.5 hover:bg-[#1c1c22] cursor-pointer"
        onClick={() => setExpanded(e => !e)}>
        <span className="text-xs font-mono text-[#5a5a70] w-8">#{job.id}</span>
        <Badge status={STATUS_COLOR[job.status]} label={job.status} />
        <span className="text-xs font-mono text-[#9090a8] w-20">{JOB_TYPE_LABELS[job.job_type] || job.job_type}</span>
        <div className="flex-1"><ProgressBar value={job.progress || 0} max={100} /></div>
        <span className="text-xs font-mono text-[#9090a8] w-8 text-right">{job.progress || 0}%</span>
        {job.script_id && <span className="text-xs text-[#5a5a70] font-mono">script#{job.script_id}</span>}
        <div className="flex gap-1">
          {['failed', 'cancelled'].includes(job.status) && (
            <Button variant="ghost" className="text-xs px-2 py-0.5" onClick={e => { e.stopPropagation(); onRetry(job.id) }}>Retry</Button>
          )}
          {['queued', 'running'].includes(job.status) && (
            <Button variant="danger" className="text-xs px-2 py-0.5" onClick={e => { e.stopPropagation(); onCancel(job.id) }}>Cancel</Button>
          )}
        </div>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          className={`text-[#5a5a70] transition-transform ${expanded ? 'rotate-180' : ''}`}>
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </div>

      {expanded && (
        <div className="border-t border-[#2a2a32] px-4 py-3 text-xs font-mono text-[#9090a8] space-y-1">
          {job.celery_task_id && <div>Task ID: <span className="text-[#e8e8f0]">{job.celery_task_id}</span></div>}
          {job.started_at && <div>Started: <span className="text-[#e8e8f0]">{new Date(job.started_at).toLocaleString()}</span></div>}
          {job.completed_at && <div>Completed: <span className="text-[#e8e8f0]">{new Date(job.completed_at).toLocaleString()}</span></div>}
          {job.error && <div className="text-[#f87171]">Error: {job.error}</div>}
          {job.details && <div>Details: <span className="text-[#e8e8f0]">{JSON.stringify(job.details)}</span></div>}

          {/* Logs */}
          {job.status === 'running' && <LogPanel logs={liveLogs} />}
          {['completed', 'failed', 'cancelled'].includes(job.status) && (
            staticLogs
              ? <LogPanel logs={staticLogs} />
              : <Button variant="ghost" size="sm" loading={loadingLog} onClick={handleViewLogs}>View Logs</Button>
          )}
        </div>
      )}
    </div>
  )
}
```

Also add `useRef` to the import at the top:
```js
import { useState, useCallback, useEffect, useRef } from 'react'
```

- [ ] **Step 2: Update handleWsMessage to merge job_logs**

In the `PipelinePage` component, update `handleWsMessage`:
```js
  const handleWsMessage = useCallback((data) => {
    if (data.type === 'pipeline_update') {
      if (data.stats)       setStats(data.stats)
      if (data.recent_jobs) {
        const jobLogs = data.job_logs || {}
        setJobs(data.recent_jobs.map(j => ({
          ...j,
          live_logs: jobLogs[j.id] || undefined,
        })))
      }
    }
  }, [])
```

- [ ] **Step 3: Verify build**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/frontend
npm run build 2>&1 | grep -E "error|built" | tail -5
```

- [ ] **Step 4: Commit**

```bash
git add console/frontend/src/pages/PipelinePage.jsx
git commit -m "feat: pipeline job live log panel with WS streaming and View Logs button"
```

---

## Task 14: LLM service — PROVIDER_REGISTRY + model endpoint

**Files:**
- Modify: `console/backend/services/llm_service.py`
- Modify: `console/backend/routers/llm.py`

- [ ] **Step 1: Rewrite llm_service.py**

Replace the full contents of `console/backend/services/llm_service.py`:
```python
"""LLMService — Gemini-only provider with extensible PROVIDER_REGISTRY."""
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

PROVIDER_REGISTRY = {
    "gemini": {
        "label": "Google Gemini",
        "description": "Cloud LLM via Google AI Studio API.",
        "fetch_models_method": "_fetch_gemini_models",
    },
    # To add a new provider: add an entry here and a corresponding
    # _fetch_<provider>_models() method below.
}


class LLMService:

    def get_status(self) -> dict:
        provider = self._current_provider()
        model    = self._current_model()
        gemini   = self._gemini_status()
        return {
            "provider":          provider,
            "model":             model,
            "providers_metadata": PROVIDER_REGISTRY,
            "gemini":            gemini,
            "timestamp":         datetime.now(timezone.utc).isoformat(),
        }

    def set_model(self, provider: str, model_name: str) -> dict:
        if provider not in PROVIDER_REGISTRY:
            raise ValueError(f"Unknown provider '{provider}'. Available: {list(PROVIDER_REGISTRY.keys())}")
        os.environ["LLM_PROVIDER"] = provider
        os.environ["LLM_MODEL"]    = model_name
        # Also update the env var that rag/llm_router.py reads
        os.environ["GEMINI_MODEL"] = model_name
        logger.info(f"LLM model set to: {provider}/{model_name}")
        return {"provider": provider, "model": model_name}

    def get_quota(self) -> dict:
        try:
            from rag.rate_limiter import get_gemini_limiter
            return {"gemini": get_gemini_limiter().usage()}
        except Exception as e:
            return {"gemini": {"error": str(e)}}

    # ── Internal ──────────────────────────────────────────────────────────────

    def _current_provider(self) -> str:
        return os.environ.get("LLM_PROVIDER", "gemini")

    def _current_model(self) -> str:
        return os.environ.get("LLM_MODEL", os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"))

    def _gemini_status(self) -> dict:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            return {"available": False, "error": "GEMINI_API_KEY not set", "api_key_set": False, "models": []}
        try:
            models = self._fetch_gemini_models(api_key)
            return {"available": True, "api_key_set": True, "models": models}
        except Exception as e:
            return {"available": False, "api_key_set": True, "error": str(e), "models": []}

    def _fetch_gemini_models(self, api_key: str | None = None) -> list[str]:
        """Fetch available Gemini models that support generateContent."""
        key = api_key or os.environ.get("GEMINI_API_KEY", "")
        try:
            from google import genai
            client = genai.Client(api_key=key)
            names = []
            for m in client.models.list():
                name = getattr(m, 'name', '') or ''
                # Filter to text-generation models; skip embedding/vision-only
                if 'gemini' in name.lower():
                    # Strip "models/" prefix if present
                    short = name.replace("models/", "")
                    names.append(short)
            return sorted(set(names))
        except Exception as e:
            logger.warning(f"Could not fetch Gemini model list: {e}")
            # Return safe defaults if API call fails
            return ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]
```

- [ ] **Step 2: Rewrite llm.py router**

Replace the full contents of `console/backend/routers/llm.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from console.backend.auth import require_admin, require_editor_or_admin
from console.backend.services.llm_service import LLMService

router = APIRouter(prefix="/llm", tags=["llm"])


class SetModelBody(BaseModel):
    provider: str
    model: str


@router.get("/status")
def get_status(_user=Depends(require_editor_or_admin)):
    return LLMService().get_status()


@router.put("/model")
def set_model(body: SetModelBody, _user=Depends(require_admin)):
    try:
        return LLMService().set_model(body.provider, body.model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/quota")
def get_quota(_user=Depends(require_editor_or_admin)):
    return LLMService().get_quota()
```

- [ ] **Step 3: Test**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
uvicorn console.backend.main:app --port 8080 &
sleep 3
TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin"}' | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/llm/status | python3 -m json.tool | head -20
kill %1
```
Expected: JSON with `provider`, `model`, `gemini.available`, `gemini.models` array.

- [ ] **Step 4: Commit**

```bash
git add console/backend/services/llm_service.py console/backend/routers/llm.py
git commit -m "feat: LLM service PROVIDER_REGISTRY, Gemini-only with dynamic model list"
```

---

## Task 15: LLMPage frontend — Gemini-only redesign

**Files:**
- Modify: `console/frontend/src/pages/LLMPage.jsx`

- [ ] **Step 1: Rewrite LLMPage.jsx**

Replace the full contents of `console/frontend/src/pages/LLMPage.jsx`:
```jsx
import { useState, useEffect } from 'react'
import { Card, Button, Select, Spinner, Toast } from '../components/index.jsx'
import { fetchApi } from '../api/client.js'

export default function LLMPage() {
  const [status,  setStatus]  = useState(null)
  const [quota,   setQuota]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving,  setSaving]  = useState(false)
  const [toast,   setToast]   = useState(null)

  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000) }

  const load = () => {
    setLoading(true)
    Promise.all([
      fetchApi('/api/llm/status'),
      fetchApi('/api/llm/quota'),
    ])
      .then(([s, q]) => { setStatus(s); setQuota(q) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleModelChange = async (model) => {
    setSaving(true)
    try {
      await fetchApi('/api/llm/model', {
        method: 'PUT',
        body: JSON.stringify({ provider: 'gemini', model }),
      })
      setStatus(s => ({ ...s, model }))
      showToast(`Model set to ${model}`)
    } catch (e) { showToast(e.message, 'error') }
    finally { setSaving(false) }
  }

  if (loading) return <div className="flex items-center justify-center h-64"><Spinner /></div>

  const gemini = status?.gemini || {}
  const models = gemini.models || []
  const currentModel = status?.model || ''
  const geminiQuota = quota?.gemini || {}

  return (
    <div className="space-y-5 max-w-2xl">
      {/* Card 1 — Active Model */}
      <Card title="Active Model" actions={saving && <Spinner size={16} />}>
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-3">
            <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${gemini.available ? 'bg-[#34d399]' : 'bg-[#f87171]'}`} />
            <span className="font-semibold text-[#e8e8f0]">Google Gemini</span>
            <span className={`text-xs font-mono ml-auto ${gemini.available ? 'text-[#34d399]' : 'text-[#f87171]'}`}>
              {gemini.available ? 'Online' : 'Offline'}
            </span>
          </div>

          <div className="flex items-center gap-3 text-sm">
            <span className="text-[#9090a8]">API Key</span>
            {gemini.api_key_set
              ? <span className="text-[#34d399] font-mono">Set ✓</span>
              : <span className="text-[#f87171] font-mono">Not set ✗</span>}
          </div>

          {gemini.error && (
            <div className="text-xs text-[#f87171] font-mono bg-[#1e0a0a] px-3 py-2 rounded border border-[#3a1010]">
              {gemini.error}
            </div>
          )}

          <Select
            label="Model"
            value={currentModel}
            onChange={e => handleModelChange(e.target.value)}
            options={models.length > 0
              ? models.map(m => ({ value: m, label: m }))
              : [{ value: currentModel, label: currentModel || 'Loading…' }]}
          />
          <p className="text-[10px] font-mono text-[#5a5a70]">Current: {currentModel || '—'}</p>
        </div>
      </Card>

      {/* Card 2 — Usage / Quota */}
      <Card title="Usage / Quota" actions={
        <Button variant="ghost" size="sm" onClick={load}>Refresh</Button>
      }>
        {geminiQuota.error ? (
          <p className="text-xs text-[#f87171] font-mono">{geminiQuota.error}</p>
        ) : (
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="bg-[#16161a] rounded-lg p-3 border border-[#2a2a32]">
              <div className="text-[#9090a8] text-xs mb-1">Requests / Minute</div>
              <div className="font-mono text-[#e8e8f0] text-lg">{geminiQuota.rpm ?? '—'}</div>
              <div className="text-[#5a5a70] text-xs">of {geminiQuota.rpm_limit ?? '—'} limit</div>
            </div>
            <div className="bg-[#16161a] rounded-lg p-3 border border-[#2a2a32]">
              <div className="text-[#9090a8] text-xs mb-1">Requests / Day</div>
              <div className="font-mono text-[#e8e8f0] text-lg">{geminiQuota.rpd ?? '—'}</div>
              <div className="text-[#5a5a70] text-xs">of {geminiQuota.rpd_limit ?? '—'} limit</div>
            </div>
          </div>
        )}
      </Card>

      {/* Card 3 — Future Providers */}
      <Card title="Additional Providers">
        <p className="text-xs text-[#5a5a70]">
          Additional providers (Ollama, OpenAI, etc.) can be configured in <span className="font-mono">pipeline.env</span> and registered in <span className="font-mono">llm_service.py</span>.
        </p>
      </Card>

      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  )
}
```

- [ ] **Step 2: Verify build**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/frontend
npm run build 2>&1 | grep -E "error|built" | tail -5
```

- [ ] **Step 3: Commit**

```bash
git add console/frontend/src/pages/LLMPage.jsx
git commit -m "feat: LLM page Gemini-only redesign with dynamic model dropdown"
```

---

## Task 16: Documentation updates

**Files:**
- Modify: `01_product_spec.md`
- Modify: `02_architecture_design.md`

- [ ] **Step 1: Update 01_product_spec.md — Section 2.1 Scraper Management**

Find section `2.1 Scraper Management` and replace the feature table with:

```markdown
| Feature | Description | Priority |
|---------|-------------|----------|
| Source Manager | View, enable/disable news scraper sources (VnExpress, Tinhte, CNN). Architecture supports future sources via a pluggable adapter interface (`scraper/base_scraper.py`) | P0 |
| Articles Browser | Tabular view of all scraped news articles: title, source, language, date. Supports filtering by source and language. Expand row to read full content | P0 |
| Article → Script | Click "→ Script" on any article to open the Generate Script modal, pre-filled with article title and language | P0 |
| Manual Scrape Trigger | Button to trigger an immediate scrape run for any news source outside the cron schedule | P1 |
```

Remove the `Data Model` note about `viral_videos` and replace with:
> **Data Model:** Reads from `news_articles` table. `viral_videos` table remains in schema for pipeline use but is not exposed in the console.

- [ ] **Step 2: Update 01_product_spec.md — add Niches module (new 2.1a)**

After section 2.1, add:

```markdown
### 2.1a Niche Management

**Purpose:** Central registry of content niches used across all script generation flows.

| Feature | Description | Priority |
|---------|-------------|----------|
| Niche List | Table of all niches with script usage count | P0 |
| Add Niche | Admin-only: add new niche via modal or inline combobox | P0 |
| Delete Niche | Admin-only: delete niche if not in use by any scripts | P0 |
| NicheCombobox | Shared dropdown+free-text component used in Generate Script modal and Composer. Typing a new name shows "+ Add" option that creates the niche inline | P0 |

**Data Model:** New `niches` table: `id, name (unique), created_at`. Seeded with: `beauty, education, finance, fitness, food, lifestyle, tech`.
```

- [ ] **Step 3: Update 01_product_spec.md — add Composer module (new 2.1b)**

After the Niches section, add:

```markdown
### 2.1b Composer

**Purpose:** Allow editors to generate scripts from free-form content or ideas without needing a scraped article.

| Feature | Description | Priority |
|---------|-------------|----------|
| Content Input | Large textarea accepting full articles, topic sentences, or general ideas | P0 |
| Expand Idea First | Optional toggle: Gemini expands the input into a detailed outline the editor can review and edit before generating the script | P0 |
| Generate Script | Calls the same generation pipeline as the Scraper flow, using the input (or expanded outline) as `raw_content` | P0 |

**Integration:** `POST /api/scripts/expand` (inline Gemini call, returns outline). `POST /api/scripts/generate` with `raw_content` field.
```

- [ ] **Step 4: Update 01_product_spec.md — Section 2.6 LLM & TTS Control**

Replace the LLM subsection under 2.6 with:

```markdown
**LLM:** Google Gemini only. Model selectable from the console UI (fetched dynamically from Gemini's model list API).

| Feature | Description | Priority |
|---------|-------------|----------|
| Active Model | Shows provider (Google Gemini), API key status, model selector dropdown | P0 |
| Quota Monitor | Gemini RPD/RPM usage from rate limiter | P0 |
| Future Providers | Extensible via `PROVIDER_REGISTRY` in `llm_service.py` — add Ollama, OpenAI etc. by adding an entry and a model-fetch method | P1 |
```

- [ ] **Step 5: Update 02_architecture_design.md — API Endpoint Summary (Section 7)**

Find the `LLM (3)` block and replace:
```
LLM (3)
  GET    /api/llm/status
  PUT    /api/llm/model        (replaces /api/llm/mode)
  GET    /api/llm/quota
```

Find the `SCRAPER (5)` block and replace with:
```
SCRAPER (4)
  GET    /api/scraper/sources
  PATCH  /api/scraper/sources/{id}/status
  POST   /api/scraper/run
  GET    /api/scraper/articles
  POST   /api/scraper/articles/from-url
  GET    /api/scraper/tasks/{task_id}
```

Add a new `NICHES (3)` block:
```
NICHES (3)
  GET    /api/niches
  POST   /api/niches
  DELETE /api/niches/{id}
```

Add `POST /api/scripts/expand` to the SCRIPTS block.

Add `GET /api/pipeline/jobs/{id}/logs` to the PIPELINE block.

Update `TOTAL` count.

- [ ] **Step 6: Update 02_architecture_design.md — Folder Structure (Section 6)**

In the frontend `pages/` list, add `NichesPage.jsx`, `ComposerPage.jsx`. In `components/`, add `NicheCombobox.jsx`. In backend `routers/`, add `niches.py`. In backend `services/`, add `niche_service.py`. In backend `models/`, add `niche.py`. In `alembic/versions/`, add `005_niches.py`.

In the `scraper/` section of the folder tree, remove the five deleted TikTok/Apify files.

- [ ] **Step 7: Update 02_architecture_design.md — Tech Stack table**

Update the LLM row:
```
| LLM | Gemini 2.5 Flash (model selectable via console) | Gemini-only; provider registry extensible for future models |
```

Remove TikTok Research / Playwright / Apify from the External APIs list in the architecture diagram.

- [ ] **Step 8: Commit**

```bash
git add 01_product_spec.md 02_architecture_design.md
git commit -m "docs: update product spec and architecture to reflect console improvements"
```

---

## Self-Review Checklist

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| Remove Videos tab + ChromaDB from Scraper | Tasks 1, 2 |
| Remove TikTok/YouTube scraper sources + files | Task 3 |
| New Niches tab — DB, service, router, UI | Tasks 4, 5, 6, 7, 8 |
| NicheCombobox in ScraperPage Generate modal | Task 2 (ScraperPage rewrite uses NicheCombobox) |
| Composer page — expand-first + generate | Tasks 9, 10 |
| Production — scene readiness dots, thumbnails, TTS player, hook | Task 11 |
| Pipeline — live logs via Redis + WS + /logs endpoint | Tasks 12, 13 |
| LLM tab — PROVIDER_REGISTRY, Gemini-only, dynamic models | Tasks 14, 15 |
| Update 01_product_spec.md + 02_architecture_design.md | Task 16 |

**Type consistency check:**
- `NicheCombobox` props: `value`, `onChange`, `label` — used consistently in ScraperPage (Task 2) and ComposerPage (Task 10).
- `nichesApi.list()` returns `[{id, name, script_count, created_at}]` — NicheCombobox reads `n.name` and `n.id` ✓
- `emit_log(job_id, level, msg)` signature — used in Task 12 service, called with `(int, str, str)` ✓
- `get_job_logs(job_id)` returns `list[dict]` — WS broadcaster and `/logs` endpoint both use it ✓
- `LLMService.set_model(provider, model_name)` — router sends `{provider, model}`, service accepts `(str, str)` ✓
- `job.live_logs` field set by `handleWsMessage` in Task 13 — read by `JobRow` in same task ✓
