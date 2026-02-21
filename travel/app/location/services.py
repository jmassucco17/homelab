"""Services for daily location tracking."""

import json
import os
from datetime import UTC, date, datetime

import httpx
from geopy import geocoders  # pyright: ignore[reportMissingTypeStubs]
from sqlmodel import Session, select

from .models import DailyLocation

GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
GOOGLE_LOCATION_REFRESH_TOKEN = os.getenv('GOOGLE_LOCATION_REFRESH_TOKEN', '')

geolocator = geocoders.Nominatim(user_agent='TravelLocationApp/1.0')


def is_google_configured() -> bool:
    """Return True if Google OAuth credentials are configured."""
    return bool(
        GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_LOCATION_REFRESH_TOKEN
    )


async def get_google_access_token() -> str | None:
    """Exchange refresh token for an access token."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            'https://oauth2.googleapis.com/token',
            data={
                'client_id': GOOGLE_CLIENT_ID,
                'client_secret': GOOGLE_CLIENT_SECRET,
                'refresh_token': GOOGLE_LOCATION_REFRESH_TOKEN,
                'grant_type': 'refresh_token',
            },
        )
        response.raise_for_status()
        return str(response.json().get('access_token', ''))


async def fetch_coords_from_google(target_date: date) -> tuple[float, float] | None:
    """Fetch lat/lon for target_date from Google Maps Timeline API."""
    access_token = await get_google_access_token()
    if not access_token:
        return None
    start = f'{target_date.isoformat()}T00:00:00Z'
    end = f'{target_date.isoformat()}T23:59:59Z'
    async with httpx.AsyncClient() as client:
        response = await client.get(
            'https://timeline.googleapis.com/v1/users/me/timelineSegments',
            params={'startTime': start, 'endTime': end},
            headers={'Authorization': f'Bearer {access_token}'},
        )
        response.raise_for_status()
        data = response.json()
    for segment in data.get('timelineSegments', []):
        if 'placeVisit' in segment:
            loc = segment['placeVisit'].get('location', {})
            lat_e7 = loc.get('latitudeE7')
            lon_e7 = loc.get('longitudeE7')
            if lat_e7 is not None and lon_e7 is not None:
                return lat_e7 / 1e7, lon_e7 / 1e7
    return None


def reverse_geocode(lat: float, lon: float) -> dict[str, str | None]:
    """Reverse geocode coordinates to city/state/country via Nominatim."""
    try:
        result = geolocator.reverse(  # type: ignore[union-attr]
            f'{lat}, {lon}', exactly_one=True
        )
        if not result:
            return {}
        raw: dict[str, object] = result.raw  # type: ignore[union-attr]
        address: dict[str, str] = raw.get('address', {})  # type: ignore[assignment]
        city: str | None = (
            address.get('city')
            or address.get('town')
            or address.get('village')
            or address.get('county')
        )
        return {
            'city': city,
            'state': address.get('state'),
            'country': address.get('country'),
            'country_code': (address.get('country_code') or '').upper(),
            'raw': json.dumps(address),
        }
    except Exception:
        return {}


def get_all_locations(session: Session) -> list[DailyLocation]:
    """Return all daily locations ordered newest first."""
    return list(
        session.exec(select(DailyLocation).order_by(DailyLocation.date.desc())).all()  # type: ignore[attr-defined]
    )


def get_location_by_date(session: Session, target_date: date) -> DailyLocation | None:
    """Return the cached location for a specific date, or None."""
    return session.exec(
        select(DailyLocation).where(DailyLocation.date == target_date)
    ).first()


def upsert_location(
    session: Session,
    target_date: date,
    latitude: float,
    longitude: float,
    city: str | None = None,
    state: str | None = None,
    country: str | None = None,
    country_code: str | None = None,
    raw_geocode: str | None = None,
) -> DailyLocation:
    """Insert or replace a location record for the given date."""
    existing = get_location_by_date(session, target_date)
    if existing:
        existing.latitude = latitude
        existing.longitude = longitude
        existing.city = city
        existing.state = state
        existing.country = country
        existing.country_code = country_code
        existing.raw_geocode = raw_geocode
        existing.fetched_at = datetime.now(UTC)
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    loc = DailyLocation(
        date=target_date,
        latitude=latitude,
        longitude=longitude,
        city=city,
        state=state,
        country=country,
        country_code=country_code,
        raw_geocode=raw_geocode,
    )
    session.add(loc)
    session.commit()
    session.refresh(loc)
    return loc


async def refresh_today(session: Session) -> DailyLocation | None:
    """Fetch today's location from Google and cache it.

    Returns None if not configured.
    """
    if not is_google_configured():
        return None
    today = datetime.now(UTC).date()
    coords = await fetch_coords_from_google(today)
    if not coords:
        return None
    lat, lon = coords
    geo = reverse_geocode(lat, lon)
    return upsert_location(
        session,
        today,
        lat,
        lon,
        city=geo.get('city'),
        state=geo.get('state'),
        country=geo.get('country'),
        country_code=geo.get('country_code'),
        raw_geocode=geo.get('raw'),
    )


def location_display_label(loc: DailyLocation, mode: str) -> str:
    """Return a human-readable label for a location given the view mode."""
    if mode == 'country':
        if loc.country_code == 'US' and loc.state:
            return loc.state
        return loc.country or 'Unknown'
    # city mode
    parts: list[str] = []
    if loc.city:
        parts.append(loc.city)
    if loc.country:
        parts.append(loc.country)
    return ', '.join(parts) if parts else 'Unknown'


def group_locations(
    locations: list[DailyLocation], mode: str
) -> list[dict[str, object]]:
    """Group consecutive same-label locations into summary rows."""
    groups: list[dict[str, object]] = []
    current_label: str | None = None
    current_group: dict[str, object] | None = None

    for loc in locations:
        label = location_display_label(loc, mode)
        if label != current_label:
            if current_group is not None:
                groups.append(current_group)
            current_label = label
            current_group = {
                'label': label,
                'to_date': loc.date,
                'from_date': loc.date,
                'days': 1,
                'latest': loc,
            }
        else:
            assert current_group is not None
            current_group['from_date'] = loc.date
            days = current_group['days']
            assert isinstance(days, int)
            current_group['days'] = days + 1

    if current_group is not None:
        groups.append(current_group)

    return groups
