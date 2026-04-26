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
  const wsRef      = useRef(null)
  const retryRef   = useRef(null)
  const onMsgRef   = useRef(onMessage)
  const enabledRef = useRef(enabled)
  const [connected, setConnected] = useState(false)

  // Keep refs in sync so ws callbacks always use the latest values without
  // needing to be listed as deps (which would re-create connect on every render).
  useEffect(() => { onMsgRef.current = onMessage }, [onMessage])

  const connect = useCallback(() => {
    if (!enabledRef.current) return
    // Guard against duplicate sockets (e.g. React StrictMode double-invoke)
    if (wsRef.current && wsRef.current.readyState < WebSocket.CLOSING) return

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
        onMsgRef.current(data)
      } catch {
        // ignore non-JSON frames
      }
    }

    ws.onclose = () => {
      setConnected(false)
      wsRef.current = null
      // Only retry if we weren't intentionally closed (cleanup sets enabledRef false)
      if (enabledRef.current) {
        retryRef.current = setTimeout(connect, retryMs)
      }
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [path, retryMs])  // onMessage and enabled intentionally omitted — accessed via refs

  useEffect(() => {
    enabledRef.current = enabled
    if (!enabled) return
    connect()
    return () => {
      // Signal onclose not to retry, then tear down
      enabledRef.current = false
      if (retryRef.current) {
        clearTimeout(retryRef.current)
        retryRef.current = null
      }
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connect, enabled])

  const send = useCallback((data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof data === 'string' ? data : JSON.stringify(data))
    }
  }, [])

  return { connected, send }
}
