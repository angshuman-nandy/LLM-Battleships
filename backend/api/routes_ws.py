# MIT License
# Copyright (c) 2026 Angshuman Nandy

"""
routes_ws.py — WebSocket streaming endpoint for LLM Battleships.

Clients connect to WS /ws/{game_id} and receive a stream of JSON-encoded
game events emitted by the game engine.  A 15-second keepalive ping is sent
whenever no event arrives, preventing proxy timeouts during idle stretches.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..game.session_store import get_game, get_queue

logger = logging.getLogger(__name__)

router = APIRouter()


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


@router.websocket("/ws/{game_id}")
async def ws_stream(websocket: WebSocket, game_id: str) -> None:
    """Stream game events over WebSocket for the given game.

    Sends one JSON message per engine event.  When no event arrives within
    15 seconds a ``ping`` message is sent to keep proxy connections alive.
    """
    if get_game(game_id) is None:
        await websocket.close(code=1008)
        return

    await websocket.accept()

    queue = get_queue(game_id)
    if queue is None:
        await websocket.close(code=1008)
        return

    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=15.0)
            await websocket.send_json({"type": event["type"], "data": event["data"]})
        except asyncio.TimeoutError:
            await websocket.send_json({"type": "ping", "data": {"timestamp": _now()}})
            if get_queue(game_id) is None:
                logger.debug("WS: game %s deleted while idle — closing", game_id)
                await websocket.close()
                return
        except WebSocketDisconnect:
            logger.debug("WS: client disconnected for game %s", game_id)
            return
        except asyncio.CancelledError:
            logger.debug("WS: stream cancelled for game %s", game_id)
            return
        except Exception:
            logger.exception("WS: unexpected error for game %s", game_id)
            return
