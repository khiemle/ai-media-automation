import { useState, useEffect, useCallback } from 'react'
import { Card, Badge, Button, Spinner, EmptyState, Modal, Textarea, Input, Select, Toast } from '../components/index.jsx'
import AssetBrowser from '../components/AssetBrowser.jsx'
import { fetchApi } from '../api/client.js'

const STATUS_COLOR = {
  approved: '#34d399', editing: '#4a9eff', producing: '#7c6af7', completed: '#34d399',
}

// ── Scene Card ────────────────────────────────────────────────────────────────
function SceneCard({ scene, index, scriptId, onUpdate, onToast }) {
  const [expanded, setExpanded]           = useState(false)
  const [assetBrowser, setAssetBrowser]   = useState(false)
  const [narration, setNarration]         = useState(scene.narration || '')
  const [visualHint, setVisualHint]       = useState(scene.visual_hint || '')
  const [overlay, setOverlay]             = useState(scene.text_overlay || '')
  const [ttsLoading, setTtsLoading]       = useState(false)
  const [veoLoading, setVeoLoading]       = useState(false)

  const handleAssetSelect = async (asset) => {
    try {
      await fetchApi(`/api/production/scripts/${scriptId}/scenes/${index}/asset`, {
        method: 'PUT',
        body: JSON.stringify({ asset_id: asset.id }),
      })
      onToast('Asset replaced')
      onUpdate()
    } catch (e) {
      onToast(e.message, 'error')
    }
  }

  const handleTtsRegen = async () => {
    setTtsLoading(true)
    try {
      const res = await fetchApi(`/api/production/scripts/${scriptId}/scenes/${index}/tts`, { method: 'POST' })
      onToast(`TTS queued (task: ${res.task_id?.slice(0, 8)}…)`)
    } catch (e) {
      onToast(e.message, 'error')
    } finally { setTtsLoading(false) }
  }

  const handleVeoGen = async () => {
    setVeoLoading(true)
    try {
      const res = await fetchApi(`/api/production/scripts/${scriptId}/scenes/${index}/veo`, { method: 'POST' })
      onToast(`Veo queued (task: ${res.task_id?.slice(0, 8)}…)`)
    } catch (e) {
      onToast(e.message, 'error')
    } finally { setVeoLoading(false) }
  }

  const durationPct = scene.duration ? Math.min((scene.duration / 60) * 100, 100) : 5

  return (
    <div className="border border-[#2a2a32] rounded-lg overflow-hidden bg-[#16161a]">
      {/* Scene header */}
      <button
        className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-[#1c1c22] transition-colors text-left"
        onClick={() => setExpanded(e => !e)}
      >
        <span className="text-xs font-mono text-[#5a5a70] w-6">{String(index + 1).padStart(2, '0')}</span>
        <span className="text-xs font-mono text-[#fbbf24] w-12">{scene.type || 'scene'}</span>
        {/* Readiness dots */}
        <span title={scene.asset_id ? 'Asset assigned' : 'No asset'}
          className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${scene.asset_id ? 'bg-[#34d399]' : 'bg-[#5a5a70]'}`} />
        <span title={scene.tts_audio_url ? 'Audio ready' : 'No audio'}
          className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${scene.tts_audio_url ? 'bg-[#34d399]' : 'bg-[#5a5a70]'}`} />
        <span className="text-sm text-[#e8e8f0] flex-1 truncate">{scene.narration?.slice(0, 80) || '—'}</span>
        <span className="text-xs font-mono text-[#9090a8]">{scene.duration || 0}s</span>
        <svg
          width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          className={`text-[#5a5a70] transition-transform ${expanded ? 'rotate-180' : ''}`}
        >
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </button>

      {/* Expanded editor */}
      {expanded && (
        <div className="border-t border-[#2a2a32] p-4 grid grid-cols-2 gap-4">
          {/* Left — visual asset */}
          <div className="space-y-3">
            <div className="text-xs font-semibold text-[#9090a8] uppercase tracking-wider">Visual Asset</div>
            <div className="aspect-[9/16] max-h-48 bg-[#0d0d0f] rounded-lg border border-[#2a2a32] flex items-center justify-center overflow-hidden">
              {scene.asset_thumbnail_url ? (
                <img src={scene.asset_thumbnail_url} alt="asset thumbnail"
                  className="w-full h-full object-cover" />
              ) : scene.asset_id ? (
                <div className="text-xs text-[#7c6af7] font-mono">Asset #{scene.asset_id}</div>
              ) : (
                <div className="text-xs text-[#5a5a70]">No asset</div>
              )}
            </div>
            <div className="flex items-center gap-2 text-xs font-mono text-[#9090a8]">
              {scene.asset_source && (
                <span className="px-1.5 py-0.5 rounded bg-[#1c1c22] border border-[#2a2a32]">{scene.asset_source}</span>
              )}
              {scene.asset_duration && <span>{scene.asset_duration}s clip</span>}
            </div>
            <Input
              label="Visual hint"
              value={visualHint}
              onChange={e => setVisualHint(e.target.value)}
              placeholder="Describe the visual…"
            />
            <div className="flex gap-2">
              <Button variant="default" className="flex-1 justify-center text-xs" onClick={() => setAssetBrowser(true)}>
                Replace
              </Button>
              <Button variant="ghost" className="flex-1 justify-center text-xs" onClick={handleVeoGen} loading={veoLoading}>
                Veo Gen
              </Button>
            </div>
          </div>

          {/* Right — audio / narration */}
          <div className="space-y-3">
            <div className="text-xs font-semibold text-[#9090a8] uppercase tracking-wider">Audio</div>
            {scene.tts_audio_url ? (
              <audio controls src={scene.tts_audio_url}
                className="w-full h-8 accent-[#7c6af7]" />
            ) : (
              <div className="text-xs text-[#5a5a70] py-2 border border-dashed border-[#2a2a32] rounded text-center">No audio yet</div>
            )}
            <Textarea
              label="Narration"
              value={narration}
              onChange={e => setNarration(e.target.value)}
              rows={5}
              placeholder="Narration text…"
            />
            <Input
              label="Text overlay"
              value={overlay}
              onChange={e => setOverlay(e.target.value)}
              placeholder="On-screen text…"
            />
            <Button variant="default" className="w-full justify-center text-xs" onClick={handleTtsRegen} loading={ttsLoading}>
              Regenerate TTS
            </Button>
          </div>
        </div>
      )}

      {/* Asset Browser */}
      <AssetBrowser
        open={assetBrowser}
        onClose={() => setAssetBrowser(false)}
        onSelect={handleAssetSelect}
        title={`Replace Scene ${index + 1} Asset`}
      />
    </div>
  )
}


// ── Main Page ─────────────────────────────────────────────────────────────────
export default function ProductionPage() {
  const [scripts,    setScripts]    = useState([])
  const [activeId,   setActiveId]   = useState(null)
  const [script,     setScript]     = useState(null)
  const [loading,    setLoading]    = useState(false)
  const [rendering,  setRendering]  = useState(false)
  const [toast,      setToast]      = useState(null)

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  // Load approved/editing scripts
  useEffect(() => {
    fetchApi('/api/scripts?status=approved&per_page=50')
      .then(r => {
        const items = r.items || []
        // Also fetch editing
        return fetchApi('/api/scripts?status=editing&per_page=50').then(r2 => {
          setScripts([...items, ...(r2.items || [])])
        })
      })
      .catch(() => setScripts([]))
  }, [])

  const loadScript = useCallback(async (id) => {
    setLoading(true)
    setActiveId(id)
    try {
      const data = await fetchApi(`/api/production/scripts/${id}`)
      setScript(data)
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setLoading(false)
    }
  }, [])

  const handleStartRender = async () => {
    if (!activeId) return
    setRendering(true)
    try {
      const res = await fetchApi(`/api/production/scripts/${activeId}/render`, { method: 'POST' })
      showToast(`Render started (task: ${res.task_id?.slice(0, 8)}…)`)
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setRendering(false)
    }
  }

  const scenes  = script?.script_json?.scenes || []
  const vidMeta = script?.script_json?.video   || {}

  // Timeline widths proportional to scene duration
  const totalDur = scenes.reduce((s, sc) => s + (sc.duration || 5), 0) || 1

  return (
    <div className="flex gap-4 h-full">
      {/* ── Sidebar — script list ── */}
      <aside className="w-56 flex-shrink-0">
        <Card title="Ready to Produce">
          {scripts.length === 0 ? (
            <p className="text-xs text-[#9090a8]">No approved scripts yet.</p>
          ) : (
            <div className="space-y-1 -mx-2">
              {scripts.map(s => {
                const isActive = activeId === s.id
                const readyCount = isActive && script
                  ? (script.script_json?.scenes || []).filter(sc => sc.asset_id && sc.tts_audio_url).length
                  : null
                const totalCount = isActive && script
                  ? (script.script_json?.scenes || []).length
                  : null
                return (
                <button
                  key={s.id}
                  onClick={() => loadScript(s.id)}
                  className={`w-full text-left px-3 py-2 rounded-lg transition-colors text-xs ${
                    activeId === s.id
                      ? 'bg-[#7c6af7]/20 text-[#7c6af7]'
                      : 'hover:bg-[#1c1c22] text-[#9090a8]'
                  }`}
                >
                  <div className="font-medium text-[#e8e8f0] truncate">{s.topic || `Script #${s.id}`}</div>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <Badge status={s.status} />
                    <span className="text-[#5a5a70] font-mono">{s.niche}</span>
                  </div>
                  {isActive && readyCount !== null && (
                    <span className="text-[#5a5a70] font-mono text-[10px]">{readyCount}/{totalCount} ready</span>
                  )}
                </button>
                )
              })}
            </div>
          )}
        </Card>
      </aside>

      {/* ── Main content ── */}
      <div className="flex-1 space-y-4 min-w-0">
        {!activeId ? (
          <EmptyState title="Select a script from the sidebar to start production editing." />
        ) : loading ? (
          <div className="flex items-center justify-center h-64"><Spinner /></div>
        ) : script ? (
          <>
            {/* Header */}
            <Card
              title={script.topic || `Script #${script.id}`}
              actions={
                <div className="flex gap-2">
                  <Badge status={script.status} />
                  <Button
                    variant="primary"
                    onClick={handleStartRender}
                    loading={rendering}
                    disabled={!['approved', 'editing'].includes(script.status)}
                  >
                    Start Render
                  </Button>
                </div>
              }
            >
              <div className="flex gap-6 text-xs text-[#9090a8]">
                <span><span className="text-[#5a5a70]">Template</span> {script.template || '—'}</span>
                <span><span className="text-[#5a5a70]">Niche</span> {script.niche || '—'}</span>
                <span><span className="text-[#5a5a70]">Voice</span> {vidMeta.voice || '—'}</span>
                <span><span className="text-[#5a5a70]">Duration</span> {vidMeta.total_duration || totalDur}s</span>
                <span><span className="text-[#5a5a70]">Scenes</span> {scenes.length}</span>
              </div>
              {vidMeta.hook && (
                <div className="mt-2 text-xs text-[#9090a8]">
                  <span className="text-[#5a5a70]">Hook </span>
                  <span className="text-[#e8e8f0] italic">"{vidMeta.hook}"</span>
                </div>
              )}
            </Card>

            {/* Timeline bar */}
            {scenes.length > 0 && (
              <div className="bg-[#1c1c22] border border-[#2a2a32] rounded-xl p-4">
                <div className="text-xs font-semibold text-[#9090a8] uppercase tracking-wider mb-3">Timeline</div>
                <div className="flex gap-0.5 h-6 rounded overflow-hidden">
                  {scenes.map((sc, i) => {
                    const pct = ((sc.duration || 5) / totalDur) * 100
                    const colors = ['#7c6af7','#4a9eff','#34d399','#fbbf24','#f87171','#c084fc']
                    return (
                      <div
                        key={i}
                        style={{ width: `${pct}%`, backgroundColor: colors[i % colors.length] + '60' }}
                        className="relative group cursor-pointer flex items-center justify-center hover:opacity-80 transition-opacity"
                        title={`Scene ${i + 1}: ${sc.duration || 5}s`}
                      >
                        <span className="text-[9px] text-white font-mono opacity-80">{i + 1}</span>
                      </div>
                    )
                  })}
                </div>
                <div className="flex justify-between mt-1 text-[9px] font-mono text-[#5a5a70]">
                  <span>0s</span><span>{totalDur}s</span>
                </div>
              </div>
            )}

            {/* Scene list */}
            <Card title={`Scenes (${scenes.length})`}>
              {scenes.length === 0 ? (
                <EmptyState title="No scenes in this script." />
              ) : (
                <div className="space-y-2">
                  {scenes.map((sc, i) => (
                    <SceneCard
                      key={i}
                      scene={sc}
                      index={i}
                      scriptId={activeId}
                      onUpdate={() => loadScript(activeId)}
                      onToast={showToast}
                    />
                  ))}
                </div>
              )}
            </Card>
          </>
        ) : null}
      </div>

      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  )
}
