"""
board.py — Grid logic and ship placement validation for LLM Battleships.

All functions operate on BoardState / PlacedShip models from models.py.
Fleet data is always passed as a parameter; this module has no config import.
"""

from __future__ import annotations

import random
from collections import Counter
from typing import Optional

from .models import BoardState, CellState, PlacedShip


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_ship_cells(ship: PlacedShip, length: int) -> list[tuple[int, int]]:
    """Return all (row, col) tuples occupied by *ship* given its *length*."""
    cells: list[tuple[int, int]] = []
    for i in range(length):
        if ship.orientation == "H":
            cells.append((ship.row, ship.col + i))
        else:  # "V"
            cells.append((ship.row + i, ship.col))
    return cells


def _empty_grid(size: int) -> list[list[CellState]]:
    return [[CellState.empty] * size for _ in range(size)]


# ---------------------------------------------------------------------------
# Board construction
# ---------------------------------------------------------------------------


def create_empty_board(size: int) -> BoardState:
    """Return a BoardState with every cell set to CellState.empty."""
    return BoardState(size=size, grid=_empty_grid(size), ships=[])


def apply_placement(
    board_size: int,
    ships: list[PlacedShip],
    fleet: list[tuple[str, int]],
) -> BoardState:
    """Build a BoardState from validated ships.

    Sets CellState.ship for every cell occupied by a ship.  The caller is
    responsible for ensuring the placement is valid (call validate_placement
    first).  *fleet* is required to resolve ship lengths.
    """
    length_map: dict[str, int] = dict(fleet)
    grid = _empty_grid(board_size)

    for ship in ships:
        length = length_map.get(ship.ship_type, 0)
        for r, c in get_ship_cells(ship, length):
            grid[r][c] = CellState.ship

    return BoardState(size=board_size, grid=grid, ships=list(ships))


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_placement(
    board_size: int,
    ships: list[PlacedShip],
    fleet: list[tuple[str, int]],
) -> tuple[bool, str]:
    """Validate a proposed ship placement against the required fleet.

    Checks (in order):
    1. All required ship types are present with the correct count.
    2. Every ship fits within board bounds.
    3. No two ships overlap.

    Returns (True, "") on success, or (False, <error message>) on failure.
    """
    required: Counter[str] = Counter(ship_type for ship_type, _ in fleet)
    length_map: dict[str, int] = dict(fleet)
    provided: Counter[str] = Counter(ship.ship_type for ship in ships)

    # 1. Fleet composition check
    if provided != required:
        missing = {k: v for k, v in required.items() if provided[k] < v}
        extra = {k: provided[k] for k in provided if provided[k] > required.get(k, 0)}
        parts: list[str] = []
        if missing:
            parts.append(f"missing {missing}")
        if extra:
            parts.append(f"unexpected extra {extra}")
        return False, f"Fleet mismatch: {'; '.join(parts)}."

    # 2. Bounds + orientation check; accumulate occupied cells
    occupied: set[tuple[int, int]] = set()

    for ship in ships:
        length = length_map.get(ship.ship_type)
        if length is None:
            return False, f"Unknown ship type '{ship.ship_type}'."

        if ship.orientation not in ("H", "V"):
            return False, (
                f"Ship '{ship.ship_type}' has invalid orientation "
                f"'{ship.orientation}' (expected 'H' or 'V')."
            )

        cells = get_ship_cells(ship, length)

        for r, c in cells:
            if not (0 <= r < board_size and 0 <= c < board_size):
                return False, (
                    f"Ship '{ship.ship_type}' at ({ship.row},{ship.col}) "
                    f"orientation={ship.orientation} extends out of bounds "
                    f"(board is {board_size}×{board_size})."
                )

        # 3. Overlap check
        for r, c in cells:
            if (r, c) in occupied:
                return False, (
                    f"Ship '{ship.ship_type}' at ({ship.row},{ship.col}) "
                    f"overlaps with another ship."
                )
            occupied.add((r, c))

    return True, ""


# ---------------------------------------------------------------------------
# Random placement
# ---------------------------------------------------------------------------


def random_placement(
    board_size: int,
    fleet: list[tuple[str, int]],
) -> list[PlacedShip]:
    """Generate a valid random placement for all ships in *fleet*.

    Shuffles orientations and candidate positions to avoid bias.  Ships are
    placed one at a time; the function retries the entire layout from scratch
    on the rare occasion that no position can be found for a later ship.
    """
    while True:
        occupied: set[tuple[int, int]] = set()
        placed: list[PlacedShip] = []
        failed = False

        for ship_type, length in fleet:
            orientations = ["H", "V"]
            random.shuffle(orientations)

            # Build and shuffle all candidate (orientation, row, col) triples
            candidates: list[tuple[str, int, int]] = []
            for orientation in orientations:
                if orientation == "H":
                    row_range = range(board_size)
                    col_range = range(board_size - length + 1)
                else:
                    row_range = range(board_size - length + 1)
                    col_range = range(board_size)
                positions = [(r, c) for r in row_range for c in col_range]
                random.shuffle(positions)
                candidates.extend((orientation, r, c) for r, c in positions)

            # Try each candidate until one fits without overlap
            ship_placed = False
            for orientation, r, c in candidates:
                ship = PlacedShip(
                    ship_type=ship_type, row=r, col=c, orientation=orientation
                )
                cells = get_ship_cells(ship, length)
                if not any(cell in occupied for cell in cells):
                    occupied.update(cells)
                    placed.append(ship)
                    ship_placed = True
                    break

            if not ship_placed:
                failed = True
                break

        if not failed:
            return placed
        # Very rare: board too crowded with previous choices — retry entire layout


# ---------------------------------------------------------------------------
# Shot application
# ---------------------------------------------------------------------------


def apply_shot(
    board: BoardState,
    shots_grid: list[list[CellState]],
    row: int,
    col: int,
    fleet: list[tuple[str, int]],
) -> tuple[CellState, Optional[str]]:
    """Apply a shot at (row, col), mutating *board* and *shots_grid* in place.

    Returns (result_cell_state, sunk_ship_type_or_None).

    Rules:
    - Already-resolved cells (hit/miss/sunk) are returned as-is without
      double-counting hits.
    - A hit on a ship that becomes fully sunk marks *all* of that ship's cells
      as CellState.sunk in both grids and returns (CellState.sunk, ship_type).
    - A hit on a ship not yet sunk returns (CellState.hit, None).
    - A shot on an empty cell returns (CellState.miss, None).
    """
    length_map: dict[str, int] = dict(fleet)
    current = board.grid[row][col]

    # Already resolved — do not double-count
    if current in (CellState.hit, CellState.miss, CellState.sunk):
        return current, None

    if current == CellState.ship:
        # Identify which ship occupies this cell
        hit_ship: Optional[PlacedShip] = None
        hit_index: int = 0
        for ship in board.ships:
            length = length_map.get(ship.ship_type, 0)
            cells = get_ship_cells(ship, length)
            if (row, col) in cells:
                hit_index = cells.index((row, col))
                hit_ship = ship
                break

        if hit_ship is None:
            # Defensive: grid says ship but no PlacedShip matches — treat as hit
            board.grid[row][col] = CellState.hit
            shots_grid[row][col] = CellState.hit
            return CellState.hit, None

        # Record the hit index (position along ship length) if not already recorded
        if hit_index not in hit_ship.hits:
            hit_ship.hits.append(hit_index)

        length = length_map[hit_ship.ship_type]

        if hit_ship.is_sunk(length):
            # Mark every cell of the sunk ship in both grids
            for r, c in get_ship_cells(hit_ship, length):
                board.grid[r][c] = CellState.sunk
                shots_grid[r][c] = CellState.sunk
            return CellState.sunk, hit_ship.ship_type
        else:
            board.grid[row][col] = CellState.hit
            shots_grid[row][col] = CellState.hit
            return CellState.hit, None

    else:  # CellState.empty
        board.grid[row][col] = CellState.miss
        shots_grid[row][col] = CellState.miss
        return CellState.miss, None


# ---------------------------------------------------------------------------
# Win condition
# ---------------------------------------------------------------------------


def all_ships_sunk(board: BoardState, fleet: list[tuple[str, int]]) -> bool:
    """Return True when every ship on *board* is fully sunk."""
    length_map: dict[str, int] = dict(fleet)
    for ship in board.ships:
        length = length_map.get(ship.ship_type, 0)
        if not ship.is_sunk(length):
            return False
    return True
