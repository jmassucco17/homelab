"""FastAPI application for the tools sub-site."""

import pathlib

import fastapi
import fastapi.responses
import fastapi.staticfiles

import common.app
import common.templates

from .routers import movie_picker

APP_DIR = pathlib.Path(__file__).resolve().parent

app = common.app.create_app('Tools')

app.mount(
    '/static',
    fastapi.staticfiles.StaticFiles(directory=APP_DIR / 'static'),
    name='static',
)

templates = common.templates.make_templates(APP_DIR / 'templates')

app.include_router(movie_picker.router)


@app.get('/', response_class=fastapi.responses.HTMLResponse)
async def index(request: fastapi.Request) -> fastapi.responses.HTMLResponse:
    """Render the tools landing page."""
    return templates.TemplateResponse(request=request, name='index.html')
