"""Unit tests for travel-maps service functions."""

import unittest

import sqlalchemy
import sqlalchemy.pool
import sqlmodel
from app import models, services


def make_in_memory_engine() -> sqlalchemy.Engine:
    """Create an in-memory SQLite engine for testing."""
    engine = sqlmodel.create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=sqlalchemy.pool.StaticPool,
    )
    sqlmodel.SQLModel.metadata.create_all(engine)
    return engine


class TestMapServices(unittest.TestCase):
    """Tests for map service functions."""

    def setUp(self) -> None:
        """Set up test database."""
        self.engine = make_in_memory_engine()

    def test_get_all_maps_empty(self) -> None:
        """Test getting all maps when database is empty."""
        with sqlmodel.Session(self.engine) as session:
            maps = services.get_all_maps(session)
            self.assertEqual(maps, [])

    def test_get_all_maps(self) -> None:
        """Test getting all maps."""
        with sqlmodel.Session(self.engine) as session:
            map1 = models.Map(name='Map 1')
            map2 = models.Map(name='Map 2')
            session.add(map1)
            session.add(map2)
            session.commit()

            maps = services.get_all_maps(session)
            self.assertEqual(len(maps), 2)

    def test_get_map_by_id(self) -> None:
        """Test getting a map by ID."""
        with sqlmodel.Session(self.engine) as session:
            map_obj = models.Map(name='Test Map')
            session.add(map_obj)
            session.commit()
            session.refresh(map_obj)

            retrieved = services.get_map_by_id(session, map_obj.id)
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.id, map_obj.id)
            self.assertEqual(retrieved.name, 'Test Map')

    def test_get_map_by_id_not_found(self) -> None:
        """Test getting a non-existent map."""
        with sqlmodel.Session(self.engine) as session:
            retrieved = services.get_map_by_id(session, 999)
            self.assertIsNone(retrieved)

    def test_create_map(self) -> None:
        """Test creating a new map."""
        with sqlmodel.Session(self.engine) as session:
            map_obj = services.create_map(session, 'New Map', 'Description')

            self.assertIsNotNone(map_obj.id)
            self.assertEqual(map_obj.name, 'New Map')
            self.assertEqual(map_obj.description, 'Description')

    def test_create_map_without_description(self) -> None:
        """Test creating a map without description."""
        with sqlmodel.Session(self.engine) as session:
            map_obj = services.create_map(session, 'Simple Map')

            self.assertIsNotNone(map_obj.id)
            self.assertEqual(map_obj.name, 'Simple Map')
            self.assertIsNone(map_obj.description)

    def test_update_map(self) -> None:
        """Test updating a map."""
        with sqlmodel.Session(self.engine) as session:
            map_obj = services.create_map(session, 'Original Name')
            map_id = map_obj.id

            updated = services.update_map(
                session, map_id, 'New Name', 'New Description'
            )

            self.assertIsNotNone(updated)
            self.assertEqual(updated.id, map_id)
            self.assertEqual(updated.name, 'New Name')
            self.assertEqual(updated.description, 'New Description')

    def test_update_map_not_found(self) -> None:
        """Test updating a non-existent map."""
        with sqlmodel.Session(self.engine) as session:
            result = services.update_map(session, 999, 'Name')
            self.assertIsNone(result)

    def test_delete_map(self) -> None:
        """Test deleting a map."""
        with sqlmodel.Session(self.engine) as session:
            map_obj = services.create_map(session, 'To Delete')
            map_id = map_obj.id

            success = services.delete_map(session, map_id)
            self.assertTrue(success)

            # Verify it's deleted
            retrieved = services.get_map_by_id(session, map_id)
            self.assertIsNone(retrieved)

    def test_delete_map_not_found(self) -> None:
        """Test deleting a non-existent map."""
        with sqlmodel.Session(self.engine) as session:
            success = services.delete_map(session, 999)
            self.assertFalse(success)


class TestLocationServices(unittest.TestCase):
    """Tests for location service functions."""

    def setUp(self) -> None:
        """Set up test database."""
        self.engine = make_in_memory_engine()

    def test_add_location_to_map(self) -> None:
        """Test adding a location to a map."""
        with sqlmodel.Session(self.engine) as session:
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

            self.assertIsNotNone(location)
            self.assertEqual(location.map_id, map_obj.id)
            self.assertEqual(location.name, 'Paris, France')
            self.assertEqual(location.latitude, 48.8566)
            self.assertEqual(location.longitude, 2.3522)
            self.assertEqual(location.nickname, 'City of Light')
            self.assertEqual(location.description, 'Beautiful city')
            self.assertEqual(location.order_index, 0)

    def test_add_location_to_nonexistent_map(self) -> None:
        """Test adding a location to a non-existent map."""
        with sqlmodel.Session(self.engine) as session:
            location = services.add_location_to_map(
                session, 999, 'Paris', 48.8566, 2.3522
            )
            self.assertIsNone(location)

    def test_add_multiple_locations_order(self) -> None:
        """Test that multiple locations get correct order_index."""
        with sqlmodel.Session(self.engine) as session:
            map_obj = services.create_map(session, 'Ordered Map')

            loc1 = services.add_location_to_map(session, map_obj.id, 'First', 0, 0)
            loc2 = services.add_location_to_map(session, map_obj.id, 'Second', 0, 0)
            loc3 = services.add_location_to_map(session, map_obj.id, 'Third', 0, 0)

            self.assertEqual(loc1.order_index, 0)
            self.assertEqual(loc2.order_index, 1)
            self.assertEqual(loc3.order_index, 2)

    def test_update_location(self) -> None:
        """Test updating a location."""
        with sqlmodel.Session(self.engine) as session:
            map_obj = services.create_map(session, 'Test Map')
            location = services.add_location_to_map(
                session, map_obj.id, 'Paris', 48.8566, 2.3522
            )

            updated = services.update_location(
                session, location.id, 'City of Light', 'Beautiful city'
            )

            self.assertIsNotNone(updated)
            self.assertEqual(updated.nickname, 'City of Light')
            self.assertEqual(updated.description, 'Beautiful city')

    def test_update_location_not_found(self) -> None:
        """Test updating a non-existent location."""
        with sqlmodel.Session(self.engine) as session:
            result = services.update_location(session, 999, 'Nickname')
            self.assertIsNone(result)

    def test_delete_location(self) -> None:
        """Test deleting a location."""
        with sqlmodel.Session(self.engine) as session:
            map_obj = services.create_map(session, 'Test Map')
            location = services.add_location_to_map(
                session, map_obj.id, 'Paris', 48.8566, 2.3522
            )

            success = services.delete_location(session, location.id)
            self.assertTrue(success)

    def test_delete_location_not_found(self) -> None:
        """Test deleting a non-existent location."""
        with sqlmodel.Session(self.engine) as session:
            success = services.delete_location(session, 999)
            self.assertFalse(success)

    def test_reorder_locations(self) -> None:
        """Test reordering locations."""
        with sqlmodel.Session(self.engine) as session:
            map_obj = services.create_map(session, 'Test Map')
            assert map_obj.id is not None

            loc1 = services.add_location_to_map(session, map_obj.id, 'First', 0, 0)
            loc2 = services.add_location_to_map(session, map_obj.id, 'Second', 0, 0)
            loc3 = services.add_location_to_map(session, map_obj.id, 'Third', 0, 0)
            assert loc1 is not None and loc1.id is not None
            assert loc2 is not None and loc2.id is not None
            assert loc3 is not None and loc3.id is not None

            # Reorder: 3, 1, 2
            success = services.reorder_locations(session, [loc3.id, loc1.id, loc2.id])
            self.assertTrue(success)

            # Verify new order
            map_obj = services.get_map_by_id(session, map_obj.id)
            assert map_obj is not None
            self.assertEqual(map_obj.locations[0].name, 'Third')
            self.assertEqual(map_obj.locations[1].name, 'First')
            self.assertEqual(map_obj.locations[2].name, 'Second')
