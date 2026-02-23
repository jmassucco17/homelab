"""Snake game router."""

import pathlib

import fastapi
import fastapi.responses
import fastapi.templating

APP_DIR = pathlib.Path(__file__).resolve().parent.parent
templates = fastapi.templating.Jinja2Templates(directory=APP_DIR / 'templates')

router = fastapi.APIRouter()


@router.get('/snake', response_class=fastapi.responses.HTMLResponse)
async def snake(request: fastapi.Request) -> fastapi.responses.HTMLResponse:
    """Render the Snake game page."""
    return templates.TemplateResponse(request=request, name='snake.html.jinja2')
