"""Main FastAPI application for the travel picture site."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import database, routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the database on startup."""

    database.create_db_and_tables()
    yield


# Create FastAPI app
app = FastAPI(
    title='Travel Picture Site',
    description='A picture-focused travel site',
    lifespan=lifespan,
)

# Include routers
app.include_router(routes.admin_router)
app.include_router(routes.public_router)

# Mount static files for CSS and other assets
app.mount('/assets', StaticFiles(directory='app/static'), name='assets')

# Mount uploaded pictures
data_dir = os.environ.get('DATA_DIR', 'data')
uploads_dir = os.path.join(data_dir, 'uploads')
if os.path.exists(uploads_dir):
    app.mount('/uploads', StaticFiles(directory=uploads_dir), name='uploads')

# Setup templates
templates = Jinja2Templates(directory='app/templates')


@app.get('/', response_class=HTMLResponse)
async def root(request: Request):
    """Root endpoint - serve the public gallery."""
    return templates.TemplateResponse(
        'public/gallery.html.jinja2',
        {'request': request},
    )


@app.get('/admin', response_class=HTMLResponse)
async def admin_root(request: Request):
    """Admin root endpoint - serve the admin upload interface."""
    return templates.TemplateResponse(
        'admin/upload.html.jinja2',
        {'request': request},
    )


@app.get('/health')
async def health_check():
    """Health check endpoint."""
    return {'status': 'healthy'}
