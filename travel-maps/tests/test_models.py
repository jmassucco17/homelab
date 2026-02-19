"""Tests for travel-maps data models."""

import pytest
from sqlmodel import Session, select

from app.models import Location, Map


def test_map_creation(session: Session) -> None:
    """Test creating a map."""
    map_obj = Map(name='Test Map', description='A test map')
    session.add(map_obj)
    session.commit()
    session.refresh(map_obj)

    assert map_obj.id is not None
    assert map_obj.name == 'Test Map'
    assert map_obj.description == 'A test map'
    assert map_obj.created_at is not None
    assert map_obj.updated_at is not None


def test_map_without_description(session: Session) -> None:
    """Test creating a map without a description."""
    map_obj = Map(name='Simple Map')
    session.add(map_obj)
    session.commit()
    session.refresh(map_obj)

    assert map_obj.id is not None
    assert map_obj.name == 'Simple Map'
    assert map_obj.description is None


def test_location_creation(session: Session) -> None:
    """Test creating a location."""
    # First create a map
    map_obj = Map(name='Test Map')
    session.add(map_obj)
    session.commit()
    session.refresh(map_obj)

    # Create a location
    location = Location(
        map_id=map_obj.id,
        name='Paris, France',
        latitude=48.8566,
        longitude=2.3522,
        order_index=0,
        nickname='City of Light',
        description='Beautiful city',
    )
    session.add(location)
    session.commit()
    session.refresh(location)

    assert location.id is not None
    assert location.map_id == map_obj.id
    assert location.name == 'Paris, France'
    assert location.latitude == 48.8566
    assert location.longitude == 2.3522
    assert location.order_index == 0
    assert location.nickname == 'City of Light'
    assert location.description == 'Beautiful city'


def test_map_location_relationship(session: Session) -> None:
    """Test the relationship between maps and locations."""
    # Create a map
    map_obj = Map(name='Europe Trip')
    session.add(map_obj)
    session.commit()
    session.refresh(map_obj)

    # Add locations
    location1 = Location(
        map_id=map_obj.id,
        name='Paris, France',
        latitude=48.8566,
        longitude=2.3522,
        order_index=0,
    )
    location2 = Location(
        map_id=map_obj.id,
        name='Rome, Italy',
        latitude=41.9028,
        longitude=12.4964,
        order_index=1,
    )
    session.add(location1)
    session.add(location2)
    session.commit()

    # Refresh map to load locations
    session.refresh(map_obj)

    assert len(map_obj.locations) == 2
    assert map_obj.locations[0].name == 'Paris, France'
    assert map_obj.locations[1].name == 'Rome, Italy'


def test_cascade_delete(session: Session) -> None:
    """Test that deleting a map deletes its locations."""
    # Create a map with locations
    map_obj = Map(name='Test Map')
    session.add(map_obj)
    session.commit()
    session.refresh(map_obj)

    location = Location(
        map_id=map_obj.id,
        name='Paris, France',
        latitude=48.8566,
        longitude=2.3522,
        order_index=0,
    )
    session.add(location)
    session.commit()

    map_id = map_obj.id

    # Delete the map
    session.delete(map_obj)
    session.commit()

    # Verify locations are also deleted
    remaining_locations = session.exec(
        select(Location).where(Location.map_id == map_id)
    ).all()
    assert len(remaining_locations) == 0


def test_location_ordering(session: Session) -> None:
    """Test that locations are ordered by order_index."""
    map_obj = Map(name='Ordered Map')
    session.add(map_obj)
    session.commit()
    session.refresh(map_obj)

    # Add locations out of order
    location2 = Location(
        map_id=map_obj.id, name='Second', latitude=0, longitude=0, order_index=2
    )
    location1 = Location(
        map_id=map_obj.id, name='First', latitude=0, longitude=0, order_index=1
    )
    location3 = Location(
        map_id=map_obj.id, name='Third', latitude=0, longitude=0, order_index=3
    )

    session.add(location2)
    session.add(location1)
    session.add(location3)
    session.commit()

    # Refresh map
    session.refresh(map_obj)

    # Verify they are ordered correctly
    assert map_obj.locations[0].name == 'First'
    assert map_obj.locations[1].name == 'Second'
    assert map_obj.locations[2].name == 'Third'
