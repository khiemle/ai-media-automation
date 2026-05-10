import { useState, useEffect, useCallback } from 'react'
import { Card, Spinner, Badge, Button, Input } from '../components/index.jsx'
import { fetchApi } from '../api/client.js'

// ── Gauge ─────────────────────────────────────────────────────────────────────
function Gauge({ label, value, unit = '%', max = 100, sub }) {
  const pct   = Math.min((value / max) * 100, 100)
  const color = pct >= 90 ? '#f87171' : pct >= 70 ? '#fbbf24' : '#34d399'
  const r = 28, cx = 36, cy = 36
  const circ = 2 * Math.PI * r
  const arc  = circ * 0.75  // 270° arc
  const dash = (pct / 100) * arc

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width="72" height="72" viewBox="0 0 72 72">
        {/* Track */}
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="#2a2a32" strokeWidth="6"
          strokeDasharray={`${arc} ${circ}`}
          strokeDashoffset={-circ * 0.125}
          strokeLinecap="round" transform={`rotate(135 ${cx} ${cy})`} />
        {/* Value */}
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={color} strokeWidth="6"
          strokeDasharray={`${dash} ${circ}`}
          strokeDashoffset={-circ * 0.125}
          strokeLinecap="round" transform={`rotate(135 ${cx} ${cy})`}
          style={{ transition: 'stroke-dasharray 0.5s ease' }} />
        <text x={cx} y={cy - 2} textAnchor="middle" fill="#e8e8f0" fontSize="13" fontWeight="bold" fontFamily="monospace">
          {Math.round(value)}
        </text>
        <text x={cx} y={cy + 11} textAnchor="middle" fill="#9090a8" fontSize="8" fontFamily="monospace">
          {unit}
        </text>
      </svg>
      <div className="text-xs text-[#9090a8] text-center">{label}</div>
      {sub && <div className="text-[10px] text-[#5a5a70] text-center font-mono">{sub}</div>}
    </div>
  )
}

// ── Service dot ───────────────────────────────────────────────────────────────
function ServiceDot({ ok }) {
  return (
    <span className={`inline-block w-2 h-2 rounded-full ${ok ? 'bg-[#34d399]' : 'bg-[#f87171]'}`} />
  )
}

// ── MCP service-account token card ────────────────────────────────────────────
function McpTokenCard() {
  const [days, setDays]         = useState(90)
  const [result, setResult]     = useState(null)  // {token, expires_at, lifetime_days}
  const [error, setError]       = useState(null)
  const [loading, setLoading]   = useState(false)
  const [showFull, setShowFull] = useState(false)
  const [copied, setCopied]     = useState(null)  // 'token' | 'cmd' | null

  // Default API base = same origin, port 8080. User can edit.
  const defaultBase = `${window.location.protocol}//${window.location.hostname}:8080`
  const [apiBase, setApiBase] = useState(defaultBase)

  const generate = async () => {
    setLoading(true); setError(null); setResult(null); setShowFull(false)
    try {
      const r = await fetchApi('/api/system/mcp/mint-token', {
        method: 'POST',
        body: JSON.stringify({ days: Number(days) || 90 }),
      })
      setResult(r)
    } catch (e) {
      setError(e?.message || 'Failed to mint token. Admin role required.')
    } finally {
      setLoading(false)
    }
  }

  const copy = async (text, key) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(key)
      setTimeout(() => setCopied(null), 1500)
    } catch {}
  }

  const claudeAddCmd = result
    ? `claude mcp add ai-media-console-prod \\
  --transport stdio \\
  --env MCP_API_TOKEN="${result.token}" \\
  --env MCP_CONSOLE_API_BASE=${apiBase} \\
  -- python -m console.mcp.stdio`
    : ''

  const tokenPreview = (t) => {
    if (!t) return ''
    if (showFull) return t
    return `${t.slice(0, 12)}…${t.slice(-8)}`
  }

  return (
    <Card title="MCP Service Token">
      <div className="space-y-3">
        <p className="text-xs text-[#9090a8]">
          Mint a JWT for the <span className="font-mono text-[#e8e8f0]">mcp-system</span> service-account user
          to configure local Claude Code MCP without SSH-ing into this host. Anyone with this
          token can act as <span className="font-mono">mcp-system</span> (admin role) — treat it like a password.
        </p>

        <div className="flex items-end gap-2">
          <Input
            label="Lifetime (days)"
            type="number"
            value={days}
            onChange={e => setDays(e.target.value)}
            className="w-32"
            min="1"
            max="365"
          />
          <Input
            label="API base URL (passed to MCP)"
            value={apiBase}
            onChange={e => setApiBase(e.target.value)}
            placeholder="http://host:8080"
            className="flex-1"
          />
          <Button variant="primary" onClick={generate} loading={loading} disabled={loading}>
            Generate Token
          </Button>
        </div>

        {error && (
          <div className="text-xs text-[#f87171] bg-[#1e0a0a] border border-[#3e1e1e] rounded px-3 py-2">
            {error}
          </div>
        )}

        {result && (
          <div className="space-y-3 pt-2 border-t border-[#2a2a32]">
            <div className="flex items-center justify-between text-xs">
              <span className="text-[#9090a8]">Expires</span>
              <span className="text-[#e8e8f0] font-mono">
                {new Date(result.expires_at).toLocaleString()} ({result.lifetime_days}d)
              </span>
            </div>

            {/* Token */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-[#9090a8] font-medium">JWT Token</span>
                <div className="flex gap-2">
                  <button onClick={() => setShowFull(s => !s)}
                    className="text-xs text-[#7c6af7] hover:text-[#9888f9] transition-colors">
                    {showFull ? 'Hide' : 'Reveal'}
                  </button>
                  <button onClick={() => copy(result.token, 'token')}
                    className="text-xs text-[#7c6af7] hover:text-[#9888f9] transition-colors">
                    {copied === 'token' ? '✓ Copied' : 'Copy token'}
                  </button>
                </div>
              </div>
              <div className="bg-[#0d0d0f] border border-[#2a2a32] rounded px-3 py-2 font-mono text-xs text-[#e8e8f0] break-all select-all">
                {tokenPreview(result.token)}
              </div>
            </div>

            {/* claude mcp add command */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-[#9090a8] font-medium">claude CLI command (paste in your terminal)</span>
                <button onClick={() => copy(claudeAddCmd, 'cmd')}
                  className="text-xs text-[#7c6af7] hover:text-[#9888f9] transition-colors">
                  {copied === 'cmd' ? '✓ Copied' : 'Copy command'}
                </button>
              </div>
              <pre className="bg-[#0d0d0f] border border-[#2a2a32] rounded px-3 py-2 font-mono text-[11px] text-[#e8e8f0] whitespace-pre overflow-x-auto leading-relaxed">
{claudeAddCmd}
              </pre>
              <p className="text-[10px] text-[#5a5a70] mt-1">
                After running, restart Claude Code and verify with <span className="font-mono text-[#9090a8]">claude mcp list</span>.
              </p>
            </div>
          </div>
        )}
      </div>
    </Card>
  )
}

export default function SystemPage() {
  const [health,  setHealth]  = useState(null)
  const [cron,    setCron]    = useState([])
  const [errors,  setErrors]  = useState([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      const [h, c, e] = await Promise.all([
        fetchApi('/api/system/health'),
        fetchApi('/api/system/cron'),
        fetchApi('/api/system/errors?limit=50'),
      ])
      setHealth(h)
      setCron(c)
      setErrors(e)
    } catch {}
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  // Auto-refresh every 10s
  useEffect(() => {
    const t = setInterval(load, 10000)
    return () => clearInterval(t)
  }, [load])

  if (loading) return <div className="flex items-center justify-center h-64"><Spinner /></div>

  const cpu   = health?.cpu   || {}
  const ram   = health?.ram   || {}
  const disk  = health?.disk  || {}
  const gpu   = health?.gpu   || {}
  const svcs  = health?.services || []

  return (
    <div className="space-y-5">
      {/* Resource gauges */}
      <Card title="Resources" actions={
        <button onClick={load} className="text-xs text-[#9090a8] hover:text-[#e8e8f0] transition-colors">↻ Refresh</button>
      }>
        <div className="flex items-center justify-around py-2">
          <Gauge label="CPU" value={cpu.percent || 0} sub={`${cpu.cores || 0} cores`} />
          <Gauge label="RAM" value={ram.percent || 0}
            sub={`${ram.used_gb || 0} / ${ram.total_gb || 0} GB`} />
          <Gauge label="Disk" value={disk.percent || 0}
            sub={`${disk.used_gb || 0} / ${disk.total_gb || 0} GB`} />
          {gpu.available ? (
            <Gauge label="GPU" value={gpu.percent || 0}
              sub={`${gpu.mem_used_mb || 0} / ${gpu.mem_total_mb || 0} MB · ${gpu.temp_c || 0}°C`} />
          ) : (
            <div className="flex flex-col items-center gap-1">
              <div className="w-16 h-16 rounded-full border-2 border-dashed border-[#2a2a32] flex items-center justify-center">
                <span className="text-[10px] text-[#5a5a70]">No GPU</span>
              </div>
              <div className="text-xs text-[#9090a8]">GPU</div>
            </div>
          )}
        </div>
      </Card>

      {/* Services grid */}
      <Card title="Services">
        <div className="grid grid-cols-3 gap-3">
          {svcs.map(s => (
            <div key={s.name}
              className="flex items-center gap-2.5 px-3 py-2.5 bg-[#16161a] rounded-lg border border-[#2a2a32]">
              <ServiceDot ok={s.ok} />
              <div className="flex-1 min-w-0">
                <div className="text-sm text-[#e8e8f0] font-medium">{s.name}</div>
                {s.error && <div className="text-[10px] text-[#f87171] truncate font-mono">{s.error}</div>}
                {s.workers != null && <div className="text-[10px] text-[#9090a8] font-mono">{s.workers} worker(s)</div>}
                {s.note && <div className="text-[10px] text-[#9090a8]">{s.note}</div>}
              </div>
              <span className={`text-xs font-mono ${s.ok ? 'text-[#34d399]' : 'text-[#f87171]'}`}>
                {s.ok ? 'OK' : 'DOWN'}
              </span>
            </div>
          ))}
        </div>
      </Card>

      {/* Cron schedule + Error log */}
      <div className="grid grid-cols-2 gap-4">
        <Card title="Celery Beat Schedule">
          {cron.length === 0 ? (
            <p className="text-xs text-[#5a5a70]">No scheduled tasks found.</p>
          ) : (
            <div className="space-y-2">
              {cron.map((c, i) => (
                <div key={i} className="flex items-start gap-2 text-xs py-1.5 border-b border-[#2a2a32] last:border-0">
                  <span className="text-[#7c6af7] font-mono mt-0.5">⏱</span>
                  <div>
                    <div className="text-[#e8e8f0] font-medium">{c.name}</div>
                    <div className="text-[#5a5a70] font-mono">{c.schedule}</div>
                    <div className="text-[#9090a8] truncate">{c.task}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title={`Error Log (${errors.length})`}>
          {errors.length === 0 ? (
            <p className="text-xs text-[#34d399]">No errors found in logs.</p>
          ) : (
            <div className="space-y-1 max-h-64 overflow-y-auto">
              {errors.map((e, i) => (
                <div key={i} className={`text-[10px] font-mono px-2 py-1 rounded ${
                  e.level === 'error' ? 'bg-[#1e0a0a] text-[#f87171]' : 'bg-[#1e1a00] text-[#fbbf24]'
                }`}>
                  <span className="text-[#5a5a70] mr-1">[{e.source}]</span>
                  {e.message}
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* MCP service-account token */}
      <McpTokenCard />
    </div>
  )
}
