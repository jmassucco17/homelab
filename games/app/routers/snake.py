"""Snake game router."""

import fastapi
import fastapi.responses

from .. import templates as tmpl

templates = tmpl.templates

router = fastapi.APIRouter()


@router.get('/snake', response_class=fastapi.responses.HTMLResponse)
async def snake(request: fastapi.Request) -> fastapi.responses.HTMLResponse:
    """Render the Snake game page."""
    return templates.TemplateResponse(request=request, name='snake.html.jinja2')
