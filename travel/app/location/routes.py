"""Routes for daily location tracking."""

import pathlib
from datetime import UTC, datetime
from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlmodel import Session

from . import services
from .database import get_session

APP_DIR = pathlib.Path(__file__).resolve().parent

router = APIRouter()
templates = Jinja2Templates(directory=APP_DIR / 'templates')


class LocationCreate(BaseModel):
    date: str  # ISO format: YYYY-MM-DD
    latitude: float
    longitude: float


@router.get('/', response_class=HTMLResponse)
async def location_index(
    request: Request,
    mode: str = 'city',
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Location tracking page showing current position and history."""
    all_locations = services.get_all_locations(session)
    today = datetime.now(UTC).date()
    current = services.get_location_by_date(session, today)
    groups = services.group_locations(all_locations, mode)
    return templates.TemplateResponse(
        request=request,
        name='location.html.jinja2',
        context={
            'current': current,
            'groups': groups,
            'all_locations': all_locations,
            'mode': mode,
            'configured': services.is_google_configured(),
            'today': today,
        },
    )


@router.post('/api/refresh')
async def refresh_location(
    session: Session = Depends(get_session),
) -> dict[str, object]:
    """Trigger a fresh fetch of today's location from Google Maps."""
    loc = await services.refresh_today(session)
    if loc is None:
        raise HTTPException(
            status_code=503, detail='Google Maps not configured or no data'
        )
    return {
        'date': loc.date.isoformat(),
        'city': loc.city,
        'state': loc.state,
        'country': loc.country,
        'latitude': loc.latitude,
        'longitude': loc.longitude,
    }


@router.post('/api/locations')
async def add_location(
    data: LocationCreate, session: Session = Depends(get_session)
) -> dict[str, object]:
    """Manually add or update a location for a given date."""
    try:
        target_date = date_type.fromisoformat(data.date)
    except ValueError:
        raise HTTPException(status_code=400, detail='Invalid date format') from None
    geo = services.reverse_geocode(data.latitude, data.longitude)
    loc = services.upsert_location(
        session,
        target_date,
        data.latitude,
        data.longitude,
        city=geo.get('city'),
        state=geo.get('state'),
        country=geo.get('country'),
        country_code=geo.get('country_code'),
        raw_geocode=geo.get('raw'),
    )
    return {
        'id': loc.id,
        'date': loc.date.isoformat(),
        'city': loc.city,
        'state': loc.state,
        'country': loc.country,
        'latitude': loc.latitude,
        'longitude': loc.longitude,
    }
