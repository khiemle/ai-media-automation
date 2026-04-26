// ── Token storage (localStorage + memory) ─────────────────────────────────────
const TOKEN_KEY = 'ai_media_token'
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

/** Restore token from localStorage into memory. Returns the token or null. */
export function loadPersistedToken() {
  const saved = localStorage.getItem(TOKEN_KEY)
  if (saved) _token = saved
  return saved
}

// ── Base fetch wrapper ─────────────────────────────────────────────────────────
export async function fetchApi(url, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  }
  if (_token) headers['Authorization'] = `Bearer ${_token}`

  const res = await fetch(url, { ...options, headers })

  if (res.status === 401) {
    clearToken()
    window.location.href = '/login'
    return
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }

  if (res.status === 204) return null
  return res.json()
}

// ── Auth ───────────────────────────────────────────────────────────────────────
export const authApi = {
  login: (username, password) =>
    fetchApi('/api/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  me: () => fetchApi('/api/auth/me'),
}

// ── Scraper ────────────────────────────────────────────────────────────────────
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

// ── Scripts ────────────────────────────────────────────────────────────────────
export const scriptsApi = {
  list: (params = {}) => {
    const q = new URLSearchParams(Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== '')))
    return fetchApi(`/api/scripts?${q}`)
  },
  get: (id) => fetchApi(`/api/scripts/${id}`),
  generate: (body) =>
    fetchApi('/api/scripts/generate', { method: 'POST', body: JSON.stringify(body) }),
  update: (id, body) =>
    fetchApi(`/api/scripts/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  approve: (id) =>
    fetchApi(`/api/scripts/${id}/approve`, { method: 'PATCH' }),
  reject: (id) =>
    fetchApi(`/api/scripts/${id}/reject`, { method: 'PATCH' }),
  regenerate: (id) =>
    fetchApi(`/api/scripts/${id}/regenerate`, { method: 'POST' }),
  regenerateScene: (id, sceneIndex) =>
    fetchApi(`/api/scripts/${id}/scenes/${sceneIndex}/regenerate`, { method: 'POST' }),
}
