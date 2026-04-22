"""
engine.py — Core game engine for LLM Battleships.

Drives the placement phase and the turn loop.  Runs as a background
asyncio.Task launched by POST /api/game/{id}/start.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from .board import apply_placement, apply_shot, all_ships_sunk, random_placement, validate_placement
from .models import (
    CellState,
    GamePhase,
    GameState,
    Move,
    PlacementMode,
    PlayerRole,
    PlayerState,
)
from .session_store import (
    enqueue_event,
    get_game,
    get_human_event,
    get_pause_event,
    get_placement_event,
    set_game,
)
from ..config import get_fleet, TURN_DELAY_SECONDS
from ..llm.factory import LLMWrapperFactory
from ..prompts import PLACEMENT_SYSTEM, THIRD_AGENT_PLACEMENT_SYSTEM, shot_system_for_player

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> str:
    """Return the current UTC time as an ISO 8601 string with a trailing Z."""
    return datetime.utcnow().isoformat() + "Z"


def _is_player1(role) -> bool:
    """Return True when *role* refers to player1 regardless of whether it is
    a :class:`PlayerRole` enum member or a plain string."""
    return role in (PlayerRole.player1, PlayerRole.player1.value, "player1")


# ---------------------------------------------------------------------------
# GameEngine
# ---------------------------------------------------------------------------


class GameEngine:
    """Manages the full lifecycle of a single Battleship game."""

    def __init__(self, game_id: str) -> None:
        self._game_id = game_id

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def start_game(self) -> None:
        """Main entry point.  Called as ``asyncio.create_task(engine.start_game())``.

        Runs the placement phase then the turn loop.  Any unhandled exception
        is caught, an ``error`` SSE event is emitted, and the exception is
        re-raised so the task's exception is preserved.
        """
        try:
            game = get_game(self._game_id)
            if game is None:
                logger.error("start_game: game %s not found", self._game_id)
                return

            fleet = get_fleet(game.board_size)

            # ── Placement phase ──────────────────────────────────────
            game.phase = GamePhase.placement
            set_game(self._game_id, game)

            await self._placement_phase(game, fleet)

            # ── In-progress phase ────────────────────────────────────
            game = get_game(self._game_id)
            game.phase = GamePhase.in_progress
            set_game(self._game_id, game)

            # ── Turn loop ────────────────────────────────────────────
            await self._turn_loop(fleet)

        except asyncio.CancelledError:
            # Game was deleted — propagate without emitting an error event.
            raise

        except Exception as exc:
            logger.exception("Unhandled error in game %s", self._game_id)
            await enqueue_event(self._game_id, "error", {
                "message": str(exc),
                "player": None,
                "retrying": False,
            })
            raise

    # ------------------------------------------------------------------
    # Placement phase
    # ------------------------------------------------------------------

    async def _placement_phase(self, game: GameState, fleet) -> None:
        """Run both players' placement concurrently, then emit all_placements_done."""
        await asyncio.gather(
            self._resolve_placement(game, game.player1, fleet),
            self._resolve_placement(game, game.player2, fleet),
        )

        # Re-fetch to get a consistent snapshot after both coroutines wrote.
        await enqueue_event(self._game_id, "all_placements_done", {
            "timestamp": _now(),
        })

    async def _resolve_placement(
        self,
        game: GameState,
        player: PlayerState,
        fleet,
    ) -> None:
        """Resolve the placement for a single player according to their PlacementMode."""
        mode = player.placement_config.mode
        role_value = player.role if isinstance(player.role, str) else player.role.value

        await enqueue_event(self._game_id, "placement_started", {
            "player": role_value,
            "mode": mode if isinstance(mode, str) else mode.value,
            "timestamp": _now(),
        })

        # ── Human placement ──────────────────────────────────────────
        if mode == PlacementMode.human:
            await enqueue_event(self._game_id, "awaiting_human_placement", {
                "player": role_value,
            })

            # Wait for POST /place/{player} to set the board and signal the event.
            event = get_placement_event(self._game_id, role_value)
            if event is None:
                raise RuntimeError(
                    f"Placement event missing for game {self._game_id} player {role_value}"
                )
            await event.wait()

            # The API route has already written the validated board into game state.
            await enqueue_event(self._game_id, "placement_done", {
                "player": role_value,
                "timestamp": _now(),
            })
            return

        # ── All non-human modes ──────────────────────────────────────
        ships = None

        if mode == PlacementMode.random:
            ships = random_placement(game.board_size, fleet)

        elif mode in (PlacementMode.llm, PlacementMode.third_agent):
            if mode == PlacementMode.llm:
                llm = LLMWrapperFactory.create(player.llm_config)
                base_system = PLACEMENT_SYSTEM
            else:
                llm = LLMWrapperFactory.create(player.placement_config.agent_config)
                base_system = THIRD_AGENT_PLACEMENT_SYSTEM

            ships = None
            last_placement_error = ""
            max_placement_attempts = 3
            for attempt in range(1, max_placement_attempts + 1):
                # On retries, append the previous error to the system prompt so
                # the model knows what constraint it violated.
                if attempt == 1:
                    system_prompt = base_system
                else:
                    system_prompt = (
                        f"{base_system}\n\nPREVIOUS ATTEMPT FAILED: {last_placement_error} "
                        f"All ships must fit entirely within rows 0–{game.board_size - 1} "
                        f"and cols 0–{game.board_size - 1}. No overlaps."
                    )

                result = await llm.place_ships(game.board_size, fleet, system_prompt)
                valid, last_placement_error = validate_placement(
                    game.board_size, result.ships, fleet
                )
                if valid:
                    ships = result.ships
                    break
                logger.warning(
                    "LLM placement invalid (attempt %d/%d) for %s: %s",
                    attempt, max_placement_attempts, role_value, last_placement_error,
                )

            if ships is None:
                raise ValueError(
                    f"LLM failed to produce a valid placement for {role_value} after "
                    f"{max_placement_attempts} attempts. Last error: {last_placement_error}"
                )

        else:
            raise ValueError(f"Unknown PlacementMode: {mode!r}")

        # Build board and an empty shots grid for this player.
        board = apply_placement(game.board_size, ships, fleet)
        shots_grid: list[list[CellState]] = [
            [CellState.empty] * game.board_size for _ in range(game.board_size)
        ]

        # Re-fetch game to avoid clobbering the other player's concurrent write.
        current_game = get_game(self._game_id)
        if _is_player1(player.role):
            current_game.player1.board = board
            current_game.player1.shots_grid = shots_grid
        else:
            current_game.player2.board = board
            current_game.player2.shots_grid = shots_grid
        set_game(self._game_id, current_game)

        await enqueue_event(self._game_id, "placement_done", {
            "player": role_value,
            "timestamp": _now(),
        })

    # ------------------------------------------------------------------
    # Turn loop
    # ------------------------------------------------------------------

    async def _turn_loop(self, fleet) -> None:
        """Main game loop.  Alternates between players until one wins."""
        turn_number = 0

        while True:
            game = get_game(self._game_id)
            is_p1_turn = _is_player1(game.current_turn)
            current_player: PlayerState = game.player1 if is_p1_turn else game.player2
            opponent: PlayerState = game.player2 if is_p1_turn else game.player1

            turn_number += 1
            role_value = (
                current_player.role
                if isinstance(current_player.role, str)
                else current_player.role.value
            )

            await enqueue_event(self._game_id, "turn_start", {
                "player": role_value,
                "turn_number": turn_number,
            })

            # ── Human turn ───────────────────────────────────────────
            if current_player.is_human:
                human_event = get_human_event(self._game_id)
                if human_event is None:
                    raise RuntimeError(
                        f"Human event missing for game {self._game_id}"
                    )

                # Clear before waiting so we don't consume a stale signal.
                human_event.clear()
                await human_event.wait()

                # POST /fire has already applied the shot and appended the Move.
                # Also check win condition using the freshly updated board.
                game = get_game(self._game_id)
                is_p1_turn = _is_player1(game.current_turn)
                opponent = game.player2 if is_p1_turn else game.player1

                if all_ships_sunk(opponent.board, fleet):
                    await self._finish_game(game, game.current_turn, turn_number)
                    return

                # Flip turn.
                game.current_turn = (
                    PlayerRole.player2 if is_p1_turn else PlayerRole.player1
                )
                set_game(self._game_id, game)
                continue

            # ── LLM turn ─────────────────────────────────────────────
            # Block here if the game has been paused.
            pause_event = get_pause_event(self._game_id)
            if pause_event is not None:
                await pause_event.wait()

            try:
                llm = LLMWrapperFactory.create(current_player.llm_config)
                system_prompt = shot_system_for_player(role_value)
                # Pass the player's shots_grid as their view of the enemy board.
                enemy_board_view = current_player.shots_grid

                shot_result = await llm.choose_shot(
                    game.board_size,
                    current_player.board,
                    enemy_board_view,
                    game.moves,
                    system_prompt,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception(
                    "LLM choose_shot failed for player %s in game %s",
                    role_value,
                    self._game_id,
                )
                await enqueue_event(self._game_id, "error", {
                    "message": str(exc),
                    "player": role_value,
                    "retrying": False,
                })
                raise

            row, col = shot_result.row, shot_result.col
            reasoning: Optional[str] = shot_result.reasoning

            # Re-fetch game state for a fresh view before mutating.
            game = get_game(self._game_id)
            is_p1_turn = _is_player1(game.current_turn)
            current_player = game.player1 if is_p1_turn else game.player2
            opponent = game.player2 if is_p1_turn else game.player1

            # apply_shot mutates opponent.board and current_player.shots_grid in place.
            result, sunk_ship = apply_shot(
                opponent.board,
                current_player.shots_grid,
                row,
                col,
                fleet,
            )

            move = Move(
                player=current_player.role,
                row=row,
                col=col,
                result=result,
                ship_sunk=sunk_ship,
                reasoning=reasoning,
            )
            game.moves.append(move)
            set_game(self._game_id, game)

            result_value = result if isinstance(result, str) else result.value
            await enqueue_event(self._game_id, "shot_fired", {
                "player": role_value,
                "row": row,
                "col": col,
                "result": result_value,
                "ship_sunk": sunk_ship,
                "reasoning": reasoning,
                "turn_number": turn_number,
            })

            # Check win condition with the freshly mutated board.
            game = get_game(self._game_id)
            is_p1_turn = _is_player1(game.current_turn)
            opponent = game.player2 if is_p1_turn else game.player1

            if all_ships_sunk(opponent.board, fleet):
                await self._finish_game(game, game.current_turn, turn_number)
                return

            # Flip turn.
            game.current_turn = (
                PlayerRole.player2 if is_p1_turn else PlayerRole.player1
            )
            set_game(self._game_id, game)

            await asyncio.sleep(TURN_DELAY_SECONDS)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _finish_game(
        self,
        game: GameState,
        winner_role,
        total_turns: int,
    ) -> None:
        """Mark the game as finished and emit game_over."""
        game.phase = GamePhase.finished
        game.winner = (
            winner_role
            if isinstance(winner_role, PlayerRole)
            else PlayerRole(winner_role)
        )
        set_game(self._game_id, game)

        winner_value = (
            winner_role if isinstance(winner_role, str) else winner_role.value
        )

        await enqueue_event(self._game_id, "game_over", {
            "winner": winner_value,
            "total_turns": total_turns,
            "player1_ships": len(game.player1.board.ships) if game.player1.board else 0,
            "player2_ships": len(game.player2.board.ships) if game.player2.board else 0,
        })
