import { useEffect, useRef } from 'react'
import type { LogEntry } from '../hooks/useGameState'

interface MoveLogProps {
  entries: LogEntry[]
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso)
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    const ss = String(d.getSeconds()).padStart(2, '0')
    return `${hh}:${mm}:${ss}`
  } catch {
    return iso
  }
}

function entryColor(type: string): string {
  switch (type) {
    case 'shot_fired':
      return '#cce'
    case 'game_over':
      return '#ffd700'
    case 'error':
      return '#f88'
    case 'all_placements_done':
    case 'placement_done':
      return '#8f8'
    default:
      return '#ccc'
  }
}

export function MoveLog({ entries }: MoveLogProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [entries])

  return (
    <div
      style={{
        maxHeight: 'min(400px, 50vh)',
        overflowY: 'auto',
        border: '1px solid #444',
        borderRadius: 6,
        padding: '8px 12px',
        backgroundColor: '#1a1a2e',
        fontFamily: 'monospace',
        fontSize: 13,
      }}
    >
      {entries.length === 0 && (
        <div style={{ color: '#666', fontStyle: 'italic' }}>No events yet…</div>
      )}

      {entries.map((entry) => (
        <div
          key={entry.id}
          style={{
            marginBottom: 8,
            paddingBottom: 8,
            borderBottom: '1px solid #2a2a3e',
          }}
        >
          <span style={{ color: '#666', marginRight: 8 }}>
            {formatTime(entry.timestamp)}
          </span>
          <span style={{ color: entryColor(entry.type) }}>{entry.message}</span>

          {entry.reasoning && (
            <details style={{ marginTop: 4 }}>
              <summary
                style={{
                  cursor: 'pointer',
                  color: '#888',
                  fontSize: 12,
                  userSelect: 'none',
                }}
              >
                LLM reasoning
              </summary>
              <div
                style={{
                  fontStyle: 'italic',
                  color: '#aaa',
                  marginTop: 4,
                  paddingLeft: 12,
                  borderLeft: '2px solid #444',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}
              >
                {entry.reasoning}
              </div>
            </details>
          )}
        </div>
      ))}

      {/* Sentinel div for auto-scroll */}
      <div ref={bottomRef} />
    </div>
  )
}
