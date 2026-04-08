import { useState, useCallback, useEffect } from 'react'
import { Card, Badge, Button, StatBox, ProgressBar, Spinner, EmptyState, Toast } from '../components/index.jsx'
import { useWebSocket } from '../hooks/useWebSocket.js'
import { fetchApi } from '../api/client.js'

const JOB_TYPE_LABELS = {
  scrape: 'Scrape', generate: 'Generate', tts: 'TTS', render: 'Render', upload: 'Upload', batch: 'Batch',
}

const STATUS_COLOR = {
  queued: 'planned', running: 'editing', completed: 'completed', failed: 'rejected', cancelled: 'standby',
}

function JobRow({ job, onRetry, onCancel }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="border border-[#2a2a32] rounded-lg overflow-hidden">
      <div
        className="flex items-center gap-3 px-4 py-2.5 hover:bg-[#1c1c22] cursor-pointer"
        onClick={() => setExpanded(e => !e)}
      >
        <span className="text-xs font-mono text-[#5a5a70] w-8">#{job.id}</span>
        <Badge status={STATUS_COLOR[job.status]} label={job.status} />
        <span className="text-xs font-mono text-[#9090a8] w-20">{JOB_TYPE_LABELS[job.job_type] || job.job_type}</span>
        <div className="flex-1">
          <ProgressBar value={job.progress || 0} max={100} />
        </div>
        <span className="text-xs font-mono text-[#9090a8] w-8 text-right">{job.progress || 0}%</span>
        {job.script_id && (
          <span className="text-xs text-[#5a5a70] font-mono">script#{job.script_id}</span>
        )}
        <div className="flex gap-1">
          {['failed', 'cancelled'].includes(job.status) && (
            <Button variant="ghost" className="text-xs px-2 py-0.5" onClick={e => { e.stopPropagation(); onRetry(job.id) }}>
              Retry
            </Button>
          )}
          {['queued', 'running'].includes(job.status) && (
            <Button variant="danger" className="text-xs px-2 py-0.5" onClick={e => { e.stopPropagation(); onCancel(job.id) }}>
              Cancel
            </Button>
          )}
        </div>
        <svg
          width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          className={`text-[#5a5a70] transition-transform ${expanded ? 'rotate-180' : ''}`}
        >
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </div>

      {expanded && (
        <div className="border-t border-[#2a2a32] px-4 py-3 text-xs font-mono text-[#9090a8] space-y-1">
          {job.celery_task_id && <div>Task ID: <span className="text-[#e8e8f0]">{job.celery_task_id}</span></div>}
          {job.started_at && <div>Started: <span className="text-[#e8e8f0]">{new Date(job.started_at).toLocaleString()}</span></div>}
          {job.completed_at && <div>Completed: <span className="text-[#e8e8f0]">{new Date(job.completed_at).toLocaleString()}</span></div>}
          {job.error && <div className="text-[#f87171]">Error: {job.error}</div>}
          {job.details && <div>Details: <span className="text-[#e8e8f0]">{JSON.stringify(job.details)}</span></div>}
        </div>
      )}
    </div>
  )
}


export default function PipelinePage() {
  const [stats,      setStats]      = useState({ queued: 0, running: 0, completed: 0, failed: 0, total: 0 })
  const [jobs,       setJobs]       = useState([])
  const [wsConnected,setWsConnected]= useState(false)
  const [statusFilter, setFilter]   = useState('all')
  const [loading,    setLoading]    = useState(false)
  const [toast,      setToast]      = useState(null)

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  // WebSocket for live updates
  const handleWsMessage = useCallback((data) => {
    if (data.type === 'pipeline_update') {
      if (data.stats)       setStats(data.stats)
      if (data.recent_jobs) setJobs(data.recent_jobs)
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
        fetchApi(`/api/pipeline/jobs?${statusFilter !== 'all' ? `status=${statusFilter}&` : ''}per_page=50`),
      ])
      setStats(statsRes)
      setJobs(jobsRes.items || [])
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setLoading(false)
    }
  }, [statusFilter])

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
      <div className="grid grid-cols-5 gap-3">
        <StatBox label="Running"   value={stats.running}   color="#7c6af7" />
        <StatBox label="Queued"    value={stats.queued}    color="#fbbf24" />
        <StatBox label="Completed" value={stats.completed} color="#34d399" />
        <StatBox label="Failed"    value={stats.failed}    color="#f87171" />
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
        }
      >
        {loading ? (
          <div className="flex items-center justify-center h-32"><Spinner /></div>
        ) : filtered.length === 0 ? (
          <EmptyState title="No jobs found. Use the controls above to start one." />
        ) : (
          <div className="space-y-2">
            {filtered.map(job => (
              <JobRow key={job.id} job={job} onRetry={handleRetry} onCancel={handleCancel} />
            ))}
          </div>
        )}
      </Card>

      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  )
}
