from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from ..game.models import BoardState, Move, PlacedShip


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class PlacementResult:
    ships: list[PlacedShip]
    reasoning: Optional[str] = None


@dataclass
class ShotResult:
    row: int
    col: int
    reasoning: Optional[str] = None


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class LLMCapabilityError(Exception):
    """Raised when a model does not support a required capability (e.g. tool use)."""


# ---------------------------------------------------------------------------
# Abstract base wrapper
# ---------------------------------------------------------------------------


class LLMWrapper(ABC):
    """Common interface for all LLM provider wrappers.

    Every concrete subclass must implement :meth:`place_ships` and
    :meth:`choose_shot` using forced tool-use so that responses are always
    structured — never free-text that requires ad-hoc parsing.
    """

    @abstractmethod
    async def place_ships(
        self,
        board_size: int,
        ships_to_place: list[tuple[str, int]],  # [(ship_type, length), ...]
        system_prompt: str,
    ) -> PlacementResult:
        """Ask the LLM to place all ships on an empty board.

        Args:
            board_size: Side length of the square grid (e.g. 10 for a 10×10 board).
            ships_to_place: Ordered list of (ship_type, length) pairs the model
                must place.  The model must place *every* ship in the list.
            system_prompt: Caller-supplied persona / strategy instructions.

        Returns:
            :class:`PlacementResult` with validated ship placements.
        """
        ...

    @abstractmethod
    async def choose_shot(
        self,
        board_size: int,
        own_board: BoardState,
        enemy_board_view: list[list[str]],  # grid of CellState values (attacker's view)
        move_history: list[Move],
        system_prompt: str,
    ) -> ShotResult:
        """Ask the LLM to pick a cell to fire at.

        Args:
            board_size: Side length of the square grid.
            own_board: The attacker's own :class:`BoardState` (shows own ships and
                any hits received).
            enemy_board_view: The attacker's view of the enemy board — a 2-D list
                of :class:`~backend.game.models.CellState` string values.  Ship
                cells that have not been hit yet appear as ``"empty"`` (hidden).
            move_history: All moves made so far in the game, ordered oldest-first.
            system_prompt: Caller-supplied persona / strategy instructions.

        Returns:
            :class:`ShotResult` with the chosen (row, col) and optional reasoning.
        """
        ...

    # ------------------------------------------------------------------
    # Shared tool definitions — identical schema for every provider
    # ------------------------------------------------------------------

    PLACE_SHIPS_TOOL: dict = {
        "name": "place_ships",
        "description": (
            "Place all ships on the board. "
            "Each ship must be fully within bounds and must not overlap any other ship."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "placements": {
                    "type": "array",
                    "description": "One entry per ship — must include every ship that was listed.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "ship_type": {
                                "type": "string",
                                "description": "Exact ship type name as provided (e.g. 'Destroyer').",
                            },
                            "row": {
                                "type": "integer",
                                "description": "0-indexed row of the ship's top-left cell.",
                            },
                            "col": {
                                "type": "integer",
                                "description": "0-indexed column of the ship's top-left cell.",
                            },
                            "orientation": {
                                "type": "string",
                                "enum": ["H", "V"],
                                "description": (
                                    "'H' places the ship horizontally (extends rightward); "
                                    "'V' places it vertically (extends downward)."
                                ),
                            },
                        },
                        "required": ["ship_type", "row", "col", "orientation"],
                    },
                }
            },
            "required": ["placements"],
        },
    }

    CHOOSE_SHOT_TOOL: dict = {
        "name": "choose_shot",
        "description": "Choose a cell to fire at on the enemy board.",
        "input_schema": {
            "type": "object",
            "properties": {
                "row": {
                    "type": "integer",
                    "description": "0-indexed row to fire at.",
                },
                "col": {
                    "type": "integer",
                    "description": "0-indexed column to fire at.",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Brief explanation of why this cell was chosen.",
                },
            },
            "required": ["row", "col"],
        },
    }


# ---------------------------------------------------------------------------
# Shared prompt-building helpers
# ---------------------------------------------------------------------------


def _build_board_description(grid: list[list[str]], label: str) -> str:
    """Render a board grid as a human-readable string for inclusion in LLM prompts.

    Args:
        grid: 2-D list of :class:`~backend.game.models.CellState` string values,
            where ``grid[row][col]`` is the state of that cell.
        label: A short title printed as the header (e.g. ``"Your board"``).

    Returns:
        A multi-line string with a header followed by one labelled row per line::

            Your board (5×5):
            Row 0: [empty, empty, ship, ship, empty]
            Row 1: [empty, hit,   miss, empty, empty]
            ...
    """
    if not grid:
        return f"{label} (empty)\n"

    n_rows = len(grid)
    n_cols = len(grid[0]) if n_rows else 0
    lines: list[str] = [f"{label} ({n_rows}×{n_cols}):"]

    for row_idx, row in enumerate(grid):
        cells = ", ".join(str(cell) for cell in row)
        lines.append(f"  Row {row_idx}: [{cells}]")

    return "\n".join(lines)
