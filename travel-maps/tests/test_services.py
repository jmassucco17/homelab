"""Tests for travel-maps service functions."""

import pytest
from sqlmodel import Session

from app import services
from app.models import Location, Map


def test_get_all_maps_empty(session: Session) -> None:
    """Test getting all maps when database is empty."""
    maps = services.get_all_maps(session)
    assert maps == []


def test_get_all_maps(session: Session) -> None:
    """Test getting all maps."""
    map1 = Map(name='Map 1')
    map2 = Map(name='Map 2')
    session.add(map1)
    session.add(map2)
    session.commit()

    maps = services.get_all_maps(session)
    assert len(maps) == 2


def test_get_map_by_id(session: Session) -> None:
    """Test getting a map by ID."""
    map_obj = Map(name='Test Map')
    session.add(map_obj)
    session.commit()
    session.refresh(map_obj)

    retrieved = services.get_map_by_id(session, map_obj.id)
    assert retrieved is not None
    assert retrieved.id == map_obj.id
    assert retrieved.name == 'Test Map'


def test_get_map_by_id_not_found(session: Session) -> None:
    """Test getting a non-existent map."""
    retrieved = services.get_map_by_id(session, 999)
    assert retrieved is None


def test_create_map(session: Session) -> None:
    """Test creating a new map."""
    map_obj = services.create_map(session, 'New Map', 'Description')

    assert map_obj.id is not None
    assert map_obj.name == 'New Map'
    assert map_obj.description == 'Description'


def test_create_map_without_description(session: Session) -> None:
    """Test creating a map without description."""
    map_obj = services.create_map(session, 'Simple Map')

    assert map_obj.id is not None
    assert map_obj.name == 'Simple Map'
    assert map_obj.description is None


def test_update_map(session: Session) -> None:
    """Test updating a map."""
    map_obj = services.create_map(session, 'Original Name')
    map_id = map_obj.id

    updated = services.update_map(session, map_id, 'New Name', 'New Description')

    assert updated is not None
    assert updated.id == map_id
    assert updated.name == 'New Name'
    assert updated.description == 'New Description'


def test_update_map_not_found(session: Session) -> None:
    """Test updating a non-existent map."""
    result = services.update_map(session, 999, 'Name')
    assert result is None


def test_delete_map(session: Session) -> None:
    """Test deleting a map."""
    map_obj = services.create_map(session, 'To Delete')
    map_id = map_obj.id

    success = services.delete_map(session, map_id)
    assert success is True

    # Verify it's deleted
    retrieved = services.get_map_by_id(session, map_id)
    assert retrieved is None


def test_delete_map_not_found(session: Session) -> None:
    """Test deleting a non-existent map."""
    success = services.delete_map(session, 999)
    assert success is False


def test_add_location_to_map(session: Session) -> None:
    """Test adding a location to a map."""
    map_obj = services.create_map(session, 'Map with Locations')

    location = services.add_location_to_map(
        session,
        map_obj.id,
        'Paris, France',
        48.8566,
        2.3522,
        'City of Light',
        'Beautiful city',
    )

    assert location is not None
    assert location.map_id == map_obj.id
    assert location.name == 'Paris, France'
    assert location.latitude == 48.8566
    assert location.longitude == 2.3522
    assert location.nickname == 'City of Light'
    assert location.description == 'Beautiful city'
    assert location.order_index == 0


def test_add_location_to_nonexistent_map(session: Session) -> None:
    """Test adding a location to a non-existent map."""
    location = services.add_location_to_map(session, 999, 'Paris', 48.8566, 2.3522)
    assert location is None


def test_add_multiple_locations_order(session: Session) -> None:
    """Test that multiple locations get correct order_index."""
    map_obj = services.create_map(session, 'Ordered Map')

    loc1 = services.add_location_to_map(session, map_obj.id, 'First', 0, 0)
    loc2 = services.add_location_to_map(session, map_obj.id, 'Second', 0, 0)
    loc3 = services.add_location_to_map(session, map_obj.id, 'Third', 0, 0)

    assert loc1.order_index == 0
    assert loc2.order_index == 1
    assert loc3.order_index == 2


def test_update_location(session: Session) -> None:
    """Test updating a location."""
    map_obj = services.create_map(session, 'Test Map')
    location = services.add_location_to_map(session, map_obj.id, 'Paris', 48.8566, 2.3522)

    updated = services.update_location(
        session, location.id, 'City of Light', 'Beautiful city'
    )

    assert updated is not None
    assert updated.nickname == 'City of Light'
    assert updated.description == 'Beautiful city'


def test_update_location_not_found(session: Session) -> None:
    """Test updating a non-existent location."""
    result = services.update_location(session, 999, 'Nickname')
    assert result is None


def test_delete_location(session: Session) -> None:
    """Test deleting a location."""
    map_obj = services.create_map(session, 'Test Map')
    location = services.add_location_to_map(session, map_obj.id, 'Paris', 48.8566, 2.3522)

    success = services.delete_location(session, location.id)
    assert success is True


def test_delete_location_not_found(session: Session) -> None:
    """Test deleting a non-existent location."""
    success = services.delete_location(session, 999)
    assert success is False


def test_reorder_locations(session: Session) -> None:
    """Test reordering locations."""
    map_obj = services.create_map(session, 'Test Map')

    loc1 = services.add_location_to_map(session, map_obj.id, 'First', 0, 0)
    loc2 = services.add_location_to_map(session, map_obj.id, 'Second', 0, 0)
    loc3 = services.add_location_to_map(session, map_obj.id, 'Third', 0, 0)

    # Reorder: 3, 1, 2
    success = services.reorder_locations(session, [loc3.id, loc1.id, loc2.id])
    assert success is True

    # Verify new order
    map_obj = services.get_map_by_id(session, map_obj.id)
    assert map_obj.locations[0].name == 'Third'
    assert map_obj.locations[1].name == 'First'
    assert map_obj.locations[2].name == 'Second'


# Note: Geocoding test would require pytest-asyncio and mocking
# Example test structure for future implementation:
# @pytest.mark.asyncio
# async def test_geocode_location():
#     from app.services import geocode_location
#     # Would need to mock httpx.AsyncClient to avoid actual API calls
#     # results = await geocode_location('Paris, France')
#     # assert isinstance(results, list)

