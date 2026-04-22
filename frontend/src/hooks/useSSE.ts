import { useEffect, useRef, useCallback } from 'react'

// All named SSE event types the server emits.
const SSE_EVENT_TYPES = [
  'awaiting_human_placement',
  'placement_started',
  'placement_done',
  'all_placements_done',
  'turn_start',
  'shot_fired',
  'game_over',
  'error',
  'ping',
] as const

interface SSEHookOptions {
  gameId: string | null
  onEvent: (type: string, data: Record<string, unknown>) => void
  onError?: (err: Event) => void
}

const MAX_RETRY_ATTEMPTS = 5
const BASE_RETRY_MS = 1000
const MAX_RETRY_MS = 30_000

export function useSSE({ gameId, onEvent, onError }: SSEHookOptions): void {
  // Stable refs — never stale inside event callbacks.
  const esRef = useRef<EventSource | null>(null)
  const retryCountRef = useRef<number>(0)
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Keep latest callbacks in refs so reconnect closure always sees current values.
  const onEventRef = useRef(onEvent)
  const onErrorRef = useRef(onError)

  useEffect(() => {
    onEventRef.current = onEvent
  }, [onEvent])

  useEffect(() => {
    onErrorRef.current = onError
  }, [onError])

  const clearRetryTimer = useCallback(() => {
    if (retryTimerRef.current !== null) {
      clearTimeout(retryTimerRef.current)
      retryTimerRef.current = null
    }
  }, [])

  const closeConnection = useCallback(() => {
    clearRetryTimer()
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }
  }, [clearRetryTimer])

  const connect = useCallback(
    (id: string) => {
      // Clean up any existing connection before opening a new one.
      closeConnection()

      const es = new EventSource(`/sse/${id}`)
      esRef.current = es

      // Register a listener for every named event type.
      for (const eventType of SSE_EVENT_TYPES) {
        es.addEventListener(eventType, (e: MessageEvent) => {
          // Any successful message resets the retry counter.
          if (eventType !== 'ping') {
            retryCountRef.current = 0
          }

          let parsed: Record<string, unknown> = {}
          try {
            parsed = JSON.parse(e.data) as Record<string, unknown>
          } catch {
            // Malformed payload — pass empty object so callers don't crash.
          }

          onEventRef.current(eventType, parsed)
        })
      }

      es.onerror = (err: Event) => {
        onErrorRef.current?.(err)

        // Close the broken connection — we will reopen after the backoff delay.
        es.close()
        esRef.current = null

        retryCountRef.current += 1

        if (retryCountRef.current > MAX_RETRY_ATTEMPTS) {
          // Give up — too many consecutive failures.
          return
        }

        // Exponential backoff: 1s, 2s, 4s, 8s, 16s → capped at 30s.
        const delayMs = Math.min(
          BASE_RETRY_MS * Math.pow(2, retryCountRef.current - 1),
          MAX_RETRY_MS,
        )

        retryTimerRef.current = setTimeout(() => {
          retryTimerRef.current = null
          // Only reconnect if we still have the same gameId in scope.
          // We capture `id` directly — the outer effect will re-run if gameId changes.
          connect(id)
        }, delayMs)
      }
    },
    [closeConnection],
  )

  useEffect(() => {
    if (!gameId) {
      // No active game — ensure any lingering connection is torn down.
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
