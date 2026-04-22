// MIT License
// Copyright (c) 2026 Angshuman Nandy

import { useEffect, useState } from 'react'
import type { GameStatusResponse, PlayerRole, CellState } from '../types/game'
import type { FiredCell } from '../hooks/useGameState'
import { GameBoard } from './GameBoard'

function useBoardLayout(boardSize: number): { cellSize: number; isMobile: boolean } {
  const [width, setWidth] = useState(window.innerWidth)
  useEffect(() => {
    const handler = () => setWidth(window.innerWidth)
    window.addEventListener('resize', handler)
    return () => window.removeEventListener('resize', handler)
  }, [])

  const isMobile = width <= 640

  // On mobile boards are stacked — one board fills most of the viewport width.
  // On desktop they sit side-by-side with a gap, so each gets ~half the width.
  const available = isMobile
    ? width - 60              // full width minus padding
    : (width - 120) / 2      // half width minus padding + gap

  // available ≈ coordLabel(24) + boardSize * cellSize  →  solve for cellSize
  const computed = Math.floor((available - 24) / boardSize)
  const cellSize = Math.max(16, Math.min(32, computed))

  return { cellSize, isMobile }
}

interface BoardPairProps {
  game: GameStatusResponse
  onFire?: (row: number, col: number) => void
  humanRole?: PlayerRole
  lastFiredCell?: FiredCell | null
}

function emptyGrid(size: number): CellState[][] {
  return Array.from({ length: size }, () =>
    Array.from({ length: size }, (): CellState => 'empty'),
  )
}

function playerLabel(game: GameStatusResponse, role: PlayerRole): string {
  const player = role === 'player1' ? game.player1 : game.player2
  const tag = role === 'player1' ? 'Player 1' : 'Player 2'
  if (player.is_human) return `${tag} (You)`
  if (player.llm_config) return `${tag} (${player.llm_config.model})`
  return tag
}

export function BoardPair({ game, onFire, humanRole, lastFiredCell }: BoardPairProps) {
  const size = game.board_size
  const { cellSize, isMobile } = useBoardLayout(size)
  const isHumanTurn =
    game.phase === 'in_progress' && humanRole !== undefined && game.current_turn === humanRole

  // Convert lastFiredCell to the shape GameBoard expects (just row/col/key)
  const firingCellFor = (targetRole: PlayerRole) => {
    if (!lastFiredCell) return undefined
    // The blink appears on the TARGET's board (the player being shot at)
    const targetOfShooter: PlayerRole = lastFiredCell.shooter === 'player1' ? 'player2' : 'player1'
    if (targetOfShooter !== targetRole) return undefined
    return { row: lastFiredCell.row, col: lastFiredCell.col, key: lastFiredCell.key }
  }

  const wrapStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: isMobile ? 'column' : 'row',
    alignItems: isMobile ? 'center' : 'flex-start',
    gap: isMobile ? 20 : 24,
    justifyContent: 'center',
  }

  // ── LLM vs LLM: show both boards, no click handlers ─────────────────────
  if (game.mode === 'llm_vs_llm') {
    const p1Grid = game.player1.board?.grid ?? emptyGrid(size)
    const p2Grid = game.player2.board?.grid ?? emptyGrid(size)

    return (
      <div style={wrapStyle}>
        <GameBoard grid={p1Grid} label={playerLabel(game, 'player1')} size={size} cellSize={cellSize} firingCell={firingCellFor('player1')} />
        <GameBoard grid={p2Grid} label={playerLabel(game, 'player2')} size={size} cellSize={cellSize} firingCell={firingCellFor('player2')} />
      </div>
    )
  }

  // ── Human vs LLM ─────────────────────────────────────────────────────────
  const ownGrid = game.player1.board?.grid ?? emptyGrid(size)
  const enemyShotsGrid = game.player1.shots_grid ?? emptyGrid(size)

  const handleFire =
    onFire && isHumanTurn
      ? (row: number, col: number) => onFire(row, col)
      : undefined

  return (
    <div style={wrapStyle}>
      <div>
        <GameBoard
          grid={ownGrid}
          label={playerLabel(game, 'player1')}
          size={size}
          cellSize={cellSize}
          firingCell={firingCellFor('player1')}
        />
        <div style={{ marginTop: 4, fontSize: 12, color: '#888' }}>
          Your fleet
        </div>
      </div>
      <div>
        <GameBoard
          grid={enemyShotsGrid}
          label={`${playerLabel(game, 'player2')} — Enemy waters`}
          size={size}
          cellSize={cellSize}
          onCellClick={handleFire}
          firingCell={firingCellFor('player2')}
        />
        {isHumanTurn && (
          <div style={{ marginTop: 4, fontSize: 12, color: '#4caf50' }}>
            Your turn — click an enemy cell to fire
          </div>
        )}
        {!isHumanTurn && game.phase === 'in_progress' && (
          <div style={{ marginTop: 4, fontSize: 12, color: '#888' }}>
            Waiting for opponent…
          </div>
        )}
      </div>
    </div>
  )
}
