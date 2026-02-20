"""Catan player data models.

Tracks a player's resources, development cards, build inventory, and
victory points throughout the game.
"""

from __future__ import annotations

import enum

import pydantic

from .board import PortType, ResourceType


class DevCardType(enum.StrEnum):
    """Development card types."""

    KNIGHT = 'knight'
    ROAD_BUILDING = 'road_building'
    YEAR_OF_PLENTY = 'year_of_plenty'
    MONOPOLY = 'monopoly'
    VICTORY_POINT = 'victory_point'


# Standard development card deck composition (25 cards total).
DEV_CARD_COUNTS: dict[DevCardType, int] = {
    DevCardType.KNIGHT: 14,
    DevCardType.ROAD_BUILDING: 2,
    DevCardType.YEAR_OF_PLENTY: 2,
    DevCardType.MONOPOLY: 2,
    DevCardType.VICTORY_POINT: 5,
}

# Standard build costs.
ROAD_COST = {'wood': 1, 'brick': 1}
SETTLEMENT_COST = {'wood': 1, 'brick': 1, 'wheat': 1, 'sheep': 1}
CITY_COST = {'wheat': 2, 'ore': 3}
DEV_CARD_COST = {'wheat': 1, 'sheep': 1, 'ore': 1}


class Resources(pydantic.BaseModel):
    """A collection of resource cards held by a player or the bank."""

    wood: int = 0
    brick: int = 0
    wheat: int = 0
    sheep: int = 0
    ore: int = 0

    def total(self) -> int:
        """Return the total number of resource cards."""
        return self.wood + self.brick + self.wheat + self.sheep + self.ore

    def can_afford(self, cost: dict[str, int]) -> bool:
        """Return True if these resources can cover the given cost dict."""
        return all(
            getattr(self, resource, 0) >= amount for resource, amount in cost.items()
        )

    def subtract(self, cost: dict[str, int]) -> Resources:
        """Return new Resources with cost subtracted. Does not validate sufficiency."""
        return Resources(
            wood=self.wood - cost.get('wood', 0),
            brick=self.brick - cost.get('brick', 0),
            wheat=self.wheat - cost.get('wheat', 0),
            sheep=self.sheep - cost.get('sheep', 0),
            ore=self.ore - cost.get('ore', 0),
        )

    def add(self, other: Resources) -> Resources:
        """Return new Resources with another set added."""
        return Resources(
            wood=self.wood + other.wood,
            brick=self.brick + other.brick,
            wheat=self.wheat + other.wheat,
            sheep=self.sheep + other.sheep,
            ore=self.ore + other.ore,
        )

    def get(self, resource_type: ResourceType) -> int:
        """Return the count for a specific resource type."""
        return getattr(self, resource_type.value, 0)

    def with_resource(self, resource_type: ResourceType, amount: int) -> Resources:
        """Return new Resources with one field replaced."""
        data = self.model_dump()
        data[resource_type.value] = amount
        return Resources(**data)


class DevCardHand(pydantic.BaseModel):
    """Development cards held by a player."""

    knight: int = 0
    road_building: int = 0
    year_of_plenty: int = 0
    monopoly: int = 0
    victory_point: int = 0

    def total(self) -> int:
        """Return the total number of development cards."""
        return (
            self.knight
            + self.road_building
            + self.year_of_plenty
            + self.monopoly
            + self.victory_point
        )

    def get(self, card_type: DevCardType) -> int:
        """Return the count for a specific card type."""
        return getattr(self, card_type.value, 0)

    def add(self, card_type: DevCardType, count: int = 1) -> DevCardHand:
        """Return new DevCardHand with count of card_type increased."""
        data = self.model_dump()
        data[card_type.value] += count
        return DevCardHand(**data)

    def remove(self, card_type: DevCardType, count: int = 1) -> DevCardHand:
        """Return new DevCardHand with count of card_type decreased."""
        data = self.model_dump()
        data[card_type.value] -= count
        return DevCardHand(**data)


class BuildInventory(pydantic.BaseModel):
    """Remaining building pieces a player can still place on the board."""

    settlements_remaining: int = 5
    cities_remaining: int = 4
    roads_remaining: int = 15


class Player(pydantic.BaseModel):
    """A Catan player's complete state."""

    player_index: int
    name: str
    color: str
    resources: Resources = pydantic.Field(default_factory=Resources)
    dev_cards: DevCardHand = pydantic.Field(default_factory=DevCardHand)
    # Cards bought this turn; not playable until next turn.
    new_dev_cards: DevCardHand = pydantic.Field(default_factory=DevCardHand)
    build_inventory: BuildInventory = pydantic.Field(default_factory=BuildInventory)
    victory_points: int = 0
    ports_owned: list[PortType] = pydantic.Field(default_factory=list)
    knights_played: int = 0
    longest_road_length: int = 0
