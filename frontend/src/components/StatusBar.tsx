import type { GameStatusResponse, PlayerRole } from '../types/game'

interface StatusBarProps {
  game: GameStatusResponse | null
  isConnected: boolean
}

function phaseLabel(phase: string): string {
  switch (phase) {
    case 'setup':
      return 'Setup'
    case 'placement':
      return 'Ship Placement'
    case 'in_progress':
      return 'In Progress'
    case 'finished':
      return 'Finished'
    default:
      return phase
  }
}

function playerName(game: GameStatusResponse, role: PlayerRole): string {
  const player = role === 'player1' ? game.player1 : game.player2
  const tag = role === 'player1' ? 'Player 1' : 'Player 2'
  if (player.is_human) return `${tag} (You)`
  if (player.llm_config) return `${tag} (${player.llm_config.model})`
  return tag
}

export function StatusBar({ game, isConnected }: StatusBarProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 20,
        padding: '10px 16px',
        backgroundColor: '#16213e',
        border: '1px solid #333',
        borderRadius: 8,
        flexWrap: 'wrap',
        fontSize: 14,
      }}
    >
      {/* Connection indicator */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <div
          style={{
            width: 10,
            height: 10,
            borderRadius: '50%',
            backgroundColor: isConnected ? '#4caf50' : '#777',
            flexShrink: 0,
          }}
          title={isConnected ? 'Connected' : 'Disconnected'}
        />
        <span style={{ color: '#aaa', fontSize: 12 }}>
          {isConnected ? 'Live' : 'Offline'}
        </span>
      </div>

      {game === null ? (
        <span style={{ color: '#888' }}>No game active</span>
      ) : (
        <>
          {/* Phase */}
          <div style={{ color: '#ccc' }}>
            Phase:{' '}
            <span style={{ color: '#fff', fontWeight: 600 }}>
              {phaseLabel(game.phase)}
            </span>
          </div>

          {/* Turn indicator */}
          {game.phase === 'in_progress' && (
            <div style={{ color: '#ccc' }}>
              Turn:{' '}
              <span style={{ color: '#4fc3f7', fontWeight: 600 }}>
                {playerName(game, game.current_turn)}
              </span>
            </div>
          )}

          {/* Winner banner */}
          {game.phase === 'finished' && game.winner && (
            <div
              style={{
                backgroundColor: '#ffd700',
                color: '#000',
                padding: '4px 12px',
                borderRadius: 4,
                fontWeight: 700,
                fontSize: 15,
              }}
            >
              Winner: {playerName(game, game.winner)}
            </div>
          )}

          {/* Move count */}
          {game.moves.length > 0 && (
            <div style={{ color: '#888', fontSize: 12, marginLeft: 'auto' }}>
              {game.moves.length} move{game.moves.length !== 1 ? 's' : ''}
            </div>
          )}
        </>
      )}
    </div>
  )
}
