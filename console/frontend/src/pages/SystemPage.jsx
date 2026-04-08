import { useState, useEffect, useCallback } from 'react'
import { Card, Spinner, Badge } from '../components/index.jsx'
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
    </div>
  )
}
