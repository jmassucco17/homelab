"""FastAPI application for the games sub-site."""

import logging
import pathlib

import fastapi
import fastapi.responses
import fastapi.staticfiles

import common.app

from . import templates as tmpl
from .routers import catan, pong, snake

APP_DIR = pathlib.Path(__file__).resolve().parent

logging.basicConfig(level=logging.INFO)

# Enable debug-level audit logging for the Catan engine
logging.getLogger('games.app.catan').setLevel(logging.DEBUG)

app = common.app.create_app('Games')

app.mount(
    '/static',
    fastapi.staticfiles.StaticFiles(directory=APP_DIR / 'static'),
    name='static',
)

templates = tmpl.templates

app.include_router(snake.router)
app.include_router(pong.router)
app.include_router(catan.router)


@app.get('/', response_class=fastapi.responses.HTMLResponse)
async def index(request: fastapi.Request) -> fastapi.responses.HTMLResponse:
    """Render the games landing page."""
    return templates.TemplateResponse(request=request, name='index.html.jinja2')
