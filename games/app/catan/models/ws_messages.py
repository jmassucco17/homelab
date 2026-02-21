"""WebSocket message schemas for Catan multiplayer communication.

Defines every message that can flow between the browser (client) and the
FastAPI WebSocket server, in both directions.
"""

from __future__ import annotations

import enum
import typing

import pydantic

from .actions import Action


class ClientMessageType(enum.StrEnum):
    """Discriminator values for client-to-server WebSocket messages."""

    JOIN_GAME = 'join_game'
    SUBMIT_ACTION = 'submit_action'
    REQUEST_UNDO = 'request_undo'


class ServerMessageType(enum.StrEnum):
    """Discriminator values for server-to-client WebSocket messages."""

    GAME_STATE_UPDATE = 'game_state_update'
    ERROR_MESSAGE = 'error_message'
    PLAYER_JOINED = 'player_joined'
    GAME_STARTED = 'game_started'
    GAME_OVER = 'game_over'


# ---------------------------------------------------------------------------
# Client → Server messages
# ---------------------------------------------------------------------------


class JoinGame(pydantic.BaseModel):
    """Sent by a client to join a game room."""

    message_type: typing.Literal[ClientMessageType.JOIN_GAME] = (
        ClientMessageType.JOIN_GAME
    )
    player_name: str
    room_code: str


class SubmitAction(pydantic.BaseModel):
    """Sent by a client to submit a game action."""

    message_type: typing.Literal[ClientMessageType.SUBMIT_ACTION] = (
        ClientMessageType.SUBMIT_ACTION
    )
    action: Action


class RequestUndo(pydantic.BaseModel):
    """Sent by a client to undo the most recent placement (setup phase only)."""

    message_type: typing.Literal[ClientMessageType.REQUEST_UNDO] = (
        ClientMessageType.REQUEST_UNDO
    )


# Discriminated union of all client message types.
ClientMessage = typing.Annotated[
    JoinGame | SubmitAction | RequestUndo,
    pydantic.Field(discriminator='message_type'),
]


# ---------------------------------------------------------------------------
# Server → Client messages
# ---------------------------------------------------------------------------


class GameStateUpdate(pydantic.BaseModel):
    """Broadcast by the server after every state change.

    ``game_state`` is typed as ``Any`` to avoid a circular import with
    ``game_state.py``; the server layer serializes it to a plain dict before
    sending.
    """

    message_type: ServerMessageType = ServerMessageType.GAME_STATE_UPDATE
    game_state: typing.Any  # serialized GameState dict


class ErrorMessage(pydantic.BaseModel):
    """Sent by the server to an individual client on an invalid action."""

    message_type: ServerMessageType = ServerMessageType.ERROR_MESSAGE
    error: str


class PlayerJoined(pydantic.BaseModel):
    """Broadcast by the server when a new player enters the room."""

    message_type: ServerMessageType = ServerMessageType.PLAYER_JOINED
    player_name: str
    player_index: int
    total_players: int


class GameStarted(pydantic.BaseModel):
    """Broadcast by the server when the game begins."""

    message_type: ServerMessageType = ServerMessageType.GAME_STARTED
    player_names: list[str]
    turn_order: list[int]  # player indices in turn order


class GameOver(pydantic.BaseModel):
    """Broadcast by the server when the game ends."""

    message_type: ServerMessageType = ServerMessageType.GAME_OVER
    winner_player_index: int
    winner_name: str
    final_victory_points: list[int]  # one entry per player in player_index order
