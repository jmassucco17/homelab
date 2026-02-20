"""Pong game router."""

import pathlib

import fastapi
import fastapi.responses
import fastapi.templating

APP_DIR = pathlib.Path(__file__).resolve().parent.parent
templates = fastapi.templating.Jinja2Templates(directory=APP_DIR / 'templates')

router = fastapi.APIRouter()


@router.get('/pong', response_class=fastapi.responses.HTMLResponse)
async def pong(request: fastapi.Request) -> fastapi.responses.HTMLResponse:
    """Render the Pong game page."""
    return templates.TemplateResponse(request=request, name='pong.html')
