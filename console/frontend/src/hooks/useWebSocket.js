import { useEffect, useRef, useCallback, useState } from 'react'
import { getToken } from '../api/client.js'

/**
 * useWebSocket — auto-reconnecting WebSocket hook.
 *
 * @param {string} path  - WebSocket path, e.g. '/ws/pipeline'
 * @param {function} onMessage - called with parsed JSON message
 * @param {object} options
 *   @param {boolean} options.enabled  - set false to skip connecting (default true)
 *   @param {number}  options.retryMs  - reconnect delay in ms (default 3000)
 */
export function useWebSocket(path, onMessage, { enabled = true, retryMs = 3000 } = {}) {
  const wsRef    = useRef(null)
  const retryRef = useRef(null)
  const [connected, setConnected] = useState(false)

  const connect = useCallback(() => {
    if (!enabled) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const token    = getToken()
    const url      = `${protocol}//${window.location.host}${path}${token ? `?token=${encodeURIComponent(token)}` : ''}`

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      if (retryRef.current) {
        clearTimeout(retryRef.current)
        retryRef.current = null
      }
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onMessage(data)
      } catch {
        // ignore non-JSON frames
      }
    }

    ws.onclose = () => {
      setConnected(false)
      wsRef.current = null
      if (enabled) {
        retryRef.current = setTimeout(connect, retryMs)
      }
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [path, onMessage, enabled, retryMs])

  useEffect(() => {
    connect()
    return () => {
      if (retryRef.current) clearTimeout(retryRef.current)
      if (wsRef.current) wsRef.current.close()
    }
  }, [connect])

  const send = useCallback((data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof data === 'string' ? data : JSON.stringify(data))
    }
  }, [])

  return { connected, send }
}
