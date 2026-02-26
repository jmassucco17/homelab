"""Snake game router."""

import pathlib

import fastapi
import fastapi.responses

import common.app

_APP_DIR = pathlib.Path(__file__).resolve().parent.parent
templates = common.app.make_templates(_APP_DIR / 'templates')

router = fastapi.APIRouter()


@router.get('/snake', response_class=fastapi.responses.HTMLResponse)
async def snake(request: fastapi.Request) -> fastapi.responses.HTMLResponse:
    """Render the Snake game page."""
    return templates.TemplateResponse(request=request, name='snake.html.jinja2')
