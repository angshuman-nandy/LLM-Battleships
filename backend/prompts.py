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
    "You are playing Battleship. CRITICAL RULE: never fire at a cell you have already "
    "fired at — always check the ALREADY FIRED list in the prompt and the enemy board "
    "view before choosing a cell. Fire strategically: track hit patterns to find "
    "ship orientations, eliminate impossible positions, and prioritise finishing "
    "damaged ships before searching new areas."
)


def shot_system_for_player(player_role: str) -> str:
    return (
        f"You are playing Battleship as {player_role}. "
        "CRITICAL RULE: never fire at a cell you have already fired at — always check the "
        "ALREADY FIRED list in the prompt and the enemy board view before choosing a cell. "
        "Fire strategically: follow up on hits to sink ships quickly, "
        "use checkerboard patterns to find new ships."
    )


def format_fleet_status(
    fleet: list[tuple[str, int]],
    move_history,
    player_role: str,
) -> str:
    sunk_names = {
        m.ship_sunk
        for m in move_history
        if (m.player if isinstance(m.player, str) else m.player.value) == player_role
        and m.ship_sunk
    }

    lines = ["Fleet status (enemy ships):"]
    for name, length in fleet:
        status = "SUNK" if name in sunk_names else "still afloat"
        lines.append(f"  {'✓' if name in sunk_names else '○'} {name} (size {length}) — {status}")

    remaining = [(n, l) for n, l in fleet if n not in sunk_names]
    if remaining:
        sizes = ", ".join(f"{n}(size {l})" for n, l in remaining)
        lines.append(f"Ships still to sink: {sizes}")
    else:
        lines.append("All enemy ships have been sunk!")

    return "\n".join(lines) + "\n\n"


def shot_user_message(
    board_size: int,
    own_board_desc: str,
    enemy_board_desc: str,
    move_history_section: str,
    enemy_board_view: list[list[str]] | None = None,
    fleet: list[tuple[str, int]] | None = None,
    move_history=None,
    player_role: str | None = None,
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

    unsunk_hits = ""
    if enemy_board_view:
        count = sum(
            1
            for row in enemy_board_view
            for cell in row
            if cell == "hit"
        )
        if count:
            unsunk_hits = (
                f"NOTE: {count} hit cell(s) on the enemy board belong to a ship not yet fully sunk — "
                "prioritise finishing that ship before searching elsewhere.\n\n"
            )

    fleet_section = ""
    sunk_names: set[str] = set()
    if fleet and move_history is not None and player_role is not None:
        fleet_section = format_fleet_status(fleet, move_history, player_role)
        sunk_names = {
            m.ship_sunk
            for m in move_history
            if (m.player if isinstance(m.player, str) else m.player.value) == player_role
            and m.ship_sunk
        }

    miss_strategy = ""
    if fleet and move_history is not None and player_role is not None:
        my_moves = [
            m for m in move_history
            if (m.player if isinstance(m.player, str) else m.player.value) == player_role
        ]
        last_was_miss = (
            my_moves
            and (my_moves[-1].result if isinstance(my_moves[-1].result, str) else my_moves[-1].result.value) == "miss"
        )
        if last_was_miss:
            remaining = [(n, l) for n, l in fleet if n not in sunk_names]
            if remaining:
                min_size = min(l for _, l in remaining)
                spacing = min_size - 1
                miss_strategy = (
                    f"SEARCH STRATEGY: Your last shot was a miss and no hit is currently in progress. "
                    f"The smallest remaining ship has size {min_size}, so it must span at least {min_size} consecutive cells. "
                    f"To cover the board efficiently, fire at cells spaced {spacing} apart "
                    f"(i.e. skip {spacing - 1} cell(s) between shots) in any direction — "
                    f"this guarantees every possible ship position contains at least one of your search shots. "
                    f"NEVER fire at a cell you have already fired at.\n\n"
                )

    return (
        f"It is your turn in a {board_size}×{board_size} Battleship game.\n\n"
        f"{fleet_section}"
        f"{own_board_desc}\n\n"
        f"{enemy_board_desc}\n\n"
        f"{move_history_section}"
        f"{already_fired}"
        f"{unsunk_hits}"
        f"{miss_strategy}"
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
