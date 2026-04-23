# LLM Battleships

A Battleship game where two LLM agents play each other (or a human plays an LLM), viewable in a browser. Deployed as a single Docker container on Hugging Face Spaces (port 7860).

---

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11, FastAPI, uvicorn |
| Frontend | React 18 + TypeScript, Vite (served as static by FastAPI) |
| Container | Docker multi-stage build, port 7860 |
| LLM providers | Anthropic, OpenAI |
| Real-time | Server-Sent Events (SSE) |
| State | In-memory only — no database |

---

## Directory Structure

```
LLM-battleships/
├── Dockerfile
├── backend/
│   ├── main.py                 # FastAPI app
│   ├── config.py               # Fleet sizes, turn delay, env
│   ├── prompts.py              # All LLM prompt helpers
│   ├── game/
│   │   ├── models.py           # Pydantic models
│   │   ├── board.py            # Grid logic, placement validation
│   │   ├── engine.py           # Placement phase + turn loop
│   │   └── session_store.py    # In-memory singleton (games, queues, events)
│   ├── llm/
│   │   ├── base.py             # Abstract LLMWrapper + shared tool schemas
│   │   ├── anthropic_wrapper.py
│   │   ├── openai_wrapper.py
│   │   └── factory.py
│   └── api/
│       ├── routes_game.py      # /api/game/* endpoints
│       ├── routes_sse.py       # /sse/{game_id}
│       └── deps.py
└── frontend/src/
    ├── App.tsx
    ├── types/game.ts
    ├── api/client.ts
    ├── hooks/
    │   ├── useSSE.ts
    │   └── useGameState.ts
    └── components/
        ├── SetupPanel.tsx
        ├── ShipPlacementBoard.tsx
        ├── GameBoard.tsx
        ├── BoardPair.tsx
        ├── MoveLog.tsx
        └── StatusBar.tsx
```

---

## API Endpoints

| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/game/create` | Returns `game_id` |
| POST | `/api/game/{id}/start` | Launches background task |
| POST | `/api/game/{id}/place/{player}` | Human ship placement |
| POST | `/api/game/{id}/fire` | Human fires a shot |
| POST | `/api/game/{id}/pause` | Pause LLM game |
| POST | `/api/game/{id}/resume` | Resume paused game |
| GET  | `/api/game/{id}/state` | Sanitized snapshot |
| DELETE | `/api/game/{id}` | Cancel and remove game |
| GET  | `/api/config` | Server-side provider availability |
| GET  | `/api/health` | Health check |
| GET  | `/sse/{id}` | SSE stream |

---

## Key Rules

- `api_key` is `SecretStr` — never logged or returned in responses
- `POST /start` uses `asyncio.create_task` — never awaited inline
- LLM shot retries feed the error back into the conversation; never silently randomize
- LLM placement falls back to random after 3 failed attempts (emits error SSE)
- Fleet by board size: 5×5 → 2 ships, 7×7 → 3 ships, 10×10 → 5 ships

---

## Local Development

```bash
# Backend
pip3 install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000 --env-file .env

# Frontend (separate terminal)
cd frontend && npm install && npm run dev   # → http://localhost:5173
```

Set `ENV=development` in `.env` to enable CORS for `localhost:5173`.

## Docker

```bash
docker build -t battleships .
docker run -p 7860:7860 battleships
```
