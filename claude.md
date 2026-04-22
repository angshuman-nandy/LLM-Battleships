# LLM Battleships — Project Reference

## What This Is
A Battleship game where two LLM agents play each other (or a human plays an LLM), viewable in a browser. Users configure providers, board size, and ship placement mode, then watch or participate in real time.

Deployed as a **single Docker container on Hugging Face Spaces** (free CPU, port 7860).

---

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11, FastAPI, uvicorn |
| Frontend | React 18 + TypeScript, Vite (built to static, served by FastAPI) |
| Container | Docker multi-stage build, port 7860 |
| LLM providers | Anthropic SDK, OpenAI SDK, Ollama (user-supplied endpoint) |
| Real-time | Server-Sent Events (SSE) — no WebSocket needed |
| State | In-memory only (no database) |

---

## Directory Structure

```
LLM-battleships/
├── claude.md                       ← this file
├── Dockerfile
├── .dockerignore
├── .gitignore
│
├── backend/
│   ├── main.py                     # FastAPI app; mounts static files, includes routers
│   ├── requirements.txt
│   ├── config.py                   # FLEET_FOR_SIZE, TURN_DELAY_SECONDS, ENV
│   │
│   ├── game/
│   │   ├── models.py               # All Pydantic models
│   │   ├── board.py                # Grid logic, ship placement validation
│   │   ├── engine.py               # GameEngine: placement phase + turn loop
│   │   └── session_store.py        # Module-level singleton; games, SSE queues, events
│   │
│   ├── llm/
│   │   ├── base.py                 # Abstract LLMWrapper; shared PLACE_SHIPS_TOOL + CHOOSE_SHOT_TOOL
│   │   ├── anthropic_wrapper.py
│   │   ├── openai_wrapper.py
│   │   ├── ollama_wrapper.py
│   │   └── factory.py              # LLMWrapperFactory.create(provider, config)
│   │
│   └── api/
│       ├── routes_game.py          # /api/game/* REST endpoints
│       ├── routes_sse.py           # /sse/{game_id} streaming endpoint
│       └── deps.py                 # get_game() FastAPI dependency
│
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── index.html
    └── src/
        ├── App.tsx
        ├── types/game.ts           # TypeScript mirrors of Pydantic models
        ├── api/client.ts           # Typed fetch wrappers for all REST endpoints
        ├── hooks/
        │   ├── useSSE.ts           # SSE connection + exponential-backoff reconnect
        │   └── useGameState.ts     # Reducer driven by SSE events
        └── components/
            ├── SetupPanel.tsx          # Provider pickers, board size, API keys, placement modes
            ├── ShipPlacementBoard.tsx  # Interactive grid for human ship placement (click + rotate + Confirm)
            ├── GameBoard.tsx           # Read-only NxN grid during play
            ├── BoardPair.tsx           # Side-by-side boards
            ├── MoveLog.tsx             # Scrollable event log; shows LLM reasoning
            └── StatusBar.tsx           # Phase, whose turn, winner
```

---

## Core Models (`backend/game/models.py`)

```
Provider          anthropic | openai | ollama
GameMode          llm_vs_llm | human_vs_llm
PlacementMode     llm | third_agent | human | random
GamePhase         setup → placement → in_progress → finished
CellState         empty | ship | hit | miss | sunk
PlayerRole        player1 | player2

LLMConfig         { provider, model, api_key: SecretStr, endpoint_url? }
PlacementConfig   { mode: PlacementMode, agent_config?: LLMConfig }
PlacedShip        { ship_type, row, col, orientation, hits[] }  +  is_sunk property
BoardState        { size, grid[][], ships[] }
PlayerState       { role, is_human, llm_config?, placement_config, board, shots_grid }
Move              { player, row, col, result, ship_sunk?, reasoning? }
GameState         { game_id, mode, phase, board_size, player1, player2, current_turn, moves[], winner }

CreateGameRequest     { mode, board_size(5-15), player1_config, player1_placement, player2_config?, player2_placement }
HumanPlacementRequest { placements: list[PlacedShip] }
FireRequest           { row, col }
GameStatusResponse    — enemy ships hidden; LLMConfig never exposed
```

---

## LLM Wrapper Pattern (`backend/llm/base.py`)

```python
class LLMWrapper(ABC):
    async def place_ships(board_size, ships_to_place, system_prompt) -> PlacementResult
    async def choose_shot(board_size, own_board, enemy_board_view, move_history, system_prompt) -> ShotResult

    PLACE_SHIPS_TOOL: dict  # shared JSON schema
    CHOOSE_SHOT_TOOL: dict  # { row, col, reasoning? }
```

**All LLM calls use forced tool use — never free-text parsing:**
- Anthropic: `tool_choice={"type": "tool", "name": "choose_shot"}`
- OpenAI: `tool_choice={"type": "function", "function": {"name": "choose_shot"}}`
- Ollama: OpenAI-compatible `/v1/chat/completions`; raise `LLMCapabilityError` if model lacks tool support

**Retry**: wrap every `choose_shot` in a max-3 retry loop. On invalid coord, append the error to the conversation and retry — never silently fall back to random.

**PlacementMode wiring in engine:**
- `llm` → call `battle_llm.place_ships(...)`
- `third_agent` → `LLMWrapperFactory.create(placement_config.agent_config).place_ships(...)`
- `human` → emit `awaiting_human_placement` SSE, `await _placement_events[player]` (set by `POST /place/{player}`)
- `random` → server generates a valid placement instantly

---

## API Endpoints

| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/game/create` | Returns `game_id` |
| POST | `/api/game/{id}/start` | Launches `asyncio.create_task`; returns immediately |
| POST | `/api/game/{id}/place/{player}` | Human ship placement; validates before signalling engine |
| POST | `/api/game/{id}/fire` | Human fires; 400 if not human's turn |
| GET  | `/api/game/{id}/state` | Sanitized snapshot |
| DELETE | `/api/game/{id}` | Cancels background task, cleans session |
| GET  | `/api/health` | HF Spaces health check |
| GET  | `/sse/{id}` | `text/event-stream` |

---

## SSE Event Types

```
awaiting_human_placement → { player }
placement_started        → { player, mode, timestamp }
placement_done           → { player, timestamp }
all_placements_done      → { timestamp }
turn_start               → { player, turn_number }
shot_fired               → { player, row, col, result, ship_sunk, reasoning, turn_number }
game_over                → { winner, total_turns, player1_ships, player2_ships }
error                    → { message, player, retrying }
ping                     → { timestamp }   (every 15s, keeps HF proxy alive)
```

---

## Session Store (`backend/game/session_store.py`)

Module-level singleton — one process, no Redis needed:

```python
_games:             dict[str, GameState]
_queues:            dict[str, asyncio.Queue]                     # SSE events per game
_human_events:      dict[str, asyncio.Event]                     # set by POST /fire
_placement_events:  dict[str, dict[PlayerRole, asyncio.Event]]   # set by POST /place/{player}
_tasks:             dict[str, asyncio.Task]                      # cancelled on DELETE
```

---

## Game Engine Flow (`backend/game/engine.py`)

```
POST /start → asyncio.create_task(engine.start_game(game_id))

placement_phase():
  asyncio.gather(resolve_placement(player1), resolve_placement(player2))
  emit all_placements_done

resolve_placement(player):
  match player.placement_config.mode:
    human       → emit awaiting_human_placement; await _placement_events[player]
    random      → server picks valid placement
    llm         → await battle_llm.place_ships(...)
    third_agent → await third_llm.place_ships(...)
  emit placement_done

run_turn_loop():
  while not game_over:
    if human turn: await _human_events[game_id]
    else: shot = await llm.choose_shot(...) with retry
    apply_shot(); emit shot_fired
    check_win(); flip current_turn
  emit game_over
```

`TURN_DELAY_SECONDS = 1.0` in `config.py` throttles LLM-vs-LLM pace so moves are visible in the UI.

---

## Dockerfile (Multi-Stage)

```dockerfile
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build           # output: /app/frontend/dist/

FROM python:3.11-slim AS runtime
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist
RUN useradd -m -u 1000 appuser && chown -R appuser /app
USER appuser
EXPOSE 7860
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
```

`main.py`: register API routers first, then `StaticFiles` for `/assets`, then catch-all `FileResponse(index.html)`.

---

## Key Rules & Gotchas

1. **`api_key` must be `SecretStr`** — never appears in logs, error messages, or API responses
2. **`POST /start` must use `asyncio.create_task`** — awaiting inline means the HTTP response never returns
3. **Ollama**: warn in UI that only tool-capable models work (e.g. `llama3.1`, `mistral-nemo`)
4. **Fleet by board size** (`config.py`):
   - 5×5 → Destroyer(2) + Submarine(3)
   - 7×7 → Destroyer + Cruiser + Battleship
   - 10×10+ → Full standard fleet (all 5 ships)
5. **CORS**: enable for `localhost:5173` only when `ENV=development`; not needed in Docker
6. **`useSSE` hook**: exponential backoff reconnect (1s → 30s, max 5 retries) for HF cold-start hibernation
7. **No persistent storage** — all in-memory; container restart loses all games (acceptable)
8. **LLM retry on bad coord**: re-send error in conversation context, never silently randomize
9. **`POST /place/{player}`**: validate non-overlapping, in-bounds, all required ships present before signalling engine
10. **`ShipPlacementBoard.tsx`**: manages local state until "Confirm" clicked; calls `POST /place/{player}` then becomes read-only

---

## Local Development

```bash
# Backend
cd backend && pip install -r requirements.txt
uvicorn main:app --reload --port 8000   # ENV=development for CORS

# Frontend (separate terminal)
cd frontend && npm install && npm run dev   # → http://localhost:5173
```

## Docker

```bash
docker build -t battleships .
docker run -p 7860:7860 battleships
```

## HF Spaces Deployment

Push as a **Docker Space**. `Dockerfile` at repo root. HF exposes port 7860 automatically. Users enter API keys in the UI — never hardcode them.

---

## Build Order

1. `backend/game/models.py`
2. `backend/game/board.py`
3. `backend/llm/base.py` + `factory.py`
4. `backend/llm/anthropic_wrapper.py` (test with real API early)
5. `backend/game/session_store.py`
6. `backend/game/engine.py`
7. `backend/api/routes_game.py` + `routes_sse.py` + `deps.py`
8. `backend/main.py`
9. `frontend/src/types/game.ts` + `api/client.ts`
10. `frontend/src/hooks/useSSE.ts` + `useGameState.ts`
11. `frontend/src/components/ShipPlacementBoard.tsx` (build before GameBoard)
12. Remaining frontend components
13. `Dockerfile` — end-to-end container test
14. `backend/llm/openai_wrapper.py` + `ollama_wrapper.py`

---

## Implementation Notes (populated during build)

### Key design decisions made during implementation

**`PlacedShip.is_sunk(ship_length)`** is a method, not a property — ship length is not stored on the model, it comes from `get_fleet(board_size)` via the `fleet: list[tuple[str, int]]` parameter pattern used everywhere.

**`GameStatusResponse.from_game_state(state, requesting_role=None)`** hides both players' ships when `requesting_role=None` (spectator/LLM-vs-LLM view). Pass `requesting_role=PlayerRole.player1` to reveal that player's own ships.

**`apply_shot` mutates in place** — `BoardState.grid` and `shots_grid` are mutated directly. The engine always re-fetches game state from session_store before and after mutations, then calls `set_game()` to persist.

**Human turn flow in engine**: The `POST /fire` endpoint applies the shot (calls `apply_shot`, appends Move, enqueues SSE), then calls `human_event.set()`. The engine's `_turn_loop` just awaits the event, reads the last move, checks win, and flips turn. The engine does NOT re-apply the shot.

**Concurrent placement**: `asyncio.gather` runs both placement coroutines concurrently. Each coroutine re-fetches game state (`get_game`) before writing its player's board to prevent one overwriting the other.

**`_is_player1(role)` helper in engine.py**: Pydantic `use_enum_values=True` means role fields may be plain strings. This helper accepts both `PlayerRole` enum members and raw strings.

**`LLMCapabilityError` in OllamaWrapper**: Raised on first attempt if model returns no tool_calls, since a non-tool-capable model won't self-correct through retries.

**SSE keepalive**: `routes_sse.py` uses `asyncio.wait_for(..., timeout=15.0)` so a ping fires every 15s of silence, keeping Hugging Face proxy connections alive.

**Frontend `useGameState` reducer**: Shot events update the shooter's `shots_grid` and the target's `board.grid` in one immutable state transition. Since the API hides ship positions, only the fired cell is updated — full ship visibility comes from the server via `SET_GAME` on state polls.

**`LogEntry` type**: Exported from `useGameState.ts` and imported by `MoveLog.tsx` to avoid duplication.

### File that required most care
`engine.py` — the concurrent placement + human-turn handoff logic is the trickiest part. The separation of concerns (engine waits, route applies) avoids double-mutation bugs.

### Local dev commands
```bash
# Backend
cd /path/to/LLM-battleships
pip3 install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000 --env-file .env

# Frontend (separate terminal)  
cd frontend && npm install && npm run dev   # → http://localhost:5173

# Verify imports
python3 -c "from backend.main import app; print(app.title)"
```

### ENV variable for local dev
Set `ENV=development` to enable CORS for `localhost:5173`. In Docker/HF Spaces, leave unset (defaults to `production`).
