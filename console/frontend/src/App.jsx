import { useState, useEffect } from 'react'
import { useLocation, Routes, Route, Navigate, NavLink } from 'react-router-dom'
import { setToken, clearToken, restoreToken, authApi } from './api/client.js'
import LoginPage from './pages/LoginPage.jsx'
import ScraperPage from './pages/ScraperPage.jsx'
import ScriptsPage from './pages/ScriptsPage.jsx'
import ProductionPage from './pages/ProductionPage.jsx'
import PipelinePage from './pages/PipelinePage.jsx'
import UploadsPage from './pages/UploadsPage.jsx'
import PerformancePage from './pages/PerformancePage.jsx'
import SystemPage from './pages/SystemPage.jsx'
import LLMPage from './pages/LLMPage.jsx'
import NichesPage from './pages/NichesPage.jsx'
import ComposerPage from './pages/ComposerPage.jsx'
import MusicPage from './pages/MusicPage.jsx'
import VideoAssetsPage from './pages/VideoAssetsPage.jsx'
import SFXPage from './pages/SFXPage.jsx'
import YouTubeVideosPage from './pages/YouTubeVideosPage.jsx'

// ── Tab icons (inline SVG) ────────────────────────────────────────────────────
const Icons = {
  Scraper: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
    </svg>
  ),
  Scripts: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>
    </svg>
  ),
  Production: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>
    </svg>
  ),
  Uploads: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/>
    </svg>
  ),
  Pipeline: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
    </svg>
  ),
  LLM: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2a10 10 0 1 0 10 10"/><path d="M12 8v4l3 3"/><circle cx="18" cy="5" r="3"/>
    </svg>
  ),
  Performance: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
    </svg>
  ),
  System: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>
    </svg>
  ),
  Niches: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/>
    </svg>
  ),
  Music: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>
    </svg>
  ),
  Composer: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
    </svg>
  ),
  Assets: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="2" width="8" height="8" rx="1"/><rect x="14" y="2" width="8" height="8" rx="1"/><rect x="14" y="14" width="8" height="8" rx="1"/><rect x="2" y="14" width="8" height="8" rx="1"/>
    </svg>
  ),
  SFX: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/>
    </svg>
  ),
  YouTube: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22.54 6.42a2.78 2.78 0 0 0-1.95-1.96C18.88 4 12 4 12 4s-6.88 0-8.59.46a2.78 2.78 0 0 0-1.95 1.96A29 29 0 0 0 1 12a29 29 0 0 0 .46 5.58A2.78 2.78 0 0 0 3.41 19.54C5.12 20 12 20 12 20s6.88 0 8.59-.46a2.78 2.78 0 0 0 1.95-1.96A29 29 0 0 0 23 12a29 29 0 0 0-.46-5.58z"/>
      <polygon points="9.75 15.02 15.5 12 9.75 8.98 9.75 15.02"/>
    </svg>
  ),
}

// system is first — it's the default landing tab
const ALL_TABS = [
  // LIBRARY
  { id: 'niches',      label: 'Niches',         Icon: Icons.Niches,      roles: ['admin', 'editor'], section: 'library' },
  { id: 'music',       label: 'Music',          Icon: Icons.Music,       roles: ['admin', 'editor'], section: 'library' },
  { id: 'sfx',         label: 'SFX',            Icon: Icons.SFX,         roles: ['admin', 'editor'], section: 'library' },
  { id: 'assets',      label: 'Assets',         Icon: Icons.Assets,      roles: ['admin', 'editor'], section: 'library' },
  // SHORT VIDEOS
  { id: 'composer',    label: 'Composer',       Icon: Icons.Composer,    roles: ['admin', 'editor'], section: 'short' },
  { id: 'scraper',     label: 'Scraper',        Icon: Icons.Scraper,     roles: ['admin', 'editor'], section: 'short' },
  { id: 'scripts',     label: 'Scripts',        Icon: Icons.Scripts,     roles: ['admin', 'editor'], section: 'short' },
  { id: 'production',  label: 'Production',     Icon: Icons.Production,  roles: ['admin', 'editor'], section: 'short' },
  // YOUTUBE VIDEOS
  { id: 'youtube',     label: 'YouTube Videos', Icon: Icons.YouTube,     roles: ['admin', 'editor'], section: 'youtube' },
  // ADMIN
  { id: 'pipeline',    label: 'Pipeline',       Icon: Icons.Pipeline,    roles: ['admin', 'editor'], section: 'short' },
  { id: 'uploads',     label: 'Uploads',        Icon: Icons.Uploads,     roles: ['admin', 'editor'], section: 'admin' },
  { id: 'llm',         label: 'LLM',            Icon: Icons.LLM,         roles: ['admin'],            section: 'admin' },
  { id: 'performance', label: 'Performance',    Icon: Icons.Performance, roles: ['admin', 'editor'], section: 'admin' },
  { id: 'system',      label: 'System',         Icon: Icons.System,      roles: ['admin'],            section: 'admin' },
]

const SECTION_LABELS = {
  library: 'LIBRARY',
  short:   'SHORT VIDEOS',
  youtube: 'YOUTUBE VIDEOS',
  admin:   'ADMIN',
}

function renderNavWithSections(tabs) {
  const items = []
  let lastSection = null

  tabs.forEach(({ id, label, Icon, section }) => {
    if (section !== lastSection && section !== 'shared' && SECTION_LABELS[section]) {
      items.push(
        <div key={`section-${section}`} className="px-4 pt-4 pb-1">
          <span className="text-[9px] font-bold tracking-widest text-[#5a5a70]">
            {SECTION_LABELS[section]}
          </span>
        </div>
      )
    }
    lastSection = section
    items.push(
      <NavLink
        key={id}
        to={'/' + id}
        className={({ isActive }) =>
          `w-full flex items-center gap-2.5 px-4 py-2.5 text-sm font-medium transition-colors text-left ${
            isActive
              ? 'bg-[#222228] text-[#7c6af7] border-r-2 border-[#7c6af7]'
              : 'text-[#9090a8] hover:bg-[#1c1c22] hover:text-[#e8e8f0]'
          }`
        }
      >
        <Icon />
        {label}
      </NavLink>
    )
  })

  return items
}

function ComingSoon({ name }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 text-center py-20">
      <div className="text-5xl">🚧</div>
      <h2 className="text-xl font-semibold text-[#e8e8f0]">{name}</h2>
      <p className="text-sm text-[#9090a8]">Coming in Sprint {
        name === 'Production' || name === 'Pipeline' ? '2' :
        name === 'Uploads' ? '3' : '4'
      }</p>
    </div>
  )
}

export default function App() {
  const [user, setUser] = useState(null)
  const location = useLocation()

  useEffect(() => {
    const token = restoreToken()
    if (!token) return
    authApi.me()
      .then(userData => setUser(userData))
      .catch(() => clearToken())
  }, [])

  const handleLogin = (token, userData) => {
    setToken(token)
    setUser(userData)
  }

  const handleLogout = () => {
    clearToken()
    setUser(null)
  }

  if (!user) return <LoginPage onLogin={handleLogin} />

  const tabs = ALL_TABS.filter(t => t.roles.includes(user.role))
  const currentTab = location.pathname.replace(/^\//, '').split('/')[0]
  const activeTabId = tabs.some(t => t.id === currentTab) ? currentTab : null

  const renderPage = (tabId) => {
    switch (tabId) {
      case 'system':      return <SystemPage />
      case 'niches':      return <NichesPage />
      case 'music':       return <MusicPage />
      case 'assets':      return <VideoAssetsPage />
      case 'sfx':         return <SFXPage />
      case 'composer':    return <ComposerPage />
      case 'scraper':     return <ScraperPage />
      case 'scripts':     return <ScriptsPage />
      case 'production':  return <ProductionPage />
      case 'youtube':     return <YouTubeVideosPage />
      case 'uploads':     return <UploadsPage />
      case 'pipeline':    return <PipelinePage />
      case 'llm':         return <LLMPage />
      case 'performance': return <PerformancePage />
      default:
        console.error(`[App] No render case for tab: ${tabId}`)
        return <ComingSoon name={ALL_TABS.find(t => t.id === tabId)?.label ?? tabId} />
    }
  }

  return (
    <div className="flex h-screen bg-[#0d0d0f] overflow-hidden">
      {/* ── Sidebar nav ── */}
      <aside className="w-[200px] flex-shrink-0 bg-[#16161a] border-r border-[#2a2a32] flex flex-col">
        {/* Logo */}
        <div className="px-4 py-4 border-b border-[#2a2a32]">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-[#7c6af7] flex items-center justify-center">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="white">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
              </svg>
            </div>
            <div>
              <div className="text-xs font-bold text-[#e8e8f0] leading-none">AI Media</div>
              <div className="text-[10px] text-[#9090a8] font-mono leading-none mt-0.5">Console</div>
            </div>
          </div>
        </div>

        {/* Nav items */}
        <nav className="flex-1 py-2 overflow-y-auto">
          {renderNavWithSections(tabs)}
        </nav>

        {/* User footer */}
        <div className="px-4 py-3 border-t border-[#2a2a32] flex items-center gap-2">
          <div className="w-6 h-6 rounded-full bg-[#7c6af7] flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
            {user.username?.[0]?.toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs font-medium text-[#e8e8f0] truncate">{user.username}</div>
            <div className="text-[10px] text-[#9090a8] font-mono">{user.role}</div>
          </div>
          <button onClick={handleLogout} title="Logout" className="text-[#9090a8] hover:text-[#f87171] transition-colors flex-shrink-0">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
            </svg>
          </button>
        </div>
      </aside>

      {/* ── Main content ── */}
      <main className="flex-1 overflow-y-auto bg-[#0d0d0f]">
        <div className="max-w-7xl mx-auto p-6">
          <Routes>
            <Route path="/" element={<Navigate to="/niches" replace />} />
            <Route
              path="/:tab"
              element={
                activeTabId
                  ? renderPage(activeTabId)
                  : <Navigate to={'/' + tabs[0].id} replace />
              }
            />
          </Routes>
        </div>
      </main>
    </div>
  )
}
