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
    ship_lines = "\n".join(f"  - {t} (length {l})" for t, l in ships_to_place)
    return (
        f"You are placing ships on a {board_size}×{board_size} Battleship grid.\n\n"
        f"Grid coordinates are 0-indexed: rows 0–{board_size - 1}, "
        f"columns 0–{board_size - 1}.\n\n"
        "Orientation rules:\n"
        "  - 'H' (horizontal): the ship extends rightward from (row, col).\n"
        "  - 'V' (vertical):   the ship extends downward  from (row, col).\n\n"
        f"Ships you must place (every one is required):\n{ship_lines}\n\n"
        f"Constraints:\n"
        f"  - All cells must be within [0, {board_size - 1}].\n"
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
) -> str:
    return (
        f"It is your turn in a {board_size}×{board_size} Battleship game.\n\n"
        f"{own_board_desc}\n\n"
        f"{enemy_board_desc}\n\n"
        f"{move_history_section}"
        f"Valid coordinates: row 0–{board_size - 1}, col 0–{board_size - 1}.\n"
        "Choose a cell to fire at. Call the choose_shot tool now."
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
