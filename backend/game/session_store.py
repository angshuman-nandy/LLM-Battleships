# MIT License
# Copyright (c) 2026 Angshuman Nandy

import asyncio
from typing import Optional

from .models import GameState, PlayerRole

# Module-level singleton state — one process, no Redis needed.
_games: dict[str, GameState] = {}
_queues: dict[str, asyncio.Queue] = {}
_human_events: dict[str, asyncio.Event] = {}
_placement_events: dict[str, dict[str, asyncio.Event]] = {}
_pause_events: dict[str, asyncio.Event] = {}
_tasks: dict[str, asyncio.Task] = {}


def create_session(game_id: str, game: GameState) -> None:
    """Initialise all per-game state.  Must be called from inside a running event loop."""
    _games[game_id] = game
    _queues[game_id] = asyncio.Queue()
    _human_events[game_id] = asyncio.Event()
    _placement_events[game_id] = {
        PlayerRole.player1.value: asyncio.Event(),
        PlayerRole.player2.value: asyncio.Event(),
    }
    pause_event = asyncio.Event()
    pause_event.set()  # set = running; clear = paused
    _pause_events[game_id] = pause_event
    # Background task is registered separately via set_task().


def get_game(game_id: str) -> Optional[GameState]:
    """Return the GameState for *game_id*, or None if it does not exist."""
    return _games.get(game_id)


def set_game(game_id: str, game: GameState) -> None:
    """Overwrite the stored GameState (e.g. after a mutation)."""
    _games[game_id] = game


def get_queue(game_id: str) -> Optional[asyncio.Queue]:
    """Return the SSE event queue for *game_id*, or None."""
    return _queues.get(game_id)


async def enqueue_event(game_id: str, event_type: str, data: dict) -> None:
    """Push a structured SSE event onto the game's queue.

    Silently no-ops when the session no longer exists (e.g. deleted mid-game).
    """
    queue = _queues.get(game_id)
    if queue is not None:
        await queue.put({"type": event_type, "data": data})


def get_human_event(game_id: str) -> Optional[asyncio.Event]:
    """Return the asyncio.Event that the engine awaits before processing a human shot."""
    return _human_events.get(game_id)


def get_placement_event(game_id: str, player: str) -> Optional[asyncio.Event]:
    """Return the placement asyncio.Event for *player* (a PlayerRole value string).

    Returns None when the session or the player key is absent.
    """
    session_events = _placement_events.get(game_id)
    if session_events is None:
        return None
    return session_events.get(player)


def get_pause_event(game_id: str) -> Optional[asyncio.Event]:
    """Return the pause asyncio.Event for *game_id*.

    Convention: event SET means running; event CLEAR means paused.
    The engine awaits this event before each LLM turn.
    """
    return _pause_events.get(game_id)


def set_task(game_id: str, task: asyncio.Task) -> None:
    """Register the background game-loop task so it can be cancelled on deletion."""
    _tasks[game_id] = task


def delete_session(game_id: str) -> None:
    """Cancel the background task (if any) and remove all state for *game_id*."""
    task = _tasks.pop(game_id, None)
    if task is not None and not task.done():
        task.cancel()

    _games.pop(game_id, None)
    _queues.pop(game_id, None)
    _human_events.pop(game_id, None)
    _placement_events.pop(game_id, None)
    _pause_events.pop(game_id, None)


def list_game_ids() -> list[str]:
    """Return a snapshot of all active game IDs."""
    return list(_games.keys())
