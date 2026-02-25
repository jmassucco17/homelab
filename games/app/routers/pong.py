"""Pong game router."""

import fastapi
import fastapi.responses

from .. import templates as tmpl

templates = tmpl.templates

router = fastapi.APIRouter()


@router.get('/pong', response_class=fastapi.responses.HTMLResponse)
async def pong(request: fastapi.Request) -> fastapi.responses.HTMLResponse:
    """Render the Pong game page."""
    return templates.TemplateResponse(request=request, name='pong.html.jinja2')
