"""HTTP routes for the Catan game sub-section.

Registers:

* ``GET  /catan``                      — lobby/landing page
* ``POST /catan/rooms``                — create a new game room
* ``GET  /catan/rooms/{room_code}``    — room status
* ``POST /catan/rooms/{room_code}/add-ai`` — add an AI player to a room
* ``POST /catan/rooms/{room_code}/start`` — start a game (≥2 players required)

The WebSocket endpoint (``/catan/ws/{room_code}/{player_name}``) is defined
in :mod:`games.app.catan.server.ws_handler` and included here so that a
single ``app.include_router(catan.router)`` call in ``main.py`` registers
everything.
"""

from __future__ import annotations

import pathlib

import fastapi
import fastapi.responses
import fastapi.templating
import pydantic

from ..catan.models import serializers, ws_messages
from ..catan.server import room_manager, ws_handler

APP_DIR = pathlib.Path(__file__).resolve().parent.parent
templates = fastapi.templating.Jinja2Templates(directory=APP_DIR / 'templates')

router = fastapi.APIRouter()

# Include the WebSocket router so all /catan routes live under one router.
router.include_router(ws_handler.router)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class RoomCreatedResponse(pydantic.BaseModel):
    """Returned by POST /catan/rooms."""

    room_code: str


class RoomStatusResponse(pydantic.BaseModel):
    """Returned by GET /catan/rooms/{room_code}."""

    room_code: str
    player_count: int
    phase: str
    players: list[str]


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------


@router.get('/catan', response_class=fastapi.responses.HTMLResponse)
async def catan_lobby(request: fastapi.Request) -> fastapi.responses.HTMLResponse:
    """Render the Catan lobby/landing page."""
    return templates.TemplateResponse(request=request, name='catan_lobby.html.jinja2')


@router.get('/catan/game', response_class=fastapi.responses.HTMLResponse)
async def catan_game(request: fastapi.Request) -> fastapi.responses.HTMLResponse:
    """Render the Catan in-game page (waiting room + board)."""
    return templates.TemplateResponse(request=request, name='catan_game.html.jinja2')


@router.post('/catan/rooms', response_model=RoomCreatedResponse)
async def create_room() -> RoomCreatedResponse:
    """Create a new game room and return its 4-character code."""
    code = room_manager.room_manager.create_room()
    return RoomCreatedResponse(room_code=code)


@router.get('/catan/rooms', response_model=list[RoomStatusResponse])
async def list_rooms() -> list[RoomStatusResponse]:
    """Return a list of all active game rooms."""
    result: list[RoomStatusResponse] = []
    for code, room in room_manager.room_manager.rooms.items():
        result.append(
            RoomStatusResponse(
                room_code=code,
                player_count=room.player_count,
                phase=room.phase,
                players=[slot.name for slot in room.players],
            )
        )
    return result


@router.get('/catan/rooms/{room_code}', response_model=RoomStatusResponse)
async def room_status(room_code: str) -> RoomStatusResponse:
    """Return the current status of a game room."""
    room = room_manager.room_manager.get_room(room_code)
    if room is None:
        raise fastapi.HTTPException(
            status_code=404, detail=f'Room {room_code!r} not found'
        )
    return RoomStatusResponse(
        room_code=room_code,
        player_count=room.player_count,
        phase=room.phase,
        players=[slot.name for slot in room.players],
    )


@router.post('/catan/rooms/{room_code}/add-ai')
async def add_ai_player(
    room_code: str, difficulty: str = 'easy'
) -> dict[str, str | int]:
    """Add an AI player to a room.

    Args:
        room_code: The room code.
        difficulty: AI difficulty level ('easy', 'medium', or 'hard').

    Returns:
        Status dict with player info.
    """
    if difficulty not in ('easy', 'medium', 'hard'):
        raise fastapi.HTTPException(
            status_code=400,
            detail=f"Invalid difficulty '{difficulty}'. "
            "Must be 'easy', 'medium', or 'hard'",
        )

    room = room_manager.room_manager.get_room(room_code)
    if room is None:
        raise fastapi.HTTPException(
            status_code=404, detail=f'Room {room_code!r} not found'
        )
    if room.game_state is not None:
        raise fastapi.HTTPException(
            status_code=400, detail='Cannot add AI after game has started'
        )

    slot = room_manager.room_manager.add_ai_player(room_code, difficulty)
    if slot is None:
        raise fastapi.HTTPException(
            status_code=400, detail='Room is full (max 4 players)'
        )

    # Broadcast PlayerJoined message to all connected clients
    joined_msg = ws_messages.PlayerJoined(
        player_name=slot.name,
        player_index=slot.player_index,
        total_players=room.player_count,
    )
    await room_manager.room_manager.broadcast(room, joined_msg.model_dump_json())

    return {
        'status': 'added',
        'player_name': slot.name,
        'player_index': slot.player_index,
        'total_players': room.player_count,
    }


@router.post('/catan/rooms/{room_code}/start')
async def start_game(
    room_code: str, background_tasks: fastapi.BackgroundTasks
) -> dict[str, str]:
    """Start the game for a room.

    Requires at least 2 players.  Broadcasts :class:`GameStarted` followed
    by the initial :class:`GameStateUpdate` to every connected client.
    """
    room = room_manager.room_manager.get_room(room_code)
    if room is None:
        raise fastapi.HTTPException(
            status_code=404, detail=f'Room {room_code!r} not found'
        )
    if room.player_count < 2:
        raise fastapi.HTTPException(
            status_code=400, detail='At least 2 players are required to start'
        )
    if room.game_state is not None:
        raise fastapi.HTTPException(status_code=400, detail='Game has already started')

    game_state = room_manager.room_manager.start_game(room)

    started_msg = ws_messages.GameStarted(
        player_names=[slot.name for slot in room.players],
        turn_order=list(range(len(room.players))),
    )
    await room_manager.room_manager.broadcast(room, started_msg.model_dump_json())

    state_update = ws_messages.GameStateUpdate(
        game_state=serializers.serialize_model(game_state)
    )
    await room_manager.room_manager.broadcast(room, state_update.model_dump_json())

    # Execute AI turns in the background to avoid blocking the HTTP response
    background_tasks.add_task(ws_handler.execute_ai_turns_if_needed, room)

    return {'status': 'started'}
