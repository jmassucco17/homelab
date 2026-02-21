"""Services for daily location tracking."""

import json
from datetime import UTC, date, datetime
from typing import Any, TypedDict

from geopy import geocoders  # pyright: ignore[reportMissingTypeStubs]
from sqlmodel import Session, select

from .models import DailyLocation

# Google Takeout exports location history as Semantic Location History JSON files.
# Download your data at https://takeout.google.com, choose "Location History (Timeline)",  # noqa: E501
# and look for files at:
#   Takeout/Location History (Timeline)/Semantic Location History/YYYY/YYYY_MONTH.json

geolocator = geocoders.Nominatim(user_agent='TravelLocationApp/1.0')


class _TakeoutLocation(TypedDict, total=False):
    latitudeE7: int
    longitudeE7: int


class _TakeoutDuration(TypedDict, total=False):
    startTimestamp: str


class _TakeoutPlaceVisit(TypedDict, total=False):
    location: _TakeoutLocation
    duration: _TakeoutDuration
    centerLatE7: int
    centerLngE7: int


class _TakeoutObject(TypedDict, total=False):
    placeVisit: _TakeoutPlaceVisit


class TakeoutData(TypedDict, total=False):
    timelineObjects: list[_TakeoutObject]


def parse_takeout_data(data: TakeoutData) -> list[tuple[date, float, float]]:
    """Parse a Google Takeout Semantic Location History JSON object.

    Returns a list of (date, latitude, longitude) tuples, one per place visit.
    Coordinates are extracted from the placeVisit's centerLatE7/centerLngE7
    fields (integers representing degrees × 10^7).

    Args:
        data: Parsed JSON from a Takeout Semantic Location History file.

    Returns:
        List of (date, lat, lon) tuples ordered by date ascending.
    """
    results: list[tuple[date, float, float]] = []
    for obj in data.get('timelineObjects', []):
        place_visit = obj.get('placeVisit')
        if place_visit is None:
            continue

        duration = place_visit.get('duration') or {}
        start_ts = duration.get('startTimestamp')
        if start_ts is None:
            continue

        try:
            visit_date = datetime.fromisoformat(start_ts.replace('Z', '+00:00')).date()
        except ValueError:
            continue

        # Prefer centerLatE7/centerLngE7; fall back to location.latitudeE7
        lat_e7: int | None = place_visit.get('centerLatE7')
        lon_e7: int | None = place_visit.get('centerLngE7')
        if lat_e7 is None or lon_e7 is None:
            location = place_visit.get('location') or {}
            lat_e7 = location.get('latitudeE7')
            lon_e7 = location.get('longitudeE7')

        if lat_e7 is None or lon_e7 is None:
            continue
        results.append((visit_date, lat_e7 / 1e7, lon_e7 / 1e7))

    results.sort(key=lambda t: t[0])
    return results


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


def import_takeout_file(session: Session, data: Any) -> list[DailyLocation]:
    """Parse a Google Takeout Semantic Location History file and upsert each day.

    For each unique calendar date, the first place visit encountered is used.
    Coordinates are reverse-geocoded to city/state/country via Nominatim.

    Args:
        session: Database session.
        data: Parsed JSON from a Takeout Semantic Location History file.

    Returns:
        List of DailyLocation records that were inserted or updated.
    """
    visits = parse_takeout_data(data)
    # Keep only the first visit per date (visits are sorted ascending).
    seen: set[date] = set()
    saved: list[DailyLocation] = []
    for visit_date, lat, lon in visits:
        if visit_date in seen:
            continue
        seen.add(visit_date)
        geo = reverse_geocode(lat, lon)
        loc = upsert_location(
            session,
            visit_date,
            lat,
            lon,
            city=geo.get('city'),
            state=geo.get('state'),
            country=geo.get('country'),
            country_code=geo.get('country_code'),
            raw_geocode=geo.get('raw'),
        )
        saved.append(loc)
    return saved


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
