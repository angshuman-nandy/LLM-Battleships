// TypeScript mirrors of the backend Pydantic models.
// Use string literal union types throughout — no enums.

export type Provider = 'anthropic' | 'openai' | 'ollama'
export type GameMode = 'llm_vs_llm' | 'human_vs_llm'
export type PlacementMode = 'llm' | 'third_agent' | 'human' | 'random'
export type GamePhase = 'setup' | 'placement' | 'in_progress' | 'finished'
export type CellState = 'empty' | 'ship' | 'hit' | 'miss' | 'sunk'
export type PlayerRole = 'player1' | 'player2'

// ── LLM configuration ───────────────────────────────────────────────────────

/** Full config including secret key — only used when sending to the backend. */
export interface LLMConfig {
  provider: Provider
  model: string
  /** Never returned by the backend; only sent during game creation. */
  api_key: string
  endpoint_url?: string
}

/** Safe subset returned by the backend — api_key is always omitted. */
export interface SafeLLMConfig {
  provider: Provider
  model: string
}

// ── Placement ────────────────────────────────────────────────────────────────

export interface PlacementConfig {
  mode: PlacementMode
  /** Only present when mode === 'third_agent'. */
  agent_config?: LLMConfig
}

export interface PlacedShip {
  ship_type: string
  row: number
  col: number
  orientation: 'H' | 'V'
  /** Indices of cells that have been hit. */
  hits: number[]
}

// ── Board ────────────────────────────────────────────────────────────────────

export interface BoardState {
  size: number
  grid: CellState[][]
  ships: PlacedShip[]
}

// ── Player ───────────────────────────────────────────────────────────────────

/**
 * Sanitised player state as returned by GET /state.
 * Enemy ships are hidden (their grid only shows hits/misses/sunk, not ship cells).
 */
export interface SafePlayerState {
  role: PlayerRole
  is_human: boolean
  /** Absent when the player has no LLM (human player without an agent). */
  llm_config?: SafeLLMConfig
  placement_config: PlacementConfig
  /** Own board including ship positions; absent until placement is complete. */
  board?: BoardState
  /** The player's view of the enemy grid (shots fired). */
  shots_grid?: CellState[][]
}

// ── Move ─────────────────────────────────────────────────────────────────────

export interface Move {
  player: PlayerRole
  row: number
  col: number
  result: CellState
  /** Present when the shot sank a ship — contains the ship type name. */
  ship_sunk?: string
  /** LLM's reasoning text, if provided by the model. */
  reasoning?: string
}

// ── Game state ───────────────────────────────────────────────────────────────

/** Full game snapshot returned by GET /api/game/{id}/state. */
export interface GameStatusResponse {
  game_id: string
  mode: GameMode
  phase: GamePhase
  board_size: number
  player1: SafePlayerState
  player2: SafePlayerState
  current_turn: PlayerRole
  moves: Move[]
  winner?: PlayerRole
}

// ── SSE events ───────────────────────────────────────────────────────────────

/** Raw SSE event envelope. The `data` shape varies by `type`. */
export interface SSEEvent {
  type: string
  data: Record<string, unknown>
}

// Typed payloads for each known SSE event type:

export interface SSEAwaitingHumanPlacement {
  player: PlayerRole
}

export interface SSEPlacementStarted {
  player: PlayerRole
  mode: PlacementMode
  timestamp: string
}

export interface SSEPlacementDone {
  player: PlayerRole
  timestamp: string
}

export interface SSEAllPlacementsDone {
  timestamp: string
}

export interface SSETurnStart {
  player: PlayerRole
  turn_number: number
}

export interface SSEShotFired {
  player: PlayerRole
  row: number
  col: number
  result: CellState
  ship_sunk?: string
  reasoning?: string
  turn_number: number
}

export interface SSEGameOver {
  winner: PlayerRole
  total_turns: number
  player1_ships: number
  player2_ships: number
}

export interface SSEError {
  message: string
  player?: PlayerRole
  retrying: boolean
}

export interface SSEPing {
  timestamp: string
}
