import { useState, useEffect, useCallback } from 'react'
import { Card, Badge, Button, Tabs, Spinner, EmptyState, Modal, Input, Select, Toast } from '../components/index.jsx'
import ChannelPicker from '../components/ChannelPicker.jsx'
import { fetchApi } from '../api/client.js'

// ── Platform config ───────────────────────────────────────────────────────────
const PLATFORMS = [
  { id: 'youtube',   label: 'YouTube',   color: '#ff6060', icon: 'YT' },
  { id: 'tiktok',    label: 'TikTok',    color: '#22d3ee', icon: 'TK' },
  { id: 'instagram', label: 'Instagram', color: '#c084fc', icon: 'IG' },
]

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmtTTL(seconds) {
  if (!seconds) return '—'
  if (seconds < 3600)  return `${Math.floor(seconds / 60)}m`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`
  return `${Math.floor(seconds / 86400)}d`
}

function PlatformDot({ platform }) {
  const p = PLATFORMS.find(x => x.id === platform)
  return <span className="inline-block w-2 h-2 rounded-full mr-1.5" style={{ backgroundColor: p?.color || '#9090a8' }} />
}

function StatusBadge({ status }) {
  const map = { pending: 'pending_review', uploading: 'editing', published: 'completed', failed: 'rejected' }
  return <Badge status={map[status] || 'planned'} label={status} />
}

// ── Video Preview Modal ───────────────────────────────────────────────────────
function VideoPreviewModal({ video, onClose }) {
  if (!video) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70" onClick={onClose}>
      <div
        className="bg-[#1c1c22] border border-[#2a2a32] rounded-xl p-4 w-full max-w-sm flex flex-col gap-3"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="text-sm font-medium text-[#e8e8f0] leading-snug">{video.title}</div>
          <button onClick={onClose} className="text-[#9090a8] hover:text-[#f87171] flex-shrink-0 transition-colors">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <video
          controls
          autoPlay
          src={`/api/uploads/videos/${video.id}/stream`}
          className="w-full rounded-lg bg-black"
          style={{ aspectRatio: '9/16', maxHeight: '60vh', objectFit: 'contain' }}
        />
      </div>
    </div>
  )
}

// ── Videos Sub-tab ────────────────────────────────────────────────────────────
function VideosTab({ channels }) {
  const [videos,       setVideos]       = useState([])
  const [loading,      setLoading]      = useState(true)
  const [targets,      setTargets]      = useState({})   // { video_id: [channel_id, ...] }
  const [toast,        setToast]        = useState(null)
  const [previewVideo, setPreviewVideo] = useState(null)
  const [videoFormat,  setVideoFormat]  = useState('all')

  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000) }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const formatParam = videoFormat === 'all' ? '' : `&video_format=${videoFormat}`
      const res = await fetchApi(`/api/uploads/videos?per_page=50${formatParam}`)
      setVideos(res.items || [])
      // Init targets from existing upload targets
      const t = {}
      for (const v of res.items || []) {
        t[v.id] = (v.targets || []).map(tg => tg.channel_id)
      }
      setTargets(t)
    } catch { setVideos([]) }
    finally { setLoading(false) }
  }, [videoFormat])

  useEffect(() => { load() }, [load])

  const handleTargetChange = (videoId, channelIds) => {
    setTargets(prev => ({ ...prev, [videoId]: channelIds }))
  }

  const handleTargetDone = async (videoId, channelIds) => {
    try {
      await fetchApi(`/api/uploads/videos/${videoId}/targets`, {
        method: 'PUT',
        body: JSON.stringify({ channel_ids: channelIds }),
      })
      showToast(`${channelIds.length} channel(s) targeted`)
    } catch (e) { showToast(e.message, 'error') }
  }

  const handleUpload = async (videoId) => {
    try {
      const channelIds = targets[videoId] || []
      await fetchApi(`/api/uploads/videos/${videoId}/targets`, {
        method: 'PUT',
        body: JSON.stringify({ channel_ids: channelIds }),
      })
      const res = await fetchApi(`/api/uploads/videos/${videoId}/upload`, { method: 'POST' })
      showToast(`${res.queued} upload task(s) queued`)
      load()
    } catch (e) { showToast(e.message, 'error') }
  }

  const handleDelete = async (videoId) => {
    try {
      await fetchApi(`/api/uploads/videos/${videoId}`, { method: 'DELETE' })
      showToast('Removed from upload queue')
      load()
    } catch (e) { showToast(e.message, 'error') }
  }

  const handleUploadAll = async () => {
    try {
      const res = await fetchApi('/api/uploads/upload-all', { method: 'POST' })
      showToast(`${res.queued} upload task(s) queued`)
      load()
    } catch (e) { showToast(e.message, 'error') }
  }

  return (
    <Card
      title="Production Videos"
      actions={
        <Button variant="primary" onClick={handleUploadAll}>Upload All Ready</Button>
      }
    >
      {loading ? (
        <div className="flex items-center justify-center h-40"><Spinner /></div>
      ) : videos.length === 0 ? (
        <EmptyState title="No production videos yet" description="Videos appear here when scripts reach 'completed' status." />
      ) : (
        <>
          <div className="mb-4 flex items-center gap-3 pb-4 border-b border-[#2a2a32]">
            <span className="text-xs font-medium text-[#5a5a70] uppercase tracking-wider">Format:</span>
            <div className="flex items-center gap-1 bg-[#16161a] border border-[#2a2a32] rounded-lg p-1">
              {['all', 'short', 'youtube_long'].map(f => (
                <button
                  key={f}
                  onClick={() => setVideoFormat(f)}
                  className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                    videoFormat === f
                      ? 'bg-[#7c6af7] text-white'
                      : 'text-[#9090a8] hover:text-[#e8e8f0]'
                  }`}
                >
                  {f === 'all' ? 'All' : f === 'short' ? 'Short' : 'YouTube Long'}
                </button>
              ))}
            </div>
          </div>
          <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-[#5a5a70] uppercase tracking-wider border-b border-[#2a2a32]">
                <th className="pb-2 pr-4 font-medium">Title</th>
                <th className="pb-2 pr-4 font-medium">Template</th>
                <th className="pb-2 pr-4 font-medium">Status</th>
                <th className="pb-2 pr-4 font-medium">Targets</th>
                <th className="pb-2 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#2a2a32]">
              {videos.map(v => {
                const vTargets = targets[v.id] || []
                const uploadable = !['uploading'].includes(v.status)
                return (
                  <tr key={v.id} className="hover:bg-[#1c1c22]/50 transition-colors">
                    <td className="py-2.5 pr-4">
                      <div className="font-medium text-[#e8e8f0] truncate max-w-[200px]">{v.title}</div>
                      <div className="text-xs text-[#5a5a70] font-mono">
                        {v.niche}
                        {v.duration_s && (
                          <>
                            {' • '}
                            {v.video_format === 'youtube_long'
                              ? `${(v.duration_s / 3600).toFixed(1)}h`
                              : `${Math.round(v.duration_s)}s`
                            }
                          </>
                        )}
                      </div>
                    </td>
                    <td className="py-2.5 pr-4 text-xs text-[#9090a8] font-mono">{v.template || '—'}</td>
                    <td className="py-2.5 pr-4"><Badge status={v.status} /></td>
                    <td className="py-2.5 pr-4">
                      <div className="flex items-center gap-1 flex-wrap">
                        {v.targets?.map(t => (
                          <span key={t.channel_id} className="text-[10px] font-mono text-[#9090a8] bg-[#222228] px-1.5 py-0.5 rounded">
                            <PlatformDot platform={t.platform} />{t.channel_name}
                          </span>
                        ))}
                        {uploadable && (
                          <ChannelPicker
                            channels={channels}
                            selected={vTargets}
                            onChange={(ids) => handleTargetChange(v.id, ids)}
                            onDone={(ids) => handleTargetDone(v.id, ids)}
                          />
                        )}
                      </div>
                    </td>
                    <td className="py-2.5 text-right">
                      <div className="flex items-center gap-1 justify-end">
                        {v.has_video && (
                          <button
                            title="Preview video"
                            onClick={() => setPreviewVideo(v)}
                            className="w-7 h-7 flex items-center justify-center rounded bg-[#222228] text-[#9090a8] hover:text-[#7c6af7] hover:bg-[#2a2a38] transition-colors"
                          >
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                              <polygon points="5 3 19 12 5 21 5 3"/>
                            </svg>
                          </button>
                        )}
                        {uploadable && vTargets.length > 0 && (
                          <Button variant="primary" className="text-xs px-2 py-1" onClick={() => handleUpload(v.id)}>
                            Upload
                          </Button>
                        )}
                        <Button variant="danger" className="text-xs px-2 py-1" onClick={() => handleDelete(v.id)}>
                          Remove
                        </Button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          </div>
        </>
      )}
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
      <VideoPreviewModal video={previewVideo} onClose={() => setPreviewVideo(null)} />
    </Card>
  )
}

// ── Credentials Sub-tab ───────────────────────────────────────────────────────
function CredentialsTab() {
  const [creds,    setCreds]    = useState([])
  const [editing,  setEditing]  = useState(null)   // platform string
  const [form,     setForm]     = useState({})
  const [loading,  setLoading]  = useState(true)
  const [expanded, setExpanded] = useState({})
  const [toast,    setToast]    = useState(null)

  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000) }

  const load = useCallback(async () => {
    setLoading(true)
    try { setCreds(await fetchApi('/api/credentials')) }
    catch { setCreds([]) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const credFor = (platform) => creds.find(c => c.platform === platform)

  const handleSave = async () => {
    try {
      await fetchApi(`/api/credentials/${editing}`, {
        method: 'PUT',
        body: JSON.stringify(form),
      })
      showToast('Credentials saved')
      setEditing(null)
      load()
    } catch (e) { showToast(e.message, 'error') }
  }

  const handleRefresh = async (credId) => {
    try {
      await fetchApi(`/api/credentials/${credId}/refresh`, { method: 'POST' })
      showToast('Token refreshed')
      load()
    } catch (e) { showToast(e.message, 'error') }
  }

  const handleTest = async (credId) => {
    try {
      const res = await fetchApi(`/api/credentials/${credId}/test`, { method: 'POST' })
      showToast(res.ok ? 'Connection OK' : `Failed: ${res.error}`, res.ok ? 'success' : 'error')
    } catch (e) { showToast(e.message, 'error') }
  }

  const handleDisconnect = async (credId) => {
    try {
      await fetchApi(`/api/credentials/${credId}/disconnect`, { method: 'POST' })
      showToast('Disconnected')
      load()
    } catch (e) { showToast(e.message, 'error') }
  }

  const handleOAuth = async (platform) => {
    try {
      const res = await fetchApi(`/api/credentials/${platform}/oauth-url`)
      window.open(res.url, '_blank')
    } catch (e) { showToast(e.message, 'error') }
  }

  return (
    <div className="space-y-3">
      {PLATFORMS.map(p => {
        const cred = credFor(p.id)
        const isExpanded = expanded[p.id]
        return (
          <div key={p.id} className="border border-[#2a2a32] rounded-xl overflow-hidden">
            {/* Header */}
            <button
              className="w-full flex items-center gap-3 px-5 py-3.5 hover:bg-[#1c1c22] transition-colors text-left"
              onClick={() => setExpanded(e => ({ ...e, [p.id]: !e[p.id] }))}
            >
              <span className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold text-white"
                style={{ backgroundColor: p.color + '30', color: p.color }}>
                {p.icon}
              </span>
              <span className="font-medium text-[#e8e8f0] flex-1">{p.label}</span>
              {cred && <Badge status={cred.status} />}
              {cred?.token_ttl_s != null && (
                <span className="text-xs font-mono text-[#9090a8]">expires {fmtTTL(cred.token_ttl_s)}</span>
              )}
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                className={`text-[#5a5a70] transition-transform ${isExpanded ? 'rotate-180' : ''}`}>
                <polyline points="6 9 12 15 18 9"/>
              </svg>
            </button>

            {/* Metrics row */}
            {cred && (
              <div className="grid grid-cols-4 gap-px bg-[#2a2a32] border-t border-[#2a2a32]">
                {[
                  { label: 'Expires', value: fmtTTL(cred.token_ttl_s) },
                  { label: 'Last Refresh', value: cred.last_refreshed ? new Date(cred.last_refreshed).toLocaleDateString() : '—' },
                  { label: 'Auth Type', value: cred.auth_type || '—' },
                  { label: 'Quota Used', value: cred.quota_total ? `${cred.quota_used}/${cred.quota_total}` : '—' },
                ].map(m => (
                  <div key={m.label} className="bg-[#16161a] px-4 py-2.5 text-center">
                    <div className="text-[10px] text-[#5a5a70] uppercase tracking-wider">{m.label}</div>
                    <div className="text-sm font-mono text-[#e8e8f0] mt-0.5">{m.value}</div>
                  </div>
                ))}
              </div>
            )}

            {/* Expanded config */}
            {isExpanded && (
              <div className="border-t border-[#2a2a32] p-5 space-y-4 bg-[#16161a]">
                {editing === p.id ? (
                  <div className="space-y-3">
                    <Input label="Client ID" value={form.client_id || ''} onChange={e => setForm(f => ({ ...f, client_id: e.target.value }))} />
                    <Input label="Client Secret" type="password" value={form.client_secret || ''} onChange={e => setForm(f => ({ ...f, client_secret: e.target.value }))} placeholder="Leave blank to keep current" />
                    <Input label="Redirect URI" value={form.redirect_uri || ''} onChange={e => setForm(f => ({ ...f, redirect_uri: e.target.value }))} />
                    <div className="flex gap-2 justify-end">
                      <Button variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
                      <Button variant="primary" onClick={handleSave}>Save</Button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div>
                        <div className="text-[#5a5a70] mb-1">Client ID</div>
                        <div className="font-mono text-[#e8e8f0] bg-[#0d0d0f] px-2 py-1.5 rounded truncate">
                          {cred?.client_id || '—'}
                        </div>
                      </div>
                      <div>
                        <div className="text-[#5a5a70] mb-1">Client Secret</div>
                        <div className="font-mono text-[#e8e8f0] bg-[#0d0d0f] px-2 py-1.5 rounded">
                          {cred?.client_secret || '—'}
                        </div>
                      </div>
                      <div>
                        <div className="text-[#5a5a70] mb-1">Redirect URI</div>
                        <div className="font-mono text-[#9090a8] bg-[#0d0d0f] px-2 py-1.5 rounded truncate">
                          {cred?.redirect_uri || '—'}
                        </div>
                      </div>
                      <div>
                        <div className="text-[#5a5a70] mb-1">Scopes</div>
                        <div className="flex flex-wrap gap-1">
                          {(cred?.scopes || []).map(s => (
                            <span key={s} className="text-[9px] bg-[#222228] text-[#9090a8] px-1.5 py-0.5 rounded font-mono">{s.split('/').pop()}</span>
                          ))}
                        </div>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button variant="primary" onClick={() => handleOAuth(p.id)}>OAuth Flow</Button>
                      {cred && <>
                        <Button variant="default" onClick={() => handleRefresh(cred.id)}>Refresh Token</Button>
                        <Button variant="default" onClick={() => handleTest(cred.id)}>Test Connection</Button>
                        <Button variant="danger" onClick={() => handleDisconnect(cred.id)}>Disconnect</Button>
                      </>}
                      <Button variant="ghost" onClick={() => { setForm({ client_id: cred?.client_id || '', redirect_uri: cred?.redirect_uri || '' }); setEditing(p.id) }}>
                        Edit Config
                      </Button>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        )
      })}
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  )
}

// ── Channels Sub-tab ──────────────────────────────────────────────────────────
function ChannelsTab({ onChannelsLoaded }) {
  const [channels,    setChannels]    = useState([])
  const [credentials, setCredentials] = useState([])
  const [loading,     setLoading]     = useState(true)
  const [modal,       setModal]       = useState(false)
  const [editing,     setEditing]     = useState(null)
  const [form,        setForm]        = useState({})
  const [toast,       setToast]       = useState(null)

  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000) }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [chData, credData] = await Promise.all([
        fetchApi('/api/channels'),
        fetchApi('/api/credentials'),
      ])
      setChannels(chData)
      setCredentials(credData)
      onChannelsLoaded?.(chData)
    } catch { setChannels([]) }
    finally { setLoading(false) }
  }, [onChannelsLoaded])

  useEffect(() => { load() }, [load])

  const openCreate = () => {
    setEditing(null)
    setForm({ name: '', platform: 'youtube', status: 'active', default_language: 'en', monetized: false, credential_id: null })
    setModal(true)
  }

  const openEdit = (ch) => {
    setEditing(ch)
    setForm({ ...ch })
    setModal(true)
  }

  const handleSave = async () => {
    try {
      if (editing) {
        await fetchApi(`/api/channels/${editing.id}`, { method: 'PUT', body: JSON.stringify(form) })
        showToast('Channel updated')
      } else {
        await fetchApi('/api/channels', { method: 'POST', body: JSON.stringify(form) })
        showToast('Channel created')
      }
      setModal(false)
      load()
    } catch (e) { showToast(e.message, 'error') }
  }

  const handleToggleStatus = async (ch) => {
    try {
      await fetchApi(`/api/channels/${ch.id}`, {
        method: 'PUT',
        body: JSON.stringify({ status: ch.status === 'active' ? 'paused' : 'active' }),
      })
      load()
    } catch (e) { showToast(e.message, 'error') }
  }

  const handleDelete = async (id) => {
    try {
      await fetchApi(`/api/channels/${id}`, { method: 'DELETE' })
      showToast('Channel deleted')
      load()
    } catch (e) { showToast(e.message, 'error') }
  }

  return (
    <>
      <Card
        title={`Channels (${channels.length})`}
        actions={<Button variant="primary" onClick={openCreate}>+ Add Channel</Button>}
      >
        {loading ? (
          <div className="flex items-center justify-center h-40"><Spinner /></div>
        ) : channels.length === 0 ? (
          <EmptyState title="No channels yet" description="Add a YouTube, TikTok, or Instagram channel to get started." />
        ) : (
          <div className="space-y-2">
            {channels.map(ch => (
              <div key={ch.id} className="flex items-center gap-3 px-4 py-3 rounded-lg border border-[#2a2a32] hover:bg-[#1c1c22] transition-colors">
                <PlatformDot platform={ch.platform} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-[#e8e8f0]">{ch.name}</span>
                    {ch.monetized && <Badge status="active" label="Monetized" />}
                    <Badge status={ch.status} />
                  </div>
                  <div className="text-xs text-[#5a5a70] mt-0.5 font-mono">
                    {ch.account_email || ch.platform} · {ch.subscriber_count?.toLocaleString() || 0} subs · {ch.video_count} videos
                  </div>
                </div>
                <div className="flex gap-1.5">
                  <Button variant="ghost" className="text-xs px-2 py-1" onClick={() => openEdit(ch)}>Edit</Button>
                  <Button
                    variant="ghost"
                    className="text-xs px-2 py-1"
                    onClick={() => handleToggleStatus(ch)}
                  >
                    {ch.status === 'active' ? 'Pause' : 'Resume'}
                  </Button>
                  <Button variant="danger" className="text-xs px-2 py-1" onClick={() => handleDelete(ch.id)}>Delete</Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Channel modal */}
      <Modal open={modal} onClose={() => setModal(false)} title={editing ? 'Edit Channel' : 'Add Channel'}>
        <div className="space-y-3">
          <Input label="Channel Name" value={form.name || ''} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
          <Select label="Platform" value={form.platform || 'youtube'} onChange={e => setForm(f => ({ ...f, platform: e.target.value }))}>
            <option value="youtube">YouTube</option>
            <option value="tiktok">TikTok</option>
            <option value="instagram">Instagram</option>
          </Select>
          <Input label="Account Email" value={form.account_email || ''} onChange={e => setForm(f => ({ ...f, account_email: e.target.value }))} />
          <Input label="Category" value={form.category || ''} onChange={e => setForm(f => ({ ...f, category: e.target.value }))} />
          <Select label="Language" value={form.default_language || 'vi'} onChange={e => setForm(f => ({ ...f, default_language: e.target.value }))}>
            <option value="vi">Vietnamese</option>
            <option value="en">English</option>
          </Select>
          <Select label="Status" value={form.status || 'active'} onChange={e => setForm(f => ({ ...f, status: e.target.value }))}>
            <option value="active">Active</option>
            <option value="paused">Paused</option>
          </Select>
          <Select
            label="OAuth Credential"
            value={form.credential_id ?? ''}
            onChange={e => setForm(f => ({ ...f, credential_id: e.target.value ? Number(e.target.value) : null }))}
          >
            <option value="">— None —</option>
            {credentials
              .filter(c => c.platform === (form.platform || 'youtube'))
              .map(c => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.status})
                </option>
              ))}
          </Select>
          <label className="flex items-center gap-2 text-sm text-[#e8e8f0] cursor-pointer">
            <input
              type="checkbox"
              checked={!!form.monetized}
              onChange={e => setForm(f => ({ ...f, monetized: e.target.checked }))}
              className="accent-[#7c6af7]"
            />
            Monetized
          </label>
        </div>
        <div className="flex justify-end gap-2 mt-5">
          <Button variant="ghost" onClick={() => setModal(false)}>Cancel</Button>
          <Button variant="primary" onClick={handleSave}>Save</Button>
        </div>
      </Modal>

      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </>
  )
}

// ── Main UploadsPage ──────────────────────────────────────────────────────────
export default function UploadsPage() {
  const [tab,      setTab]      = useState('videos')
  const [channels, setChannels] = useState([])

  // Fetch channels on mount so VideosTab has them without requiring ChannelsTab to load first
  useEffect(() => {
    fetchApi('/api/channels')
      .then(data => setChannels(Array.isArray(data) ? data : []))
      .catch(() => {})
  }, [])

  const TABS = [
    { id: 'videos',      label: 'Videos' },
    { id: 'credentials', label: 'Auth & Credentials' },
    { id: 'channels',    label: 'Channels' },
  ]

  // Platform summary cards
  const platformStats = PLATFORMS.map(p => {
    const chCount = channels.filter(c => c.platform === p.id).length
    return { ...p, channels: chCount }
  })

  return (
    <div className="space-y-5">
      {/* Platform overview cards */}
      <div className="grid grid-cols-3 gap-4">
        {platformStats.map(p => (
          <div key={p.id} className="bg-[#1c1c22] border border-[#2a2a32] rounded-xl p-4">
            <div className="flex items-center gap-3 mb-3">
              <span className="w-9 h-9 rounded-lg flex items-center justify-center text-sm font-bold"
                style={{ backgroundColor: p.color + '20', color: p.color }}>
                {p.icon}
              </span>
              <div>
                <div className="font-semibold text-[#e8e8f0]">{p.label}</div>
                <div className="text-xs text-[#5a5a70]">{p.channels} channel{p.channels !== 1 ? 's' : ''}</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Sub-tabs */}
      <div className="flex gap-1 border-b border-[#2a2a32]">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
              tab === t.id
                ? 'text-[#7c6af7] border-[#7c6af7]'
                : 'text-[#9090a8] border-transparent hover:text-[#e8e8f0]'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'videos'      && <VideosTab channels={channels} />}
      {tab === 'credentials' && <CredentialsTab />}
      {tab === 'channels'    && <ChannelsTab onChannelsLoaded={setChannels} />}
    </div>
  )
}
