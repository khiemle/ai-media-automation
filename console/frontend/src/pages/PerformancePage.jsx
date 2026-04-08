import { useState, useEffect } from 'react'
import { Card, StatBox, Spinner, EmptyState, Badge } from '../components/index.jsx'
import { fetchApi } from '../api/client.js'

// ── Mini sparkline ────────────────────────────────────────────────────────────
function Sparkline({ data, color = '#7c6af7', height = 32 }) {
  if (!data?.length) return null
  const max = Math.max(...data, 1)
  const min = Math.min(...data, 0)
  const range = max - min || 1
  const w = 80, h = height
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w
    const y = h - ((v - min) / range) * h
    return `${x},${y}`
  }).join(' ')
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

// ── Bar chart ─────────────────────────────────────────────────────────────────
function BarChart({ data, valueKey, labelKey = 'date', color = '#7c6af7', height = 80 }) {
  if (!data?.length) return <div className="h-20 flex items-center justify-center text-xs text-[#5a5a70]">No data</div>
  const max = Math.max(...data.map(d => d[valueKey]), 1)
  return (
    <div className="flex items-end gap-0.5" style={{ height }}>
      {data.map((d, i) => {
        const pct = (d[valueKey] / max) * 100
        const label = typeof d[labelKey] === 'string' ? d[labelKey].slice(5) : d[labelKey]
        return (
          <div key={i} className="flex-1 flex flex-col items-center gap-0.5 group relative">
            <div
              className="w-full rounded-t-sm transition-opacity group-hover:opacity-80"
              style={{ height: `${Math.max(pct, 2)}%`, backgroundColor: color + 'cc' }}
            />
            {data.length <= 14 && (
              <div className="text-[8px] font-mono text-[#5a5a70] rotate-45 origin-left hidden group-hover:block absolute -bottom-4 left-0 whitespace-nowrap z-10">
                {label}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

export default function PerformancePage() {
  const [summary,  setSummary]  = useState(null)
  const [daily,    setDaily]    = useState([])
  const [niches,   setNiches]   = useState([])
  const [topVids,  setTopVids]  = useState([])
  const [loading,  setLoading]  = useState(true)
  const [days,     setDays]     = useState(14)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      fetchApi('/api/performance/summary'),
      fetchApi(`/api/performance/daily?days=${days}`),
      fetchApi('/api/performance/niches'),
      fetchApi('/api/performance/top-videos?limit=8'),
    ]).then(([s, d, n, t]) => {
      setSummary(s)
      setDaily(d)
      setNiches(n)
      setTopVids(t)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [days])

  if (loading) return <div className="flex items-center justify-center h-64"><Spinner /></div>

  const completedSpark = daily.map(d => d.completed)
  const scoreSpark     = daily.map(d => d.avg_score)

  return (
    <div className="space-y-5">
      {/* Summary stat boxes */}
      <div className="grid grid-cols-4 gap-3">
        <StatBox label="Total Scripts"  value={summary?.total        ?? 0} />
        <StatBox label="Completed"      value={summary?.completed    ?? 0} color="#34d399" />
        <StatBox label="Avg Score"      value={`${summary?.avg_score ?? 0}`} color="#7c6af7" />
        <StatBox label="Success Rate"   value={`${summary?.success_rate ?? 0}%`} color="#fbbf24" />
      </div>

      {/* Daily output chart */}
      <Card
        title="Daily Output"
        actions={
          <div className="flex gap-1">
            {[7, 14, 30].map(d => (
              <button key={d} onClick={() => setDays(d)}
                className={`px-2 py-0.5 rounded text-xs font-mono transition-colors ${
                  days === d ? 'bg-[#7c6af7] text-white' : 'text-[#9090a8] hover:text-[#e8e8f0]'
                }`}>{d}d</button>
            ))}
          </div>
        }
      >
        <div className="grid grid-cols-2 gap-6">
          <div>
            <div className="text-xs text-[#9090a8] mb-2 flex items-center justify-between">
              <span>Videos Completed</span>
              <Sparkline data={completedSpark} color="#34d399" />
            </div>
            <BarChart data={daily} valueKey="completed" color="#34d399" height={80} />
          </div>
          <div>
            <div className="text-xs text-[#9090a8] mb-2 flex items-center justify-between">
              <span>Avg Performance Score</span>
              <Sparkline data={scoreSpark} color="#7c6af7" />
            </div>
            <BarChart data={daily} valueKey="avg_score" color="#7c6af7" height={80} />
          </div>
        </div>
      </Card>

      {/* Niche breakdown + Top videos */}
      <div className="grid grid-cols-2 gap-4">
        {/* Niche breakdown */}
        <Card title="Niche Breakdown">
          {niches.length === 0 ? <EmptyState title="No niche data yet" /> : (
            <div className="space-y-3">
              {niches.map(n => {
                const maxTotal = Math.max(...niches.map(x => x.total), 1)
                const pct = Math.round((n.total / maxTotal) * 100)
                return (
                  <div key={n.niche}>
                    <div className="flex justify-between items-center mb-1">
                      <span className="text-sm text-[#e8e8f0] capitalize">{n.niche}</span>
                      <div className="flex items-center gap-3 text-xs font-mono text-[#9090a8]">
                        <span>{n.total} scripts</span>
                        <span className="text-[#34d399]">{n.success_rate}% success</span>
                        <span className="text-[#7c6af7]">{n.avg_score} score</span>
                      </div>
                    </div>
                    <div className="h-1.5 bg-[#2a2a32] rounded-full overflow-hidden">
                      <div className="h-full bg-[#7c6af7] rounded-full transition-all"
                        style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </Card>

        {/* Top videos */}
        <Card title="Top Videos by Score">
          {topVids.length === 0 ? <EmptyState title="No performance data yet" /> : (
            <div className="space-y-2">
              {topVids.map((v, i) => (
                <div key={v.id} className="flex items-center gap-3 py-1.5">
                  <span className="text-xs font-mono text-[#5a5a70] w-4">{i + 1}</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-[#e8e8f0] truncate">{v.topic || `Script #${v.id}`}</div>
                    <div className="flex gap-2 mt-0.5">
                      <Badge status="planned" label={v.niche || '—'} />
                      <span className="text-[10px] text-[#5a5a70] font-mono">{v.template}</span>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-mono font-bold"
                      style={{ color: v.score >= 70 ? '#34d399' : v.score >= 40 ? '#fbbf24' : '#f87171' }}>
                      {v.score}
                    </div>
                    {v.is_successful && <div className="text-[9px] text-[#34d399]">✓ success</div>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
