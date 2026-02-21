"""Catan game router.

Serves the lobby and game pages, and provides HTTP endpoints for room
management.  The WebSocket connection endpoint will be added in Phase 5
(catan-server-agent) on top of this file.
"""

import pathlib
import secrets
import string

import fastapi
import fastapi.responses
import fastapi.templating

APP_DIR = pathlib.Path(__file__).resolve().parent.parent
templates = fastapi.templating.Jinja2Templates(directory=APP_DIR / 'templates')

router = fastapi.APIRouter()


@router.get('/catan', response_class=fastapi.responses.HTMLResponse)
async def catan_lobby(request: fastapi.Request) -> fastapi.responses.HTMLResponse:
    """Render the Catan lobby / landing page."""
    return templates.TemplateResponse(request=request, name='catan_lobby.html')


@router.get('/catan/game', response_class=fastapi.responses.HTMLResponse)
async def catan_game(request: fastapi.Request) -> fastapi.responses.HTMLResponse:
    """Render the Catan in-game page."""
    return templates.TemplateResponse(request=request, name='catan_game.html')


@router.post('/catan/rooms')
async def create_room() -> dict[str, str]:
    """Create a new game room and return a 4-character room code.

    The in-memory room registry lives in the WebSocket server (Phase 5).
    This endpoint generates a code that the lobby can use immediately;
    the full room state is created when the first WebSocket client connects.
    """
    code = ''.join(secrets.choice(string.ascii_uppercase) for _ in range(4))
    return {'room_code': code}


@router.get('/catan/rooms/{room_code}')
async def get_room(room_code: str) -> dict[str, str | int]:
    """Return basic room status.

    Returns a minimal response until Phase 5 integrates the live room
    manager.
    """
    return {
        'room_code': room_code.upper(),
        'player_count': 0,
        'phase': 'waiting',
    }
