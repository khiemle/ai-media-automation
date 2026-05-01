import { useState, useCallback, useEffect, useRef } from 'react'
import { Card, Badge, Button, StatBox, ProgressBar, Spinner, EmptyState, Toast, Select } from '../components/index.jsx'
import { useWebSocket } from '../hooks/useWebSocket.js'
import { fetchApi, youtubeVideosApi } from '../api/client.js'

const JOB_TYPE_LABELS = {
  scrape: 'Scrape', generate: 'Generate', tts: 'TTS', render: 'Render', upload: 'Upload', batch: 'Batch',
}

const STATUS_COLOR = {
  queued: 'planned', running: 'editing', completed: 'completed', failed: 'rejected', cancelled: 'standby',
}

function LogPanel({ logs }) {
  const ref = useRef(null)
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight
  }, [logs?.length])

  return (
    <div ref={ref} className="bg-[#0d0d0f] px-3 py-2.5 max-h-52 overflow-y-auto font-mono text-xs leading-5 space-y-0.5 mt-2 rounded-lg border border-[#2a2a32]">
      {!logs || logs.length === 0
        ? <span className="text-[#5a5a70]">No logs yet…</span>
        : logs.map((l, i) => (
          <div key={`${l.ts}-${i}`} className="flex gap-1.5">
            <span className="text-[#5a5a70] flex-shrink-0">{l.ts ? l.ts.slice(11, 19) : ''}</span>
            <span className={`flex-shrink-0 ${l.level === 'ERROR' ? 'text-[#f87171]' : l.level === 'WARNING' ? 'text-[#fbbf24]' : 'text-[#34d399]'}`}>[{l.level}]</span>
            <span className={l.level === 'ERROR' ? 'text-[#f87171]' : l.level === 'WARNING' ? 'text-[#fbbf24]' : 'text-[#9090a8]'}>{l.msg}</span>
          </div>
        ))}
    </div>
  )
}

function JobRow({ job, videoMap = {}, onRetry, onCancel, onError }) {
  const [expanded,   setExpanded]   = useState(false)
  const [staticLogs, setStaticLogs] = useState(null)
  const [loadingLog, setLoadingLog] = useState(false)
  // Issue 8: preserve last-seen live logs so they don't vanish on job completion
  const prevLiveLogsRef = useRef(null)

  const handleViewLogs = async () => {
    setLoadingLog(true)
    try {
      const res = await fetchApi(`/api/pipeline/jobs/${job.id}/logs`)
      setStaticLogs(res.logs || [])
    } catch (e) {
      // Issue 9: surface fetch errors via the parent toast system
      setStaticLogs([])
      onError?.(`Could not load logs for job ${job.id}: ${e.message}`)
    }
    finally { setLoadingLog(false) }
  }

  const liveLogs = job.live_logs  // populated from WS when status === 'running'
  // Issue 8: keep snapshot of the last live logs received
  if (liveLogs) prevLiveLogsRef.current = liveLogs

  return (
    <div className="border border-[#2a2a32] rounded-lg overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-2.5 hover:bg-[#1c1c22] cursor-pointer"
        onClick={() => setExpanded(e => !e)}>
        <span className="text-xs font-mono text-[#5a5a70] w-8">#{job.id}</span>
        <Badge status={STATUS_COLOR[job.status]} label={job.status} />
        <span className="text-xs font-mono text-[#9090a8] w-20">{JOB_TYPE_LABELS[job.job_type] || job.job_type}</span>
        {job.video_format === 'youtube_long' && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#14b8a6] bg-opacity-20 text-[#14b8a6] font-mono">YOUTUBE</span>
        )}
        <div className="flex-1"><ProgressBar value={job.progress || 0} max={100} /></div>
        <span className="text-xs font-mono text-[#9090a8] w-8 text-right">{job.progress || 0}%</span>
        {job.script_id && <span className="text-xs text-[#5a5a70] font-mono">script#{job.script_id}</span>}
        <div className="flex gap-1">
          {['failed', 'cancelled'].includes(job.status) && (
            <Button variant="ghost" className="text-xs px-2 py-0.5" onClick={e => { e.stopPropagation(); onRetry(job.id) }}>Retry</Button>
          )}
          {['queued', 'running'].includes(job.status) && (
            <Button variant="danger" className="text-xs px-2 py-0.5" onClick={e => { e.stopPropagation(); onCancel(job.id) }}>Cancel</Button>
          )}
        </div>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          className={`text-[#5a5a70] transition-transform ${expanded ? 'rotate-180' : ''}`}>
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </div>

      {expanded && (
        <div className="border-t border-[#2a2a32] px-4 py-3 text-xs font-mono text-[#9090a8] space-y-1">
          {job.celery_task_id && <div>Task ID: <span className="text-[#e8e8f0]">{job.celery_task_id}</span></div>}
          {job.parent_youtube_video_id && (
            <div>
              YouTube Video:{' '}
              <span className="text-[#e8e8f0]">
                {videoMap[job.parent_youtube_video_id]
                  ? `${videoMap[job.parent_youtube_video_id]} (#${job.parent_youtube_video_id})`
                  : `#${job.parent_youtube_video_id}`}
              </span>
            </div>
          )}
          {job.started_at && <div>Started: <span className="text-[#e8e8f0]">{new Date(job.started_at).toLocaleString()}</span></div>}
          {job.completed_at && <div>Completed: <span className="text-[#e8e8f0]">{new Date(job.completed_at).toLocaleString()}</span></div>}
          {job.error && <div className="text-[#f87171]">Error: {job.error}</div>}
          {job.details && <div>Details: <span className="text-[#e8e8f0]">{JSON.stringify(job.details)}</span></div>}

          {/* Logs */}
          {job.status === 'running' && <LogPanel logs={liveLogs} />}
          {['completed', 'failed', 'cancelled'].includes(job.status) && (
            staticLogs
              ? <LogPanel logs={staticLogs} />
              : <>
                  {prevLiveLogsRef.current && <LogPanel logs={prevLiveLogsRef.current} />}
                  <Button variant="ghost" size="sm" loading={loadingLog} onClick={handleViewLogs}>
                    {prevLiveLogsRef.current ? 'Reload Logs' : 'View Logs'}
                  </Button>
                </>
          )}
        </div>
      )}
    </div>
  )
}


export default function PipelinePage() {
  const [stats,      setStats]      = useState({ queued: 0, running: 0, completed: 0, failed: 0, cancelled: 0, total: 0 })
  const [jobs,       setJobs]       = useState([])
  const [wsConnected,setWsConnected]= useState(false)
  const [statusFilter, setFilter]   = useState('all')
  const [filterFormat, setFilterFormat] = useState('')
  const [loading,    setLoading]    = useState(false)
  const [toast,      setToast]      = useState(null)
  const [videoMap,   setVideoMap]   = useState({})  // { id: title }

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  // Fetch YouTube videos on mount
  useEffect(() => {
    youtubeVideosApi.list()
      .then(res => {
        const m = {}
        for (const v of res.items || res || []) m[v.id] = v.title
        setVideoMap(m)
      })
      .catch(() => {})
  }, [])

  // WebSocket for live updates
  const handleWsMessage = useCallback((data) => {
    if (data.type === 'pipeline_update') {
      if (data.stats)       setStats(data.stats)
      if (data.recent_jobs) {
        const jobLogs = data.job_logs || {}
        setJobs(data.recent_jobs.map(j => ({
          ...j,
          live_logs: jobLogs[j.id] || undefined,
        })))
      }
    }
  }, [])

  const { connected } = useWebSocket('/ws/pipeline', handleWsMessage)

  useEffect(() => { setWsConnected(connected) }, [connected])

  // Initial load (fallback if WS not connected)
  const loadJobs = useCallback(async () => {
    setLoading(true)
    try {
      const [statsRes, jobsRes] = await Promise.all([
        fetchApi('/api/pipeline/stats'),
        fetchApi(`/api/pipeline/jobs?${statusFilter !== 'all' ? `status=${statusFilter}&` : ''}${filterFormat ? `video_format=${filterFormat}&` : ''}per_page=50`),
      ])
      setStats(statsRes)
      setJobs(jobsRes.items || [])
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setLoading(false)
    }
  }, [statusFilter, filterFormat])

  useEffect(() => { loadJobs() }, [loadJobs])

  const handleRetry = async (jobId) => {
    try {
      await fetchApi(`/api/pipeline/jobs/${jobId}/retry`, { method: 'PATCH' })
      showToast('Job queued for retry')
      loadJobs()
    } catch (e) { showToast(e.message, 'error') }
  }

  const handleCancel = async (jobId) => {
    try {
      await fetchApi(`/api/pipeline/jobs/${jobId}/cancel`, { method: 'PATCH' })
      showToast('Job cancelled')
      loadJobs()
    } catch (e) { showToast(e.message, 'error') }
  }

  const handleCreateJob = async (job_type) => {
    try {
      await fetchApi('/api/pipeline/jobs', { method: 'POST', body: JSON.stringify({ job_type }) })
      showToast(`${JOB_TYPE_LABELS[job_type]} job created`)
      loadJobs()
    } catch (e) { showToast(e.message, 'error') }
  }

  const filtered = statusFilter === 'all' ? jobs : jobs.filter(j => j.status === statusFilter)

  return (
    <div className="space-y-5">
      {/* Stats row */}
      <div className="grid grid-cols-6 gap-3">
        <StatBox label="Running"   value={stats.running}   color="#7c6af7" />
        <StatBox label="Queued"    value={stats.queued}    color="#fbbf24" />
        <StatBox label="Completed" value={stats.completed} color="#34d399" />
        <StatBox label="Failed"    value={stats.failed}    color="#f87171" />
        <StatBox label="Cancelled" value={stats?.cancelled ?? 0} color="#9090a8" />
        <StatBox label="Total"     value={stats.total}     />
      </div>

      {/* Controls */}
      <Card
        title="Batch Controls"
        actions={
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-[#34d399]' : 'bg-[#f87171]'}`} />
            <span className="text-xs text-[#9090a8]">{wsConnected ? 'Live' : 'Polling'}</span>
            <Button variant="ghost" onClick={loadJobs}>Refresh</Button>
          </div>
        }
      >
        <div className="flex flex-wrap gap-2">
          {Object.entries(JOB_TYPE_LABELS).map(([type, label]) => (
            <Button key={type} variant="default" onClick={() => handleCreateJob(type)}>
              + {label}
            </Button>
          ))}
        </div>
      </Card>

      {/* Job list */}
      <Card
        title={`Jobs (${filtered.length})`}
        actions={
          <div className="flex gap-3 items-center">
            <div className="flex gap-1">
              {['all', 'queued', 'running', 'completed', 'failed', 'cancelled'].map(s => (
                <button
                  key={s}
                  onClick={() => setFilter(s)}
                  className={`px-2 py-0.5 rounded text-xs font-mono transition-colors ${
                    statusFilter === s
                      ? 'bg-[#7c6af7] text-white'
                      : 'text-[#9090a8] hover:text-[#e8e8f0]'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
            <Select value={filterFormat} onChange={e => setFilterFormat(e.target.value)} className="max-w-[160px]">
              <option value="">Format: All</option>
              <option value="short">Short</option>
              <option value="youtube_long">YouTube Long</option>
            </Select>
          </div>
        }
      >
        {loading ? (
          <div className="flex items-center justify-center h-32"><Spinner /></div>
        ) : filtered.length === 0 ? (
          <EmptyState title="No jobs found. Use the controls above to start one." />
        ) : (
          <div className="space-y-2">
            {filtered.map(job => (
              <JobRow key={job.id} job={job} videoMap={videoMap} onRetry={handleRetry} onCancel={handleCancel} onError={(msg) => showToast(msg, 'error')} />
            ))}
          </div>
        )}
      </Card>

      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  )
}
