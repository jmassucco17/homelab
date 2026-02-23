"""Pydantic action schemas for every legal Catan game action.

Each action subclass carries the data needed to apply that action to a
GameState.  The ActionResult carries the outcome back to the caller.
"""

from __future__ import annotations

import enum
from typing import Annotated, Any, Literal

import pydantic

from .board import ResourceType


class ActionType(enum.StrEnum):
    """Discriminator values for every legal action type."""

    PLACE_SETTLEMENT = 'place_settlement'
    PLACE_ROAD = 'place_road'
    PLACE_CITY = 'place_city'
    ROLL_DICE = 'roll_dice'
    BUILD_DEV_CARD = 'build_dev_card'
    PLAY_KNIGHT = 'play_knight'
    PLAY_ROAD_BUILDING = 'play_road_building'
    PLAY_YEAR_OF_PLENTY = 'play_year_of_plenty'
    PLAY_MONOPOLY = 'play_monopoly'
    TRADE_OFFER = 'trade_offer'
    TRADE_WITH_BANK = 'trade_with_bank'
    TRADE_WITH_PORT = 'trade_with_port'
    END_TURN = 'end_turn'
    MOVE_ROBBER = 'move_robber'
    STEAL_RESOURCE = 'steal_resource'
    DISCARD_RESOURCES = 'discard_resources'
    ACCEPT_TRADE = 'accept_trade'
    REJECT_TRADE = 'reject_trade'
    CANCEL_TRADE = 'cancel_trade'


class BaseAction(pydantic.BaseModel):
    """Base for all game actions. Every action identifies its type and acting player."""

    player_index: int


class PlaceSettlement(BaseAction):
    """Place a settlement on a vertex."""

    action_type: Literal[ActionType.PLACE_SETTLEMENT] = ActionType.PLACE_SETTLEMENT
    vertex_id: int


class PlaceRoad(BaseAction):
    """Place a road on an edge."""

    action_type: Literal[ActionType.PLACE_ROAD] = ActionType.PLACE_ROAD
    edge_id: int


class PlaceCity(BaseAction):
    """Upgrade an existing settlement to a city on a vertex."""

    action_type: Literal[ActionType.PLACE_CITY] = ActionType.PLACE_CITY
    vertex_id: int


class RollDice(BaseAction):
    """Roll the two dice to start a main-phase turn."""

    action_type: Literal[ActionType.ROLL_DICE] = ActionType.ROLL_DICE


class BuildDevCard(BaseAction):
    """Purchase one development card from the deck."""

    action_type: Literal[ActionType.BUILD_DEV_CARD] = ActionType.BUILD_DEV_CARD


class PlayKnight(BaseAction):
    """Play a Knight card before or after rolling to move the robber."""

    action_type: Literal[ActionType.PLAY_KNIGHT] = ActionType.PLAY_KNIGHT


class PlayRoadBuilding(BaseAction):
    """Play a Road Building card to place up to two free roads."""

    action_type: Literal[ActionType.PLAY_ROAD_BUILDING] = ActionType.PLAY_ROAD_BUILDING


class PlayYearOfPlenty(BaseAction):
    """Play a Year of Plenty card to take any two resources from the bank."""

    action_type: Literal[ActionType.PLAY_YEAR_OF_PLENTY] = (
        ActionType.PLAY_YEAR_OF_PLENTY
    )
    resource1: ResourceType
    resource2: ResourceType


class PlayMonopoly(BaseAction):
    """Play a Monopoly card to steal all of one resource type from every opponent."""

    action_type: Literal[ActionType.PLAY_MONOPOLY] = ActionType.PLAY_MONOPOLY
    resource: ResourceType


class TradeOffer(BaseAction):
    """Propose a domestic trade to one or all other players."""

    action_type: Literal[ActionType.TRADE_OFFER] = ActionType.TRADE_OFFER
    # Maps resource name → quantity being offered.
    offering: dict[str, int]
    # Maps resource name → quantity being requested in return.
    requesting: dict[str, int]
    # Specific target player index, or None to broadcast to all.
    target_player: int | None = None


class TradeWithBank(BaseAction):
    """Trade four of one resource to the bank for one of another."""

    action_type: Literal[ActionType.TRADE_WITH_BANK] = ActionType.TRADE_WITH_BANK
    giving: ResourceType
    receiving: ResourceType


class TradeWithPort(BaseAction):
    """Trade via a port the player's settlements border (2:1 specific, 3:1 generic)."""

    action_type: Literal[ActionType.TRADE_WITH_PORT] = ActionType.TRADE_WITH_PORT
    giving: ResourceType
    giving_count: int  # 2 for a specific-resource port, 3 for a generic port
    receiving: ResourceType


class EndTurn(BaseAction):
    """End the current player's turn and advance to the next player."""

    action_type: Literal[ActionType.END_TURN] = ActionType.END_TURN


class MoveRobber(BaseAction):
    """Move the robber to a new tile (after rolling 7 or playing a Knight)."""

    action_type: Literal[ActionType.MOVE_ROBBER] = ActionType.MOVE_ROBBER
    tile_index: int  # index into Board.tiles


class StealResource(BaseAction):
    """Steal one random resource from a player adjacent to the newly placed robber."""

    action_type: Literal[ActionType.STEAL_RESOURCE] = ActionType.STEAL_RESOURCE
    target_player_index: int


class DiscardResources(BaseAction):
    """Discard half of hand when holding more than 7 cards after a 7 is rolled."""

    action_type: Literal[ActionType.DISCARD_RESOURCES] = ActionType.DISCARD_RESOURCES
    # Maps resource name → quantity to discard.
    resources: dict[str, int]


class AcceptTrade(BaseAction):
    """Accept a pending domestic trade offer."""

    action_type: Literal[ActionType.ACCEPT_TRADE] = ActionType.ACCEPT_TRADE
    trade_id: str


class RejectTrade(BaseAction):
    """Decline a pending domestic trade offer."""

    action_type: Literal[ActionType.REJECT_TRADE] = ActionType.REJECT_TRADE
    trade_id: str


class CancelTrade(BaseAction):
    """Cancel a trade offer (initiated by the offering player)."""

    action_type: Literal[ActionType.CANCEL_TRADE] = ActionType.CANCEL_TRADE
    trade_id: str


# Discriminated union of all action types for deserialization.
Action = Annotated[
    PlaceSettlement
    | PlaceRoad
    | PlaceCity
    | RollDice
    | BuildDevCard
    | PlayKnight
    | PlayRoadBuilding
    | PlayYearOfPlenty
    | PlayMonopoly
    | TradeOffer
    | TradeWithBank
    | TradeWithPort
    | EndTurn
    | MoveRobber
    | StealResource
    | DiscardResources
    | AcceptTrade
    | RejectTrade
    | CancelTrade,
    pydantic.Field(discriminator='action_type'),
]


class ActionResult(pydantic.BaseModel):
    """Result returned by the rules engine after attempting to apply an action.

    The updated GameState is carried as ``Any`` here to avoid a circular
    import with ``game_state.py``; callers in the engine layer cast it to
    ``GameState`` explicitly.
    """

    success: bool
    error_message: str | None = None
    # Updated game state after the action (None on failure).
    updated_state: Any | None = None
