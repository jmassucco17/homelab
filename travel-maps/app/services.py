from datetime import UTC, datetime

import httpx
from app.models import Location, Map
from sqlmodel import Session, select


async def geocode_location(query: str) -> list[dict]:
    """
    Search for locations using Nominatim geocoding API.

    Args:
        query: Search query string

    Returns:
        List of location results with name, lat, lon
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            'https://nominatim.openstreetmap.org/search',
            params={'q': query, 'format': 'json', 'limit': 5},
            headers={'User-Agent': 'TravelMapsApp/1.0'},
        )
        response.raise_for_status()
        results = response.json()

        return [
            {
                'name': result.get('display_name'),
                'latitude': float(result.get('lat')),
                'longitude': float(result.get('lon')),
            }
            for result in results
        ]


def get_all_maps(session: Session) -> list[Map]:
    """Get all maps."""
    return session.exec(select(Map).order_by(Map.updated_at.desc())).all()


def get_map_by_id(session: Session, map_id: int) -> Map | None:
    """Get a map by ID."""
    return session.get(Map, map_id)


def create_map(session: Session, name: str, description: str | None = None) -> Map:
    """Create a new map."""
    map_obj = Map(name=name, description=description)
    session.add(map_obj)
    session.commit()
    session.refresh(map_obj)
    return map_obj


def update_map(
    session: Session, map_id: int, name: str, description: str | None = None
) -> Map | None:
    """Update an existing map."""
    map_obj = session.get(Map, map_id)
    if not map_obj:
        return None

    map_obj.name = name
    map_obj.description = description
    map_obj.updated_at = datetime.now(UTC)
    session.add(map_obj)
    session.commit()
    session.refresh(map_obj)
    return map_obj


def delete_map(session: Session, map_id: int) -> bool:
    """Delete a map and all its locations."""
    map_obj = session.get(Map, map_id)
    if not map_obj:
        return False

    session.delete(map_obj)
    session.commit()
    return True


def add_location_to_map(
    session: Session,
    map_id: int,
    name: str,
    latitude: float,
    longitude: float,
    nickname: str | None = None,
    description: str | None = None,
) -> Location | None:
    """Add a location to a map."""
    map_obj = session.get(Map, map_id)
    if not map_obj:
        return None

    max_order = session.exec(
        select(Location.order_index)
        .where(Location.map_id == map_id)
        .order_by(Location.order_index.desc())
    ).first()
    order_index = (max_order + 1) if max_order is not None else 0

    location = Location(
        map_id=map_id,
        name=name,
        latitude=latitude,
        longitude=longitude,
        nickname=nickname,
        description=description,
        order_index=order_index,
    )
    session.add(location)

    map_obj.updated_at = datetime.now(UTC)
    session.add(map_obj)

    session.commit()
    session.refresh(location)
    return location


def update_location(
    session: Session,
    location_id: int,
    nickname: str | None = None,
    description: str | None = None,
) -> Location | None:
    """Update a location's nickname and description."""
    location = session.get(Location, location_id)
    if not location:
        return None

    location.nickname = nickname
    location.description = description
    session.add(location)

    map_obj = session.get(Map, location.map_id)
    if map_obj:
        map_obj.updated_at = datetime.now(UTC)
        session.add(map_obj)

    session.commit()
    session.refresh(location)
    return location


def delete_location(session: Session, location_id: int) -> bool:
    """Delete a location from a map."""
    location = session.get(Location, location_id)
    if not location:
        return False

    map_id = location.map_id
    session.delete(location)

    map_obj = session.get(Map, map_id)
    if map_obj:
        map_obj.updated_at = datetime.now(UTC)
        session.add(map_obj)

    session.commit()
    return True


def reorder_locations(session: Session, location_ids: list[int]) -> bool:
    """Reorder locations based on provided list of IDs."""
    for index, location_id in enumerate(location_ids):
        location = session.get(Location, location_id)
        if location:
            location.order_index = index
            session.add(location)

            if index == 0:
                map_obj = session.get(Map, location.map_id)
                if map_obj:
                    map_obj.updated_at = datetime.now(UTC)
                    session.add(map_obj)

    session.commit()
    return True
