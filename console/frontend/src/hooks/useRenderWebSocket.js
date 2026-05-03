import { useEffect, useRef, useState } from 'react'
import { getToken } from '../api/client.js'

const RECONNECT_DELAYS_MS = [1000, 2000, 4000, 8000, 16000]

export function useRenderWebSocket(videoId) {
  const [state, setState] = useState(null)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const reconnectAttemptRef = useRef(0)
  const closedByCleanupRef = useRef(false)

  useEffect(() => {
    if (!videoId) return
    closedByCleanupRef.current = false

    const connect = () => {
      const token = getToken()
      if (!token) return
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const url = `${proto}//${window.location.host}/ws/render/youtube/${videoId}?token=${encodeURIComponent(token)}`
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        reconnectAttemptRef.current = 0
      }
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data)
          if (msg.type === 'snapshot' || msg.type === 'update') setState(msg)
          // 'ping' frames are heartbeat — ignore
        } catch {}
      }
      ws.onclose = () => {
        setConnected(false)
        if (closedByCleanupRef.current) return
        const attempt = Math.min(reconnectAttemptRef.current, RECONNECT_DELAYS_MS.length - 1)
        const delay = RECONNECT_DELAYS_MS[attempt]
        reconnectAttemptRef.current += 1
        setTimeout(connect, delay)
      }
      ws.onerror = () => ws.close()
    }
    connect()

    return () => {
      closedByCleanupRef.current = true
      if (wsRef.current) wsRef.current.close()
    }
  }, [videoId])

  return { state, connected }
}
