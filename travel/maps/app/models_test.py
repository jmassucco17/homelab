"""Unit tests for travel-maps data models."""

import unittest

import sqlalchemy
import sqlalchemy.pool
import sqlmodel
from app import models


def make_in_memory_engine() -> sqlalchemy.Engine:
    """Create an in-memory SQLite engine for testing."""
    engine = sqlmodel.create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=sqlalchemy.pool.StaticPool,
    )
    sqlmodel.SQLModel.metadata.create_all(engine)
    return engine


class TestMapModel(unittest.TestCase):
    """Tests for Map model."""

    def setUp(self) -> None:
        """Set up test database."""
        self.engine = make_in_memory_engine()

    def test_map_creation(self) -> None:
        """Test creating a map."""
        with sqlmodel.Session(self.engine) as session:
            map_obj = models.Map(name='Test Map', description='A test map')
            session.add(map_obj)
            session.commit()
            session.refresh(map_obj)

            self.assertIsNotNone(map_obj.id)
            self.assertEqual(map_obj.name, 'Test Map')
            self.assertEqual(map_obj.description, 'A test map')
            self.assertIsNotNone(map_obj.created_at)
            self.assertIsNotNone(map_obj.updated_at)

    def test_map_without_description(self) -> None:
        """Test creating a map without a description."""
        with sqlmodel.Session(self.engine) as session:
            map_obj = models.Map(name='Simple Map')
            session.add(map_obj)
            session.commit()
            session.refresh(map_obj)

            self.assertIsNotNone(map_obj.id)
            self.assertEqual(map_obj.name, 'Simple Map')
            self.assertIsNone(map_obj.description)


class TestLocationModel(unittest.TestCase):
    """Tests for Location model."""

    def setUp(self) -> None:
        """Set up test database."""
        self.engine = make_in_memory_engine()

    def test_location_creation(self) -> None:
        """Test creating a location."""
        with sqlmodel.Session(self.engine) as session:
            # First create a map
            map_obj = models.Map(name='Test Map')
            session.add(map_obj)
            session.commit()
            session.refresh(map_obj)
            assert map_obj.id is not None

            # Create a location
            location = models.Location(
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

            self.assertIsNotNone(location.id)
            self.assertEqual(location.map_id, map_obj.id)
            self.assertEqual(location.name, 'Paris, France')
            self.assertEqual(location.latitude, 48.8566)
            self.assertEqual(location.longitude, 2.3522)
            self.assertEqual(location.order_index, 0)
            self.assertEqual(location.nickname, 'City of Light')
            self.assertEqual(location.description, 'Beautiful city')


class TestMapLocationRelationship(unittest.TestCase):
    """Tests for Map-Location relationships."""

    def setUp(self) -> None:
        """Set up test database."""
        self.engine = make_in_memory_engine()

    def test_map_location_relationship(self) -> None:
        """Test the relationship between maps and locations."""
        with sqlmodel.Session(self.engine) as session:
            # Create a map
            map_obj = models.Map(name='Europe Trip')
            session.add(map_obj)
            session.commit()
            session.refresh(map_obj)
            assert map_obj.id is not None

            # Add locations
            location1 = models.Location(
                map_id=map_obj.id,
                name='Paris, France',
                latitude=48.8566,
                longitude=2.3522,
                order_index=0,
            )
            location2 = models.Location(
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

            self.assertEqual(len(map_obj.locations), 2)
            self.assertEqual(map_obj.locations[0].name, 'Paris, France')
            self.assertEqual(map_obj.locations[1].name, 'Rome, Italy')

    def test_cascade_delete(self) -> None:
        """Test that deleting a map deletes its locations."""
        with sqlmodel.Session(self.engine) as session:
            # Create a map with locations
            map_obj = models.Map(name='Test Map')
            session.add(map_obj)
            session.commit()
            session.refresh(map_obj)
            assert map_obj.id is not None

            location = models.Location(
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
                sqlmodel.select(models.Location).where(models.Location.map_id == map_id)
            ).all()
            self.assertEqual(len(remaining_locations), 0)

    def test_location_ordering(self) -> None:
        """Test that locations are ordered by order_index."""
        with sqlmodel.Session(self.engine) as session:
            map_obj = models.Map(name='Ordered Map')
            session.add(map_obj)
            session.commit()
            session.refresh(map_obj)
            assert map_obj.id is not None

            # Add locations out of order
            location2 = models.Location(
                map_id=map_obj.id, name='Second', latitude=0, longitude=0, order_index=2
            )
            location1 = models.Location(
                map_id=map_obj.id, name='First', latitude=0, longitude=0, order_index=1
            )
            location3 = models.Location(
                map_id=map_obj.id, name='Third', latitude=0, longitude=0, order_index=3
            )

            session.add(location2)
            session.add(location1)
            session.add(location3)
            session.commit()

            # Refresh map
            session.refresh(map_obj)

            # Verify they are ordered correctly
            self.assertEqual(map_obj.locations[0].name, 'First')
            self.assertEqual(map_obj.locations[1].name, 'Second')
            self.assertEqual(map_obj.locations[2].name, 'Third')
