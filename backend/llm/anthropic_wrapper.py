from __future__ import annotations

import logging
import os
from typing import Any

import anthropic

from ..game.models import BoardState, LLMConfig, Move, PlacedShip
from .base import (
    LLMCapabilityError,  # noqa: F401 — re-exported for callers
    LLMWrapper,
    PlacementResult,
    ShotResult,
    _build_board_description,
)
from ..prompts import (
    PLACEMENT_SYSTEM,
    SHOT_SYSTEM,
    format_move_history,
    placement_user_message,
    shot_retry_message,
    shot_user_message,
)

logger = logging.getLogger(__name__)


class AnthropicWrapper(LLMWrapper):
    """LLM wrapper backed by the Anthropic Messages API.

    All LLM interactions use *forced* tool use — the model is never allowed to
    respond with free text.  This guarantees that every response can be parsed
    without heuristics.
    """

    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        api_key = (
            config.api_key.get_secret_value()
            if config.api_key is not None
            else os.getenv("ANTHROPIC_API_KEY", "")
        )
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    # ------------------------------------------------------------------
    # place_ships
    # ------------------------------------------------------------------

    async def place_ships(
        self,
        board_size: int,
        ships_to_place: list[tuple[str, int]],
        system_prompt: str,
    ) -> PlacementResult:
        """Ask the model to place every ship in *ships_to_place* on the board.

        Uses forced tool use — ``tool_choice`` is pinned to ``place_ships`` so
        the response is always a structured JSON object.
        """
        system = system_prompt.strip() if system_prompt.strip() else PLACEMENT_SYSTEM
        user_message = placement_user_message(board_size, ships_to_place)

        try:
            response = await self._client.messages.create(
                model=self._config.model,
                max_tokens=1024,
                system=system,
                tools=[self.PLACE_SHIPS_TOOL],
                tool_choice={"type": "tool", "name": "place_ships"},
                messages=[{"role": "user", "content": user_message}],
            )
        except anthropic.APIError as exc:
            raise anthropic.APIError(
                f"Anthropic API error during place_ships: {exc}",
                request=exc.request,
                body=exc.body,
            ) from exc

        tool_input = _extract_tool_input(response, "place_ships")

        ships: list[PlacedShip] = []
        for placement in tool_input.get("placements", []):
            ships.append(
                PlacedShip(
                    ship_type=placement["ship_type"],
                    row=int(placement["row"]),
                    col=int(placement["col"]),
                    orientation=placement["orientation"],
                    hits=[],
                )
            )

        logger.debug(
            "place_ships: model=%s board=%d×%d ships_placed=%d",
            self._config.model,
            board_size,
            board_size,
            len(ships),
        )
        return PlacementResult(ships=ships)

    # ------------------------------------------------------------------
    # choose_shot
    # ------------------------------------------------------------------

    async def choose_shot(
        self,
        board_size: int,
        own_board: BoardState,
        enemy_board_view: list[list[str]],
        move_history: list[Move],
        system_prompt: str,
    ) -> ShotResult:
        """Ask the model to fire at a cell on the enemy board.

        Retries up to 3 times when the model returns an out-of-bounds
        coordinate.  On each retry the error is appended to the conversation
        so the model has full context — the shot is *never* silently randomised.
        """
        system = system_prompt.strip() if system_prompt.strip() else SHOT_SYSTEM

        own_desc = _build_board_description(
            [[cell for cell in row] for row in own_board.grid],
            "Your board",
        )
        enemy_desc = _build_board_description(enemy_board_view, "Enemy board (your view)")
        base_user_message = shot_user_message(
            board_size, own_desc, enemy_desc, format_move_history(move_history),
            enemy_board_view=enemy_board_view,
        )

        messages: list[dict[str, Any]] = [
            {"role": "user", "content": base_user_message}
        ]

        last_exc: Exception | None = None

        for attempt in range(1, 4):
            if attempt > 1:
                messages.append({"role": "user", "content": shot_retry_message(attempt - 1, board_size, last_exc)})

            try:
                response = await self._client.messages.create(
                    model=self._config.model,
                    max_tokens=512,
                    system=system,
                    tools=[self.CHOOSE_SHOT_TOOL],
                    tool_choice={"type": "tool", "name": "choose_shot"},
                    messages=messages,
                )
            except anthropic.APIError as exc:
                raise anthropic.APIError(
                    f"Anthropic API error during choose_shot (attempt {attempt}): {exc}",
                    request=exc.request,
                    body=exc.body,
                ) from exc

            tool_input = _extract_tool_input(response, "choose_shot")

            row: int = int(tool_input["row"])
            col: int = int(tool_input["col"])
            reasoning: str | None = tool_input.get("reasoning")

            # Validate bounds and that the cell hasn't already been fired at.
            if not (0 <= row < board_size and 0 <= col < board_size):
                last_exc = ValueError(
                    f"row={row}, col={col} is out of bounds for a "
                    f"{board_size}×{board_size} board"
                )
            elif enemy_board_view[row][col] != "empty":
                cell_state = enemy_board_view[row][col]
                last_exc = ValueError(
                    f"({row}, {col}) has already been fired at (state: {cell_state!r}). "
                    "Choose a cell that is still 'empty'."
                )
            else:
                logger.debug(
                    "choose_shot: model=%s attempt=%d row=%d col=%d reasoning=%r",
                    self._config.model,
                    attempt,
                    row,
                    col,
                    reasoning,
                )
                return ShotResult(row=row, col=col, reasoning=reasoning)
            logger.warning(
                "choose_shot: invalid coordinate from model=%s attempt=%d "
                "row=%d col=%d board_size=%d — retrying",
                self._config.model,
                attempt,
                row,
                col,
                board_size,
            )

            # Append the raw assistant message so the conversation is coherent
            # for the next API call.
            messages.append({"role": "assistant", "content": response.content})

        raise ValueError(
            f"Failed to get valid shot after 3 attempts from model '{self._config.model}'. "
            f"Last error: {last_exc}"
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_tool_input(response: anthropic.types.Message, tool_name: str) -> dict[str, Any]:
    """Pull the ``input`` dict out of the first tool-use block in *response*.

    Args:
        response: The Anthropic API response object.
        tool_name: The expected tool name (used only for the error message).

    Returns:
        The ``input`` mapping from the tool-use block.

    Raises:
        ValueError: If no tool-use block is found in the response.
    """
    for block in response.content:
        if block.type == "tool_use":
            return block.input  # type: ignore[return-value]
    raise ValueError(
        f"No tool_use block found in Anthropic response for tool '{tool_name}'. "
        f"Stop reason: {response.stop_reason!r}. "
        f"Content types: {[b.type for b in response.content]}"
    )
