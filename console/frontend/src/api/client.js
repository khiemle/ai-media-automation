// ── Token storage ────────────────────────────────────────────────────────────
const TOKEN_KEY = 'auth_token'
let _token = null

export function setToken(token) {
  if (!token) return
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
    window.location.href = '/'
    return
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const error = new Error(err.detail || `HTTP ${res.status}`)
    error.status = res.status
    throw error
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

// ── Niches ─────────────────────────────────────────────────────────────────────
export const nichesApi = {
  list: () => fetchApi('/api/niches'),
  create: (name) => fetchApi('/api/niches', { method: 'POST', body: JSON.stringify({ name }) }),
  remove: (id) => fetchApi(`/api/niches/${id}`, { method: 'DELETE' }),
}

// ── Music ──────────────────────────────────────────────────────────────────────
export const musicApi = {
  list: (params = {}) => {
    const q = new URLSearchParams(Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== '')))
    return fetchApi(`/api/music?${q}`)
  },
  generate: (body) =>
    fetchApi('/api/music/generate', { method: 'POST', body: JSON.stringify(body) }),
  upload: (file, metadata) => {
    const form = new FormData()
    form.append('file', file)
    form.append('metadata', JSON.stringify(metadata))
    // fetchApi adds Content-Type: application/json which breaks multipart — use raw fetch
    const headers = {}
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
    return fetch('/api/music/upload', { method: 'POST', body: form, headers })
      .then(async res => {
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }))
          throw new Error(err.detail || `HTTP ${res.status}`)
        }
        return res.json()
      })
  },
  get: (id) => fetchApi(`/api/music/${id}`),
  update: (id, body) =>
    fetchApi(`/api/music/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  delete: (id) =>
    fetchApi(`/api/music/${id}`, { method: 'DELETE' }),
  pollTask: (taskId) => fetchApi(`/api/music/tasks/${taskId}`),
  streamUrl: (id) => `/api/music/${id}/stream`,
}

// ── Video Assets ───────────────────────────────────────────────────────────────
export const assetsApi = {
  list: (params = {}) => {
    const q = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ''))
    )
    return fetchApi(`/api/production/assets?${q}`)
  },
  update: (id, body) =>
    fetchApi(`/api/production/assets/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  delete: (id) =>
    fetchApi(`/api/production/assets/${id}`, { method: 'DELETE' }),
  streamUrl: (id) => `/api/production/assets/${id}/stream`,
}
