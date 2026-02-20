"""Unit tests for travel-maps main application."""

import unittest

import sqlalchemy
import sqlalchemy.pool
import sqlmodel
from fastapi.testclient import TestClient

from travel.maps.app import database, main


def make_in_memory_engine() -> sqlalchemy.Engine:
    """Create an in-memory SQLite engine for testing."""
    engine = sqlmodel.create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=sqlalchemy.pool.StaticPool,
    )
    sqlmodel.SQLModel.metadata.create_all(engine)
    return engine


class TestMainApplication(unittest.TestCase):
    """Tests for main FastAPI application."""

    def setUp(self) -> None:
        """Set up test client with in-memory database."""
        self.original_engine = database.engine
        database.engine = make_in_memory_engine()
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        """Restore original database engine."""
        database.engine = self.original_engine

    def test_app_exists(self) -> None:
        """Test that app object exists."""
        self.assertIsNotNone(main.app)

    def test_health_endpoint_exists(self) -> None:
        """Test that health endpoint is accessible."""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)

    def test_index_page_exists(self) -> None:
        """Test that index page is accessible."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_new_map_page_exists(self) -> None:
        """Test that new map form page is accessible."""
        response = self.client.get('/maps/new')
        self.assertEqual(response.status_code, 200)
