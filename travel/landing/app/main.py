"""Travel landing page application."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import Response

APP_DIR = Path(__file__).parent

app = FastAPI(title='Travel')

# Mount static files
app.mount('/static', StaticFiles(directory=APP_DIR / 'static'), name='static')

# Templates
templates = Jinja2Templates(directory=str(APP_DIR / 'templates'))


@app.get('/', response_class=HTMLResponse)
async def index(request: Request) -> Response:
    """Landing page with links to photos and maps."""
    return templates.TemplateResponse(request=request, name='index.html.jinja2')


@app.api_route('/health', methods=['GET', 'HEAD'])
async def health_check():
    """Health check endpoint."""
    return {'status': 'healthy'}
