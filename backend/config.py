# MIT License
# Copyright (c) 2026 Angshuman Nandy

import os
from dotenv import load_dotenv

load_dotenv()

FLEET_FOR_SIZE: dict[int, list[tuple[str, int]]] = {
    5: [("Destroyer", 2), ("Submarine", 3)],
    7: [("Destroyer", 2), ("Cruiser", 3), ("Battleship", 4)],
    10: [("Carrier", 5), ("Battleship", 4), ("Cruiser", 3), ("Submarine", 3), ("Destroyer", 2)],
}


def get_fleet(board_size: int) -> list[tuple[str, int]]:
    for threshold in sorted(FLEET_FOR_SIZE.keys(), reverse=True):
        if board_size >= threshold:
            return FLEET_FOR_SIZE[threshold]
    return FLEET_FOR_SIZE[5]


TURN_DELAY_SECONDS: float = 1.0

ENV: str = os.getenv("ENV", "production")

# Optional default API keys — used to pre-fill the UI via /api/config.
# Set these in .env for local dev so you don't re-enter keys every session.
DEFAULT_ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
DEFAULT_OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
