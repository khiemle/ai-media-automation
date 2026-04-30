import { useState, useEffect, useRef } from 'react'
import { Card, Button, Select, Spinner, Toast, ProgressBar } from '../components/index.jsx'
import { fetchApi } from '../api/client.js'

const GEMINI_MEDIA_MODELS = ['veo-3.1-lite-generate-preview', 'veo-2.0-flash', 'veo-2.0-flash-lite']
const GEMINI_MUSIC_MODELS = ['lyria-3-clip-preview', 'lyria-3-pro-preview']
const ELEVENLABS_MODELS   = [
  { value: 'eleven_flash_v2_5',      label: 'Eleven 2.5 Flash',   hint: 'Fast, low-latency. Best for most uses.' },
  { value: 'eleven_v3',              label: 'Eleven 3',           hint: 'Highest quality, most expressive.' },
  { value: 'eleven_multilingual_v2', label: 'Multilingual v2',    hint: 'Legacy. Broad language support.' },
]
const SUNO_MODELS         = ['V4_5', 'V4', 'V3_5']

function KeyInput({ value, onChange, placeholder = '••••••••' }) {
  const [shown, setShown] = useState(false)
  return (
    <div className="flex gap-2 items-center">
      <input
        type={shown ? 'text' : 'password'}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="flex-1 bg-[#16161a] border border-[#2a2a32] rounded px-3 py-1.5 text-sm font-mono text-[#e8e8f0] placeholder-[#5a5a70] focus:outline-none focus:border-[#7c6af7]"
      />
      <button
        type="button"
        onClick={() => setShown(s => !s)}
        className="text-xs text-[#9090a8] hover:text-[#e8e8f0] px-2"
      >
        {shown ? 'hide' : 'show'}
      </button>
    </div>
  )
}

function StatusDot({ available }) {
  return (
    <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 inline-block ${available ? 'bg-[#34d399]' : 'bg-[#f87171]'}`} />
  )
}

export default function LLMPage() {
  const [formData, setFormData] = useState(null)
  const [status,   setStatus]   = useState(null)
  const [quota,    setQuota]    = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [saving,   setSaving]   = useState(null)  // 'script'|'media'|'music'|'elevenlabs'|'kokoro'|'sunoapi'|'pexels'
  const [voices,   setVoices]   = useState(null)
  const [toast,    setToast]    = useState(null)
  const [runwayConfig, setRunwayConfig] = useState(null)
  const [runwayKey, setRunwayKey] = useState('')
  const [runwayModel, setRunwayModel] = useState('gen3-alpha')
  const [runwaySaving, setRunwaySaving] = useState(false)
  const [runwayTesting, setRunwayTesting] = useState(false)
  const [runwayTestResult, setRunwayTestResult] = useState(null)
  const timerRef = useRef(null)

  const showToast = (msg, type = 'success') => {
    if (timerRef.current) clearTimeout(timerRef.current)
    setToast({ msg, type })
    timerRef.current = setTimeout(() => setToast(null), 3000)
  }

  const load = async () => {
    setLoading(true)
    try {
      const [cfg, st, q, v] = await Promise.all([
        fetchApi('/api/llm/config/raw'),
        fetchApi('/api/llm/status'),
        fetchApi('/api/llm/quota'),
        fetchApi('/api/llm/voices'),
      ])
      setFormData(cfg)
      setStatus(st)
      setQuota(q)
      setVoices(v)
    } catch (e) {
      showToast(e.message || 'Failed to load config', 'error')
    } finally {
      setLoading(false)
    }

    // Load Runway config separately
    try {
      const runwayData = await fetchApi('/api/llm/runway')
      setRunwayConfig(runwayData)
      setRunwayModel(runwayData.model || 'gen3-alpha')
    } catch (e) {
      // Silently fail if Runway endpoint not available
    }
  }

  useEffect(() => { load() }, [])
  useEffect(() => () => { if (timerRef.current) clearTimeout(timerRef.current) }, [])

  const patch = (path, value) => {
    setFormData(prev => {
      const next = JSON.parse(JSON.stringify(prev))
      const keys = path.split('.')
      let obj = next
      for (let i = 0; i < keys.length - 1; i++) {
        if (obj[keys[i]] == null) obj[keys[i]] = {}
        obj = obj[keys[i]]
      }
      obj[keys[keys.length - 1]] = value
      return next
    })
  }

  const saveCard = async (cardKey) => {
    setSaving(cardKey)
    try {
      await fetchApi('/api/llm/config', { method: 'PUT', body: JSON.stringify(formData) })
      showToast(`${cardKey} settings saved`)
      const st = await fetchApi('/api/llm/status')
      setStatus(st)
    } catch (e) {
      showToast(e.message || 'Save failed', 'error')
    } finally {
      setSaving(null)
    }
  }

  const handleRunwaySave = async () => {
    setRunwaySaving(true)
    try {
      const result = await fetchApi('/api/llm/runway', {
        method: 'PUT',
        body: JSON.stringify({ api_key: runwayKey, model: runwayModel }),
      })
      setRunwayConfig(result)
      setRunwayKey('')
      showToast('Runway settings saved')
    } catch (e) {
      showToast(e.message || 'Save failed', 'error')
    } finally {
      setRunwaySaving(false)
    }
  }

  const handleRunwayTest = async () => {
    setRunwayTesting(true)
    setRunwayTestResult(null)
    try {
      const result = await fetchApi('/api/llm/runway/test-connection', { method: 'POST' })
      setRunwayTestResult(result)
    } catch (e) {
      setRunwayTestResult({ ok: false, error: e.message })
    } finally {
      setRunwayTesting(false)
    }
  }

  if (loading || !formData) return (
    <div className="flex items-center justify-center h-64"><Spinner /></div>
  )

  const g  = formData.gemini || {}
  const el = formData.elevenlabs || {}
  const su = formData.sunoapi || {}
  const px = formData.pexels || {}
  const ko = formData.kokoro || {}
  const st = status || {}
  const q  = quota  || {}

  return (
    <div className="space-y-5 max-w-2xl">

      {/* Gemini — Script */}
      <Card title={
        <span className="flex items-center gap-2">
          <StatusDot available={st.gemini?.script?.available} />
          Gemini — Script
        </span>
      } actions={saving === 'script' && <Spinner size={16} />}>
        <div className="space-y-3">
          <label className="text-xs text-[#9090a8]">API Key</label>
          <KeyInput value={g.script?.api_key || ''} onChange={v => patch('gemini.script.api_key', v)} />
          <Select
            label="Model"
            value={g.script?.model || ''}
            onChange={e => patch('gemini.script.model', e.target.value)}
            options={(st.gemini?.script?.models?.length
              ? st.gemini.script.models
              : ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-pro']
            ).map(m => ({ value: m, label: m }))}
          />
          {q.gemini_script && !q.gemini_script.error && (
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="bg-[#16161a] rounded-lg p-3 border border-[#2a2a32]">
                <div className="text-[#9090a8] text-xs mb-1">Requests / Min</div>
                <div className="font-mono text-[#e8e8f0]">{q.gemini_script.rpm ?? '—'} <span className="text-[#5a5a70] text-xs">/ {q.gemini_script.rpm_limit ?? '—'}</span></div>
              </div>
              <div className="bg-[#16161a] rounded-lg p-3 border border-[#2a2a32]">
                <div className="text-[#9090a8] text-xs mb-1">Requests / Day</div>
                <div className="font-mono text-[#e8e8f0]">{q.gemini_script.rpd ?? '—'} <span className="text-[#5a5a70] text-xs">/ {q.gemini_script.rpd_limit ?? '—'}</span></div>
              </div>
            </div>
          )}
          <Button size="sm" onClick={() => saveCard('script')}>Save</Button>
        </div>
      </Card>

      {/* Gemini — Media (Veo) */}
      <Card title={
        <span className="flex items-center gap-2">
          <StatusDot available={st.gemini?.media?.available} />
          Gemini — Media (Veo)
        </span>
      } actions={saving === 'media' && <Spinner size={16} />}>
        <div className="space-y-3">
          <label className="text-xs text-[#9090a8]">API Key</label>
          <KeyInput value={g.media?.api_key || ''} onChange={v => patch('gemini.media.api_key', v)} />
          <Select
            label="Model"
            value={g.media?.model || ''}
            onChange={e => patch('gemini.media.model', e.target.value)}
            options={GEMINI_MEDIA_MODELS.map(m => ({ value: m, label: m }))}
          />
          <p className="text-[10px] text-[#5a5a70] font-mono">Quota managed by Google AI Studio</p>
          <Button size="sm" onClick={() => saveCard('media')}>Save</Button>
        </div>
      </Card>

      {/* Gemini — Music (Lyria) */}
      <Card title={
        <span className="flex items-center gap-2">
          <StatusDot available={st.gemini?.music?.available} />
          Gemini — Music (Lyria)
        </span>
      } actions={saving === 'music' && <Spinner size={16} />}>
        <div className="space-y-3">
          <label className="text-xs text-[#9090a8]">API Key</label>
          <KeyInput value={g.music?.api_key || ''} onChange={v => patch('gemini.music.api_key', v)} />
          <Select
            label="Model"
            value={g.music?.model || ''}
            onChange={e => patch('gemini.music.model', e.target.value)}
            options={GEMINI_MUSIC_MODELS.map(m => ({ value: m, label: m }))}
          />
          <p className="text-[10px] text-[#5a5a70] font-mono">Quota managed by Google AI Studio</p>
          <Button size="sm" onClick={() => saveCard('music')}>Save</Button>
        </div>
      </Card>

      {/* ElevenLabs */}
      <Card title={
        <span className="flex items-center gap-2">
          <StatusDot available={st.elevenlabs?.available} />
          ElevenLabs
        </span>
      } actions={saving === 'elevenlabs' && <Spinner size={16} />}>
        <div className="space-y-3">
          <label className="text-xs text-[#9090a8]">API Key</label>
          <KeyInput value={el.api_key || ''} onChange={v => patch('elevenlabs.api_key', v)} />

          {/* Model */}
          <div>
            <label className="text-xs text-[#9090a8] block mb-1">Model</label>
            <select
              value={el.model || 'eleven_flash_v2_5'}
              onChange={e => patch('elevenlabs.model', e.target.value)}
              className="w-full bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7] transition-colors appearance-none cursor-pointer"
            >
              {ELEVENLABS_MODELS.map(m => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
            <p className="text-[10px] text-[#5a5a70] mt-1 font-mono">
              {ELEVENLABS_MODELS.find(m => m.value === (el.model || 'eleven_flash_v2_5'))?.hint}
            </p>
          </div>

          {/* Default EN voice */}
          <div>
            <label className="text-xs text-[#9090a8] block mb-1">Default English Voice</label>
            <select
              value={el.voice_id_en || ''}
              onChange={e => patch('elevenlabs.voice_id_en', e.target.value)}
              className="w-full bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7] transition-colors appearance-none cursor-pointer"
            >
              <option value="">— select —</option>
              {voices && (
                <>
                  <optgroup label="Male">
                    {voices.elevenlabs?.en?.male?.map(v => (
                      <option key={v.id} value={v.id}>{v.name !== 'Unknown' ? v.name : v.id}</option>
                    ))}
                  </optgroup>
                  <optgroup label="Female">
                    {voices.elevenlabs?.en?.female?.map(v => (
                      <option key={v.id} value={v.id}>{v.name !== 'Unknown' ? v.name : v.id}</option>
                    ))}
                  </optgroup>
                </>
              )}
            </select>
          </div>

          {/* Default VI voice */}
          <div>
            <label className="text-xs text-[#9090a8] block mb-1">Default Vietnamese Voice</label>
            <select
              value={el.voice_id_vi || ''}
              onChange={e => patch('elevenlabs.voice_id_vi', e.target.value)}
              className="w-full bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7] transition-colors appearance-none cursor-pointer"
            >
              <option value="">— select —</option>
              {voices && (
                <>
                  <optgroup label="Male">
                    {voices.elevenlabs?.vi?.male?.map(v => (
                      <option key={v.id} value={v.id}>{v.name !== 'Unknown' ? v.name : v.id}</option>
                    ))}
                  </optgroup>
                  <optgroup label="Female">
                    {voices.elevenlabs?.vi?.female?.map(v => (
                      <option key={v.id} value={v.id}>{v.name !== 'Unknown' ? v.name : v.id}</option>
                    ))}
                  </optgroup>
                </>
              )}
            </select>
          </div>

          {q.elevenlabs && !q.elevenlabs.error && !q.elevenlabs.scope_restricted && (
            <div>
              <div className="flex justify-between text-xs text-[#9090a8] mb-1">
                <span>Characters this month</span>
                <span className="font-mono">{q.elevenlabs.characters_used?.toLocaleString()} / {q.elevenlabs.characters_limit?.toLocaleString()}</span>
              </div>
              <ProgressBar value={q.elevenlabs.characters_used} max={q.elevenlabs.characters_limit} />
            </div>
          )}
          {q.elevenlabs?.scope_restricted && (
            <p className="text-xs text-[#9090a8]">
              Quota unavailable — add <span className="font-mono">user_read</span> permission to the API key to see usage
            </p>
          )}
          {q.elevenlabs?.error && <p className="text-xs text-[#f87171] font-mono">{q.elevenlabs.error}</p>}
          <Button size="sm" onClick={() => saveCard('elevenlabs')}>Save</Button>
        </div>
      </Card>

      {/* Kokoro TTS */}
      <Card title={
        <span className="flex items-center gap-2">
          <StatusDot available={st.kokoro?.available} />
          Kokoro TTS
        </span>
      } actions={saving === 'kokoro' && <Spinner size={16} />}>
        <div className="space-y-3">
          <p className="text-xs text-[#9090a8]">Local neural TTS — no API key required.</p>
          <div>
            <label className="text-xs text-[#9090a8] block mb-1">Default English Voice</label>
            <select
              value={ko.default_voice_en || 'af_heart'}
              onChange={e => patch('kokoro.default_voice_en', e.target.value)}
              className="w-full bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7] transition-colors appearance-none cursor-pointer"
            >
              {voices && (
                <>
                  <optgroup label="American English — Female">
                    {voices.kokoro?.american_english?.female?.map(v => (
                      <option key={v.id} value={v.id}>{v.name} ({v.id})</option>
                    ))}
                  </optgroup>
                  <optgroup label="American English — Male">
                    {voices.kokoro?.american_english?.male?.map(v => (
                      <option key={v.id} value={v.id}>{v.name} ({v.id})</option>
                    ))}
                  </optgroup>
                  <optgroup label="British English — Female">
                    {voices.kokoro?.british_english?.female?.map(v => (
                      <option key={v.id} value={v.id}>{v.name} ({v.id})</option>
                    ))}
                  </optgroup>
                  <optgroup label="British English — Male">
                    {voices.kokoro?.british_english?.male?.map(v => (
                      <option key={v.id} value={v.id}>{v.name} ({v.id})</option>
                    ))}
                  </optgroup>
                </>
              )}
            </select>
          </div>
          <Button size="sm" onClick={() => saveCard('kokoro')}>Save</Button>
        </div>
      </Card>

      {/* Suno */}
      <Card title={
        <span className="flex items-center gap-2">
          <StatusDot available={st.sunoapi?.available} />
          Suno
        </span>
      } actions={saving === 'sunoapi' && <Spinner size={16} />}>
        <div className="space-y-3">
          <label className="text-xs text-[#9090a8]">API Key</label>
          <KeyInput value={su.api_key || ''} onChange={v => patch('sunoapi.api_key', v)} />
          <Select
            label="Model"
            value={su.model || ''}
            onChange={e => patch('sunoapi.model', e.target.value)}
            options={SUNO_MODELS.map(m => ({ value: m, label: m }))}
          />
          {q.sunoapi?.credits != null && (
            <p className="text-xs text-[#9090a8] font-mono">Credits remaining: {q.sunoapi.credits}</p>
          )}
          {q.sunoapi?.error && <p className="text-xs text-[#f87171] font-mono">{q.sunoapi.error}</p>}
          <Button size="sm" onClick={() => saveCard('sunoapi')}>Save</Button>
        </div>
      </Card>

      {/* Pexels */}
      <Card title={
        <span className="flex items-center gap-2">
          <StatusDot available={st.pexels?.available} />
          Pexels
        </span>
      } actions={saving === 'pexels' && <Spinner size={16} />}>
        <div className="space-y-3">
          <label className="text-xs text-[#9090a8]">API Key</label>
          <KeyInput value={px.api_key || ''} onChange={v => patch('pexels.api_key', v)} />
          {q.pexels?.status === 'ok'
            ? <p className="text-xs text-[#34d399] font-mono">Connected ✓</p>
            : q.pexels?.status
              ? <p className="text-xs text-[#f87171] font-mono">{q.pexels.status}</p>
              : null
          }
          <Button size="sm" onClick={() => saveCard('pexels')}>Save</Button>
        </div>
      </Card>

      {/* Runway */}
      <Card title={
        <span className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full flex-shrink-0 inline-block bg-[#14b8a6]" />
          Runway
        </span>
      } actions={runwaySaving && <Spinner size={16} />}>
        <div className="space-y-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[#9090a8] font-medium">API Key</label>
            <KeyInput
              value={runwayKey}
              onChange={v => setRunwayKey(v)}
              placeholder="rw-..."
            />
            {runwayConfig?.api_key_masked && (
              <span className="text-xs text-[#5a5a70] font-mono">{runwayConfig.api_key_masked}</span>
            )}
          </div>
          <Select
            label="Model"
            value={runwayModel}
            onChange={e => setRunwayModel(e.target.value)}
            options={[
              { value: 'gen3-alpha', label: 'gen3-alpha' },
              { value: 'gen4-turbo', label: 'gen4-turbo' },
            ]}
          />
          <div className="flex gap-2">
            <Button size="sm" loading={runwaySaving} onClick={handleRunwaySave}>Save</Button>
            <Button size="sm" variant="ghost" loading={runwayTesting} onClick={handleRunwayTest}>Test Connection</Button>
          </div>
          {runwayTestResult && (
            <div className={`text-xs px-3 py-2 rounded-lg font-mono ${runwayTestResult.ok ? 'bg-[#34d399] bg-opacity-10 text-[#34d399]' : 'bg-[#f87171] bg-opacity-10 text-[#f87171]'}`}>
              {runwayTestResult.ok ? '✓ Connected' : `✗ ${runwayTestResult.error}`}
            </div>
          )}
        </div>
      </Card>

      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  )
}
