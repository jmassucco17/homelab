"""Unit tests for the combined travel FastAPI application."""

import collections.abc
import unittest

import fastapi.testclient
import sqlalchemy
import sqlalchemy.pool
import sqlmodel

from travel.app import main
from travel.app.maps import database as maps_db
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


class TestApp(unittest.TestCase):
    """Tests for combined travel FastAPI application."""

    def setUp(self) -> None:
        """Set up test client with in-memory databases."""
        self.engine = make_in_memory_engine()

        def override_get_session() -> collections.abc.Generator[
            sqlmodel.Session, None, None
        ]:
            """Yield an in-memory database session for testing."""
            with sqlmodel.Session(self.engine) as session:
                yield session

        overrides = main.app.dependency_overrides
        overrides[photos_db.get_session] = override_get_session
        overrides[photos_db.get_admin_session] = override_get_session
        overrides[maps_db.get_session] = override_get_session
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

    def test_landing_root_endpoint(self) -> None:
        """Test root endpoint serves the landing page."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])

    def test_photos_index_endpoint(self) -> None:
        """Test photos index serves the map page."""
        response = self.client.get('/photos')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])

    def test_photos_gallery_endpoint(self) -> None:
        """Test gallery endpoint serves the gallery page."""
        response = self.client.get('/photos/gallery')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])

    def test_photos_admin_endpoint(self) -> None:
        """Test admin endpoint serves the admin upload page."""
        response = self.client.get('/photos/admin')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])

    def test_get_public_pictures_empty(self) -> None:
        """Test public pictures endpoint returns empty list when no pictures."""
        response = self.client.get('/photos/pictures')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_get_locations_empty(self) -> None:
        """Test public locations endpoint returns empty list when no locations."""
        response = self.client.get('/photos/locations')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_get_picture_not_found(self) -> None:
        """Test getting a non-existent picture returns 404."""
        response = self.client.get('/photos/pictures/9999')
        self.assertEqual(response.status_code, 404)
        self.assertIn('Picture not found', response.json()['detail'])

    def test_get_admin_pictures_empty(self) -> None:
        """Test admin pictures endpoint returns empty list when no pictures."""
        response = self.client.get('/photos/admin/pictures')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_delete_picture_not_found(self) -> None:
        """Test deleting a non-existent picture returns 404."""
        response = self.client.delete('/photos/admin/pictures/9999')
        self.assertEqual(response.status_code, 404)
        self.assertIn('Picture not found', response.json()['detail'])

    def test_get_picture_file_not_found(self) -> None:
        """Test getting file for a non-existent picture returns 404."""
        response = self.client.get('/photos/pictures/9999/file')
        self.assertEqual(response.status_code, 404)

    def test_maps_index_endpoint(self) -> None:
        """Test maps index serves the maps list page."""
        response = self.client.get('/maps/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])

    def test_maps_new_page_exists(self) -> None:
        """Test that the new map form page is accessible."""
        response = self.client.get('/maps/new')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])


if __name__ == '__main__':
    unittest.main()
