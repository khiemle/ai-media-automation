// ── Token storage (session-persistent) ────────────────────────────────────────
let _token = null

export function setToken(token) {
  if (!token) return
  _token = token
  sessionStorage.setItem('console_token', token)
}

export function clearToken() {
  _token = null
  sessionStorage.removeItem('console_token')
}

export function getToken() { return _token }

export function restoreToken() {
  const t = sessionStorage.getItem('console_token')
  if (t) _token = t
  return t || null
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
  listTemplates: () => fetchApi('/api/music/templates'),
  elevenlabsPlan: (input, music_length_ms = 60000) =>
    fetchApi('/api/music/elevenlabs/plan', {
      method: 'POST',
      body: JSON.stringify({ input, music_length_ms }),
    }),
  elevenlabsCompose: (body) =>
    fetchApi('/api/music/elevenlabs/compose', { method: 'POST', body: JSON.stringify(body) }),
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
  thumbnailUrl: (id) => `/api/production/assets/${id}/thumbnail`,
  animateWithRunway: (id, body) =>
    fetchApi(`/api/production/assets/${id}/animate`, { method: 'POST', body: JSON.stringify(body) }),
  upload: (file, { source = 'manual', description = '', keywords = '', asset_type = '', generation_prompt = '' } = {}) => {
    const form = new FormData()
    form.append('file', file)
    form.append('source', source)
    if (description) form.append('description', description)
    if (keywords) form.append('keywords', keywords)
    if (asset_type) form.append('asset_type', asset_type)
    if (generation_prompt) form.append('generation_prompt', generation_prompt)
    // fetchApi adds Content-Type: application/json which breaks multipart — use raw fetch
    const headers = {}
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
    return fetch('/api/production/assets/upload', { method: 'POST', body: form, headers })
      .then(async res => {
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }))
          throw new Error(err.detail || `HTTP ${res.status}`)
        }
        return res.json()
      })
  },
}

// ── SFX ─────────────────────────────────────────────────────────────────────────
export const sfxApi = {
  list: (params = {}) => {
    const filtered = Object.fromEntries(
      Object.entries(params).filter(([, v]) => v != null && v !== '')
    )
    const qs = new URLSearchParams(filtered).toString()
    return fetchApi(`/api/sfx${qs ? `?${qs}` : ''}`)
  },
  listSoundTypes: () => fetchApi('/api/sfx/sound-types'),
  import: (formData) => {
    const headers = {}
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
    return fetch('/api/sfx/import', {
      method: 'POST',
      body: formData,
      headers,
    })
      .then(async res => {
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }))
          throw new Error(err.detail || `HTTP ${res.status}`)
        }
        return res.json()
      })
  },
  delete: (id) =>
    fetchApi(`/api/sfx/${id}`, { method: 'DELETE' }),
  streamUrl: (id) => `/api/sfx/${id}/stream`,
}

// ── YouTube Videos ─────────────────────────────────────────────────────────────
export const youtubeVideosApi = {
  listTemplates: () => fetchApi('/api/youtube-videos/templates'),
  getTemplate: (id) => fetchApi(`/api/youtube-videos/templates/${id}`),
  list: (params = {}) => {
    const filtered = Object.fromEntries(
      Object.entries(params).filter(([, v]) => v != null && v !== '')
    )
    const qs = new URLSearchParams(filtered).toString()
    return fetchApi(`/api/youtube-videos${qs ? `?${qs}` : ''}`)
  },
  get: (id) => fetchApi(`/api/youtube-videos/${id}`),
  create: (data) => fetchApi('/api/youtube-videos', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  update: (id, data) => fetchApi(`/api/youtube-videos/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  updateStatus: (id, status) => fetchApi(`/api/youtube-videos/${id}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  }),
  delete: (id) => fetchApi(`/api/youtube-videos/${id}`, { method: 'DELETE' }),
  render: (id) => fetchApi(`/api/youtube-videos/${id}/render`, { method: 'POST' }),
  streamUrl: (id) => `/api/youtube-videos/${id}/stream`,
  upload: (id, channelId) => fetchApi(`/api/youtube-videos/${id}/upload`, {
    method: 'POST',
    body: JSON.stringify({ channel_id: channelId }),
  }),

  // ── ASMR / Soundscape render lifecycle ──
  getRenderState: (id) => fetchApi(`/api/youtube-videos/${id}/render/state`),
  startAudioPreview: (id) => fetchApi(`/api/youtube-videos/${id}/render/audio-preview`, { method: 'POST' }),
  approveAudioPreview: (id) => fetchApi(`/api/youtube-videos/${id}/render/audio-preview/approve`, { method: 'POST' }),
  rejectAudioPreview: (id) => fetchApi(`/api/youtube-videos/${id}/render/audio-preview/reject`, { method: 'POST' }),
  startVideoPreview: (id) => fetchApi(`/api/youtube-videos/${id}/render/video-preview`, { method: 'POST' }),
  approveVideoPreview: (id) => fetchApi(`/api/youtube-videos/${id}/render/video-preview/approve`, { method: 'POST' }),
  rejectVideoPreview: (id) => fetchApi(`/api/youtube-videos/${id}/render/video-preview/reject`, { method: 'POST' }),
  startFinal: (id) => fetchApi(`/api/youtube-videos/${id}/render/final`, { method: 'POST' }),
  resume: (id) => fetchApi(`/api/youtube-videos/${id}/render/resume`, { method: 'POST' }),
  cancel: (id) => fetchApi(`/api/youtube-videos/${id}/render/cancel`, { method: 'POST' }),
  audioPreviewUrl: (id) => `/api/youtube-videos/${id}/preview/audio`,
  videoPreviewUrl: (id) => `/api/youtube-videos/${id}/preview/video`,

  uploadThumbnailImage: (id, file) => {
    const form = new FormData()
    form.append('image', file)
    const headers = {}
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
    return fetch(`/api/youtube-videos/${id}/thumbnail-image`, { method: 'POST', body: form, headers })
      .then(async res => {
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }))
          throw new Error(err.detail || `HTTP ${res.status}`)
        }
        return res.json()
      })
  },
  generateThumbnail: (id, text) => fetchApi(`/api/youtube-videos/${id}/thumbnail-generate`, {
    method: 'POST',
    body: JSON.stringify({ text: text || null }),
  }),
  thumbnailUrl: (id) => `/api/youtube-videos/${id}/thumbnail`,
}

// ── Templates ───────────────────────────────────────────────────────────────────
export const templatesApi = {
  list: () => fetchApi('/api/youtube-videos/templates'),
  musicTypes: () => fetchApi('/api/music/templates'),
}

// ── Autofill ─────────────────────────────────────────────────────────────────
export const autofillApi = {
  suggest: (modal_type, metadata, form_values) => fetchApi('/api/llm/autofill', {
    method: 'POST',
    body: JSON.stringify({ modal_type, metadata, form_values }),
  }),
}

// ── Channel Plans ──────────────────────────────────────────────────────────────
export const channelPlansApi = {
  list: () => fetchApi('/api/channel-plans'),

  get: (id) => fetchApi(`/api/channel-plans/${id}`),

  import: (file) => {
    const form = new FormData()
    form.append('file', file)
    const headers = {}
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
    return fetch('/api/channel-plans/import', { method: 'POST', body: form, headers })
      .then(async res => {
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }))
          throw new Error(err.detail || `HTTP ${res.status}`)
        }
        return res.json()
      })
  },

  update: (id, mdContent, channelId = null) =>
    fetchApi(`/api/channel-plans/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ md_content: mdContent, channel_id: channelId }),
    }),

  delete: (id) => fetchApi(`/api/channel-plans/${id}`, { method: 'DELETE' }),

  aiSeo: (id, theme, context = '') =>
    fetchApi(`/api/channel-plans/${id}/ai/seo`, {
      method: 'POST',
      body: JSON.stringify({ theme, context }),
    }),

  aiPrompts: (id, theme, context = '') =>
    fetchApi(`/api/channel-plans/${id}/ai/prompts`, {
      method: 'POST',
      body: JSON.stringify({ theme, context }),
    }),

  aiAsk: (id, question) =>
    fetchApi(`/api/channel-plans/${id}/ai/ask`, {
      method: 'POST',
      body: JSON.stringify({ question }),
    }),

  aiAutofill: (id, theme, context = '') =>
    fetchApi(`/api/channel-plans/${id}/ai/autofill`, {
      method: 'POST',
      body: JSON.stringify({ theme, context }),
    }),
}
