---
title: LLM Battleships
emoji: 🚢
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---

# LLM Battleships

A Battleship game where two LLM agents play each other — or you play against one — viewable live in a browser. Configure providers, board size, and ship placement strategy, then watch the AIs duel in real time.

Deployable as a single Docker container on [Hugging Face Spaces](https://huggingface.co/spaces) (free CPU tier).

---

## How to Play

### LLM vs LLM (spectator)
Both players are AI models. You pick the provider, model, and API key for each, choose a board size, and watch them play. Both boards are fully visible — see where ships are placed and watch cells turn red as they're hit.

### Human vs LLM
You are Player 1. The LLM is Player 2.

1. **Place your ships** — click a ship from the list to select it, hover over the board to preview placement, click to place. Press **Rotate** to toggle horizontal/vertical. Press **Confirm** when done.
2. **Fire** — click any unrevealed cell on the enemy board to fire. Your turn indicator shows when it's your go.
3. **Win** — sink all enemy ships before yours are sunk.

### Board legend

| Colour | Meaning |
|--------|---------|
| Dark blue | Empty sea |
| Green | Your ship |
| Red | Hit |
| Dark red | Sunk ship |
| Gray dot | Miss |

### Placement modes

Each player's ships can be placed by one of four strategies:

| Mode | Description |
|------|-------------|
| `llm` | The battle LLM places its own ships |
| `third_agent` | A separate LLM (different model/provider) places ships |
| `human` | You click ships onto the board interactively |
| `random` | Server generates a valid random layout instantly |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, uvicorn |
| Frontend | React 18, TypeScript, Vite |
| Real-time | Server-Sent Events (SSE) |
| LLM providers | Anthropic SDK, OpenAI SDK |
| Data validation | Pydantic v2 |
| Container | Docker multi-stage build |
| Hosting | Hugging Face Spaces (port 7860) |
| State | In-memory only — no database |

---

## Architecture

```
Browser (React + TypeScript)
│
│  HTTP REST              SSE stream
│  POST /api/game/create  GET /sse/{game_id}
│  POST /api/game/start   ─────────────────────────────────────┐
│  POST /api/game/fire                                          │
│  GET  /api/game/state                                         │
│                                                               │
▼                                                               │
┌─────────────────────────────────────────────────────────────┐ │
│  FastAPI  (backend/main.py)                                 │ │
│                                                             │ │
│  ┌─────────────────┐    ┌──────────────────────────────┐   │ │
│  │  routes_game.py │    │       routes_sse.py           │   │ │
│  │  ─ create       │    │  asyncio.Queue per game       │───┼─┘
│  │  ─ start        │    │  ping every 15s               │   │
│  │  ─ place        │    └──────────────────────────────┘   │
│  │  ─ fire         │                                        │
│  │  ─ state        │                                        │
│  └────────┬────────┘                                        │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  session_store.py  (module-level singleton)         │    │
│  │                                                     │    │
│  │  _games      dict[game_id → GameState]              │    │
│  │  _queues     dict[game_id → asyncio.Queue]  ────────┼────┘
│  │  _tasks      dict[game_id → asyncio.Task]           │
│  │  _human_events / _placement_events                  │
│  └─────────────────────────────────────────────────────┘
│           │
│           ▼
│  ┌─────────────────────────────────────────────────────┐
│  │  engine.py  (GameEngine — runs as asyncio.Task)     │
│  │                                                     │
│  │  start_game()                                       │
│  │    └─ placement_phase()                             │
│  │         ├─ asyncio.gather(resolve_p1, resolve_p2)   │
│  │         └─ emit all_placements_done                 │
│  │    └─ turn_loop()                                   │
│  │         ├─ human turn → await human_event           │
│  │         └─ LLM turn  → llm.choose_shot() + retry   │
│  └──────────────────┬──────────────────────────────────┘
│                     │
│           ┌─────────▼─────────┐
│           │   llm/            │
│           │   ─ base.py       │  Forced tool use on every call
│           │   ─ anthropic_    │  Max 3 retries on bad coords
│           │     wrapper.py    │
│           │   ─ openai_       │
│           │     wrapper.py    │
│           │   ─ factory.py    │
│           └───────────────────┘
└─────────────────────────────────────────────────────────────┘

Frontend state flow
───────────────────
useSSE  ──event──▶  useGameState (reducer)  ──▶  BoardPair / MoveLog
                       │
                       ├─ all_placements_done → re-fetch /state (boards now live)
                       ├─ shot_fired          → update grid cell + blink animation
                       ├─ shot_fired (sunk)   → re-fetch /state (all cells marked)
                       └─ game_over           → re-fetch /state (final snapshot)
```

---

## Local Development

### Prerequisites
- Python 3.11+
- Node.js 20+

### Backend

```bash
cd LLM-battleships
cp .env.example .env          # fill in your API keys
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

### Frontend (separate terminal)

```bash
cd frontend
npm install
npm run dev                   # → http://localhost:5173 (proxies /api to :8000)
```

Set `ENV=development` in `.env` to enable CORS between the two dev servers.

### Environment variables (`.env`)

```
ENV=development

ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

Keys set here pre-fill the setup form in the browser. Leave blank to enter them manually in the UI. API keys are **never** logged or stored server-side.

---

## Docker

```bash
docker build -t battleships .
docker run -p 7860:7860 battleships
# → http://localhost:7860
```

The multi-stage Dockerfile builds the React frontend first, then copies the static output into the Python image alongside the backend. No separate frontend server is needed at runtime — FastAPI serves the built assets.

---

## Hugging Face Spaces

Push the repo as a **Docker Space**. HF exposes port 7860 automatically. Users supply their own API keys via the UI — never hardcode them in the image.

```
Space type: Docker
Port:       7860
```

---

## Supported LLM Providers

| Provider | Notes |
|----------|-------|
| Anthropic | claude-3-5-haiku |
| OpenAI | gpt-4o-mini |

All LLM calls use **forced tool use** — structured JSON responses only, no free-text parsing.

---

## Board Sizes & Fleets

| Board | Fleet |
|-------|-------|
| 5×5 | Destroyer (2), Submarine (3) |
| 7×7 | Destroyer (2), Cruiser (3), Battleship (4) |
| 10×10 – 15×15 | Carrier (5), Battleship (4), Cruiser (3), Submarine (3), Destroyer (2) |
