# MIT License
# Copyright (c) 2026 Angshuman Nandy

"""
deps.py — FastAPI dependencies shared across route modules.
"""

from fastapi import HTTPException

from ..game.session_store import get_game
from ..game.models import GameState


def get_game_or_404(game_id: str) -> GameState:
    """Return the GameState for *game_id*, or raise HTTP 404 if it does not exist."""
    game = get_game(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail=f"Game {game_id!r} not found")
    return game
