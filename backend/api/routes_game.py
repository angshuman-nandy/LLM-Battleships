"""
routes_game.py — REST endpoints for LLM Battleships game management.

Endpoints
---------
POST   /api/game/create                — create a new game session
POST   /api/game/{game_id}/start       — launch the background game engine task
POST   /api/game/{game_id}/place/{player} — submit human ship placements
POST   /api/game/{game_id}/fire        — human fires a shot
GET    /api/game/{game_id}/state       — sanitized game snapshot
DELETE /api/game/{game_id}             — cancel and clean up a game
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException

from ..config import get_fleet
from ..game.board import all_ships_sunk, apply_placement, apply_shot, validate_placement
from ..game.engine import GameEngine
from ..game.models import (
    BoardState,
    CellState,
    CreateGameRequest,
    FireRequest,
    GameMode,
    GamePhase,
    GameState,
    GameStatusResponse,
    HumanPlacementRequest,
    Move,
    PlacementConfig,
    PlacementMode,
    PlayerRole,
    PlayerState,
)
from ..game.session_store import (
    create_session,
    delete_session,
    enqueue_event,
    get_game,
    get_human_event,
    get_placement_event,
    set_game,
    set_task,
)
from .deps import get_game_or_404

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/game")


def _now() -> str:
    """Return the current UTC time as an ISO 8601 string with a trailing Z."""
    return datetime.utcnow().isoformat() + "Z"


# ---------------------------------------------------------------------------
# POST /api/game/create
# ---------------------------------------------------------------------------


@router.post("/create")
async def create_game(request: CreateGameRequest) -> dict[str, str]:
    """Create a new game session and return its ID.

    For *llm_vs_llm* games both player configs are required.  For
    *human_vs_llm* games the human (player 1) does not need an LLM config.
    """
    # Validate configuration completeness.
    if request.mode == GameMode.llm_vs_llm and request.player2_config is None:
        raise HTTPException(
            status_code=400,
            detail="player2_config is required for llm_vs_llm mode.",
        )

    game_id = str(uuid.uuid4())

    # Determine whether player 1 is a human.
    p1_is_human = request.mode == GameMode.human_vs_llm

    player1 = PlayerState(
        role=PlayerRole.player1,
        is_human=p1_is_human,
        llm_config=request.player1_config,
        placement_config=request.player1_placement,
    )

    player2 = PlayerState(
        role=PlayerRole.player2,
        is_human=False,
        llm_config=request.player2_config,
        placement_config=request.player2_placement,
    )

    game = GameState(
        game_id=game_id,
        mode=request.mode,
        phase=GamePhase.setup,
        board_size=request.board_size,
        player1=player1,
        player2=player2,
    )

    create_session(game_id, game)
    logger.info("Created game %s mode=%s board=%d", game_id, request.mode, request.board_size)

    return {"game_id": game_id}


# ---------------------------------------------------------------------------
# POST /api/game/{game_id}/start
# ---------------------------------------------------------------------------


@router.post("/{game_id}/start")
async def start_game(game_id: str) -> dict[str, str]:
    """Transition the game from *setup* to *placement* and launch the engine task.

    The engine runs as a background ``asyncio.Task`` so this endpoint returns
    immediately without blocking the event loop.
    """
    game = get_game_or_404(game_id)

    if game.phase != GamePhase.setup:
        raise HTTPException(
            status_code=400,
            detail=f"Game is in phase '{game.phase}'; can only start from 'setup'.",
        )

    # Advance phase before spawning the task so the engine sees placement.
    game.phase = GamePhase.placement
    set_game(game_id, game)

    engine = GameEngine(game_id)
    task = asyncio.create_task(engine.start_game(), name=f"game-{game_id}")
    set_task(game_id, task)

    logger.info("Started game %s", game_id)
    return {"status": "started", "game_id": game_id}


# ---------------------------------------------------------------------------
# POST /api/game/{game_id}/place/{player}
# ---------------------------------------------------------------------------


@router.post("/{game_id}/place/{player}")
async def place_ships(
    game_id: str,
    player: str,
    request: HumanPlacementRequest,
) -> dict[str, str]:
    """Accept and validate a human player's ship placements.

    The *player* path parameter must be ``"player1"`` or ``"player2"``.
    After successful validation the engine's placement event is set so
    :py:meth:`GameEngine._resolve_placement` can proceed.
    """
    # Validate the player path parameter.
    try:
        player_role = PlayerRole(player)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid player '{player}'. Must be 'player1' or 'player2'.",
        )

    game = get_game_or_404(game_id)

    if game.phase != GamePhase.placement:
        raise HTTPException(
            status_code=400,
            detail=f"Game is in phase '{game.phase}'; ship placement is only allowed during 'placement'.",
        )

    # Resolve the target PlayerState.
    player_state: PlayerState = (
        game.player1 if player_role == PlayerRole.player1 else game.player2
    )

    # Only players configured for human placement may submit via this endpoint.
    placement_mode = player_state.placement_config.mode
    if placement_mode != PlacementMode.human:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Player '{player}' has placement mode '{placement_mode}', "
                "not 'human'. This endpoint is only for human placements."
            ),
        )

    fleet = get_fleet(game.board_size)

    # Validate the proposed placement.
    valid, error_msg = validate_placement(game.board_size, request.placements, fleet)
    if not valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # Build board and initialise an empty shots grid.
    board: BoardState = apply_placement(game.board_size, request.placements, fleet)
    shots_grid: list[list[CellState]] = [
        [CellState.empty] * game.board_size for _ in range(game.board_size)
    ]

    # Re-fetch for a fresh snapshot to avoid clobbering concurrent writes.
    game = get_game_or_404(game_id)
    if player_role == PlayerRole.player1:
        game.player1.board = board
        game.player1.shots_grid = shots_grid
    else:
        game.player2.board = board
        game.player2.shots_grid = shots_grid

    set_game(game_id, game)

    # Signal the engine that this player's placement is done.
    event = get_placement_event(game_id, player_role.value)
    if event is None:
        raise HTTPException(
            status_code=500,
            detail="Internal error: placement event not found.",
        )
    event.set()

    logger.info("Human placement received for game %s player %s", game_id, player)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /api/game/{game_id}/fire
# ---------------------------------------------------------------------------


@router.post("/{game_id}/fire")
async def fire(game_id: str, request: FireRequest) -> dict[str, Any]:
    """Accept a human player's shot during the *in_progress* phase.

    Validates the shot, applies it, emits the ``shot_fired`` SSE event, and
    signals the engine to continue the turn loop.  Win detection is also
    performed here so the engine can emit ``game_over`` immediately after.
    """
    game = get_game_or_404(game_id)

    if game.phase != GamePhase.in_progress:
        raise HTTPException(
            status_code=400,
            detail=f"Game is in phase '{game.phase}'; firing is only allowed during 'in_progress'.",
        )

    # Determine which player is the human and confirm it's their turn.
    is_p1_turn = game.current_turn in (PlayerRole.player1, PlayerRole.player1.value, "player1")
    current_player: PlayerState = game.player1 if is_p1_turn else game.player2
    opponent: PlayerState = game.player2 if is_p1_turn else game.player1

    if not current_player.is_human:
        raise HTTPException(status_code=400, detail="Not human's turn.")

    row, col = request.row, request.col

    # Bounds check.
    if not (0 <= row < game.board_size and 0 <= col < game.board_size):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Coordinates ({row}, {col}) are out of bounds for a "
                f"{game.board_size}×{game.board_size} board."
            ),
        )

    # Duplicate-fire check: cell must still be empty in the shots grid.
    if current_player.shots_grid is None:
        raise HTTPException(status_code=400, detail="Player board not initialised.")

    if current_player.shots_grid[row][col] != CellState.empty:
        raise HTTPException(
            status_code=400,
            detail=f"Cell ({row}, {col}) has already been fired at.",
        )

    if opponent.board is None:
        raise HTTPException(status_code=500, detail="Opponent board not initialised.")

    fleet = get_fleet(game.board_size)

    # Apply the shot — mutates opponent.board and current_player.shots_grid in place.
    result, sunk_ship = apply_shot(
        opponent.board,
        current_player.shots_grid,
        row,
        col,
        fleet,
    )

    role_value = (
        current_player.role
        if isinstance(current_player.role, str)
        else current_player.role.value
    )
    result_value = result if isinstance(result, str) else result.value

    move = Move(
        player=current_player.role,
        row=row,
        col=col,
        result=result,
        ship_sunk=sunk_ship,
        reasoning=None,
    )
    game.moves.append(move)
    set_game(game_id, game)

    # Emit the shot_fired SSE event so the frontend updates immediately.
    await enqueue_event(game_id, "shot_fired", {
        "player": role_value,
        "row": row,
        "col": col,
        "result": result_value,
        "ship_sunk": sunk_ship,
        "reasoning": None,
        "turn_number": len(game.moves),
    })

    # Check win condition.
    if all_ships_sunk(opponent.board, fleet):
        game = get_game_or_404(game_id)
        game.phase = GamePhase.finished
        game.winner = current_player.role
        set_game(game_id, game)

        winner_value = (
            current_player.role
            if isinstance(current_player.role, str)
            else current_player.role.value
        )
        await enqueue_event(game_id, "game_over", {
            "winner": winner_value,
            "total_turns": len(game.moves),
            "player1_ships": len(game.player1.board.ships) if game.player1.board else 0,
            "player2_ships": len(game.player2.board.ships) if game.player2.board else 0,
        })

        logger.info("Game %s finished — winner: %s", game_id, winner_value)
        return {"result": result_value, "ship_sunk": sunk_ship}

    # Game continues — signal the engine to proceed with the next turn.
    # The engine clears the event before awaiting it; we set it here.
    human_event = get_human_event(game_id)
    if human_event is not None:
        human_event.set()

    return {"result": result_value, "ship_sunk": sunk_ship}


# ---------------------------------------------------------------------------
# GET /api/game/{game_id}/state
# ---------------------------------------------------------------------------


@router.get("/{game_id}/state")
async def get_state(game_id: str) -> GameStatusResponse:
    """Return a sanitized snapshot of the game state.

    - llm_vs_llm: all ships visible (spectator can watch both boards)
    - human_vs_llm: human's own ships visible, enemy LLM ships hidden
    """
    game = get_game_or_404(game_id)
    if game.mode == GameMode.human_vs_llm:
        return GameStatusResponse.from_game_state(game, requesting_role=PlayerRole.player1)
    return GameStatusResponse.from_game_state(game, requesting_role=None)


# ---------------------------------------------------------------------------
# DELETE /api/game/{game_id}
# ---------------------------------------------------------------------------


@router.delete("/{game_id}")
async def delete_game(game_id: str) -> dict[str, str]:
    """Cancel the background task and remove all state for the given game."""
    if get_game(game_id) is None:
        raise HTTPException(status_code=404, detail=f"Game {game_id!r} not found")

    delete_session(game_id)
    logger.info("Deleted game %s", game_id)
    return {"status": "deleted"}
