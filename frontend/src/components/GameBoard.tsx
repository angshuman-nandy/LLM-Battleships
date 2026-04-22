import type { CellState } from '../types/game'

interface FiringCell {
  row: number
  col: number
  key: number
}

interface GameBoardProps {
  grid: CellState[][]
  label: string
  size: number
  cellSize?: number
  onCellClick?: (row: number, col: number) => void
  highlightCells?: Array<{ row: number; col: number }>
  firingCell?: FiringCell
}

function cellClass(state: CellState): string {
  return `cell cell-${state}`
}

function isHighlighted(
  row: number,
  col: number,
  highlights: Array<{ row: number; col: number }> | undefined,
): boolean {
  if (!highlights) return false
  return highlights.some((h) => h.row === row && h.col === col)
}

export function GameBoard({
  grid,
  label,
  size,
  cellSize = 32,
  onCellClick,
  highlightCells,
  firingCell,
}: GameBoardProps) {
  const colLabels = Array.from({ length: size }, (_, i) => i)
  const rowLabels = Array.from({ length: size }, (_, i) => i)
  const coordLabelWidth = cellSize <= 24 ? 16 : 20

  return (
    <div style={{ display: 'inline-block' }}>
      <div className="board-label">{label}</div>

      {/* Column coordinate row */}
      <div style={{ display: 'flex', marginLeft: coordLabelWidth + 4, marginBottom: 2 }}>
        {colLabels.map((c) => (
          <div
            key={c}
            style={{
              width: cellSize,
              textAlign: 'center',
              fontSize: cellSize <= 24 ? 9 : 11,
              color: '#888',
              lineHeight: '14px',
            }}
          >
            {c}
          </div>
        ))}
      </div>

      <div style={{ display: 'flex' }}>
        {/* Row coordinate column */}
        <div style={{ display: 'flex', flexDirection: 'column', marginRight: 4 }}>
          {rowLabels.map((r) => (
            <div
              key={r}
              style={{
                height: cellSize,
                width: coordLabelWidth,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-end',
                fontSize: cellSize <= 24 ? 9 : 11,
                color: '#888',
                paddingRight: 2,
              }}
            >
              {r}
            </div>
          ))}
        </div>

        {/* The actual grid */}
        <div
          className="board-grid"
          style={{ gridTemplateColumns: `repeat(${size}, ${cellSize}px)` }}
        >
          {grid.map((row, r) =>
            row.map((state, c) => {
              const highlighted = isHighlighted(r, c, highlightCells)
              const clickable = !!onCellClick && state === 'empty'
              const isFiring = firingCell?.row === r && firingCell?.col === c
              return (
                <div
                  key={isFiring ? `${r}-${c}-${firingCell!.key}` : `${r}-${c}`}
                  className={`${cellClass(state)}${isFiring ? ' cell-firing' : ''}`}
                  style={{
                    width: cellSize,
                    height: cellSize,
                    cursor: clickable ? 'pointer' : 'default',
                    outline: highlighted ? '2px solid rgba(100,160,255,0.8)' : undefined,
                    backgroundColor: highlighted ? 'rgba(100,160,255,0.25)' : undefined,
                    boxSizing: 'border-box',
                  }}
                  onClick={() => {
                    if (onCellClick && state === 'empty') {
                      onCellClick(r, c)
                    }
                  }}
                  title={`(${r}, ${c}) ${state}`}
                />
              )
            }),
          )}
        </div>
      </div>
    </div>
  )
}
