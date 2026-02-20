"""Combined travel application - landing, photos, and maps."""

import os
import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import Response

from travel.maps.app import database as maps_db
from travel.maps.app import routes as maps_routes
from travel.photos.app import database as photos_db
from travel.photos.app import routes as photos_routes

APP_DIR = pathlib.Path(__file__).resolve().parent
LANDING_DIR = APP_DIR.parent / 'landing' / 'app'
PHOTOS_DIR = APP_DIR.parent / 'photos' / 'app'
MAPS_DIR = APP_DIR.parent / 'maps' / 'app'


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize databases on startup."""
    photos_db.create_db_and_tables()
    maps_db.create_db_and_tables()
    yield


app = FastAPI(title='Travel', lifespan=lifespan)

# Static files
app.mount('/static', StaticFiles(directory=LANDING_DIR / 'static'), name='static')
app.mount(
    '/photos/assets', StaticFiles(directory=PHOTOS_DIR / 'static'), name='photos-assets'
)
app.mount(
    '/maps/static', StaticFiles(directory=MAPS_DIR / 'static'), name='maps-static'
)

# Photos uploads (if available)
data_dir = os.environ.get('DATA_DIR', 'data')
uploads_dir = os.path.join(data_dir, 'uploads')
if os.path.exists(uploads_dir):
    app.mount(
        '/photos/uploads', StaticFiles(directory=uploads_dir), name='photos-uploads'
    )

# Templates
landing_templates = Jinja2Templates(directory=str(LANDING_DIR / 'templates'))
photos_templates = Jinja2Templates(directory=str(PHOTOS_DIR / 'templates'))

# Include sub-app routers with path prefixes
app.include_router(photos_routes.admin_router, prefix='/photos')
app.include_router(photos_routes.public_router, prefix='/photos')
app.include_router(maps_routes.router, prefix='/maps')


@app.get('/', response_class=HTMLResponse)
async def landing_index(request: Request) -> Response:
    """Landing page with links to photos and maps."""
    return landing_templates.TemplateResponse(request=request, name='index.html.jinja2')


@app.get('/photos', response_class=HTMLResponse)
async def photos_index(request: Request) -> Response:
    """Photos home - interactive map view."""
    return photos_templates.TemplateResponse(
        request=request, name='public/map.html.jinja2'
    )


@app.get('/photos/gallery', response_class=HTMLResponse)
async def photos_gallery(request: Request) -> Response:
    """Photos gallery view."""
    return photos_templates.TemplateResponse(
        request=request, name='public/gallery.html.jinja2'
    )


@app.get('/photos/admin', response_class=HTMLResponse)
async def photos_admin_view(request: Request) -> Response:
    """Photos admin interface."""
    return photos_templates.TemplateResponse(
        request=request, name='admin/upload.html.jinja2'
    )


@app.api_route('/health', methods=['GET', 'HEAD'])
async def health_check():
    """Health check endpoint."""
    return {'status': 'healthy'}
