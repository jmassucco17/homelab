import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import database, routes

APP_DIR = pathlib.Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    database.create_db_and_tables()
    yield


app = FastAPI(title='Travel Maps', lifespan=lifespan)

app.mount('/static', StaticFiles(directory=APP_DIR / 'static'), name='static')

app.include_router(routes.router)


@app.get('/health')
async def health():
    """Health check endpoint."""
    return {'status': 'healthy'}
