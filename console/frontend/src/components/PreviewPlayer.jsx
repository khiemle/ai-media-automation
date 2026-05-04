import { useEffect, useRef, useState } from 'react'

// Module-level "currently playing" reference so starting one preview stops any other.
let _activeStop = null

/**
 * PreviewPlayer
 * Props:
 *   src   — URL of the audio or video file
 *   kind  — 'audio' | 'video' | 'image'
 *   size  — 'sm' (default) | 'md' for thumbnail rendering
 *   className — extra classes for the wrapper
 *
 * For 'image', renders a small static preview tile (no play button).
 * For 'audio'/'video', renders a play/pause button. Clicking play stops any other
 * PreviewPlayer that is currently playing.
 */
export default function PreviewPlayer({ src, kind, size = 'sm', className = '' }) {
  const mediaRef = useRef(null)
  const [playing, setPlaying] = useState(false)

  useEffect(() => () => {
    // On unmount, stop playback and clear the active-stop ref if it points at us
    if (mediaRef.current) mediaRef.current.pause()
    if (_activeStop && _activeStop === stop) _activeStop = null
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const stop = () => {
    if (mediaRef.current) {
      mediaRef.current.pause()
      mediaRef.current.currentTime = 0
    }
    setPlaying(false)
  }

  const handleToggle = (e) => {
    e.stopPropagation()
    if (playing) {
      stop()
      _activeStop = null
      return
    }
    if (_activeStop && _activeStop !== stop) _activeStop()
    _activeStop = stop
    if (mediaRef.current) {
      mediaRef.current.play().catch(() => {})
      setPlaying(true)
    }
  }

  if (kind === 'image') {
    return (
      <img
        src={src}
        alt=""
        className={`object-cover bg-[#0d0d0f] ${size === 'md' ? 'w-24 h-24' : 'w-12 h-12'} ${className}`}
      />
    )
  }

  return (
    <div className={`inline-flex items-center ${className}`}>
      <button
        type="button"
        onClick={handleToggle}
        aria-label={playing ? 'Pause preview' : 'Play preview'}
        className="w-7 h-7 flex items-center justify-center rounded bg-[#1c1c22] border border-[#2a2a32] text-[#9090a8] hover:text-[#e8e8f0] hover:border-[#7c6af7] transition-colors"
      >
        {playing ? '⏸' : '▶'}
      </button>
      {kind === 'audio' ? (
        <audio ref={mediaRef} src={src} preload="none" onEnded={() => { setPlaying(false); if (_activeStop === stop) _activeStop = null }} />
      ) : (
        <video ref={mediaRef} src={src} preload="none" muted={false} className="hidden" onEnded={() => { setPlaying(false); if (_activeStop === stop) _activeStop = null }} />
      )}
    </div>
  )
}
