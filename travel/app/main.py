"""Combined travel application - landing, photos, and maps."""

import contextlib
import logging
import os
import pathlib
from collections.abc import AsyncGenerator

import fastapi
import fastapi.responses
import fastapi.staticfiles
import fastapi.templating

from travel.app.maps import database as maps_db
from travel.app.maps import routes as maps_routes
from travel.app.photos import database as photos_db
from travel.app.photos import routes as photos_routes

APP_DIR = pathlib.Path(__file__).resolve().parent

DOMAIN = os.environ.get('DOMAIN', '.jamesmassucco.com')
HOME_URL = 'https://' + DOMAIN[1:]


class HealthCheckFilter(logging.Filter):
    """Filter out health check requests from uvicorn access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Return False to suppress health check log entries."""
        return '/health' not in record.getMessage()


logging.getLogger('uvicorn.access').addFilter(HealthCheckFilter())


@contextlib.asynccontextmanager
async def lifespan(app: fastapi.FastAPI) -> AsyncGenerator[None, None]:
    """Initialize databases on startup."""
    photos_db.create_db_and_tables()
    maps_db.create_db_and_tables()
    yield


app = fastapi.FastAPI(title='Travel', lifespan=lifespan)

# Static files - single mount covering all CSS and JS
app.mount(
    '/static',
    fastapi.staticfiles.StaticFiles(directory=APP_DIR / 'static'),
    name='static',
)

# Photos uploads (if available)
data_dir = os.environ.get('DATA_DIR', 'data')
uploads_dir = os.path.join(data_dir, 'uploads')
if os.path.exists(uploads_dir):
    app.mount(
        '/photos/uploads',
        fastapi.staticfiles.StaticFiles(directory=uploads_dir),
        name='photos-uploads',
    )

# Templates
templates = fastapi.templating.Jinja2Templates(directory=str(APP_DIR / 'templates'))
templates.env.globals['domain'] = DOMAIN  # type: ignore[reportUnknownMemberType]
templates.env.globals['home_url'] = HOME_URL  # type: ignore[reportUnknownMemberType]

# Include sub-app routers with path prefixes
app.include_router(photos_routes.admin_router, prefix='/photos')
app.include_router(photos_routes.public_router, prefix='/photos')
app.include_router(maps_routes.router, prefix='/maps')


@app.get('/', response_class=fastapi.responses.HTMLResponse)
async def landing_index(request: fastapi.Request) -> fastapi.responses.Response:
    """Landing page with links to photos and maps."""
    return templates.TemplateResponse(request=request, name='index.html.jinja2')


@app.get('/photos', response_class=fastapi.responses.HTMLResponse)
async def photos_index(request: fastapi.Request) -> fastapi.responses.Response:
    """Photos home - interactive map view."""
    return templates.TemplateResponse(request=request, name='public/map.html.jinja2')


@app.get('/photos/gallery', response_class=fastapi.responses.HTMLResponse)
async def photos_gallery(request: fastapi.Request) -> fastapi.responses.Response:
    """Photos gallery view."""
    return templates.TemplateResponse(
        request=request, name='public/gallery.html.jinja2'
    )


@app.get('/photos/admin', response_class=fastapi.responses.HTMLResponse)
async def photos_admin_view(request: fastapi.Request) -> fastapi.responses.Response:
    """Photos admin interface."""
    return templates.TemplateResponse(request=request, name='admin/upload.html.jinja2')


@app.api_route('/health', methods=['GET', 'HEAD'])
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {'status': 'healthy'}
