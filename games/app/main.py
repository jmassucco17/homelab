"""FastAPI application for the games sub-site."""

import logging
import os
import pathlib

import fastapi
import fastapi.responses
import fastapi.staticfiles
import fastapi.templating

from .routers import catan, pong, snake

APP_DIR = pathlib.Path(__file__).resolve().parent

DOMAIN = os.environ.get('DOMAIN', 'jamesmassucco.com')

logging.basicConfig(level=logging.INFO)

app = fastapi.FastAPI(title='Games')


class HealthCheckFilter(logging.Filter):
    """Filter out health check requests from uvicorn access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Return False to suppress health check log entries."""
        return '/health' not in record.getMessage()


logging.getLogger('uvicorn.access').addFilter(HealthCheckFilter())

app.mount(
    '/static',
    fastapi.staticfiles.StaticFiles(directory=APP_DIR / 'static'),
    name='static',
)

templates = fastapi.templating.Jinja2Templates(directory=APP_DIR / 'templates')
templates.env.globals['domain'] = DOMAIN  # type: ignore[reportUnknownMemberType]

app.include_router(snake.router)
app.include_router(pong.router)
app.include_router(catan.router)


@app.get('/', response_class=fastapi.responses.HTMLResponse)
async def index(request: fastapi.Request) -> fastapi.responses.HTMLResponse:
    """Render the games landing page."""
    return templates.TemplateResponse(request=request, name='index.html.jinja2')


@app.api_route('/health', methods=['GET', 'HEAD'])
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {'status': 'healthy'}
