"""Unit tests for travel-maps API routes through the combined app."""

import unittest
from collections.abc import Generator

import fastapi.testclient
import sqlalchemy
import sqlalchemy.pool
import sqlmodel

from travel.app import main
from travel.app.maps import database, services
from travel.app.photos import database as photos_db


def make_in_memory_engine() -> sqlalchemy.Engine:
    """Create an in-memory SQLite engine for testing."""
    engine = sqlmodel.create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=sqlalchemy.pool.StaticPool,
    )
    sqlmodel.SQLModel.metadata.create_all(engine)
    return engine


class _MapsTestBase(unittest.TestCase):
    """Base class that wires both DB dependencies to an in-memory engine."""

    def setUp(self) -> None:
        """Set up test client with in-memory databases."""
        self.engine = make_in_memory_engine()

        def override_get_session() -> Generator[sqlmodel.Session, None, None]:
            """Yield an in-memory database session for testing."""
            with sqlmodel.Session(self.engine) as session:
                yield session

        overrides = main.app.dependency_overrides
        overrides[photos_db.get_session] = override_get_session
        overrides[photos_db.get_admin_session] = override_get_session
        overrides[database.get_session] = override_get_session
        self.client = fastapi.testclient.TestClient(main.app)

    def tearDown(self) -> None:
        """Restore original dependency overrides."""
        main.app.dependency_overrides.clear()


class TestHealthEndpoint(_MapsTestBase):
    """Tests for health check endpoint."""

    def test_health_endpoint(self) -> None:
        """Test the health check endpoint."""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'healthy'})


class TestIndexPage(_MapsTestBase):
    """Tests for maps index page routes."""

    def test_index_page_empty(self) -> None:
        """Test the index page with no maps."""
        response = self.client.get('/maps/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('No maps yet', response.text)

    def test_index_page_with_maps(self) -> None:
        """Test the index page with maps."""
        with sqlmodel.Session(self.engine) as session:
            services.create_map(session, 'Test Map', 'A test map')

        response = self.client.get('/maps/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Test Map', response.text)


class TestMapAPI(_MapsTestBase):
    """Tests for map API endpoints."""

    def test_create_map_api(self) -> None:
        """Test creating a map via API."""
        response = self.client.post(
            '/maps/api/maps',
            json={'name': 'New Map', 'description': 'Test description'},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['name'], 'New Map')
        self.assertEqual(data['description'], 'Test description')
        self.assertIn('id', data)

    def test_get_map_api(self) -> None:
        """Test getting a map via API."""
        with sqlmodel.Session(self.engine) as session:
            map_obj = services.create_map(session, 'Test Map')

        response = self.client.get(f'/maps/api/maps/{map_obj.id}')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['id'], map_obj.id)
        self.assertEqual(data['name'], 'Test Map')
        self.assertIn('locations', data)

    def test_get_map_not_found(self) -> None:
        """Test getting a non-existent map."""
        response = self.client.get('/maps/api/maps/999')
        self.assertEqual(response.status_code, 404)

    def test_update_map_api(self) -> None:
        """Test updating a map via API."""
        with sqlmodel.Session(self.engine) as session:
            map_obj = services.create_map(session, 'Original Name')

        response = self.client.put(
            f'/maps/api/maps/{map_obj.id}',
            json={'name': 'Updated Name', 'description': 'Updated description'},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['name'], 'Updated Name')
        self.assertEqual(data['description'], 'Updated description')

    def test_delete_map_api(self) -> None:
        """Test deleting a map via API."""
        with sqlmodel.Session(self.engine) as session:
            map_obj = services.create_map(session, 'To Delete')

        response = self.client.delete(f'/maps/api/maps/{map_obj.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['success'], True)


class TestLocationAPI(_MapsTestBase):
    """Tests for location API endpoints."""

    def test_add_location_api(self) -> None:
        """Test adding a location via API."""
        with sqlmodel.Session(self.engine) as session:
            map_obj = services.create_map(session, 'Test Map')

        response = self.client.post(
            f'/maps/api/maps/{map_obj.id}/locations',
            json={
                'name': 'Paris, France',
                'latitude': 48.8566,
                'longitude': 2.3522,
                'nickname': 'City of Light',
                'description': 'Beautiful',
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['name'], 'Paris, France')
        self.assertEqual(data['latitude'], 48.8566)
        self.assertEqual(data['longitude'], 2.3522)
        self.assertEqual(data['nickname'], 'City of Light')
        self.assertEqual(data['order_index'], 0)

    def test_update_location_api(self) -> None:
        """Test updating a location via API."""
        with sqlmodel.Session(self.engine) as session:
            map_obj = services.create_map(session, 'Test Map')
            assert map_obj.id is not None
            location = services.add_location_to_map(
                session, map_obj.id, 'Paris', 48.8566, 2.3522
            )
        assert location is not None
        assert location.id is not None

        response = self.client.put(
            f'/maps/api/locations/{location.id}',
            json={'nickname': 'City of Light', 'description': 'Beautiful city'},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['nickname'], 'City of Light')
        self.assertEqual(data['description'], 'Beautiful city')

    def test_delete_location_api(self) -> None:
        """Test deleting a location via API."""
        with sqlmodel.Session(self.engine) as session:
            map_obj = services.create_map(session, 'Test Map')
            assert map_obj.id is not None
            location = services.add_location_to_map(
                session, map_obj.id, 'Paris', 48.8566, 2.3522
            )
        assert location is not None
        assert location.id is not None

        response = self.client.delete(f'/maps/api/locations/{location.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['success'], True)

    def test_reorder_locations_api(self) -> None:
        """Test reordering locations via API."""
        with sqlmodel.Session(self.engine) as session:
            map_obj = services.create_map(session, 'Test Map')
            assert map_obj.id is not None
            loc1 = services.add_location_to_map(session, map_obj.id, 'First', 0, 0)
            loc2 = services.add_location_to_map(session, map_obj.id, 'Second', 0, 0)
            assert loc1 is not None
            assert loc2 is not None
            assert loc1.id is not None
            assert loc2.id is not None
            loc1_id = loc1.id
            loc2_id = loc2.id

        response = self.client.post(
            '/maps/api/locations/reorder', json={'location_ids': [loc2_id, loc1_id]}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['success'], True)
