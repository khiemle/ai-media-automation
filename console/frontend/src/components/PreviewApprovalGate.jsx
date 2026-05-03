import { Button, Card } from './index.jsx'
import { youtubeVideosApi } from '../api/client.js'

export default function PreviewApprovalGate({ videoId, kind, mediaPath, onAction }) {
  const isAudio = kind === 'audio'
  const title = isAudio ? 'Approve Audio Preview' : 'Approve Video Preview'

  const approveFn = isAudio ? youtubeVideosApi.approveAudioPreview : youtubeVideosApi.approveVideoPreview
  const rejectFn  = isAudio ? youtubeVideosApi.rejectAudioPreview  : youtubeVideosApi.rejectVideoPreview
  const nextFn    = isAudio ? youtubeVideosApi.startVideoPreview   : youtubeVideosApi.startFinal

  const previewUrl = isAudio
    ? youtubeVideosApi.audioPreviewUrl(videoId)
    : youtubeVideosApi.videoPreviewUrl(videoId)

  const handleApprove = async () => {
    try {
      await approveFn(videoId)
      await nextFn(videoId)
      onAction?.()
    } catch (e) { alert(e.message) }
  }
  const handleReject = async () => {
    try { await rejectFn(videoId); onAction?.() } catch (e) { alert(e.message) }
  }

  return (
    <Card title={title}>
      <div className="space-y-3">
        {mediaPath ? (
          isAudio
            ? <audio controls src={previewUrl} className="w-full" />
            : <video controls src={previewUrl} className="w-full max-h-96" />
        ) : (
          <p className="text-xs text-[#9090a8]">No preview available.</p>
        )}
        <div className="flex gap-2">
          <Button variant="primary" onClick={handleApprove}>
            Approve & {isAudio ? 'Render Video Preview' : 'Render Final'}
          </Button>
          <Button variant="danger" onClick={handleReject}>Reject</Button>
        </div>
      </div>
    </Card>
  )
}
