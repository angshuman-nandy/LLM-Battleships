// MIT License
// Copyright (c) 2026 Angshuman Nandy

import type { GameStatusResponse, PlacedShip } from '../types/game'

const BASE = '/api'

// ── Shared request payload types ─────────────────────────────────────────────

export interface LLMConfigPayload {
  provider: string
  model: string
  api_key?: string
  endpoint_url?: string
}

export interface PlacementConfigPayload {
  mode: string
  agent_config?: LLMConfigPayload
}

export interface CreateGamePayload {
  mode: string
  board_size: number
  player1_config: LLMConfigPayload
  player1_placement: PlacementConfigPayload
  /** Required for llm_vs_llm; omitted for human_vs_llm. */
  player2_config?: LLMConfigPayload
  player2_placement?: PlacementConfigPayload
}

// ── Internal helpers ─────────────────────────────────────────────────────────

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error((err as { detail?: string }).detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error((err as { detail?: string }).detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: 'DELETE' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error((err as { detail?: string }).detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

// ── Public API surface ────────────────────────────────────────────────────────

export const api = {
  /**
   * POST /api/game/create
   * Creates a new game and returns its ID.
   */
  createGame: (payload: CreateGamePayload): Promise<{ game_id: string }> =>
    post('/game/create', payload),

  /**
   * POST /api/game/{id}/start
   * Launches the game engine as a background task.
   * Returns immediately — the game progresses via SSE.
   */
  startGame: (gameId: string): Promise<{ status: string; game_id: string }> =>
    post(`/game/${gameId}/start`),

  /**
   * POST /api/game/{id}/place/{player}
   * Submits human ship placements. Validated server-side before signalling the engine.
   */
  placeShips: (
    gameId: string,
    player: string,
    placements: PlacedShip[],
  ): Promise<{ status: string }> =>
    post(`/game/${gameId}/place/${player}`, { placements }),

  /**
   * POST /api/game/{id}/fire
   * Human fires a shot at (row, col). Returns 400 if it is not the human's turn.
   */
  fire: (
    gameId: string,
    row: number,
    col: number,
  ): Promise<{ result: string; ship_sunk?: string }> =>
    post(`/game/${gameId}/fire`, { row, col }),

  /**
   * GET /api/game/{id}/state
   * Returns a sanitised game snapshot — enemy ship positions are hidden.
   */
  getState: (gameId: string): Promise<GameStatusResponse> =>
    get(`/game/${gameId}/state`),

  /**
   * DELETE /api/game/{id}
   * Cancels the background task and removes the session from memory.
   */
  deleteGame: (gameId: string): Promise<{ status: string }> =>
    del(`/game/${gameId}`),

  /**
   * POST /api/game/{id}/pause
   * Pauses an in-progress LLM game between turns.
   */
  pauseGame: (gameId: string): Promise<{ status: string }> =>
    post(`/game/${gameId}/pause`),

  /**
   * POST /api/game/{id}/resume
   * Resumes a paused game.
   */
  resumeGame: (gameId: string): Promise<{ status: string }> =>
    post(`/game/${gameId}/resume`),

  /**
   * GET /api/config
   * Returns server-side defaults (from .env) to pre-fill the setup form.
   * available_providers lists providers with configured keys (+ ollama always).
   */
  getConfig: (): Promise<{
    ollama_endpoint_url: string
    available_providers: string[]
  }> => get('/config'),
}
