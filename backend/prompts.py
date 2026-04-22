# MIT License
# Copyright (c) 2026 Angshuman Nandy

# ── Placement ────────────────────────────────────────────────────────────────

PLACEMENT_SYSTEM = (
    "You are playing Battleship. Place your ships strategically — spread them "
    "out, avoid the edges, and don't create predictable patterns."
)

THIRD_AGENT_PLACEMENT_SYSTEM = (
    "You are a Battleship strategist hired to place ships for a player. "
    "Maximise survivability: spread ships across all quadrants, avoid clustering "
    "near edges, and vary orientations."
)


def placement_user_message(board_size: int, ships_to_place: list[tuple[str, int]]) -> str:
    ship_lines = []
    for name, length in ships_to_place:
        max_row_h = board_size - 1        # horizontal: row can be 0..board_size-1
        max_col_h = board_size - length   # horizontal: col must leave room for length
        max_row_v = board_size - length   # vertical: row must leave room for length
        max_col_v = board_size - 1        # vertical: col can be 0..board_size-1
        ship_lines.append(
            f"  - {name} (length {length}): "
            f"H → row 0–{max_row_h}, col 0–{max_col_h}  |  "
            f"V → row 0–{max_row_v}, col 0–{max_col_v}"
        )
    ships_block = "\n".join(ship_lines)
    return (
        f"You are placing ships on a {board_size}×{board_size} Battleship grid.\n\n"
        f"Grid coordinates are 0-indexed: rows 0–{board_size - 1}, "
        f"columns 0–{board_size - 1}.\n\n"
        "Orientation rules:\n"
        "  - 'H' (horizontal): the ship occupies (row, col), (row, col+1), … (row, col+length-1).\n"
        "  - 'V' (vertical):   the ship occupies (row, col), (row+1, col), … (row+length-1, col).\n\n"
        "Ships you must place — VALID starting positions shown per orientation:\n"
        f"{ships_block}\n\n"
        "Constraints:\n"
        f"  - Every cell of every ship must be within [0, {board_size - 1}].\n"
        "  - No two ships may overlap.\n\n"
        "Call the place_ships tool with your placement decisions now."
    )


# ── Shooting ─────────────────────────────────────────────────────────────────

SHOT_SYSTEM = (
    "You are playing Battleship. Fire strategically: track hit patterns to find "
    "ship orientations, eliminate impossible positions, and prioritise finishing "
    "damaged ships before searching new areas."
)


def shot_system_for_player(player_role: str) -> str:
    return (
        f"You are playing Battleship as {player_role}. "
        "Fire strategically: follow up on hits to sink ships quickly, "
        "use checkerboard patterns to find new ships, and avoid cells you've already fired at."
    )


def shot_user_message(
    board_size: int,
    own_board_desc: str,
    enemy_board_desc: str,
    move_history_section: str,
    enemy_board_view: list[list[str]] | None = None,
) -> str:
    already_fired = ""
    if enemy_board_view:
        fired = [
            f"({r},{c})"
            for r, row in enumerate(enemy_board_view)
            for c, cell in enumerate(row)
            if cell != "empty"
        ]
        if fired:
            already_fired = (
                f"ALREADY FIRED (do NOT repeat these): {', '.join(fired)}\n\n"
            )

    return (
        f"It is your turn in a {board_size}×{board_size} Battleship game.\n\n"
        f"{own_board_desc}\n\n"
        f"{enemy_board_desc}\n\n"
        f"{move_history_section}"
        f"{already_fired}"
        f"Valid coordinates: row 0–{board_size - 1}, col 0–{board_size - 1}.\n"
        "Choose a cell that has NOT been fired at yet. Call the choose_shot tool now."
    )


def format_move_history(moves) -> str:  # moves: list[Move]
    if not moves:
        return "No moves have been made yet.\n\n"
    lines = [
        f"  Turn {i + 1}: {m.player} fired at ({m.row}, {m.col}) → {m.result}"
        + (f" [{m.ship_sunk} sunk]" if m.ship_sunk else "")
        for i, m in enumerate(moves)
    ]
    return f"Full move history ({len(moves)} turns):\n" + "\n".join(lines) + "\n\n"


def shot_retry_message(attempt: int, board_size: int, error: Exception) -> str:
    return (
        f"Your previous shot was invalid (attempt {attempt}/3): {error}. "
        f"row and col must both be in [0, {board_size - 1}]. "
        "Call the choose_shot tool again with a corrected answer."
    )
