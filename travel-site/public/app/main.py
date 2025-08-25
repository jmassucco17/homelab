import contextlib
from collections.abc import Generator
from typing import Annotated

import fastapi
import uvicorn
from app import database
from fastapi import responses, templating


@contextlib.asynccontextmanager
async def db_lifespan(app: fastapi.FastAPI):
    """Lifespan function for database (read-only)"""
    # Just ensure database exists, don't keep persistent session
    database.start_db().close()
    yield


def get_db() -> Generator[database.ReadOnlySession, None, None]:
    """Create a fresh database session for each request"""
    session = database.start_db()
    try:
        yield session
    finally:
        session.close()


DatabaseSession = Annotated[
    database.ReadOnlySession,
    fastapi.Depends(get_db),
]

# Create app
app = fastapi.FastAPI(title='Travel Calendar Public View', lifespan=db_lifespan)
templates = templating.Jinja2Templates(directory='app/templates')


@app.get('/health')
def health_check():
    """Health check endpoint"""
    return {'status': 'healthy', 'service': 'travel-calendar-public'}


@app.get('/', response_class=responses.HTMLResponse)
def public_calendar(
    request: fastapi.Request, db: DatabaseSession
) -> responses.HTMLResponse:
    """Public calendar view of all trips"""
    trips = db.query(database.Trip).all()  # type: ignore
    return templates.TemplateResponse(
        'calendar.html.jinja2',
        {'request': request, 'trips': trips},
    )


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
