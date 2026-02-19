"""FastAPI application for the games sub-site."""

import pathlib

import fastapi
import fastapi.responses
import fastapi.staticfiles
import fastapi.templating

from .routers import snake

APP_DIR = pathlib.Path(__file__).resolve().parent

app = fastapi.FastAPI(title='Games')

app.mount(
    '/static',
    fastapi.staticfiles.StaticFiles(directory=APP_DIR / 'static'),
    name='static',
)

templates = fastapi.templating.Jinja2Templates(directory=APP_DIR / 'templates')

app.include_router(snake.router)


@app.get('/', response_class=fastapi.responses.HTMLResponse)
async def index(request: fastapi.Request) -> fastapi.responses.HTMLResponse:
    """Render the games landing page."""
    return templates.TemplateResponse(request=request, name='index.html')


@app.api_route('/health', methods=['GET', 'HEAD'])
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {'status': 'healthy'}
