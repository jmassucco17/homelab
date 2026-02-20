"""Unit tests for database.py."""

import unittest

import sqlalchemy
import sqlalchemy.pool
import sqlmodel

from travel.app import database, models


def make_in_memory_engine() -> sqlalchemy.Engine:
    """Create an in-memory SQLite engine for testing."""
    engine = sqlmodel.create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=sqlalchemy.pool.StaticPool,
    )
    sqlmodel.SQLModel.metadata.create_all(engine)
    return engine


class TestCreateDbAndTables(unittest.TestCase):
    """Tests for create_db_and_tables function."""

    def test_creates_tables_does_not_raise(self) -> None:
        """Test that create_db_and_tables does not raise when called."""
        engine = make_in_memory_engine()
        # Verify tables were created by inserting a row
        with sqlmodel.Session(engine) as session:
            location = models.PhotoLocation(name='Test', latitude=0.0, longitude=0.0)
            session.add(location)
            session.commit()


class TestGetSession(unittest.TestCase):
    """Tests for get_session generator."""

    def test_get_session_yields_session(self) -> None:
        """Test that get_session yields a usable Session."""
        gen = database.get_session()
        session = next(gen)
        self.assertIsInstance(session, sqlmodel.Session)
        try:
            next(gen)
        except StopIteration:
            pass


class TestGetAdminSession(unittest.TestCase):
    """Tests for get_admin_session generator."""

    def test_get_admin_session_yields_session(self) -> None:
        """Test that get_admin_session yields a usable Session."""
        gen = database.get_admin_session()
        session = next(gen)
        self.assertIsInstance(session, sqlmodel.Session)
        try:
            next(gen)
        except StopIteration:
            pass


class TestInMemoryDatabase(unittest.TestCase):
    """Integration tests using an in-memory SQLite database."""

    def setUp(self) -> None:
        """Set up in-memory database and session for each test."""
        self.engine = make_in_memory_engine()
        self.session = sqlmodel.Session(self.engine)

    def tearDown(self) -> None:
        """Close session after each test."""
        self.session.close()

    def test_location_crud(self) -> None:
        """Test creating and retrieving a Location record."""
        location = models.PhotoLocation(
            name='Tokyo',
            latitude=35.6762,
            longitude=139.6503,
            location_name='Tokyo, Japan',
        )
        self.session.add(location)
        self.session.commit()
        self.session.refresh(location)

        self.assertIsNotNone(location.id)
        fetched = self.session.get(models.PhotoLocation, location.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, 'Tokyo')  # type: ignore[union-attr]

    def test_picture_crud(self) -> None:
        """Test creating and retrieving a Picture record."""
        picture = models.Picture(
            filename='test-uuid.jpg',
            original_filename='my_photo.jpg',
            file_size=102400,
            mime_type='image/jpeg',
        )
        self.session.add(picture)
        self.session.commit()
        self.session.refresh(picture)

        self.assertIsNotNone(picture.id)
        fetched = self.session.get(models.Picture, picture.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.original_filename, 'my_photo.jpg')  # type: ignore[union-attr]


if __name__ == '__main__':
    unittest.main()
