"""HTTP routes for the Catan game sub-section.

Registers:

* ``GET  /catan``                      — lobby/landing page
* ``POST /catan/rooms``                — create a new game room
* ``GET  /catan/rooms/{room_code}``    — room status
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

from ..catan.models.serializers import serialize_model
from ..catan.models.ws_messages import GameStarted, GameStateUpdate
from ..catan.server import ws_handler
from ..catan.server.room_manager import room_manager

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
    return templates.TemplateResponse(request=request, name='catan_lobby.html')


@router.post('/catan/rooms', response_model=RoomCreatedResponse)
async def create_room() -> RoomCreatedResponse:
    """Create a new game room and return its 4-character code."""
    code = room_manager.create_room()
    return RoomCreatedResponse(room_code=code)


@router.get('/catan/rooms/{room_code}', response_model=RoomStatusResponse)
async def room_status(room_code: str) -> RoomStatusResponse:
    """Return the current status of a game room."""
    room = room_manager.get_room(room_code)
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


@router.post('/catan/rooms/{room_code}/start')
async def start_game(room_code: str) -> dict[str, str]:
    """Start the game for a room.

    Requires at least 2 players.  Broadcasts :class:`GameStarted` followed
    by the initial :class:`GameStateUpdate` to every connected client.
    """
    room = room_manager.get_room(room_code)
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

    game_state = room_manager.start_game(room)

    started_msg = GameStarted(
        player_names=[slot.name for slot in room.players],
        turn_order=list(range(len(room.players))),
    )
    await room_manager.broadcast(room, started_msg.model_dump_json())

    state_update = GameStateUpdate(game_state=serialize_model(game_state))
    await room_manager.broadcast(room, state_update.model_dump_json())

    return {'status': 'started'}
