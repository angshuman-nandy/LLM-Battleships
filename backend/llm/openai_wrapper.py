from __future__ import annotations

import json
import os
from typing import Optional

import openai

from ..game.models import BoardState, LLMConfig, Move, PlacedShip
from .base import LLMWrapper, PlacementResult, ShotResult, _build_board_description
from ..prompts import (
    PLACEMENT_SYSTEM,
    SHOT_SYSTEM,
    format_move_history,
    placement_user_message,
    shot_user_message,
)


class OpenAIWrapper(LLMWrapper):
    """LLM wrapper for OpenAI models using forced tool use via the openai SDK."""

    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        api_key = (
            config.api_key.get_secret_value()
            if config.api_key is not None
            else os.getenv("OPENAI_API_KEY", "")
        )
        self._client = openai.AsyncOpenAI(api_key=api_key)

    # ------------------------------------------------------------------
    # Tool format conversion
    # ------------------------------------------------------------------

    def _to_openai_tool(self, tool: dict) -> dict:
        """Convert an Anthropic-style tool definition to the OpenAI tool format.

        Anthropic tools use ``input_schema`` for the JSON Schema; OpenAI
        expects ``parameters`` nested under a ``function`` key.
        """
        return {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        }

    # ------------------------------------------------------------------
    # place_ships
    # ------------------------------------------------------------------

    async def place_ships(
        self,
        board_size: int,
        ships_to_place: list[tuple[str, int]],
        system_prompt: str,
    ) -> PlacementResult:
        """Ask the model to place all ships on an empty board.

        Uses forced tool use so the response is always structured JSON —
        never free text that requires ad-hoc parsing.

        Args:
            board_size: Side length of the square grid.
            ships_to_place: Ordered list of ``(ship_type, length)`` pairs.
            system_prompt: Persona / strategy instructions for the model.

        Returns:
            :class:`PlacementResult` containing the list of placed ships.

        Raises:
            openai.APIError: On any unrecoverable API-level failure.
        """
        system = system_prompt.strip() if system_prompt.strip() else PLACEMENT_SYSTEM
        user_message = placement_user_message(board_size, ships_to_place)

        try:
            response = await self._client.chat.completions.create(
                model=self._config.model,
                tools=[self._to_openai_tool(self.PLACE_SHIPS_TOOL)],
                tool_choice={
                    "type": "function",
                    "function": {"name": "place_ships"},
                },
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
            )
        except openai.APIError:
            raise

        tool_call = response.choices[0].message.tool_calls[0]
        arguments = json.loads(tool_call.function.arguments)
        raw_placements: list[dict] = arguments["placements"]

        ships = [
            PlacedShip(
                ship_type=p["ship_type"],
                row=p["row"],
                col=p["col"],
                orientation=p["orientation"],
            )
            for p in raw_placements
        ]
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
        """Ask the model to pick a cell to fire at, with up to 3 retries.

        On an invalid coordinate the error is appended to the conversation
        and the model is asked to retry — it never silently falls back to a
        random shot.

        Args:
            board_size: Side length of the square grid.
            own_board: The attacker's own :class:`BoardState`.
            enemy_board_view: 2-D list of :class:`CellState` strings showing
                the attacker's view of the enemy board (unhit ships are
                ``"empty"``).
            move_history: All moves so far, oldest-first.
            system_prompt: Persona / strategy instructions for the model.

        Returns:
            :class:`ShotResult` with the chosen ``(row, col)`` and optional
            reasoning.

        Raises:
            ValueError: After 3 consecutive failures to produce valid coords.
            openai.APIError: On any unrecoverable API-level failure.
        """
        system = system_prompt.strip() if system_prompt.strip() else SHOT_SYSTEM
        own_desc = _build_board_description(
            [[cell for cell in row] for row in own_board.grid],
            "Your board",
        )
        enemy_desc = _build_board_description(enemy_board_view, "Enemy board (your view)")
        initial_user_content = shot_user_message(
            board_size, own_desc, enemy_desc, format_move_history(move_history),
            enemy_board_view=enemy_board_view,
        )

        messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": initial_user_content},
        ]

        max_retries = 3
        last_error: Optional[str] = None

        for attempt in range(max_retries):
            if attempt > 0 and last_error:
                # Append the previous (invalid) assistant reply and an error
                # correction request so the model has full context.
                messages.append({"role": "user", "content": last_error})

            try:
                response = await self._client.chat.completions.create(
                    model=self._config.model,
                    tools=[self._to_openai_tool(self.CHOOSE_SHOT_TOOL)],
                    tool_choice={
                        "type": "function",
                        "function": {"name": "choose_shot"},
                    },
                    messages=messages,
                )
            except openai.APIError:
                raise

            assistant_message = response.choices[0].message

            # Accumulate the assistant turn into the conversation.
            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in (assistant_message.tool_calls or [])
                    ],
                }
            )

            if not assistant_message.tool_calls:
                last_error = (
                    "You did not call the choose_shot tool. "
                    "You MUST call choose_shot with a valid (row, col) within "
                    f"the grid bounds 0–{board_size - 1}. Try again."
                )
                continue

            tool_call = assistant_message.tool_calls[0]

            # Feed the tool result back so the conversation is valid.
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": "Acknowledged. Validating your choice now.",
                }
            )

            try:
                arguments = json.loads(tool_call.function.arguments)
                row: int = int(arguments["row"])
                col: int = int(arguments["col"])
            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                last_error = (
                    f"Your tool call arguments could not be parsed: {exc}. "
                    f"Call choose_shot with integer 'row' and 'col' in range 0–{board_size - 1}."
                )
                continue

            # Validate bounds.
            if not (0 <= row < board_size and 0 <= col < board_size):
                last_error = (
                    f"({row}, {col}) is out of bounds. "
                    f"Both row and col must be in the range 0–{board_size - 1}. "
                    "Call choose_shot again with a valid cell."
                )
                continue

            # Validate not already fired at (present as "hit" or "miss" in enemy view).
            cell_state = enemy_board_view[row][col]
            if cell_state in ("hit", "miss", "sunk"):
                last_error = (
                    f"({row}, {col}) has already been fired at (state: {cell_state!r}). "
                    "Choose a cell that is still 'empty'. Call choose_shot again."
                )
                continue

            reasoning: Optional[str] = arguments.get("reasoning")
            return ShotResult(row=row, col=col, reasoning=reasoning)

        raise ValueError(
            f"OpenAI model failed to produce valid shot coordinates after "
            f"{max_retries} attempts. Last error: {last_error}"
        )
