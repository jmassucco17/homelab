"""Combined travel application - landing, photos, and maps."""

import os
import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import Response

from travel.app.maps import database as maps_db
from travel.app.maps import routes as maps_routes
from travel.app.photos import database as photos_db
from travel.app.photos import routes as photos_routes

APP_DIR = pathlib.Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize databases on startup."""
    photos_db.create_db_and_tables()
    maps_db.create_db_and_tables()
    yield


app = FastAPI(title='Travel', lifespan=lifespan)

# Static files - single mount covering all CSS and JS
app.mount('/static', StaticFiles(directory=APP_DIR / 'static'), name='static')

# Photos uploads (if available)
data_dir = os.environ.get('DATA_DIR', 'data')
uploads_dir = os.path.join(data_dir, 'uploads')
if os.path.exists(uploads_dir):
    app.mount(
        '/photos/uploads', StaticFiles(directory=uploads_dir), name='photos-uploads'
    )

# Templates
templates = Jinja2Templates(directory=str(APP_DIR / 'templates'))

# Include sub-app routers with path prefixes
app.include_router(photos_routes.admin_router, prefix='/photos')
app.include_router(photos_routes.public_router, prefix='/photos')
app.include_router(maps_routes.router, prefix='/maps')


@app.get('/', response_class=HTMLResponse)
async def landing_index(request: Request) -> Response:
    """Landing page with links to photos and maps."""
    return templates.TemplateResponse(request=request, name='index.html.jinja2')


@app.get('/photos', response_class=HTMLResponse)
async def photos_index(request: Request) -> Response:
    """Photos home - interactive map view."""
    return templates.TemplateResponse(request=request, name='public/map.html.jinja2')


@app.get('/photos/gallery', response_class=HTMLResponse)
async def photos_gallery(request: Request) -> Response:
    """Photos gallery view."""
    return templates.TemplateResponse(
        request=request, name='public/gallery.html.jinja2'
    )


@app.get('/photos/admin', response_class=HTMLResponse)
async def photos_admin_view(request: Request) -> Response:
    """Photos admin interface."""
    return templates.TemplateResponse(request=request, name='admin/upload.html.jinja2')


@app.api_route('/health', methods=['GET', 'HEAD'])
async def health_check():
    """Health check endpoint."""
    return {'status': 'healthy'}
