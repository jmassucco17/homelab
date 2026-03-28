"""Unit tests for the combined travel FastAPI application."""

from __future__ import annotations

import unittest
from collections.abc import Generator

import fastapi.testclient
import sqlalchemy
import sqlalchemy.pool
import sqlmodel

from travel.app import main
from travel.app.maps import database as maps_db
from travel.app.photos import database as photos_db


def _make_in_memory_engine() -> sqlalchemy.Engine:
    """Create an in-memory SQLite engine for testing."""
    engine = sqlmodel.create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=sqlalchemy.pool.StaticPool,
    )
    sqlmodel.SQLModel.metadata.create_all(engine)
    return engine


class TestTravelApp(unittest.TestCase):
    """Tests for the combined travel application."""

    def setUp(self) -> None:
        """Set up test client with in-memory databases."""
        self.engine = _make_in_memory_engine()

        def override_get_session() -> Generator[sqlmodel.Session, None, None]:
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
        """Health check returns 200 with healthy status."""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'healthy'})

    def test_landing_page(self) -> None:
        """Root endpoint serves the landing HTML page."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])

    def test_photos_index(self) -> None:
        """Photos index endpoint serves an HTML page."""
        response = self.client.get('/photos')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])

    def test_photos_gallery(self) -> None:
        """Photos gallery endpoint serves an HTML page."""
        response = self.client.get('/photos/gallery')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])

    def test_photos_admin(self) -> None:
        """Photos admin endpoint serves an HTML page."""
        response = self.client.get('/photos/admin')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])


class TestTravelAppLifespan(unittest.TestCase):
    """Tests for the travel app lifespan (startup/shutdown)."""

    def test_lifespan_runs_on_startup(self) -> None:
        """The lifespan creates database tables without raising."""
        import unittest.mock

        engine = _make_in_memory_engine()

        def override_session() -> Generator[sqlmodel.Session, None, None]:
            """Yield an in-memory database session for testing."""
            with sqlmodel.Session(engine) as session:
                yield session

        main.app.dependency_overrides[photos_db.get_session] = override_session
        main.app.dependency_overrides[photos_db.get_admin_session] = override_session
        main.app.dependency_overrides[maps_db.get_session] = override_session
        try:
            with (
                unittest.mock.patch.object(photos_db, 'create_db_and_tables'),
                unittest.mock.patch.object(maps_db, 'create_db_and_tables'),
                fastapi.testclient.TestClient(main.app) as client,
            ):
                response = client.get('/health')
                self.assertEqual(response.status_code, 200)
        finally:
            main.app.dependency_overrides.clear()


if __name__ == '__main__':
    unittest.main()
