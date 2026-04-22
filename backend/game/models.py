from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class Provider(str, Enum):
    anthropic = "anthropic"
    openai = "openai"
    ollama = "ollama"


class GameMode(str, Enum):
    llm_vs_llm = "llm_vs_llm"
    human_vs_llm = "human_vs_llm"


class PlacementMode(str, Enum):
    llm = "llm"
    third_agent = "third_agent"
    human = "human"
    random = "random"


class GamePhase(str, Enum):
    setup = "setup"
    placement = "placement"
    in_progress = "in_progress"
    finished = "finished"


class CellState(str, Enum):
    empty = "empty"
    ship = "ship"
    hit = "hit"
    miss = "miss"
    sunk = "sunk"


class PlayerRole(str, Enum):
    player1 = "player1"
    player2 = "player2"


# ---------------------------------------------------------------------------
# LLM Configuration
# ---------------------------------------------------------------------------


class LLMConfig(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    provider: Provider
    model: str
    api_key: Optional[SecretStr] = None
    endpoint_url: Optional[str] = None


class PlacementConfig(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    mode: PlacementMode
    agent_config: Optional[LLMConfig] = None


# ---------------------------------------------------------------------------
# Board / Ship Models
# ---------------------------------------------------------------------------


class PlacedShip(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    ship_type: str
    row: int
    col: int
    orientation: Literal["H", "V"]
    hits: list[int] = Field(default_factory=list)

    def is_sunk(self, ship_length: int) -> bool:
        """Return True when the number of recorded hits equals or exceeds the ship's length."""
        return len(self.hits) >= ship_length


class BoardState(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    size: int
    grid: list[list[CellState]]
    ships: list[PlacedShip]


# ---------------------------------------------------------------------------
# Player / Game State
# ---------------------------------------------------------------------------


class PlayerState(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    role: PlayerRole
    is_human: bool
    llm_config: Optional[LLMConfig] = None
    placement_config: PlacementConfig
    board: Optional[BoardState] = None
    shots_grid: Optional[list[list[CellState]]] = None


class Move(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    player: PlayerRole
    row: int
    col: int
    result: CellState
    ship_sunk: Optional[str] = None
    reasoning: Optional[str] = None


class GameState(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    game_id: str
    mode: GameMode
    phase: GamePhase
    board_size: int
    player1: PlayerState
    player2: PlayerState
    current_turn: PlayerRole = PlayerRole.player1
    moves: list[Move] = Field(default_factory=list)
    winner: Optional[PlayerRole] = None


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------


class CreateGameRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    mode: GameMode
    board_size: int = Field(default=10, ge=5, le=15)
    player1_config: LLMConfig
    player1_placement: PlacementConfig
    player2_config: Optional[LLMConfig] = None
    player2_placement: PlacementConfig = Field(
        default_factory=lambda: PlacementConfig(mode=PlacementMode.random)
    )


class HumanPlacementRequest(BaseModel):
    placements: list[PlacedShip]


class FireRequest(BaseModel):
    row: int
    col: int


# ---------------------------------------------------------------------------
# Safe (sanitized) models for API responses
# ---------------------------------------------------------------------------


class SafeLLMConfig(BaseModel):
    """LLMConfig with the api_key stripped — safe to return in API responses."""

    model_config = ConfigDict(use_enum_values=True)

    provider: Provider
    model: str

    @classmethod
    def from_llm_config(cls, config: LLMConfig) -> SafeLLMConfig:
        return cls(provider=config.provider, model=config.model)


class SafePlayerState(BaseModel):
    """PlayerState with api_key removed from llm_config."""

    model_config = ConfigDict(use_enum_values=True)

    role: PlayerRole
    is_human: bool
    llm_config: Optional[SafeLLMConfig] = None
    placement_config: PlacementConfig
    board: Optional[BoardState] = None
    shots_grid: Optional[list[list[CellState]]] = None

    @classmethod
    def from_player_state(
        cls,
        state: PlayerState,
        *,
        hide_ships: bool = False,
    ) -> SafePlayerState:
        """Build a SafePlayerState, optionally hiding ship positions on the board.

        When *hide_ships* is True the ``ships`` list is cleared and all ``ship``
        cells in the grid are replaced with ``empty``, so the enemy's board
        layout is not revealed to the client.
        """
        safe_config = (
            SafeLLMConfig.from_llm_config(state.llm_config)
            if state.llm_config is not None
            else None
        )

        board = state.board
        if board is not None and hide_ships:
            sanitized_grid = [
                [
                    CellState.empty if cell == CellState.ship else cell
                    for cell in row
                ]
                for row in board.grid
            ]
            board = BoardState(size=board.size, grid=sanitized_grid, ships=[])

        return cls(
            role=state.role,
            is_human=state.is_human,
            llm_config=safe_config,
            placement_config=state.placement_config,
            board=board,
            shots_grid=state.shots_grid,
        )


class GameStatusResponse(BaseModel):
    """Sanitized view of GameState returned by GET /api/game/{id}/state.

    Routes are responsible for deciding which player's ships to hide before
    constructing this model (typically the *opponent's* ships are hidden).
    """

    model_config = ConfigDict(use_enum_values=True)

    game_id: str
    mode: GameMode
    phase: GamePhase
    board_size: int
    player1: SafePlayerState
    player2: SafePlayerState
    current_turn: PlayerRole
    moves: list[Move] = Field(default_factory=list)
    winner: Optional[PlayerRole] = None

    @classmethod
    def from_game_state(
        cls,
        state: GameState,
        *,
        requesting_role: Optional[PlayerRole] = None,
    ) -> GameStatusResponse:
        """Build a sanitized response from a full GameState.

        The opponent's ship positions are hidden; the requesting player (if any)
        sees their own board in full.  When *requesting_role* is None (spectator /
        LLM-vs-LLM game), all ships are visible so the viewer can watch both boards.
        """
        if requesting_role is None:
            hide_p1 = False
            hide_p2 = False
        else:
            hide_p1 = requesting_role != PlayerRole.player1
            hide_p2 = requesting_role != PlayerRole.player2

        return cls(
            game_id=state.game_id,
            mode=state.mode,
            phase=state.phase,
            board_size=state.board_size,
            player1=SafePlayerState.from_player_state(
                state.player1, hide_ships=hide_p1
            ),
            player2=SafePlayerState.from_player_state(
                state.player2, hide_ships=hide_p2
            ),
            current_turn=state.current_turn,
            moves=state.moves,
            winner=state.winner,
        )
