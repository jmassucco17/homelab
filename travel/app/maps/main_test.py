"""Unit tests for maps routes through the combined travel application."""

import unittest

import sqlalchemy
import sqlalchemy.pool
import sqlmodel
from fastapi.testclient import TestClient

from travel.app import main
from travel.app.maps import database as maps_db
from travel.app.maps import services
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


class TestMapsRoutes(unittest.TestCase):
    """Tests for maps routes through the combined app."""

    def setUp(self) -> None:
        """Set up test client with in-memory databases."""
        self.engine = make_in_memory_engine()

        def override_get_session():
            with sqlmodel.Session(self.engine) as session:
                yield session

        overrides = main.app.dependency_overrides
        overrides[photos_db.get_session] = override_get_session
        overrides[photos_db.get_admin_session] = override_get_session
        overrides[maps_db.get_session] = override_get_session
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        """Restore original dependency overrides."""
        main.app.dependency_overrides.clear()

    def test_app_exists(self) -> None:
        """Test that app object exists."""
        self.assertIsNotNone(main.app)

    def test_health_endpoint_exists(self) -> None:
        """Test that health endpoint is accessible."""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)

    def test_maps_index_page_exists(self) -> None:
        """Test that maps index page is accessible."""
        response = self.client.get('/maps/')
        self.assertEqual(response.status_code, 200)

    def test_new_map_page_exists(self) -> None:
        """Test that new map form page is accessible."""
        response = self.client.get('/maps/new')
        self.assertEqual(response.status_code, 200)

    def test_maps_index_page_with_maps(self) -> None:
        """Test the maps index page shows maps from the database."""
        with sqlmodel.Session(self.engine) as session:
            services.create_map(session, 'Test Map', 'A test map')

        response = self.client.get('/maps/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Test Map', response.text)
