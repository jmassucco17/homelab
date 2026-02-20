"""Catan game state model.

Captures the complete mutable state of a game in progress, including the
board, all players, the current turn, and special award tracking.
"""

from __future__ import annotations

import enum

import pydantic

from .board import Board
from .player import DevCardType, Player


class GamePhase(enum.StrEnum):
    """High-level phases of a Catan game."""

    # Initial placement: settlement/road pairs placed 1→N order.
    SETUP_FORWARD = 'setup_forward'
    # Initial placement: settlement/road pairs placed N→1 order.
    SETUP_BACKWARD = 'setup_backward'
    # Main game: dice rolls, building, trading.
    MAIN = 'main'
    # A player has reached 10 VP and the game is over.
    ENDED = 'ended'


class PendingActionType(enum.StrEnum):
    """Specific sub-actions that must be resolved before play continues."""

    PLACE_SETTLEMENT = 'place_settlement'  # setup phase: place initial settlement
    PLACE_ROAD = 'place_road'  # setup phase or Road Building card
    ROLL_DICE = 'roll_dice'  # start of main turn
    MOVE_ROBBER = 'move_robber'  # after rolling 7 or playing Knight
    STEAL_RESOURCE = 'steal_resource'  # after placing robber on an occupied tile
    DISCARD_RESOURCES = 'discard_resources'  # players with >7 cards after a 7 roll
    YEAR_OF_PLENTY = 'year_of_plenty'  # choose 2 free resources
    MONOPOLY = 'monopoly'  # choose resource type to steal
    BUILD_OR_TRADE = 'build_or_trade'  # build/trade actions after rolling


class TurnState(pydantic.BaseModel):
    """Transient state for the currently active turn."""

    player_index: int
    roll_value: int | None = None  # None until dice are rolled
    has_rolled: bool = False
    pending_action: PendingActionType = PendingActionType.ROLL_DICE
    # Remaining free road placements from a Road Building card.
    free_roads_remaining: int = 0
    # Remaining free resource picks from a Year of Plenty card.
    year_of_plenty_remaining: int = 0
    # Player indices who still need to discard after a 7 roll.
    discard_player_indices: list[int] = pydantic.Field(default_factory=list)
    # Active trade offer ID, if any.
    active_trade_id: str | None = None


class GameState(pydantic.BaseModel):
    """Complete snapshot of a Catan game at any point in time."""

    players: list[Player]
    board: Board
    phase: GamePhase = GamePhase.SETUP_FORWARD
    turn_state: TurnState
    # Remaining development cards in the draw pile (list of DevCardType values).
    dev_card_deck: list[DevCardType] = pydantic.Field(default_factory=list)
    # player_index of the current Longest Road holder, or None.
    longest_road_owner: int | None = None
    # player_index of the current Largest Army holder, or None.
    largest_army_owner: int | None = None
    # Full history of dice roll totals for this game.
    dice_roll_history: list[int] = pydantic.Field(default_factory=list)
    # Number of complete rounds played.
    turn_number: int = 0
    # player_index of the winner once phase == ENDED, or None.
    winner_index: int | None = None
