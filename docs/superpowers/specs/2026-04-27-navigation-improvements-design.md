# Navigation Improvements Design

**Date:** 2026-04-27  
**Scope:** Frontend only — `console/frontend/src`  
**Status:** Approved

---

## Problem

1. **Auth not persisted:** Every page reload forces the user to log in again. The `loadPersistedToken()` function is a deliberate no-op per the original CLAUDE.md rule, but this creates poor UX for a daily-use internal tool.
2. **No URL routing:** Active tab is stored only in React state (`useState`). Navigating between tabs does not update the URL, so the browser back/forward buttons do nothing and tabs cannot be bookmarked or linked directly.

---

## Decisions

| Topic | Decision | Rationale |
|-------|----------|-----------|
| Token persistence | `localStorage` | Internal tool — convenience outweighs XSS risk that sessionStorage only marginally reduces. No backend changes required. |
| URL routing | React Router DOM | Standard industry approach; cleaner URLs (`/scripts` not `/#/scripts`); enables future deep links (e.g. `/scripts/123`). |
| Default route | `/system` | System tab moves to top of nav and becomes the landing page. |
| Login gate | Conditional render (not a route) | Keeps URL intact through the login flow — user lands on the correct tab after authenticating. |

---

## Auth Persistence — `console/frontend/src/api/client.js`

### Changes

- **`setToken(token)`** — writes to the in-memory `_token` variable AND `localStorage.setItem('auth_token', token)`.
- **`clearToken()`** — clears `_token` AND `localStorage.removeItem('auth_token')`.
- **`loadPersistedToken()`** — reads `localStorage.getItem('auth_token')`, seeds `_token`, and returns the value (or `null` if absent).

### No changes required in `App.jsx`

The session-restore `useEffect` (lines 109–115) already calls `loadPersistedToken()` and validates the token with `authApi.me()`. Once `loadPersistedToken()` returns a real token, the silent restore works automatically.

### 401 handling

The existing `window.location.href = '/'` redirect in `fetchApi` is kept as-is. It clears the invalid token via `clearToken()` (which now also removes from localStorage) before redirecting.

---

## URL Routing — React Router DOM

### Dependency

Add `react-router-dom` to `console/frontend/package.json` dependencies.

### `main.jsx`

Wrap the root render in `<BrowserRouter>`:

```jsx
import { BrowserRouter } from 'react-router-dom'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
)
```

### `App.jsx` — nav order

`system` moves to the top of `ALL_TABS`. Roles unchanged (`admin` only).

```js
const ALL_TABS = [
  { id: 'system',      label: 'System',      Icon: Icons.System,      roles: ['admin'] },
  { id: 'niches',      label: 'Niches',      Icon: Icons.Niches,      roles: ['admin', 'editor'] },
  { id: 'music',       label: 'Music',        Icon: Icons.Music,       roles: ['admin', 'editor'] },
  // ... rest unchanged
]
```

### `App.jsx` — routing

Replace `useState('niches')` / `setTab` / `renderPage()` with React Router:

- Use `useNavigate` to push a new history entry on nav click: `navigate('/' + id)`.
- Use `useLocation` (or `useParams`) to derive the active tab from the current URL path.
- Use `<Routes>` + `<Route path="/:tab" element={<PageSwitch />} />` + `<Route path="/" element={<Navigate to="/system" replace />} />` to render the correct page.
- Active nav item highlight: compare `location.pathname` to `'/' + id`.

### Role-gating with URLs

Because users can now type any path directly into the address bar, the router must enforce role access. When the tab derived from the URL is **not in the current user's allowed `tabs` list**, redirect to the first tab in that user's allowed list (e.g. `editor` typing `/system` → redirected to `/niches`). This check runs inside the page-rendering component, not in the nav.

### Back / forward

Each tab click calls `navigate('/' + id)`, pushing onto the browser history stack. The browser back/forward buttons traverse that stack — React Router updates the URL and re-renders the correct page automatically.

### Deep links & bookmarks

Because the URL reflects the active tab at all times, users can bookmark `/scripts` or share `/pipeline` and land directly on that tab after login.

---

## Files Changed

| File | Change |
|------|--------|
| `console/frontend/package.json` | Add `react-router-dom` |
| `console/frontend/src/main.jsx` | Wrap app in `<BrowserRouter>` |
| `console/frontend/src/api/client.js` | `setToken`, `clearToken`, `loadPersistedToken` use localStorage |
| `console/frontend/src/App.jsx` | Move `system` to top of `ALL_TABS`; replace tab state with React Router hooks and `<Routes>` |

---

## Out of Scope

- Deep links to specific scripts/videos (e.g. `/scripts/123`) — future work.
- httpOnly cookie auth — not needed for this internal tool.
- Animated tab transitions.
