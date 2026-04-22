import { useState, useCallback, useEffect } from 'react'
import { SetupPanel } from './components/SetupPanel'
import { BoardPair } from './components/BoardPair'
import { MoveLog } from './components/MoveLog'
import { StatusBar } from './components/StatusBar'
import { ShipPlacementBoard } from './components/ShipPlacementBoard'
import { HowToPlay } from './components/HowToPlay'
import { useSSE } from './hooks/useSSE'
import { useGameState } from './hooks/useGameState'
import { api } from './api/client'
import type { PlayerRole, PlacedShip } from './types/game'

// ── Fleet helper ──────────────────────────────────────────────────────────────

function getFleet(size: number): Array<{ ship_type: string; length: number }> {
  if (size <= 6)
    return [
      { ship_type: 'Destroyer', length: 2 },
      { ship_type: 'Submarine', length: 3 },
    ]
  if (size <= 9)
    return [
      { ship_type: 'Destroyer', length: 2 },
      { ship_type: 'Cruiser', length: 3 },
      { ship_type: 'Battleship', length: 4 },
    ]
  return [
    { ship_type: 'Carrier', length: 5 },
    { ship_type: 'Battleship', length: 4 },
    { ship_type: 'Cruiser', length: 3 },
    { ship_type: 'Submarine', length: 3 },
    { ship_type: 'Destroyer', length: 2 },
  ]
}

// ── App ───────────────────────────────────────────────────────────────────────

export default function App() {
  const [gameId, setGameId] = useState<string | null>(null)
  const [gameStarted, setGameStarted] = useState(false)
  const [showSetup, setShowSetup] = useState(true)
  const [needsHumanPlacement, setNeedsHumanPlacement] = useState(false)
  const [placementConfirmed, setPlacementConfirmed] = useState(false)
  const [humanRole] = useState<PlayerRole>('player1')
  const [fireError, setFireError] = useState<string | null>(null)

  const { game, isConnected, log, lastFiredCell, handleEvent, setGame, reset } = useGameState()

  // ── SSE event handler ─────────────────────────────────────────────────────

  const onSSEEvent = useCallback(
    (type: string, data: Record<string, unknown>) => {
      if (type === 'awaiting_human_placement') {
        const player = data.player as PlayerRole | undefined
        if (player === 'player1') setNeedsHumanPlacement(true)
      }

      // Re-fetch full state when boards first become populated (placement done)
      // or when a ship sinks (need all sunk cells, not just the fired one).
      if (
        type === 'all_placements_done' ||
        (type === 'shot_fired' && data.result === 'sunk') ||
        type === 'game_over'
      ) {
        if (gameId) {
          api.getState(gameId).then(setGame).catch(() => {})
        }
      }

      handleEvent(type, data)
    },
    [handleEvent, gameId, setGame],
  )

  const onSSEError = useCallback(() => {
    // Connection dropped — useSSE will reconnect automatically.
  }, [])

  // Connect SSE only once the game has started.
  useSSE({
    gameId: gameStarted ? gameId : null,
    onEvent: onSSEEvent,
    onError: onSSEError,
  })

  // Load initial state after game start so boards render immediately.
  useEffect(() => {
    if (!gameId || !gameStarted) return
    api.getState(gameId).then(setGame).catch(() => {
      // Non-fatal — SSE events will fill in the state.
    })
  }, [gameId, gameStarted, setGame])

  // ── Handlers ──────────────────────────────────────────────────────────────

  const handleGameCreated = useCallback((id: string) => {
    setGameId(id)
  }, [])

  const handleGameStarted = useCallback(() => {
    setGameStarted(true)
    setShowSetup(false)
  }, [])

  const handlePlacementConfirm = useCallback(
    async (placements: PlacedShip[]) => {
      if (!gameId) return
      try {
        await api.placeShips(gameId, 'player1', placements)
        setNeedsHumanPlacement(false)
        setPlacementConfirmed(true)
      } catch (e) {
        alert(
          `Failed to submit placement: ${e instanceof Error ? e.message : String(e)}`,
        )
      }
    },
    [gameId],
  )

  const handleFire = useCallback(
    async (row: number, col: number) => {
      if (!gameId) return
      setFireError(null)
      try {
        await api.fire(gameId, row, col)
      } catch (e) {
        setFireError(e instanceof Error ? e.message : 'Failed to fire')
      }
    },
    [gameId],
  )

  const handleNewGame = useCallback(async () => {
    if (gameId) {
      try {
        await api.deleteGame(gameId)
      } catch {
        // Ignore — it may already be gone.
      }
    }
    setGameId(null)
    setGameStarted(false)
    setShowSetup(true)
    setNeedsHumanPlacement(false)
    setPlacementConfirmed(false)
    setFireError(null)
    reset()
  }, [gameId, reset])

  // ── Derived values ────────────────────────────────────────────────────────

  const isHumanVsLLM = game?.mode === 'human_vs_llm'
  const boardSize = game?.board_size ?? 10
  const fleet = getFleet(boardSize)

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: '#0a0a14',
        color: '#ddd',
        fontFamily: 'system-ui, sans-serif',
        padding: 'clamp(12px, 4vw, 24px)',
        boxSizing: 'border-box',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 24,
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <h1 style={{ margin: 0, fontSize: 'clamp(18px, 5vw, 24px)', color: '#4fc3f7', letterSpacing: 1 }}>
          LLM Battleships
        </h1>

        {gameStarted && (
          <button
            onClick={handleNewGame}
            style={{
              padding: '8px 16px',
              cursor: 'pointer',
              backgroundColor: '#2a1a1a',
              color: '#f88',
              border: '1px solid #833',
              borderRadius: 6,
              fontSize: 13,
            }}
          >
            New Game
          </button>
        )}
      </div>

      {/* How to play — only visible on the setup screen */}
      {showSetup && <HowToPlay />}

      {/* Setup panel */}
      {showSetup && (
        <SetupPanel
          onGameCreated={handleGameCreated}
          onGameStarted={handleGameStarted}
        />
      )}

      {/* Game area */}
      {gameStarted && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Status bar */}
          <StatusBar game={game} isConnected={isConnected} />

          {/* Human ship placement */}
          {isHumanVsLLM && needsHumanPlacement && !placementConfirmed && (
            <div
              style={{
                padding: 20,
                backgroundColor: '#0f1a2a',
                border: '1px solid #2a4a8a',
                borderRadius: 10,
              }}
            >
              <h3 style={{ margin: '0 0 16px', color: '#4fc3f7' }}>
                Place Your Ships
              </h3>
              <ShipPlacementBoard
                boardSize={boardSize}
                fleet={fleet}
                onConfirm={handlePlacementConfirm}
                disabled={false}
              />
            </div>
          )}

          {/* Waiting for placement to complete */}
          {isHumanVsLLM && placementConfirmed && game?.phase === 'placement' && (
            <div style={{ color: '#888', fontStyle: 'italic' }}>
              Ships submitted — waiting for opponent to finish placing…
            </div>
          )}

          {/* Game boards — shown once placement is done or human has submitted placement */}
          {game && game.phase !== 'setup' && !needsHumanPlacement && (
            <div>
              {fireError && (
                <div
                  style={{
                    padding: '8px 12px',
                    marginBottom: 12,
                    backgroundColor: '#3a1a1a',
                    border: '1px solid #833',
                    borderRadius: 4,
                    color: '#f88',
                    fontSize: 13,
                  }}
                >
                  {fireError}
                </div>
              )}
              <BoardPair
                game={game}
                onFire={isHumanVsLLM ? handleFire : undefined}
                humanRole={isHumanVsLLM ? humanRole : undefined}
                lastFiredCell={lastFiredCell}
              />
            </div>
          )}

          {/* Move log */}
          <div>
            <h3 style={{ margin: '0 0 8px', fontSize: 15, color: '#aaa' }}>
              Event Log
            </h3>
            <MoveLog entries={log} />
          </div>
        </div>
      )}
    </div>
  )
}
