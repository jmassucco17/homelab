"""Unit tests for travel-maps API routes."""

import unittest

import sqlalchemy
import sqlalchemy.pool
import sqlmodel
from app import database, main, models, services
from fastapi.testclient import TestClient


def make_in_memory_engine() -> sqlalchemy.Engine:
    """Create an in-memory SQLite engine for testing."""
    engine = sqlmodel.create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=sqlalchemy.pool.StaticPool,
    )
    sqlmodel.SQLModel.metadata.create_all(engine)
    return engine


class TestHealthEndpoint(unittest.TestCase):
    """Tests for health check endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        # Replace database engine with in-memory for testing
        self.original_engine = database.engine
        database.engine = make_in_memory_engine()
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        """Restore original database engine."""
        database.engine = self.original_engine

    def test_health_endpoint(self) -> None:
        """Test the health check endpoint."""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'healthy'})


class TestIndexPage(unittest.TestCase):
    """Tests for index page routes."""

    def setUp(self) -> None:
        """Set up test client and database."""
        self.original_engine = database.engine
        database.engine = make_in_memory_engine()
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        """Restore original database engine."""
        database.engine = self.original_engine

    def test_index_page_empty(self) -> None:
        """Test the index page with no maps."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('No maps yet', response.text)

    def test_index_page_with_maps(self) -> None:
        """Test the index page with maps."""
        with sqlmodel.Session(database.engine) as session:
            services.create_map(session, 'Test Map', 'A test map')

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Test Map', response.text)


class TestMapAPI(unittest.TestCase):
    """Tests for map API endpoints."""

    def setUp(self) -> None:
        """Set up test client and database."""
        self.original_engine = database.engine
        database.engine = make_in_memory_engine()
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        """Restore original database engine."""
        database.engine = self.original_engine

    def test_create_map_api(self) -> None:
        """Test creating a map via API."""
        response = self.client.post(
            '/api/maps', json={'name': 'New Map', 'description': 'Test description'}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['name'], 'New Map')
        self.assertEqual(data['description'], 'Test description')
        self.assertIn('id', data)

    def test_get_map_api(self) -> None:
        """Test getting a map via API."""
        with sqlmodel.Session(database.engine) as session:
            map_obj = services.create_map(session, 'Test Map')

        response = self.client.get(f'/api/maps/{map_obj.id}')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['id'], map_obj.id)
        self.assertEqual(data['name'], 'Test Map')
        self.assertIn('locations', data)

    def test_get_map_not_found(self) -> None:
        """Test getting a non-existent map."""
        response = self.client.get('/api/maps/999')
        self.assertEqual(response.status_code, 404)

    def test_update_map_api(self) -> None:
        """Test updating a map via API."""
        with sqlmodel.Session(database.engine) as session:
            map_obj = services.create_map(session, 'Original Name')

        response = self.client.put(
            f'/api/maps/{map_obj.id}',
            json={'name': 'Updated Name', 'description': 'Updated description'},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['name'], 'Updated Name')
        self.assertEqual(data['description'], 'Updated description')

    def test_delete_map_api(self) -> None:
        """Test deleting a map via API."""
        with sqlmodel.Session(database.engine) as session:
            map_obj = services.create_map(session, 'To Delete')

        response = self.client.delete(f'/api/maps/{map_obj.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['success'], True)


class TestLocationAPI(unittest.TestCase):
    """Tests for location API endpoints."""

    def setUp(self) -> None:
        """Set up test client and database."""
        self.original_engine = database.engine
        database.engine = make_in_memory_engine()
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        """Restore original database engine."""
        database.engine = self.original_engine

    def test_add_location_api(self) -> None:
        """Test adding a location via API."""
        with sqlmodel.Session(database.engine) as session:
            map_obj = services.create_map(session, 'Test Map')

        response = self.client.post(
            f'/api/maps/{map_obj.id}/locations',
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
        with sqlmodel.Session(database.engine) as session:
            map_obj = services.create_map(session, 'Test Map')
            location = services.add_location_to_map(session, map_obj.id, 'Paris', 48.8566, 2.3522)

        response = self.client.put(
            f'/api/locations/{location.id}',
            json={'nickname': 'City of Light', 'description': 'Beautiful city'},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['nickname'], 'City of Light')
        self.assertEqual(data['description'], 'Beautiful city')

    def test_delete_location_api(self) -> None:
        """Test deleting a location via API."""
        with sqlmodel.Session(database.engine) as session:
            map_obj = services.create_map(session, 'Test Map')
            location = services.add_location_to_map(session, map_obj.id, 'Paris', 48.8566, 2.3522)

        response = self.client.delete(f'/api/locations/{location.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['success'], True)

    def test_reorder_locations_api(self) -> None:
        """Test reordering locations via API."""
        with sqlmodel.Session(database.engine) as session:
            map_obj = services.create_map(session, 'Test Map')
            loc1 = services.add_location_to_map(session, map_obj.id, 'First', 0, 0)
            loc2 = services.add_location_to_map(session, map_obj.id, 'Second', 0, 0)
            loc1_id = loc1.id
            loc2_id = loc2.id

        response = self.client.post(
            '/api/locations/reorder', json={'location_ids': [loc2_id, loc1_id]}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['success'], True)
