import { useState, useEffect, useRef } from 'react'
import { Card, Button, Select, Spinner, Toast } from '../components/index.jsx'
import { fetchApi } from '../api/client.js'

export default function LLMPage() {
  const [status,  setStatus]  = useState(null)
  const [quota,   setQuota]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving,  setSaving]  = useState(false)
  const [toast,   setToast]   = useState(null)

  const toastTimer = useRef(null)
  const showToast = (msg, type = 'success') => {
    if (toastTimer.current) clearTimeout(toastTimer.current)
    setToast({ msg, type })
    toastTimer.current = setTimeout(() => setToast(null), 3000)
  }

  const load = () => {
    setLoading(true)
    Promise.all([
      fetchApi('/api/llm/status'),
      fetchApi('/api/llm/quota'),
    ])
      .then(([s, q]) => { setStatus(s); setQuota(q) })
      .catch((e) => showToast(e.message || 'Failed to load LLM status', 'error'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleModelChange = async (model) => {
    setSaving(true)
    try {
      await fetchApi('/api/llm/model', {
        method: 'PUT',
        body: JSON.stringify({ provider: status?.provider ?? 'gemini', model }),
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
