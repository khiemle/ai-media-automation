import { useState, useEffect, useRef } from 'react'
import { channelPlansApi, fetchApi } from '../api/client.js'
import { Card, Button, Badge, Select, Toast, Spinner, EmptyState, Modal } from '../components/index.jsx'
import AIAssistantPanel from '../components/AIAssistantPanel.jsx'

function PlanCard({ plan, onClick }) {
  return (
    <Card className="cursor-pointer hover:border-[#7c6af7] transition-colors" onClick={onClick}>
      <div className="flex flex-col gap-2">
        <div className="flex items-start justify-between gap-2">
          <div className="text-sm font-semibold text-[#e8e8f0]">{plan.name}</div>
          {plan.channel_id && (
            <Badge status="youtube" label="linked" />
          )}
        </div>
        {plan.focus && (
          <p className="text-xs text-[#9090a8] leading-relaxed">{plan.focus}</p>
        )}
        <div className="flex flex-wrap gap-2 mt-1">
          {plan.upload_frequency && (
            <span className="text-[10px] font-mono bg-[#1c1c22] border border-[#2a2a32] px-2 py-0.5 rounded text-[#9090a8]">
              {plan.upload_frequency}
            </span>
          )}
          {plan.rpm_estimate && (
            <span className="text-[10px] font-mono bg-[#1c1c22] border border-[#2a2a32] px-2 py-0.5 rounded text-[#34d399]">
              RPM {plan.rpm_estimate}
            </span>
          )}
        </div>
        {plan.md_filename && (
          <p className="text-[10px] text-[#5a5a70] font-mono">{plan.md_filename}</p>
        )}
      </div>
    </Card>
  )
}

function ImportModal({ onClose, onImported }) {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleImport = async () => {
    if (!file) { setError('Select a .md file'); return }
    setLoading(true); setError(null)
    try {
      const plan = await channelPlansApi.import(file)
      onImported(plan)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Import Channel Plan"
      width="max-w-sm"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={loading} onClick={handleImport}>Import</Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <p className="text-xs text-[#9090a8]">
          Select a Markdown file following the channel plan template format.
        </p>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Markdown file (.md)</label>
          <input
            type="file"
            accept=".md"
            onChange={e => { setFile(e.target.files?.[0] || null); setError(null) }}
            className="text-sm text-[#9090a8] file:mr-3 file:py-1 file:px-2 file:rounded file:border-0 file:bg-[#2a2a32] file:text-[#e8e8f0] file:text-xs cursor-pointer"
          />
        </div>
        {error && <p className="text-xs text-[#f87171]">{error}</p>}
      </div>
    </Modal>
  )
}

function DetailPanel({ plan: initialPlan, channels, onClose, onSaved }) {
  const [plan, setPlan]           = useState(initialPlan)
  const [mdContent, setMdContent] = useState(initialPlan.md_content ?? '')
  const [channelId, setChannelId] = useState(String(initialPlan.channel_id ?? ''))
  const [activeTab, setActiveTab] = useState('plan')
  const [saving, setSaving]       = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [toast, setToast]         = useState(null)
  const toastTimerRef             = useRef(null)

  useEffect(() => {
    if (!plan.md_content) {
      channelPlansApi.get(plan.id)
        .then(full => { setPlan(full); setMdContent(full.md_content) })
        .catch(() => {})
    }
  }, [plan.id])

  useEffect(() => () => { if (toastTimerRef.current) clearTimeout(toastTimerRef.current) }, [])

  const handleSave = async () => {
    setSaving(true); setSaveError(null)
    try {
      const updated = await channelPlansApi.update(
        plan.id,
        mdContent,
        channelId ? parseInt(channelId, 10) : null
      )
      setPlan(updated)
      setToast({ msg: 'Saved', type: 'success' })
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current)
      toastTimerRef.current = setTimeout(() => setToast(null), 2000)
      onSaved(updated)
    } catch (e) {
      setSaveError(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative w-[560px] h-full bg-[#16161a] border-l border-[#2a2a32] flex flex-col overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#2a2a32] gap-3">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-[#e8e8f0] truncate">{plan.name}</h2>
            {plan.md_filename && (
              <p className="text-[10px] text-[#5a5a70] font-mono truncate">{plan.md_filename}</p>
            )}
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <Button variant="primary" size="sm" loading={saving} onClick={handleSave}>Save</Button>
            <button onClick={onClose} className="text-[#9090a8] hover:text-[#e8e8f0] transition-colors">✕</button>
          </div>
        </div>

        {/* Toast */}
        {toast && (
          <div className="absolute top-16 left-0 right-0 z-10 px-6">
            <Toast message={toast.msg} type={toast.type} />
          </div>
        )}

        {/* Tabs */}
        <div className="flex border-b border-[#2a2a32]">
          {[['plan', 'Plan'], ['ai', 'AI Assistant']].map(([id, label]) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`px-5 py-2.5 text-sm font-medium transition-colors border-b-2 ${
                activeTab === id
                  ? 'border-[#7c6af7] text-[#7c6af7]'
                  : 'border-transparent text-[#9090a8] hover:text-[#e8e8f0]'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-y-auto">
          {activeTab === 'plan' && (
            <div className="flex flex-col gap-4 p-6">
              {/* Metadata chips */}
              <div className="flex flex-wrap gap-2">
                {plan.focus && (
                  <span className="text-[10px] font-mono bg-[#1c1c22] border border-[#2a2a32] px-2 py-0.5 rounded text-[#9090a8]">
                    {plan.focus}
                  </span>
                )}
                {plan.upload_frequency && (
                  <span className="text-[10px] font-mono bg-[#1c1c22] border border-[#2a2a32] px-2 py-0.5 rounded text-[#9090a8]">
                    {plan.upload_frequency}
                  </span>
                )}
                {plan.rpm_estimate && (
                  <span className="text-[10px] font-mono bg-[#1c1c22] border border-[#2a2a32] px-2 py-0.5 rounded text-[#34d399]">
                    RPM {plan.rpm_estimate}
                  </span>
                )}
              </div>

              {/* Channel link */}
              <Select
                label="Linked YouTube Channel (optional)"
                value={channelId}
                onChange={e => setChannelId(e.target.value)}
              >
                <option value="">— Not linked —</option>
                {channels.map(ch => (
                  <option key={ch.id} value={String(ch.id)}>{ch.name}</option>
                ))}
              </Select>

              {/* MD editor */}
              <div className="flex flex-col gap-1">
                <label className="text-xs text-[#9090a8] font-medium">Markdown content</label>
                <textarea
                  value={mdContent}
                  onChange={e => setMdContent(e.target.value)}
                  className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3 text-xs text-[#e8e8f0] font-mono leading-relaxed resize-none focus:outline-none focus:border-[#7c6af7] transition-colors"
                  style={{ minHeight: '50vh' }}
                  spellCheck={false}
                />
              </div>

              {saveError && <p className="text-xs text-[#f87171]">{saveError}</p>}
            </div>
          )}
          {activeTab === 'ai' && (
            <div className="p-6">
              <AIAssistantPanel planId={plan.id} />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function ChannelPlansPage() {
  const [plans, setPlans]           = useState([])
  const [channels, setChannels]     = useState([])
  const [loading, setLoading]       = useState(true)
  const [showImport, setShowImport] = useState(false)
  const [activePlan, setActivePlan] = useState(null)
  const [toast, setToast]           = useState(null)

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  const load = async () => {
    setLoading(true)
    try {
      const [p, ch] = await Promise.all([
        channelPlansApi.list(),
        fetchApi('/api/channels').catch(() => []),
      ])
      setPlans(p)
      setChannels(Array.isArray(ch) ? ch.filter(c => c.platform === 'youtube') : [])
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleImported = (plan) => {
    setShowImport(false)
    showToast(`"${plan.name}" imported`, 'success')
    load()
    setActivePlan(plan)
  }

  const handleSaved = (updated) => {
    setPlans(prev => prev.map(p => p.id === updated.id ? { ...p, ...updated } : p))
  }

  return (
    <div className="flex flex-col gap-6">
      {toast && <Toast message={toast.msg} type={toast.type} />}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#e8e8f0]">Channel Plans</h1>
          <p className="text-sm text-[#9090a8] mt-0.5">{plans.length} plan{plans.length !== 1 ? 's' : ''}</p>
        </div>
        <Button variant="primary" onClick={() => setShowImport(true)}>+ Import Plan</Button>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex justify-center py-12"><Spinner /></div>
      ) : plans.length === 0 ? (
        <EmptyState
          title="No channel plans"
          description="Import a Markdown channel plan file to get started."
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {plans.map(plan => (
            <PlanCard
              key={plan.id}
              plan={plan}
              onClick={() => setActivePlan(plan)}
            />
          ))}
        </div>
      )}

      {showImport && (
        <ImportModal onClose={() => setShowImport(false)} onImported={handleImported} />
      )}

      {activePlan && (
        <DetailPanel
          plan={activePlan}
          channels={channels}
          onClose={() => setActivePlan(null)}
          onSaved={handleSaved}
        />
      )}
    </div>
  )
}
