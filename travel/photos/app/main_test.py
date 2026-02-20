"""Unit tests for main.py FastAPI application."""

import unittest

import fastapi.testclient
import sqlalchemy
import sqlalchemy.pool
import sqlmodel

from travel.photos.app import database, main


def make_in_memory_engine() -> sqlalchemy.Engine:
    """Create an in-memory SQLite engine for testing."""
    engine = sqlmodel.create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=sqlalchemy.pool.StaticPool,
    )
    sqlmodel.SQLModel.metadata.create_all(engine)
    return engine


class TestApp(unittest.TestCase):
    """Tests for travel-photos FastAPI application."""

    def setUp(self) -> None:
        """Set up test client with an in-memory database."""
        self.engine = make_in_memory_engine()

        def override_get_session():
            with sqlmodel.Session(self.engine) as session:
                yield session

        main.app.dependency_overrides[database.get_session] = override_get_session
        main.app.dependency_overrides[database.get_admin_session] = override_get_session
        self.client = fastapi.testclient.TestClient(main.app)

    def tearDown(self) -> None:
        """Remove dependency overrides after each test."""
        main.app.dependency_overrides.clear()

    def test_health_endpoint(self) -> None:
        """Test health check endpoint."""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'healthy'})

    def test_health_endpoint_head(self) -> None:
        """Test health check endpoint with HEAD method."""
        response = self.client.head('/health')
        self.assertEqual(response.status_code, 200)

    def test_root_endpoint(self) -> None:
        """Test root endpoint serves the map page."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])

    def test_gallery_endpoint(self) -> None:
        """Test gallery endpoint serves the gallery page."""
        response = self.client.get('/gallery')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])

    def test_admin_endpoint(self) -> None:
        """Test admin root endpoint serves the admin upload page."""
        response = self.client.get('/admin')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])

    def test_get_public_pictures_empty(self) -> None:
        """Test public pictures endpoint returns empty list when no pictures."""
        response = self.client.get('/pictures')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_get_locations_empty(self) -> None:
        """Test public locations endpoint returns empty list when no locations."""
        response = self.client.get('/locations')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_get_picture_not_found(self) -> None:
        """Test getting a non-existent picture returns 404."""
        response = self.client.get('/pictures/9999')
        self.assertEqual(response.status_code, 404)
        self.assertIn('Picture not found', response.json()['detail'])

    def test_get_admin_pictures_empty(self) -> None:
        """Test admin pictures endpoint returns empty list when no pictures."""
        response = self.client.get('/admin/pictures')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_delete_picture_not_found(self) -> None:
        """Test deleting a non-existent picture returns 404."""
        response = self.client.delete('/admin/pictures/9999')
        self.assertEqual(response.status_code, 404)
        self.assertIn('Picture not found', response.json()['detail'])

    def test_get_picture_file_not_found(self) -> None:
        """Test getting file for a non-existent picture returns 404."""
        response = self.client.get('/pictures/9999/file')
        self.assertEqual(response.status_code, 404)


if __name__ == '__main__':
    unittest.main()
