"""Unit tests for DailyLocation model."""

import datetime
import unittest

import sqlalchemy
import sqlalchemy.exc
import sqlalchemy.pool
import sqlmodel

from travel.app.location import models


def make_in_memory_engine() -> sqlalchemy.Engine:
    """Create an in-memory SQLite engine for testing."""
    engine = sqlmodel.create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=sqlalchemy.pool.StaticPool,
    )
    sqlmodel.SQLModel.metadata.create_all(engine)
    return engine


class TestDailyLocationModel(unittest.TestCase):
    """Tests for DailyLocation model."""

    def setUp(self) -> None:
        """Set up test database."""
        self.engine = make_in_memory_engine()

    def test_daily_location_creation(self) -> None:
        """Test creating a DailyLocation record."""
        with sqlmodel.Session(self.engine) as session:
            loc = models.DailyLocation(
                date=datetime.date(2025, 6, 1),
                latitude=48.8566,
                longitude=2.3522,
                city='Paris',
                state=None,
                country='France',
                country_code='FR',
            )
            session.add(loc)
            session.commit()
            session.refresh(loc)

            self.assertIsNotNone(loc.id)
            self.assertEqual(loc.city, 'Paris')
            self.assertEqual(loc.country, 'France')
            self.assertEqual(loc.country_code, 'FR')
            self.assertIsNotNone(loc.fetched_at)

    def test_optional_fields_default_none(self) -> None:
        """Test that optional fields default to None."""
        with sqlmodel.Session(self.engine) as session:
            loc = models.DailyLocation(
                date=datetime.date(2025, 6, 2),
                latitude=0.0,
                longitude=0.0,
            )
            session.add(loc)
            session.commit()
            session.refresh(loc)

            self.assertIsNone(loc.city)
            self.assertIsNone(loc.state)
            self.assertIsNone(loc.country)
            self.assertIsNone(loc.country_code)
            self.assertIsNone(loc.raw_geocode)

    def test_unique_date_constraint(self) -> None:
        """Test that two records for the same date raise an integrity error."""
        with sqlmodel.Session(self.engine) as session:
            loc1 = models.DailyLocation(
                date=datetime.date(2025, 6, 3), latitude=0.0, longitude=0.0
            )
            session.add(loc1)
            session.commit()

        with sqlmodel.Session(self.engine) as session:
            loc2 = models.DailyLocation(
                date=datetime.date(2025, 6, 3), latitude=1.0, longitude=1.0
            )
            session.add(loc2)
            with self.assertRaises(sqlalchemy.exc.IntegrityError):
                session.commit()
