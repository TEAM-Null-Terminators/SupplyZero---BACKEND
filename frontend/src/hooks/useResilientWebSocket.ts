import { useEffect } from 'react'
import { API_BASE } from '../services/api'
import { useFleetStore } from '../store/fleetStore'

const WS_URL = (import.meta.env.VITE_WS_URL ?? API_BASE.replace(/^http/, 'ws') + '/ws/stream')

export function useResilientWebSocket() {
  const setConnection = useFleetStore((state) => state.setConnection)
  const applyEvent = useFleetStore((state) => state.applyEvent)
  const tickDemo = useFleetStore((state) => state.tickDemo)

  useEffect(() => {
    let socket: WebSocket | null = null
    let stopped = false
    let retryTimer: number | undefined
    let heartbeatTimer: number | undefined
    let watchdogTimer: number | undefined
    let demoTimer: number | undefined
    let retries = 0
    let lastPong = 0
    let offline = false

    const setOffline = () => {
      if (offline) return
      offline = true
      setConnection('offline', true)
      demoTimer = window.setInterval(tickDemo, 4_000)
    }
    const connect = () => {
      if (stopped) return
      setConnection(offline ? 'offline' : 'connecting', offline)
      try { socket = new WebSocket(WS_URL) } catch { scheduleRetry(); return }
      socket.onopen = () => {
        retries = 0
        offline = false
        lastPong = Date.now()
        if (demoTimer) window.clearInterval(demoTimer)
        demoTimer = undefined
        setConnection('live', false)
        heartbeatTimer = window.setInterval(() => {
          if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'ping', ts: Date.now() }))
        }, 15_000)
        watchdogTimer = window.setInterval(() => {
          if (Date.now() - lastPong > 30_000) socket?.close(4000, 'heartbeat timeout')
        }, 5_000)
      }
      socket.onmessage = (message) => {
        lastPong = Date.now()
        try {
          const event = JSON.parse(String(message.data)) as Record<string, unknown>
          if (event.type !== 'pong') applyEvent(event)
        } catch { /* Ignore malformed frames and keep the socket alive. */ }
      }
      socket.onerror = () => socket?.close()
      socket.onclose = () => {
        if (heartbeatTimer) window.clearInterval(heartbeatTimer)
        if (watchdogTimer) window.clearInterval(watchdogTimer)
        heartbeatTimer = undefined
        watchdogTimer = undefined
        if (retries >= 3) setOffline()
        scheduleRetry()
      }
    }
    const scheduleRetry = () => {
      if (stopped || retryTimer) return
      retries += 1
      if (retries >= 3) setOffline()
      const ceiling = Math.min(30_000, 1_000 * 2 ** Math.min(retries - 1, 5))
      const jitter = Math.random() * Math.min(1_000, ceiling * 0.2)
      retryTimer = window.setTimeout(() => { retryTimer = undefined; connect() }, ceiling + jitter)
    }
    connect()
    return () => {
      stopped = true
      if (retryTimer) window.clearTimeout(retryTimer)
      if (heartbeatTimer) window.clearInterval(heartbeatTimer)
      if (watchdogTimer) window.clearInterval(watchdogTimer)
      if (demoTimer) window.clearInterval(demoTimer)
      socket?.close(1000, 'component cleanup')
    }
  }, [applyEvent, setConnection, tickDemo])
}
