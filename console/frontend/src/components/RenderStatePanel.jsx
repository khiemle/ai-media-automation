import { Button, Card, ProgressBar } from './index.jsx'
import { youtubeVideosApi } from '../api/client.js'

export default function RenderStatePanel({ videoId, state, onAction }) {
  if (!state) {
    return (
      <Card title="Render Status">
        <p className="text-xs text-[#9090a8]">Connecting...</p>
      </Card>
    )
  }

  const { status, chunks = [], chunk_summary = {}, overall_progress = 0,
          current_job, logs_tail = [] } = state

  const STATUS_COLORS = {
    completed: '#34d399', running: '#fbbf24',
    failed: '#f87171', pending: '#5a5a70', cancelled: '#5a5a70',
  }

  const handle = async (fn) => {
    try { await fn(videoId); onAction?.() } catch (e) { alert(e.message) }
  }

  const showResume = chunks.some(c => c.status === 'failed')
  const showCancel = ['rendering', 'audio_preview_rendering', 'video_preview_rendering'].includes(status)

  return (
    <Card title="Render Status" actions={
      <div className="flex gap-2">
        {showResume && <Button variant="default" onClick={() => handle(youtubeVideosApi.resume)}>Resume</Button>}
        {showCancel && <Button variant="danger"  onClick={() => handle(youtubeVideosApi.cancel)}>Cancel</Button>}
      </div>
    }>
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-[#9090a8] w-32">{status}</span>
          <ProgressBar value={overall_progress} />
          <span className="text-xs font-mono text-[#9090a8] w-12 text-right">{overall_progress}%</span>
        </div>

        {chunks.length > 0 && (
          <div>
            <div className="text-xs text-[#5a5a70] mb-2">
              Chunks: {chunk_summary.completed}/{chunk_summary.total} done
              {chunk_summary.failed > 0 && <span className="text-[#f87171] ml-2">{chunk_summary.failed} failed</span>}
            </div>
            <div className="flex gap-1 flex-wrap">
              {chunks.map(c => (
                <div key={c.idx}
                  title={`Chunk ${c.idx + 1} [${c.start_s?.toFixed(0)}s–${c.end_s?.toFixed(0)}s]: ${c.status}${c.error ? ` — ${c.error}` : ''}`}
                  className="w-8 h-6 rounded text-[10px] flex items-center justify-center font-mono text-white"
                  style={{ backgroundColor: STATUS_COLORS[c.status] || '#5a5a70' }}>
                  {c.idx + 1}
                </div>
              ))}
            </div>
          </div>
        )}

        {current_job?.error && (
          <div className="text-xs text-[#f87171] bg-[#f87171]/10 border border-[#f87171]/30 rounded p-2 font-mono">
            {current_job.error}
          </div>
        )}

        {logs_tail.length > 0 && (
          <details className="text-xs">
            <summary className="cursor-pointer text-[#9090a8]">Recent logs ({logs_tail.length})</summary>
            <div className="mt-2 max-h-48 overflow-y-auto space-y-1 font-mono">
              {logs_tail.map((l, i) => (
                <div key={i} className={l.level === 'ERROR' ? 'text-[#f87171]' : 'text-[#9090a8]'}>
                  <span className="text-[#5a5a70]">{l.ts?.slice(11, 19)}</span> {l.msg}
                </div>
              ))}
            </div>
          </details>
        )}
      </div>
    </Card>
  )
}
