// MIT License
// Copyright (c) 2026 Angshuman Nandy

import { useState, useEffect } from 'react'
import type { Provider, GameMode, PlacementMode } from '../types/game'
import { api } from '../api/client'
import type { LLMConfigPayload, PlacementConfigPayload, CreateGamePayload } from '../api/client'

interface SetupPanelProps {
  onGameCreated: (gameId: string) => void
  onGameStarted: () => void
}

interface LLMFormState {
  provider: Provider
  model: string
  endpointUrl: string
}

interface PlacementFormState {
  mode: PlacementMode
  agentProvider: Provider
  agentModel: string
  agentEndpointUrl: string
}

const PRESET_MODELS: Record<Provider, Array<{ value: string; label: string }>> = {
  anthropic: [
    { value: 'claude-haiku-4-5-20251001', label: 'Claude Haiku 4.5 (fast · cheap)' },
    { value: 'claude-sonnet-4-6',         label: 'Claude Sonnet 4.6 (balanced)' },
  ],
  openai: [
    { value: 'gpt-4o-mini',  label: 'GPT-4o mini (fast · cheap)' },
    { value: 'gpt-4.1-nano', label: 'GPT-4.1 nano (fastest · cheapest)' },
    { value: 'gpt-4.1-mini', label: 'GPT-4.1 mini (balanced)' },
    { value: 'gpt-4.1',      label: 'GPT-4.1 (flagship)' },
    { value: 'gpt-4o',       label: 'GPT-4o (capable)' },
    { value: 'o4-mini',      label: 'o4-mini (reasoning)' },
  ],
}

const PROVIDER_LABELS: Record<Provider, string> = {
  anthropic: 'Anthropic',
  openai: 'OpenAI',
}

const BOARD_SIZES = [5, 7, 10]

// ── Shared inline styles ──────────────────────────────────────────────────────

const selectStyle: React.CSSProperties = {
  display: 'block',
  marginTop: 4,
  width: '100%',
  padding: '6px 8px',
  backgroundColor: '#1a1a2e',
  color: '#ddd',
  border: '1px solid #444',
  borderRadius: 4,
  fontSize: 13,
}

// ── Sub-components ────────────────────────────────────────────────────────────

function ModelSelector({
  provider,
  model,
  onChange,
  disabled,
}: {
  provider: Provider
  model: string
  onChange: (m: string) => void
  disabled?: boolean
}) {
  const presets = PRESET_MODELS[provider] ?? []

  return (
    <select
      value={model}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
      style={selectStyle}
    >
      {presets.map((p) => (
        <option key={p.value} value={p.value}>
          {p.label}
        </option>
      ))}
    </select>
  )
}

function LLMConfigForm({
  label,
  value,
  onChange,
  availableProviders,
  disabled,
}: {
  label: string
  value: LLMFormState
  onChange: (v: LLMFormState) => void
  availableProviders: Provider[]
  disabled?: boolean
}) {
  return (
    <fieldset
      style={{
        border: '1px solid #444',
        borderRadius: 6,
        padding: '12px 16px',
        marginBottom: 12,
      }}
    >
      <legend style={{ color: '#aaa', padding: '0 6px', fontWeight: 600 }}>
        {label}
      </legend>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <label style={{ fontSize: 13, color: '#ccc' }}>
          Provider
          <select
            value={value.provider}
            disabled={disabled}
            onChange={(e) => {
              const p = e.target.value as Provider
              const defaultModel = PRESET_MODELS[p]?.[0]?.value ?? ''
              onChange({ ...value, provider: p, model: defaultModel })
            }}
            style={selectStyle}
          >
            {availableProviders.map((p) => (
              <option key={p} value={p}>
                {PROVIDER_LABELS[p]}
              </option>
            ))}
          </select>
        </label>

        <label style={{ fontSize: 13, color: '#ccc' }}>
          Model
          <div style={{ marginTop: 4 }}>
            <ModelSelector
              provider={value.provider}
              model={value.model}
              onChange={(m) => onChange({ ...value, model: m })}
              disabled={disabled}
            />
          </div>
        </label>
      </div>
    </fieldset>
  )
}

function PlacementForm({
  label,
  value,
  onChange,
  availableModes,
  availableProviders,
  disabled,
}: {
  label: string
  value: PlacementFormState
  onChange: (v: PlacementFormState) => void
  availableModes: PlacementMode[]
  availableProviders: Provider[]
  disabled?: boolean
}) {
  return (
    <fieldset
      style={{
        border: '1px solid #333',
        borderRadius: 6,
        padding: '10px 14px',
        marginBottom: 8,
      }}
    >
      <legend style={{ color: '#999', padding: '0 4px', fontSize: 12 }}>{label}</legend>

      <label style={{ fontSize: 13, color: '#ccc' }}>
        Placement Mode
        <select
          value={value.mode}
          disabled={disabled}
          onChange={(e) => onChange({ ...value, mode: e.target.value as PlacementMode })}
          style={selectStyle}
        >
          {availableModes.map((m) => (
            <option key={m} value={m}>
              {m === 'llm'
                ? 'LLM places ships'
                : m === 'third_agent'
                ? 'Third-party agent'
                : m === 'human'
                ? 'Human (you)'
                : 'Random'}
            </option>
          ))}
        </select>
      </label>

      {value.mode === 'third_agent' && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: 12, color: '#888', marginBottom: 6 }}>
            Placement Agent Config
          </div>

          <label style={{ fontSize: 13, color: '#ccc', display: 'block', marginBottom: 6 }}>
            Provider
            <select
              value={value.agentProvider}
              disabled={disabled}
              onChange={(e) => {
                const p = e.target.value as Provider
                const defaultModel = PRESET_MODELS[p]?.[0]?.value ?? ''
                onChange({ ...value, agentProvider: p, agentModel: defaultModel })
              }}
              style={selectStyle}
            >
              {availableProviders.map((p) => (
                <option key={p} value={p}>
                  {PROVIDER_LABELS[p]}
                </option>
              ))}
            </select>
          </label>

          <label style={{ fontSize: 13, color: '#ccc', display: 'block', marginBottom: 6 }}>
            Model
            <div style={{ marginTop: 4 }}>
              <ModelSelector
                provider={value.agentProvider}
                model={value.agentModel}
                onChange={(m) => onChange({ ...value, agentModel: m })}
                disabled={disabled}
              />
            </div>
          </label>
        </div>
      )}
    </fieldset>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function SetupPanel({ onGameCreated, onGameStarted }: SetupPanelProps) {
  const [availableProviders, setAvailableProviders] = useState<Provider[]>([])
  const [configLoaded, setConfigLoaded] = useState(false)

  const [mode, setMode] = useState<GameMode>('llm_vs_llm')
  const [boardSize, setBoardSize] = useState<number>(5)

  const [p1LLM, setP1LLM] = useState<LLMFormState>({ provider: 'anthropic', model: '', endpointUrl: '' })
  const [p1Placement, setP1Placement] = useState<PlacementFormState>({
    mode: 'llm', agentProvider: 'anthropic', agentModel: '', agentEndpointUrl: '',
  })
  const [p2LLM, setP2LLM] = useState<LLMFormState>({ provider: 'anthropic', model: '', endpointUrl: '' })
  const [p2Placement, setP2Placement] = useState<PlacementFormState>({
    mode: 'llm', agentProvider: 'anthropic', agentModel: '', agentEndpointUrl: '',
  })

  const [gameId, setGameId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Fetch server config on mount to discover which providers are available.
  useEffect(() => {
    api.getConfig().then((cfg) => {
      const providers = cfg.available_providers as Provider[]
      setAvailableProviders(providers)

      // Default selectors to first available provider + its first preset model.
      const first = providers[0] ?? 'anthropic'
      const firstModel = PRESET_MODELS[first]?.[0]?.value ?? ''
      setP1LLM((prev) => ({ ...prev, provider: first, model: firstModel }))
      setP2LLM((prev) => ({ ...prev, provider: first, model: firstModel }))
      setP1Placement((prev) => ({ ...prev, agentProvider: first, agentModel: firstModel }))
      setP2Placement((prev) => ({ ...prev, agentProvider: first, agentModel: firstModel }))
      setConfigLoaded(true)
    }).catch(() => {
      setConfigLoaded(true)
    })
  }, [])

  function buildLLMPayload(form: LLMFormState): LLMConfigPayload {
    const fallback = PRESET_MODELS[form.provider]?.[0]?.value ?? ''
    return {
      provider: form.provider,
      model: form.model || fallback,
    }
  }

  function buildPlacementPayload(form: PlacementFormState): PlacementConfigPayload {
    const payload: PlacementConfigPayload = { mode: form.mode }
    if (form.mode === 'third_agent') {
      const agentFallback = PRESET_MODELS[form.agentProvider]?.[0]?.value ?? ''
      payload.agent_config = {
        provider: form.agentProvider,
        model: form.agentModel || agentFallback,
      }
    }
    return payload
  }

  async function handleCreate() {
    setError(null)
    setLoading(true)
    try {
      const payload: CreateGamePayload = {
        mode,
        board_size: boardSize,
        player1_config:
          mode === 'human_vs_llm'
            ? { provider: 'anthropic', model: 'human' }
            : buildLLMPayload(p1LLM),
        player1_placement:
          mode === 'human_vs_llm'
            ? { mode: 'human' }
            : buildPlacementPayload(p1Placement),
        player2_config: buildLLMPayload(p2LLM),
        player2_placement: buildPlacementPayload(p2Placement),
      }

      const { game_id } = await api.createGame(payload)
      setGameId(game_id)
      onGameCreated(game_id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create game')
    } finally {
      setLoading(false)
    }
  }

  async function handleStart() {
    if (!gameId) return
    setError(null)
    setLoading(true)
    try {
      await api.startGame(gameId)
      onGameStarted()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start game')
    } finally {
      setLoading(false)
    }
  }

  const p1PlacementModes: PlacementMode[] =
    mode === 'llm_vs_llm' ? ['llm', 'third_agent', 'random'] : ['human']
  const p2PlacementModes: PlacementMode[] = ['llm', 'third_agent', 'random']

  const formDisabled = !!gameId || loading

  if (!configLoaded) {
    return (
      <div style={{ color: '#888', padding: 24 }}>Loading server config…</div>
    )
  }

  return (
    <div
      style={{
        maxWidth: 600,
        margin: '0 auto',
        padding: 'clamp(12px, 4vw, 24px)',
        backgroundColor: '#0f0f1a',
        borderRadius: 10,
        border: '1px solid #333',
      }}
    >
      <h2 style={{ color: '#ddd', marginTop: 0, marginBottom: 20 }}>New Game</h2>

      {availableProviders.length === 0 && (
        <div
          style={{
            padding: '10px 14px',
            marginBottom: 16,
            backgroundColor: '#2a2000',
            border: '1px solid #664',
            borderRadius: 6,
            color: '#fa0',
            fontSize: 13,
          }}
        >
          No API keys detected. Set <code>ANTHROPIC_API_KEY</code> or{' '}
          <code>OPENAI_API_KEY</code> in your <code>.env</code>.
        </div>
      )}

      {error && (
        <div
          style={{
            padding: '10px 14px',
            marginBottom: 16,
            backgroundColor: '#3a1a1a',
            border: '1px solid #833',
            borderRadius: 6,
            color: '#f88',
            fontSize: 13,
          }}
        >
          {error}
        </div>
      )}

      {/* Game Mode */}
      <div style={{ marginBottom: 16 }}>
        <label style={{ fontSize: 14, color: '#ccc', fontWeight: 600 }}>
          Game Mode
          <select
            value={mode}
            disabled={formDisabled}
            onChange={(e) => setMode(e.target.value as GameMode)}
            style={{ ...selectStyle, marginTop: 6 }}
          >
            <option value="llm_vs_llm">LLM vs LLM</option>
            <option value="human_vs_llm">Human vs LLM</option>
          </select>
        </label>
      </div>

      {/* Board Size */}
      <div style={{ marginBottom: 16 }}>
        <label style={{ fontSize: 14, color: '#ccc', fontWeight: 600 }}>
          Board Size
          <select
            value={boardSize}
            disabled={formDisabled}
            onChange={(e) => setBoardSize(Number(e.target.value))}
            style={{ ...selectStyle, marginTop: 6 }}
          >
            {BOARD_SIZES.map((s) => (
              <option key={s} value={s}>
                {s}×{s}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* Player 1 */}
      {mode === 'llm_vs_llm' ? (
        <>
          <LLMConfigForm
            label="Player 1 — LLM"
            value={p1LLM}
            onChange={setP1LLM}
            availableProviders={availableProviders}
            disabled={formDisabled}
          />
          <PlacementForm
            label="Player 1 Placement"
            value={p1Placement}
            onChange={setP1Placement}
            availableModes={p1PlacementModes}
            availableProviders={availableProviders}
            disabled={formDisabled}
          />
        </>
      ) : (
        <div
          style={{
            padding: '10px 14px',
            marginBottom: 12,
            backgroundColor: '#1a2a1a',
            border: '1px solid #444',
            borderRadius: 6,
            color: '#8f8',
            fontSize: 13,
          }}
        >
          Player 1: You (Human) — placement will be done interactively.
        </div>
      )}

      {/* Player 2 */}
      <LLMConfigForm
        label={mode === 'human_vs_llm' ? 'Opponent (Player 2) — LLM' : 'Player 2 — LLM'}
        value={p2LLM}
        onChange={setP2LLM}
        availableProviders={availableProviders}
        disabled={formDisabled}
      />
      <PlacementForm
        label="Player 2 Placement"
        value={p2Placement}
        onChange={setP2Placement}
        availableModes={p2PlacementModes}
        availableProviders={availableProviders}
        disabled={formDisabled}
      />

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
        {!gameId ? (
          <button
            onClick={handleCreate}
            disabled={formDisabled}
            style={{
              padding: '10px 20px',
              cursor: loading ? 'wait' : 'pointer',
              backgroundColor: '#1a3a6a',
              color: '#4fc3f7',
              border: '1px solid #4fc3f7',
              borderRadius: 6,
              fontSize: 14,
              fontWeight: 600,
            }}
          >
            {loading ? 'Creating…' : 'Create Game'}
          </button>
        ) : (
          <button
            onClick={handleStart}
            disabled={loading}
            style={{
              padding: '10px 20px',
              cursor: loading ? 'wait' : 'pointer',
              backgroundColor: '#1a4a2a',
              color: '#4caf50',
              border: '2px solid #4caf50',
              borderRadius: 6,
              fontSize: 14,
              fontWeight: 600,
            }}
          >
            {loading ? 'Starting…' : 'Start Game'}
          </button>
        )}
      </div>

      {gameId && (
        <div style={{ marginTop: 10, fontSize: 12, color: '#666' }}>
          Game ID: <code>{gameId}</code>
        </div>
      )}
    </div>
  )
}
