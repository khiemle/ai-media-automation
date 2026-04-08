import { useState, useEffect } from 'react'
import { Card, Button, Spinner, Toast } from '../components/index.jsx'
import { fetchApi } from '../api/client.js'

function ModeCard({ id, info, active, onSelect }) {
  const costColor = info.cost === 'Free' ? '#34d399'
    : info.cost === '$$' ? '#f87171'
    : info.cost === '$'  ? '#fbbf24'
    : '#9090a8'

  return (
    <button
      onClick={() => onSelect(id)}
      className={`w-full text-left p-4 rounded-xl border-2 transition-all ${
        active
          ? 'border-[#7c6af7] bg-[#7c6af7]/10'
          : 'border-[#2a2a32] bg-[#16161a] hover:border-[#5a5a70]'
      }`}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <span className="font-semibold text-[#e8e8f0] text-sm">{info.label}</span>
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono font-bold" style={{ color: costColor }}>{info.cost}</span>
          {active && (
            <span className="text-[10px] bg-[#7c6af7] text-white px-1.5 py-0.5 rounded font-mono">ACTIVE</span>
          )}
        </div>
      </div>
      <p className="text-xs text-[#9090a8] leading-relaxed">{info.description}</p>
      <div className="flex flex-wrap gap-1 mt-2">
        {info.models?.map(m => (
          <span key={m} className="text-[9px] bg-[#222228] text-[#5a5a70] px-1.5 py-0.5 rounded font-mono">{m}</span>
        ))}
      </div>
    </button>
  )
}

function ProviderCard({ name, status, color }) {
  const dot = status?.available ? '#34d399' : '#f87171'
  return (
    <div className="bg-[#16161a] border border-[#2a2a32] rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: dot }} />
        <span className="font-semibold text-[#e8e8f0]">{name}</span>
        <span className={`text-xs font-mono ml-auto ${status?.available ? 'text-[#34d399]' : 'text-[#f87171]'}`}>
          {status?.available ? 'Online' : 'Offline'}
        </span>
      </div>
      {status?.error && (
        <div className="text-[10px] text-[#f87171] font-mono bg-[#1e0a0a] px-2 py-1 rounded mb-2 truncate">
          {status.error}
        </div>
      )}
      {status?.endpoint && (
        <div className="text-[10px] text-[#5a5a70] font-mono">{status.endpoint}</div>
      )}
      {status?.models?.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {status.models.slice(0, 4).map(m => (
            <span key={m} className="text-[9px] bg-[#222228] text-[#9090a8] px-1.5 py-0.5 rounded font-mono">{m}</span>
          ))}
        </div>
      )}
    </div>
  )
}

export default function LLMPage() {
  const [status,  setStatus]  = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving,  setSaving]  = useState(false)
  const [toast,   setToast]   = useState(null)

  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000) }

  useEffect(() => {
    fetchApi('/api/llm/status')
      .then(setStatus)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const handleSelect = async (mode) => {
    setSaving(true)
    try {
      await fetchApi('/api/llm/mode', { method: 'PUT', body: JSON.stringify({ mode }) })
      setStatus(s => ({ ...s, mode }))
      showToast(`LLM mode set to: ${status?.all_modes?.[mode]?.label || mode}`)
    } catch (e) {
      showToast(e.message, 'error')
    } finally { setSaving(false) }
  }

  if (loading) return <div className="flex items-center justify-center h-64"><Spinner /></div>

  const allModes = status?.all_modes || {}
  const activeMode = status?.mode || 'hybrid'

  return (
    <div className="space-y-5">
      {/* Mode selector */}
      <Card title="LLM Routing Mode" actions={saving && <Spinner size={16} />}>
        <div className="grid grid-cols-2 gap-3">
          {Object.entries(allModes).map(([id, info]) => (
            <ModeCard key={id} id={id} info={info} active={activeMode === id} onSelect={handleSelect} />
          ))}
        </div>
      </Card>

      {/* Provider status */}
      <Card title="Provider Status">
        <div className="grid grid-cols-2 gap-4">
          <ProviderCard name="Google Gemini" status={status?.gemini} color="#4a9eff" />
          <ProviderCard name="Ollama (Local)" status={status?.ollama} color="#34d399" />
        </div>
      </Card>

      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  )
}
