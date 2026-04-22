// MIT License
// Copyright (c) 2026 Angshuman Nandy

const section: React.CSSProperties = {
  marginBottom: 16,
}

const heading: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 700,
  color: '#4fc3f7',
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
  marginBottom: 6,
}

const body: React.CSSProperties = {
  fontSize: 13,
  color: '#bbb',
  lineHeight: 1.6,
}

const badge = (color: string): React.CSSProperties => ({
  display: 'inline-block',
  padding: '1px 7px',
  borderRadius: 4,
  backgroundColor: color + '22',
  border: `1px solid ${color}55`,
  color: color,
  fontSize: 12,
  fontWeight: 600,
  marginRight: 6,
  whiteSpace: 'nowrap',
})

const row: React.CSSProperties = {
  display: 'flex',
  gap: 8,
  alignItems: 'flex-start',
  marginBottom: 8,
}

const rowLabel: React.CSSProperties = {
  flexShrink: 0,
  width: 120,
  fontWeight: 600,
  color: '#aaa',
  fontSize: 13,
}

const rowDesc: React.CSSProperties = {
  fontSize: 13,
  color: '#bbb',
  lineHeight: 1.5,
}

export function HowToPlay() {
  return (
    <details
      style={{
        maxWidth: 700,
        margin: '0 auto 24px',
        backgroundColor: '#0d1520',
        border: '1px solid #1e3a5f',
        borderRadius: 10,
        overflow: 'hidden',
      }}
    >
      <summary
        style={{
          padding: '12px 20px',
          cursor: 'pointer',
          fontSize: 14,
          fontWeight: 600,
          color: '#4fc3f7',
          userSelect: 'none',
          listStyle: 'none',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}
      >
        <span style={{ fontSize: 16 }}>?</span>
        What is this &amp; how to play
        <span style={{ marginLeft: 'auto', fontSize: 12, color: '#4fc3f788', fontWeight: 400 }}>
          click to expand
        </span>
      </summary>

      <div style={{ padding: '4px 20px 20px' }}>

        {/* What is it */}
        <div style={section}>
          <div style={heading}>What is LLM Battleships?</div>
          <p style={{ ...body, marginTop: 0 }}>
            A classic Battleship game where AI language models play against each other — or against
            you. Each AI receives the current board state and move history and must call a structured
            tool to fire a shot. You watch (or play) live as moves stream in via Server-Sent Events.
          </p>
        </div>

        {/* Game modes */}
        <div style={section}>
          <div style={heading}>Game Modes</div>
          <div style={row}>
            <span style={rowLabel}>LLM vs LLM</span>
            <span style={rowDesc}>
              Two AI models play each other. Configure a model for each player, sit back, and watch.
              Both boards are fully visible.
            </span>
          </div>
          <div style={row}>
            <span style={rowLabel}>Human vs LLM</span>
            <span style={rowDesc}>
              You are Player 1. You place your ships on an interactive grid, then click cells on the
              enemy board to fire each turn. The AI plays as Player 2.
            </span>
          </div>
        </div>

        {/* Providers */}
        <div style={section}>
          <div style={heading}>Providers</div>
          <div style={row}>
            <span style={rowLabel}>
              <span style={badge('#a78bfa')}>Anthropic</span>
            </span>
            <span style={rowDesc}>
              Claude models (e.g. <code>claude-3-5-sonnet-20241022</code>). Requires
              an <code>ANTHROPIC_API_KEY</code> in the server's <code>.env</code>.
            </span>
          </div>
          <div style={row}>
            <span style={rowLabel}>
              <span style={badge('#34d399')}>OpenAI</span>
            </span>
            <span style={rowDesc}>
              GPT models (e.g. <code>gpt-4o</code>). Requires
              an <code>OPENAI_API_KEY</code> in the server's <code>.env</code>.
            </span>
          </div>
          <div style={row}>
            <span style={rowLabel}>
              <span style={badge('#fb923c')}>Ollama (local)</span>
            </span>
            <span style={rowDesc}>
              Runs a model locally via{' '}
              <a href="https://ollama.com" target="_blank" rel="noreferrer">Ollama</a>.
              No API key needed, but the model <strong>must support tool calls</strong> —
              e.g. <code>llama3.1</code>, <code>mistral-nemo</code>. Provide the endpoint URL
              (default: <code>http://localhost:11434/v1</code>).
            </span>
          </div>
          <p style={{ ...body, marginTop: 4, color: '#888', fontSize: 12 }}>
            Only providers whose API keys are set in the server environment appear in the dropdowns.
            Ollama is always shown.
          </p>
        </div>

        {/* Placement modes */}
        <div style={section}>
          <div style={heading}>Ship Placement Modes</div>
          <div style={row}>
            <span style={rowLabel}>LLM places ships</span>
            <span style={rowDesc}>
              The same battle model also chooses where to place all ships. It receives board size and
              ship list, and must call the <code>place_ships</code> tool.
            </span>
          </div>
          <div style={row}>
            <span style={rowLabel}>Third-party agent</span>
            <span style={rowDesc}>
              A <em>different</em> model handles placement. Useful to compare placement strategies
              or use a cheaper model for setup and a smarter one for combat.
            </span>
          </div>
          <div style={row}>
            <span style={rowLabel}>Human (you)</span>
            <span style={rowDesc}>
              Only available for Player 1 in Human vs LLM mode. You drag ships onto an interactive
              grid and click Confirm before the game starts.
            </span>
          </div>
          <div style={row}>
            <span style={rowLabel}>Random</span>
            <span style={rowDesc}>
              The server places ships randomly. Fastest option — good for testing.
            </span>
          </div>
        </div>

        {/* Board sizes */}
        <div style={section}>
          <div style={heading}>Board Size &amp; Fleet</div>
          <p style={{ ...body, marginTop: 0 }}>
            Smaller boards mean shorter, faster games. The fleet scales automatically:
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 4 }}>
            {[
              { size: '5×5', fleet: 'Destroyer (2) + Submarine (3)' },
              { size: '7×7', fleet: 'Destroyer + Cruiser + Battleship' },
              { size: '10×10 – 15×15', fleet: 'Full 5-ship fleet' },
            ].map(({ size, fleet }) => (
              <div
                key={size}
                style={{
                  padding: '6px 10px',
                  backgroundColor: '#111827',
                  border: '1px solid #1e3a5f',
                  borderRadius: 6,
                  fontSize: 12,
                  color: '#aaa',
                }}
              >
                <span style={{ color: '#4fc3f7', fontWeight: 700 }}>{size}</span>{' '}
                — {fleet}
              </div>
            ))}
          </div>
        </div>

        {/* How to play */}
        <div style={{ ...section, marginBottom: 0 }}>
          <div style={heading}>Quick Start</div>
          <ol style={{ ...body, margin: 0, paddingLeft: 20 }}>
            <li>Choose a <strong>Game Mode</strong> and <strong>Board Size</strong>.</li>
            <li>Select a <strong>Provider</strong> and <strong>Model</strong> for each player.</li>
            <li>Pick a <strong>Placement Mode</strong> for each player.</li>
            <li>Click <strong>Create Game</strong>, then <strong>Start Game</strong>.</li>
            <li>
              Watch the boards update in real time. In Human vs LLM, click enemy cells to fire on
              your turn.
            </li>
            <li>
              Expand the <strong>LLM reasoning</strong> entries in the Event Log to see why the AI
              picked each shot.
            </li>
          </ol>
        </div>

      </div>
    </details>
  )
}
