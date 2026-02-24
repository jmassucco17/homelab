"""JSON serialization helpers for Catan models.

Provides thin wrappers around Pydantic's built-in serialization so that
callers (WebSocket handlers, persistence layer) can serialize and deserialize
any model without directly depending on Pydantic internals.
"""

from __future__ import annotations

import json
import typing

import pydantic

from .board import Board
from .game_state import GameState
from .player import Player


def serialize_model(model: pydantic.BaseModel) -> dict[str, typing.Any]:
    """Return a JSON-serializable dict representation of any Pydantic model."""
    return model.model_dump(mode='json')


def serialize_to_json(model: pydantic.BaseModel) -> str:
    """Serialize any Pydantic model to a compact JSON string."""
    return model.model_dump_json()


def deserialize_board(data: dict[str, typing.Any]) -> Board:
    """Deserialize a plain dict into a Board instance."""
    from .board import Board

    return Board.model_validate(data)


def deserialize_game_state(data: dict[str, typing.Any]) -> GameState:
    """Deserialize a plain dict into a GameState instance."""
    from .game_state import GameState

    return GameState.model_validate(data)


def deserialize_player(data: dict[str, typing.Any]) -> Player:
    """Deserialize a plain dict into a Player instance."""
    from .player import Player

    return Player.model_validate(data)


def game_state_to_json(game_state: GameState) -> str:
    """Convert a GameState to a JSON string suitable for WebSocket transport."""
    return serialize_to_json(game_state)


def game_state_from_json(json_str: str) -> GameState:
    """Parse a JSON string back into a GameState instance."""
    from .game_state import GameState

    return GameState.model_validate(json.loads(json_str))
