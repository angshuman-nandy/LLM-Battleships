"""
routes_sse.py — Server-Sent Events streaming endpoint for LLM Battleships.

Clients connect to GET /sse/{game_id} and receive a stream of structured
events emitted by the game engine.  A 15-second keepalive ping is sent
whenever no event arrives, which prevents Hugging Face's proxy from
closing idle connections.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from ..game.session_store import get_game, get_queue

logger = logging.getLogger(__name__)

router = APIRouter()


def _now() -> str:
    """Return the current UTC time as an ISO 8601 string with a trailing Z."""
    return datetime.utcnow().isoformat() + "Z"


@router.get("/sse/{game_id}")
async def sse_stream(game_id: str) -> EventSourceResponse:
    """Stream SSE events for the given game.

    Yields one SSE frame per engine event.  When no event arrives within
    15 seconds a ``ping`` frame is sent to keep the HF proxy connection alive.
    The stream ends when the generator exits (on disconnect or exception).
    """
    if get_game(game_id) is None:
        raise HTTPException(status_code=404, detail=f"Game {game_id!r} not found")

    async def event_generator():
        queue = get_queue(game_id)
        if queue is None:
            # Session was deleted between the guard check and now.
            return

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15.0)
                yield {
                    "event": event["type"],
                    "data": json.dumps(event["data"]),
                }
            except asyncio.TimeoutError:
                # Send a keepalive ping so the HF proxy does not close the
                # connection during idle stretches (e.g. human thinking).
                yield {
                    "event": "ping",
                    "data": json.dumps({"timestamp": _now()}),
                }
                # After a ping, verify the session still exists before looping.
                if get_queue(game_id) is None:
                    logger.debug("SSE: game %s deleted while idle — closing stream", game_id)
                    return
            except asyncio.CancelledError:
                # Client disconnected or server shutting down.
                logger.debug("SSE: stream cancelled for game %s", game_id)
                return
            except Exception:
                logger.exception("SSE: unexpected error for game %s", game_id)
                return

    return EventSourceResponse(event_generator())
