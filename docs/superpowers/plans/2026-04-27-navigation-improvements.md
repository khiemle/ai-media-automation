# Navigation Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist the JWT in localStorage so page reloads don't force re-login, and replace React state-based tab switching with React Router DOM so URLs update, back/forward works, and tabs are bookmarkable.

**Architecture:** `client.js` gains real localStorage read/write in `setToken`/`clearToken`/`loadPersistedToken`. `main.jsx` wraps the app in `<BrowserRouter>`. `App.jsx` drops `useState` for the active tab in favour of `useNavigate` + `useLocation`, renders pages via `<Routes>/<Route>`, and redirects unauthorized URL access to the first allowed tab.

**Tech Stack:** React 18, React Router DOM v6, Vite, localStorage API.

---

## File Map

| File | What changes |
|------|-------------|
| `console/frontend/package.json` | Add `react-router-dom` dependency |
| `console/frontend/src/main.jsx` | Wrap root render in `<BrowserRouter>` |
| `console/frontend/src/api/client.js` | `setToken`, `clearToken`, `loadPersistedToken` — read/write localStorage |
| `console/frontend/src/App.jsx` | Move `system` to top of `ALL_TABS`; replace `useState`/`setTab`/`renderPage` with router hooks + `<Routes>` |

---

## Task 1: Install react-router-dom

**Files:**
- Modify: `console/frontend/package.json`

- [ ] **Step 1: Install the package**

Run from `console/frontend/`:
```bash
cd console/frontend
npm install react-router-dom
```

Expected output: a line like `added 1 package` and `react-router-dom` appearing in `package.json` dependencies.

- [ ] **Step 2: Verify the install**

```bash
grep react-router-dom console/frontend/package.json
```

Expected output: `"react-router-dom": "^6.x.x"` (exact minor may vary).

- [ ] **Step 3: Commit**

```bash
git add console/frontend/package.json console/frontend/package-lock.json
git commit -m "feat: add react-router-dom"
```

---

## Task 2: Persist auth token in localStorage

**Files:**
- Modify: `console/frontend/src/api/client.js` (lines 1–17, line 31)

- [ ] **Step 1: Replace the token storage block**

In `console/frontend/src/api/client.js`, replace the entire top section (lines 1–17 — the comment through the `loadPersistedToken` export) with:

```js
// ── Token storage ────────────────────────────────────────────────────────────
const TOKEN_KEY = 'auth_token'
let _token = null

export function setToken(token) {
  _token = token
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  _token = null
  localStorage.removeItem(TOKEN_KEY)
}

export function getToken() { return _token }

export function loadPersistedToken() {
  const stored = localStorage.getItem(TOKEN_KEY)
  if (stored) _token = stored
  return stored
}
```

- [ ] **Step 2: Fix the 401 redirect**

In `console/frontend/src/api/client.js`, the `fetchApi` function currently redirects to `/login` on a 401 (line ~31). With React Router there is no `/login` route — change it to `/` so the router's default redirect to `/system` takes over cleanly after the page reloads.

Find this block:
```js
  if (res.status === 401) {
    clearToken()
    window.location.href = '/login'
    return
  }
```

Replace with:
```js
  if (res.status === 401) {
    clearToken()
    window.location.href = '/'
    return
  }
```

- [ ] **Step 3: Verify the dev server still starts**

```bash
cd console/frontend && npm run dev
```

Expected: Vite reports `Local: http://localhost:5173/` with no errors.

- [ ] **Step 4: Manual smoke test — reload persistence**

1. Open `http://localhost:5173` and log in.
2. Open DevTools → Application → Local Storage → `http://localhost:5173` — confirm `auth_token` key exists with a JWT value.
3. Reload the page (Cmd+R / F5).
4. Confirm the app loads directly to the page you were on **without showing the login screen**.

- [ ] **Step 5: Manual smoke test — logout clears token**

1. Click the logout icon in the sidebar footer.
2. Open DevTools → Application → Local Storage — confirm `auth_token` key is gone.
3. Reload — confirm the login screen appears.

- [ ] **Step 6: Commit**

```bash
git add console/frontend/src/api/client.js
git commit -m "feat: persist JWT in localStorage for session restore on reload"
```

---

## Task 3: Wrap app in BrowserRouter

**Files:**
- Modify: `console/frontend/src/main.jsx`

- [ ] **Step 1: Update main.jsx**

Replace the entire contents of `console/frontend/src/main.jsx` with:

```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.jsx'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
)
```

- [ ] **Step 2: Verify the app still renders**

With the dev server running, open `http://localhost:5173`. The app should load (login page or dashboard — no white screen, no console errors).

- [ ] **Step 3: Commit**

```bash
git add console/frontend/src/main.jsx
git commit -m "feat: wrap app in BrowserRouter"
```

---

## Task 4: Replace tab state with React Router in App.jsx

**Files:**
- Modify: `console/frontend/src/App.jsx`

This is the largest change. Replace the entire file with the version below. The Icons definitions and ComingSoon component are unchanged — copy them verbatim from the current file.

- [ ] **Step 1: Replace App.jsx**

Replace `console/frontend/src/App.jsx` with:

```jsx
import { useState, useEffect } from 'react'
import { useNavigate, useLocation, Routes, Route, Navigate } from 'react-router-dom'
import { setToken, clearToken, loadPersistedToken, authApi } from './api/client.js'
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
}

// system is first — it's the default landing tab
const ALL_TABS = [
  { id: 'system',      label: 'System',      Icon: Icons.System,      roles: ['admin'] },
  { id: 'niches',      label: 'Niches',      Icon: Icons.Niches,      roles: ['admin', 'editor'] },
  { id: 'music',       label: 'Music',       Icon: Icons.Music,       roles: ['admin', 'editor'] },
  { id: 'composer',    label: 'Composer',    Icon: Icons.Composer,    roles: ['admin', 'editor'] },
  { id: 'scraper',     label: 'Scraper',     Icon: Icons.Scraper,     roles: ['admin', 'editor'] },
  { id: 'scripts',     label: 'Scripts',     Icon: Icons.Scripts,     roles: ['admin', 'editor'] },
  { id: 'production',  label: 'Production',  Icon: Icons.Production,  roles: ['admin', 'editor'] },
  { id: 'uploads',     label: 'Uploads',     Icon: Icons.Uploads,     roles: ['admin', 'editor'] },
  { id: 'pipeline',    label: 'Pipeline',    Icon: Icons.Pipeline,    roles: ['admin', 'editor'] },
  { id: 'llm',         label: 'LLM',         Icon: Icons.LLM,         roles: ['admin'] },
  { id: 'performance', label: 'Performance', Icon: Icons.Performance, roles: ['admin', 'editor'] },
]

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
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    const token = loadPersistedToken()
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
  const currentTab = location.pathname.slice(1)
  const activeTabId = tabs.some(t => t.id === currentTab) ? currentTab : null

  const renderPage = (tabId) => {
    switch (tabId) {
      case 'system':      return <SystemPage />
      case 'niches':      return <NichesPage />
      case 'music':       return <MusicPage />
      case 'composer':    return <ComposerPage />
      case 'scraper':     return <ScraperPage />
      case 'scripts':     return <ScriptsPage />
      case 'production':  return <ProductionPage />
      case 'uploads':     return <UploadsPage />
      case 'pipeline':    return <PipelinePage />
      case 'llm':         return <LLMPage />
      case 'performance': return <PerformancePage />
      default:            return <ComingSoon name={ALL_TABS.find(t => t.id === tabId)?.label ?? tabId} />
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
          {tabs.map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => navigate('/' + id)}
              className={`w-full flex items-center gap-2.5 px-4 py-2.5 text-sm font-medium transition-colors text-left ${
                activeTabId === id
                  ? 'bg-[#222228] text-[#7c6af7] border-r-2 border-[#7c6af7]'
                  : 'text-[#9090a8] hover:bg-[#1c1c22] hover:text-[#e8e8f0]'
              }`}
            >
              <Icon />
              {label}
            </button>
          ))}
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
            <Route path="/" element={<Navigate to="/system" replace />} />
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
```

- [ ] **Step 2: Verify the app compiles**

With `npm run dev` running, open `http://localhost:5173`. Expected: no white screen, no console errors. The URL should update to `/system` (or the first allowed tab for the logged-in user).

- [ ] **Step 3: Manual smoke test — URL updates on tab click**

1. Log in if needed.
2. Click **Scripts** in the sidebar.
3. Confirm the URL bar shows `/scripts` and the Scripts page is visible.
4. Click **Pipeline**.
5. Confirm the URL bar shows `/pipeline`.

- [ ] **Step 4: Manual smoke test — back/forward**

1. Click through three different tabs (e.g. System → Scripts → Pipeline).
2. Press the browser **Back** button.
3. Confirm the URL changes to `/scripts` and the Scripts page loads.
4. Press **Back** again.
5. Confirm the URL changes to `/system` and the System page loads.
6. Press **Forward** — confirm `/scripts` returns.

- [ ] **Step 5: Manual smoke test — bookmarks and deep links**

1. Navigate to `/scraper` manually in the address bar.
2. Confirm the Scraper page loads and the Scraper nav item is highlighted.
3. Navigate to `/niches`.
4. Reload — confirm Niches page loads directly (no login screen, given Task 2 is done).

- [ ] **Step 6: Manual smoke test — role-gating**

If you have an `editor` account available:
1. Log in as `editor`.
2. Type `/system` in the address bar and press Enter.
3. Confirm the app redirects to `/niches` (first tab allowed for `editor`).
4. Type `/llm` in the address bar.
5. Confirm the app redirects to `/niches` again.

If no `editor` account is available, skip this step — role definitions are correct by inspection of the `ALL_TABS` array.

- [ ] **Step 7: Manual smoke test — System tab is first in nav**

1. Log in as `admin`.
2. Confirm **System** is the first item in the sidebar.
3. Navigate to `/` — confirm it redirects to `/system`.

- [ ] **Step 8: Commit**

```bash
git add console/frontend/src/App.jsx
git commit -m "feat: replace tab state with React Router — URL routing, back/forward, role-gating"
```

---

## Verification Checklist

Run through this after all tasks are complete:

| Scenario | Expected |
|----------|----------|
| Page reload after login | Lands on same tab, no login screen |
| Logout then reload | Login screen appears |
| Click any nav tab | URL updates to `/<tab>` |
| Browser back | Previous tab URL and page restored |
| Browser forward | Next tab URL and page restored |
| Navigate to `/` | Redirects to `/system` |
| Type `/system` as `editor` | Redirects to first editor tab |
| Bookmark `/scripts`, open fresh tab | Loads Scripts page after login |
| System tab position | First item in sidebar |
