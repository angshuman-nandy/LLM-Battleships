// MIT License
// Copyright (c) 2026 Angshuman Nandy

import { useEffect, useRef, useCallback } from 'react'

interface WebSocketHookOptions {
  gameId: string | null
  onEvent: (type: string, data: Record<string, unknown>) => void
  onError?: (err: Event) => void
}

const MAX_RETRY_ATTEMPTS = 5
const BASE_RETRY_MS = 1000
const MAX_RETRY_MS = 30_000

export function useWebSocket({ gameId, onEvent, onError }: WebSocketHookOptions): void {
  const wsRef = useRef<WebSocket | null>(null)
  const retryCountRef = useRef<number>(0)
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const intentionalCloseRef = useRef<boolean>(false)
  const onEventRef = useRef(onEvent)
  const onErrorRef = useRef(onError)

  useEffect(() => { onEventRef.current = onEvent }, [onEvent])
  useEffect(() => { onErrorRef.current = onError }, [onError])

  const clearRetryTimer = useCallback(() => {
    if (retryTimerRef.current !== null) {
      clearTimeout(retryTimerRef.current)
      retryTimerRef.current = null
    }
  }, [])

  const closeConnection = useCallback(() => {
    clearRetryTimer()
    intentionalCloseRef.current = true
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [clearRetryTimer])

  const connect = useCallback(
    (id: string) => {
      closeConnection()
      intentionalCloseRef.current = false

      const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(`${protocol}//${location.host}/ws/${id}`)
      wsRef.current = ws

      ws.onmessage = (e: MessageEvent) => {
        let msg: { type: string; data: Record<string, unknown> } | null = null
        try {
          msg = JSON.parse(e.data as string) as { type: string; data: Record<string, unknown> }
        } catch {
          return
        }
        if (!msg) return
        if (msg.type !== 'ping') {
          retryCountRef.current = 0
        }
        onEventRef.current(msg.type, msg.data ?? {})
      }

      ws.onerror = (err: Event) => {
        onErrorRef.current?.(err)
      }

      // Retry on unexpected close (network drop, server restart, etc.).
      ws.onclose = () => {
        wsRef.current = null
        if (intentionalCloseRef.current) return

        retryCountRef.current += 1
        if (retryCountRef.current > MAX_RETRY_ATTEMPTS) return

        const delayMs = Math.min(
          BASE_RETRY_MS * Math.pow(2, retryCountRef.current - 1),
          MAX_RETRY_MS,
        )
        retryTimerRef.current = setTimeout(() => {
          retryTimerRef.current = null
          connect(id)
        }, delayMs)
      }
    },
    [closeConnection],
  )

  useEffect(() => {
    if (!gameId) {
      closeConnection()
      retryCountRef.current = 0
      return
    }

    retryCountRef.current = 0
    connect(gameId)

    return () => {
      closeConnection()
      retryCountRef.current = 0
    }
  }, [gameId, connect, closeConnection])
}
