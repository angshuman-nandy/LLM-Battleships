import { useReducer, useCallback } from 'react'
import type {
  GameStatusResponse,
  CellState,
  PlayerRole,
  GamePhase,
} from '../types/game'

// ── Public types ──────────────────────────────────────────────────────────────

export interface LogEntry {
  id: number
  type: string
  message: string
  reasoning?: string
  timestamp: string
}

export interface FiredCell {
  shooter: PlayerRole
  row: number
  col: number
  key: number  // incremented each shot so React re-triggers the CSS animation
}

export interface GameStateHook {
  game: GameStatusResponse | null
  isConnected: boolean
  log: LogEntry[]
  lastFiredCell: FiredCell | null
  handleEvent: (type: string, data: Record<string, unknown>) => void
  setGame: (game: GameStatusResponse) => void
  reset: () => void
}

// ── Internal state & actions ──────────────────────────────────────────────────

interface State {
  game: GameStatusResponse | null
  isConnected: boolean
  log: LogEntry[]
  logIdCounter: number
  lastFiredCell: FiredCell | null
}

type Action =
  | { type: 'SET_GAME'; payload: GameStatusResponse }
  | { type: 'SSE_EVENT'; eventType: string; data: Record<string, unknown> }
  | { type: 'RESET' }

// ── Helpers ───────────────────────────────────────────────────────────────────

function now(): string {
  return new Date().toISOString()
}

function roleLabel(player: PlayerRole): string {
  return player === 'player1' ? 'Player 1' : 'Player 2'
}

/**
 * Returns a fresh log entry.  `id` is managed by the caller so the reducer
 * can increment `logIdCounter` atomically inside the state update.
 */
function makeEntry(
  id: number,
  type: string,
  message: string,
  reasoning?: string,
): LogEntry {
  return { id, type, message, reasoning, timestamp: now() }
}

/**
 * Immutably updates a single cell in the 2-D grid at [row][col].
 * Returns the original grid reference unchanged if the cell already has that value.
 */
function setGridCell(
  grid: CellState[][],
  row: number,
  col: number,
  value: CellState,
): CellState[][] {
  if (grid[row]?.[col] === value) return grid
  return grid.map((r, ri) =>
    ri === row ? r.map((c, ci) => (ci === col ? value : c)) : r,
  )
}

// ── Reducer ───────────────────────────────────────────────────────────────────

const initialState: State = {
  game: null,
  isConnected: false,
  log: [],
  logIdCounter: 0,
  lastFiredCell: null,
}

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'SET_GAME':
      return { ...state, game: action.payload }

    case 'RESET':
      return { ...initialState }

    case 'SSE_EVENT': {
      const { eventType, data } = action

      // Pings carry no meaningful state — skip silently.
      if (eventType === 'ping') return state

      // Every non-ping event marks the SSE stream as live.
      const base: State = { ...state, isConnected: true }

      switch (eventType) {
        // ── awaiting_human_placement ─────────────────────────────────────────
        case 'awaiting_human_placement': {
          const player = data.player as PlayerRole | undefined
          const label = player ? roleLabel(player) : 'Human'
          const id = base.logIdCounter + 1
          return {
            ...base,
            logIdCounter: id,
            log: [
              ...base.log,
              makeEntry(id, eventType, `Waiting for ${label} to place ships...`),
            ],
          }
        }

        // ── placement_started ────────────────────────────────────────────────
        case 'placement_started': {
          const player = data.player as PlayerRole | undefined
          const mode = typeof data.mode === 'string' ? data.mode : 'unknown'
          const label = player ? roleLabel(player) : 'Unknown player'
          const id = base.logIdCounter + 1
          return {
            ...base,
            logIdCounter: id,
            log: [
              ...base.log,
              makeEntry(id, eventType, `${label} is placing ships (${mode} mode)...`),
            ],
          }
        }

        // ── placement_done ───────────────────────────────────────────────────
        case 'placement_done': {
          const player = data.player as PlayerRole | undefined
          const label = player ? roleLabel(player) : 'Unknown player'
          const id = base.logIdCounter + 1
          return {
            ...base,
            logIdCounter: id,
            log: [
              ...base.log,
              makeEntry(id, eventType, `${label} finished placing ships`),
            ],
          }
        }

        // ── all_placements_done ──────────────────────────────────────────────
        case 'all_placements_done': {
          const id = base.logIdCounter + 1
          // The game is now transitioning from placement → in_progress.
          // Reflect the phase change optimistically if we have a game snapshot.
          const updatedGame: GameStatusResponse | null = base.game
            ? { ...base.game, phase: 'placement' as GamePhase }
            : null
          return {
            ...base,
            game: updatedGame,
            logIdCounter: id,
            log: [
              ...base.log,
              makeEntry(id, eventType, 'All ships placed — battle begins!'),
            ],
          }
        }

        // ── turn_start ───────────────────────────────────────────────────────
        case 'turn_start': {
          const player = data.player as PlayerRole | undefined
          const turnNumber =
            typeof data.turn_number === 'number' ? data.turn_number : '?'
          const label = player ? roleLabel(player) : 'Unknown player'
          const id = base.logIdCounter + 1
          // Update current_turn in the game snapshot.
          const updatedGame: GameStatusResponse | null =
            base.game && player
              ? { ...base.game, current_turn: player }
              : base.game
          return {
            ...base,
            game: updatedGame,
            logIdCounter: id,
            log: [
              ...base.log,
              makeEntry(id, eventType, `Turn ${turnNumber}: ${label}'s turn`),
            ],
          }
        }

        // ── shot_fired ───────────────────────────────────────────────────────
        case 'shot_fired': {
          const shooter = data.player as PlayerRole | undefined
          const row = typeof data.row === 'number' ? data.row : -1
          const col = typeof data.col === 'number' ? data.col : -1
          const result = data.result as CellState | undefined
          const shipSunk = typeof data.ship_sunk === 'string' ? data.ship_sunk : undefined
          const reasoning =
            typeof data.reasoning === 'string' ? data.reasoning : undefined
          const turnNumber =
            typeof data.turn_number === 'number' ? data.turn_number : '?'

          // Build the log message.
          const coordStr = row >= 0 && col >= 0 ? `(${row},${col})` : '(?)'
          const resultStr = result ?? 'unknown'
          let msg = `${shooter ? roleLabel(shooter) : 'Unknown'} fired at ${coordStr} → ${resultStr}!`
          if (shipSunk) msg += ` Sunk: ${shipSunk}`

          const id = base.logIdCounter + 1

          // Apply board updates if we have a live game snapshot.
          let updatedGame = base.game
          if (updatedGame && shooter && result && row >= 0 && col >= 0) {
            const targetRole: PlayerRole =
              shooter === 'player1' ? 'player2' : 'player1'

            const shooterPlayer =
              shooter === 'player1' ? updatedGame.player1 : updatedGame.player2
            const targetPlayer =
              targetRole === 'player1' ? updatedGame.player1 : updatedGame.player2

            // 1. Update shooter's shots_grid at [row][col].
            const oldShotsGrid = shooterPlayer.shots_grid
            const newShotsGrid = oldShotsGrid
              ? setGridCell(oldShotsGrid, row, col, result)
              : oldShotsGrid

            // 2. Update target's board.grid at [row][col] to reflect the hit/miss/sunk.
            const oldBoardGrid = targetPlayer.board?.grid
            const newBoardGrid = oldBoardGrid
              ? setGridCell(oldBoardGrid, row, col, result)
              : oldBoardGrid

            const newShooterPlayer = newShotsGrid !== oldShotsGrid
              ? {
                  ...shooterPlayer,
                  shots_grid: newShotsGrid,
                }
              : shooterPlayer

            const newTargetPlayer =
              newBoardGrid !== oldBoardGrid && targetPlayer.board
                ? {
                    ...targetPlayer,
                    board: { ...targetPlayer.board, grid: newBoardGrid! },
                  }
                : targetPlayer

            updatedGame = {
              ...updatedGame,
              // Append the move to the moves array.
              moves: [
                ...updatedGame.moves,
                {
                  player: shooter,
                  row,
                  col,
                  result,
                  ...(shipSunk ? { ship_sunk: shipSunk } : {}),
                  ...(reasoning ? { reasoning } : {}),
                },
              ],
              player1:
                shooter === 'player1'
                  ? newShooterPlayer
                  : targetRole === 'player1'
                  ? newTargetPlayer
                  : updatedGame.player1,
              player2:
                shooter === 'player2'
                  ? newShooterPlayer
                  : targetRole === 'player2'
                  ? newTargetPlayer
                  : updatedGame.player2,
            }
          }

          // Suppress turn number in the message if it's the default sentinel.
          void turnNumber // acknowledged — used only for log context

          return {
            ...base,
            game: updatedGame,
            logIdCounter: id,
            log: [
              ...base.log,
              makeEntry(id, eventType, msg, reasoning),
            ],
            lastFiredCell:
              shooter && row >= 0 && col >= 0
                ? {
                    shooter,
                    row,
                    col,
                    key: (base.lastFiredCell?.key ?? 0) + 1,
                  }
                : base.lastFiredCell,
          }
        }

        // ── game_over ────────────────────────────────────────────────────────
        case 'game_over': {
          const winner = data.winner as PlayerRole | undefined
          const totalTurns =
            typeof data.total_turns === 'number' ? data.total_turns : '?'
          const id = base.logIdCounter + 1

          const msg = winner
            ? `Game over! ${roleLabel(winner)} wins after ${totalTurns} turns!`
            : `Game over after ${totalTurns} turns!`

          const updatedGame: GameStatusResponse | null = base.game
            ? {
                ...base.game,
                phase: 'finished' as GamePhase,
                ...(winner ? { winner } : {}),
              }
            : null

          return {
            ...base,
            game: updatedGame,
            logIdCounter: id,
            log: [...base.log, makeEntry(id, eventType, msg)],
          }
        }

        // ── error ────────────────────────────────────────────────────────────
        case 'error': {
          const message =
            typeof data.message === 'string' ? data.message : 'An unknown error occurred'
          const id = base.logIdCounter + 1
          return {
            ...base,
            logIdCounter: id,
            log: [...base.log, makeEntry(id, eventType, `Error: ${message}`)],
          }
        }

        // ── unrecognised events ──────────────────────────────────────────────
        default:
          return base
      }
    }

    default:
      return state
  }
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useGameState(): GameStateHook {
  const [state, dispatch] = useReducer(reducer, initialState)

  const handleEvent = useCallback(
    (type: string, data: Record<string, unknown>) => {
      dispatch({ type: 'SSE_EVENT', eventType: type, data })
    },
    [],
  )

  const setGame = useCallback((game: GameStatusResponse) => {
    dispatch({ type: 'SET_GAME', payload: game })
  }, [])

  const reset = useCallback(() => {
    dispatch({ type: 'RESET' })
  }, [])

  return {
    game: state.game,
    isConnected: state.isConnected,
    log: state.log,
    lastFiredCell: state.lastFiredCell,
    handleEvent,
    setGame,
    reset,
  }
}
