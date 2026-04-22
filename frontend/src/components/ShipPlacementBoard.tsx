import { useState, useCallback } from 'react'
import type { PlacedShip, CellState } from '../types/game'

interface ShipDef {
  ship_type: string
  length: number
}

// Internal type that extends PlacedShip with a length field for placement tracking.
interface PlacedShipWithLength extends PlacedShip {
  length: number
}

interface ShipPlacementBoardProps {
  boardSize: number
  fleet: ShipDef[]
  onConfirm: (placements: PlacedShip[]) => void
  disabled?: boolean
}

// Build a CellState grid marking placed ship cells.
function buildGrid(
  size: number,
  placed: PlacedShipWithLength[],
): CellState[][] {
  const grid: CellState[][] = Array.from({ length: size }, () =>
    Array.from({ length: size }, (): CellState => 'empty'),
  )
  for (const ship of placed) {
    for (let i = 0; i < ship.length; i++) {
      const r = ship.orientation === 'H' ? ship.row : ship.row + i
      const c = ship.orientation === 'H' ? ship.col + i : ship.col
      if (r < size && c < size) grid[r][c] = 'ship'
    }
  }
  return grid
}

// Cells that a ship of `length` would occupy if placed at (row, col) with orientation.
function shipCells(
  row: number,
  col: number,
  length: number,
  orientation: 'H' | 'V',
): Array<{ row: number; col: number }> {
  return Array.from({ length }, (_, i) => ({
    row: orientation === 'H' ? row : row + i,
    col: orientation === 'H' ? col + i : col,
  }))
}

// Check if a placement is valid: in bounds and not overlapping existing ships.
function isValidPlacement(
  row: number,
  col: number,
  length: number,
  orientation: 'H' | 'V',
  size: number,
  grid: CellState[][],
): boolean {
  const cells = shipCells(row, col, length, orientation)
  for (const { row: r, col: c } of cells) {
    if (r < 0 || r >= size || c < 0 || c >= size) return false
    if (grid[r][c] !== 'empty') return false
  }
  return true
}

export function ShipPlacementBoard({
  boardSize,
  fleet,
  onConfirm,
  disabled = false,
}: ShipPlacementBoardProps) {
  const [placedShips, setPlacedShips] = useState<PlacedShipWithLength[]>([])
  const [selectedShip, setSelectedShip] = useState<ShipDef | null>(null)
  const [orientation, setOrientation] = useState<'H' | 'V'>('H')
  const [hoverCell, setHoverCell] = useState<{ row: number; col: number } | null>(null)

  const grid = buildGrid(boardSize, placedShips)

  // Types of ships already placed.
  const placedTypes = new Set(placedShips.map((s) => s.ship_type))
  const remainingFleet = fleet.filter((s) => !placedTypes.has(s.ship_type))
  const allPlaced = remainingFleet.length === 0

  // Preview cells for the hovered position.
  const previewCells: Array<{ row: number; col: number }> =
    hoverCell && selectedShip
      ? shipCells(hoverCell.row, hoverCell.col, selectedShip.length, orientation)
      : []

  const previewValid =
    hoverCell && selectedShip
      ? isValidPlacement(
          hoverCell.row,
          hoverCell.col,
          selectedShip.length,
          orientation,
          boardSize,
          grid,
        )
      : false

  const handleCellClick = useCallback(
    (row: number, col: number) => {
      if (disabled || !selectedShip) return
      if (
        isValidPlacement(row, col, selectedShip.length, orientation, boardSize, grid)
      ) {
        const newShip: PlacedShipWithLength = {
          ship_type: selectedShip.ship_type,
          row,
          col,
          orientation,
          hits: [],
          length: selectedShip.length,
        }
        setPlacedShips((prev) => [...prev, newShip])
        setSelectedShip(null)
        setHoverCell(null)
      }
    },
    [disabled, selectedShip, orientation, boardSize, grid],
  )

  const handleReset = () => {
    setPlacedShips([])
    setSelectedShip(null)
    setHoverCell(null)
  }

  const handleConfirm = () => {
    if (allPlaced && !disabled) {
      // Strip internal `length` field — PlacedShip type doesn't include it.
      const cleanPlacements: PlacedShip[] = placedShips.map(
        ({ length: _len, ...rest }) => rest,
      )
      onConfirm(cleanPlacements)
    }
  }

  // Determine cell visual state for rendering.
  function getCellDisplay(row: number, col: number): {
    baseClass: string
    style: React.CSSProperties
  } {
    const isPreview = previewCells.some((c) => c.row === row && c.col === col)
    const cellState = grid[row][col]

    if (cellState === 'ship') {
      return { baseClass: 'cell cell-ship', style: {} }
    }
    if (isPreview) {
      return {
        baseClass: 'cell cell-empty',
        style: {
          backgroundColor: previewValid
            ? 'rgba(100, 200, 100, 0.5)'
            : 'rgba(220, 80, 80, 0.5)',
          outline: '2px solid rgba(255,255,255,0.3)',
        },
      }
    }
    return { baseClass: 'cell cell-empty', style: {} }
  }

  const canClick = !disabled && !!selectedShip

  return (
    <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap', alignItems: 'flex-start' }}>
      {/* Ship selector panel */}
      <div style={{ minWidth: 180 }}>
        <div style={{ fontWeight: 600, marginBottom: 8, color: '#ccc' }}>
          Place Your Ships
        </div>

        {/* Remaining fleet */}
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>
            Ships to place:
          </div>
          {remainingFleet.length === 0 ? (
            <div style={{ color: '#4caf50', fontSize: 13 }}>All ships placed!</div>
          ) : (
            remainingFleet.map((ship) => (
              <div
                key={ship.ship_type}
                onClick={() => {
                  if (!disabled) setSelectedShip(ship)
                }}
                style={{
                  padding: '6px 10px',
                  marginBottom: 4,
                  borderRadius: 4,
                  cursor: disabled ? 'default' : 'pointer',
                  backgroundColor:
                    selectedShip?.ship_type === ship.ship_type
                      ? '#2a4a8a'
                      : '#222',
                  border:
                    selectedShip?.ship_type === ship.ship_type
                      ? '1px solid #4488cc'
                      : '1px solid #444',
                  color: '#ddd',
                  fontSize: 13,
                  display: 'flex',
                  justifyContent: 'space-between',
                }}
              >
                <span>{ship.ship_type}</span>
                <span style={{ color: '#888' }}>
                  {'█'.repeat(ship.length)}
                </span>
              </div>
            ))
          )}
        </div>

        {/* Already placed ships */}
        {placedShips.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>
              Placed:
            </div>
            {placedShips.map((ship) => (
              <div
                key={ship.ship_type}
                style={{
                  padding: '4px 10px',
                  marginBottom: 3,
                  color: '#4caf50',
                  fontSize: 12,
                }}
              >
                {ship.ship_type} ({ship.orientation === 'H' ? 'Horizontal' : 'Vertical'})
              </div>
            ))}
          </div>
        )}

        {/* Controls */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <button
            onClick={() => setOrientation((o) => (o === 'H' ? 'V' : 'H'))}
            disabled={disabled}
            style={{
              padding: '6px 12px',
              cursor: disabled ? 'default' : 'pointer',
              backgroundColor: '#333',
              color: '#ccc',
              border: '1px solid #555',
              borderRadius: 4,
              fontSize: 13,
            }}
          >
            Rotate: {orientation === 'H' ? 'Horizontal' : 'Vertical'}
          </button>

          <button
            onClick={handleReset}
            disabled={disabled}
            style={{
              padding: '6px 12px',
              cursor: disabled ? 'default' : 'pointer',
              backgroundColor: '#3a1a1a',
              color: '#f88',
              border: '1px solid #833',
              borderRadius: 4,
              fontSize: 13,
            }}
          >
            Reset
          </button>

          {allPlaced && !disabled && (
            <button
              onClick={handleConfirm}
              style={{
                padding: '8px 16px',
                cursor: 'pointer',
                backgroundColor: '#1a4a2a',
                color: '#4caf50',
                border: '2px solid #4caf50',
                borderRadius: 4,
                fontSize: 14,
                fontWeight: 600,
              }}
            >
              Confirm Placement
            </button>
          )}

          {disabled && (
            <div style={{ color: '#4caf50', fontSize: 13, marginTop: 4 }}>
              Placement confirmed.
            </div>
          )}
        </div>

        {selectedShip && (
          <div style={{ marginTop: 12, fontSize: 12, color: '#4fc3f7' }}>
            Placing: <strong>{selectedShip.ship_type}</strong> (length{' '}
            {selectedShip.length})
            <br />
            Click on the grid to place.
          </div>
        )}
      </div>

      {/* Grid */}
      <div>
        {/* Column labels */}
        <div style={{ display: 'flex', marginLeft: 24, marginBottom: 2 }}>
          {Array.from({ length: boardSize }, (_, i) => (
            <div
              key={i}
              style={{
                width: 32,
                textAlign: 'center',
                fontSize: 11,
                color: '#888',
              }}
            >
              {i}
            </div>
          ))}
        </div>

        <div style={{ display: 'flex' }}>
          {/* Row labels */}
          <div style={{ display: 'flex', flexDirection: 'column', marginRight: 4 }}>
            {Array.from({ length: boardSize }, (_, i) => (
              <div
                key={i}
                style={{
                  height: 32,
                  width: 20,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'flex-end',
                  fontSize: 11,
                  color: '#888',
                  paddingRight: 2,
                }}
              >
                {i}
              </div>
            ))}
          </div>

          {/* Grid cells */}
          <div
            className="board-grid"
            style={{ gridTemplateColumns: `repeat(${boardSize}, 32px)` }}
          >
            {Array.from({ length: boardSize }, (_, r) =>
              Array.from({ length: boardSize }, (_, c) => {
                const { baseClass, style } = getCellDisplay(r, c)
                return (
                  <div
                    key={`${r}-${c}`}
                    className={baseClass}
                    style={{
                      cursor: canClick ? 'crosshair' : 'default',
                      boxSizing: 'border-box',
                      ...style,
                    }}
                    onMouseEnter={() => {
                      if (!disabled && selectedShip) {
                        setHoverCell({ row: r, col: c })
                      }
                    }}
                    onMouseLeave={() => setHoverCell(null)}
                    onClick={() => handleCellClick(r, c)}
                    title={`(${r}, ${c})`}
                  />
                )
              }),
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
