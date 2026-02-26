"""FastAPI application for the tools sub-site."""

import pathlib

import fastapi
import fastapi.responses
import fastapi.staticfiles
import fastapi.templating

import common.log
import common.settings

from .routers import movie_picker

APP_DIR = pathlib.Path(__file__).resolve().parent

app = fastapi.FastAPI(title='Tools')

common.log.configure_logging()

app.mount(
    '/static',
    fastapi.staticfiles.StaticFiles(directory=APP_DIR / 'static'),
    name='static',
)

templates = fastapi.templating.Jinja2Templates(directory=APP_DIR / 'templates')
templates.env.globals['domain'] = common.settings.DOMAIN  # type: ignore[reportUnknownMemberType]
templates.env.globals['home_url'] = common.settings.HOME_URL  # type: ignore[reportUnknownMemberType]

app.include_router(movie_picker.router)


@app.get('/', response_class=fastapi.responses.HTMLResponse)
async def index(request: fastapi.Request) -> fastapi.responses.HTMLResponse:
    """Render the tools landing page."""
    return templates.TemplateResponse(request=request, name='index.html')


@app.api_route('/health', methods=['GET', 'HEAD'])
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {'status': 'healthy'}
