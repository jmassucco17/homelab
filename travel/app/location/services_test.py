"""Unit tests for location tracking services."""

import datetime
import unittest
from unittest.mock import MagicMock, patch

import sqlalchemy
import sqlalchemy.pool
import sqlmodel

from travel.app.location import models, services


def make_in_memory_engine() -> sqlalchemy.Engine:
    """Create an in-memory SQLite engine for testing."""
    engine = sqlmodel.create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=sqlalchemy.pool.StaticPool,
    )
    sqlmodel.SQLModel.metadata.create_all(engine)
    return engine


class TestIsGoogleConfigured(unittest.TestCase):
    """Tests for is_google_configured."""

    def test_not_configured_when_missing(self) -> None:
        """Returns False when env vars are not set."""
        with (
            patch.object(services, 'GOOGLE_CLIENT_ID', ''),
            patch.object(services, 'GOOGLE_CLIENT_SECRET', ''),
            patch.object(services, 'GOOGLE_LOCATION_REFRESH_TOKEN', ''),
        ):
            self.assertFalse(services.is_google_configured())

    def test_configured_when_all_set(self) -> None:
        """Returns True when all env vars are set."""
        with (
            patch.object(services, 'GOOGLE_CLIENT_ID', 'id'),
            patch.object(services, 'GOOGLE_CLIENT_SECRET', 'secret'),
            patch.object(services, 'GOOGLE_LOCATION_REFRESH_TOKEN', 'token'),
        ):
            self.assertTrue(services.is_google_configured())


class TestReverseGeocode(unittest.TestCase):
    """Tests for reverse_geocode."""

    def test_reverse_geocode_success(self) -> None:
        """Returns city/country dict on success."""
        mock_result = MagicMock()
        mock_result.raw = {
            'address': {
                'city': 'Paris',
                'country': 'France',
                'country_code': 'fr',
            }
        }
        with patch.object(services.geolocator, 'reverse', return_value=mock_result):
            result = services.reverse_geocode(48.8566, 2.3522)
        self.assertEqual(result['city'], 'Paris')
        self.assertEqual(result['country'], 'France')
        self.assertEqual(result['country_code'], 'FR')

    def test_reverse_geocode_no_result(self) -> None:
        """Returns empty dict when geocoder finds nothing."""
        with patch.object(services.geolocator, 'reverse', return_value=None):
            result = services.reverse_geocode(0.0, 0.0)
        self.assertEqual(result, {})

    def test_reverse_geocode_exception(self) -> None:
        """Returns empty dict on exception."""
        with patch.object(
            services.geolocator, 'reverse', side_effect=Exception('network error')
        ):
            result = services.reverse_geocode(0.0, 0.0)
        self.assertEqual(result, {})


class TestUpsertAndGetLocation(unittest.TestCase):
    """Tests for upsert_location and get_location_by_date."""

    def setUp(self) -> None:
        """Set up test database."""
        self.engine = make_in_memory_engine()

    def test_insert_new_location(self) -> None:
        """upsert_location creates a new record when date is not in DB."""
        with sqlmodel.Session(self.engine) as session:
            loc = services.upsert_location(
                session,
                datetime.date(2025, 7, 1),
                48.8566,
                2.3522,
                city='Paris',
                country='France',
                country_code='FR',
            )
        self.assertIsNotNone(loc.id)
        self.assertEqual(loc.city, 'Paris')

    def test_update_existing_location(self) -> None:
        """upsert_location updates an existing record for the same date."""
        target_date = datetime.date(2025, 7, 2)
        with sqlmodel.Session(self.engine) as session:
            services.upsert_location(session, target_date, 0.0, 0.0, city='Old')
            updated = services.upsert_location(
                session, target_date, 1.0, 2.0, city='New'
            )
        self.assertEqual(updated.city, 'New')
        self.assertEqual(updated.latitude, 1.0)

    def test_get_location_by_date_not_found(self) -> None:
        """get_location_by_date returns None for a missing date."""
        with sqlmodel.Session(self.engine) as session:
            result = services.get_location_by_date(session, datetime.date(2000, 1, 1))
        self.assertIsNone(result)


class TestLocationDisplayLabel(unittest.TestCase):
    """Tests for location_display_label."""

    def _make_loc(
        self,
        city: str | None = None,
        state: str | None = None,
        country: str | None = None,
        country_code: str | None = None,
    ) -> models.DailyLocation:
        return models.DailyLocation(
            date=datetime.date(2025, 1, 1),
            latitude=0.0,
            longitude=0.0,
            city=city,
            state=state,
            country=country,
            country_code=country_code,
        )

    def test_city_mode_with_city_and_country(self) -> None:
        loc = self._make_loc(city='Paris', country='France')
        self.assertEqual(services.location_display_label(loc, 'city'), 'Paris, France')

    def test_city_mode_missing_city(self) -> None:
        loc = self._make_loc(country='France')
        self.assertEqual(services.location_display_label(loc, 'city'), 'France')

    def test_city_mode_empty(self) -> None:
        loc = self._make_loc()
        self.assertEqual(services.location_display_label(loc, 'city'), 'Unknown')

    def test_country_mode_non_us(self) -> None:
        loc = self._make_loc(country='France', country_code='FR')
        self.assertEqual(services.location_display_label(loc, 'country'), 'France')

    def test_country_mode_us_returns_state(self) -> None:
        loc = self._make_loc(
            country='United States', country_code='US', state='California'
        )
        self.assertEqual(services.location_display_label(loc, 'country'), 'California')

    def test_country_mode_us_no_state(self) -> None:
        loc = self._make_loc(country='United States', country_code='US')
        self.assertEqual(
            services.location_display_label(loc, 'country'), 'United States'
        )


class TestGroupLocations(unittest.TestCase):
    """Tests for group_locations."""

    def _make_loc(
        self,
        day: int,
        city: str | None = None,
        country: str | None = None,
        country_code: str | None = None,
        state: str | None = None,
    ) -> models.DailyLocation:
        return models.DailyLocation(
            date=datetime.date(2025, 1, day),
            latitude=0.0,
            longitude=0.0,
            city=city,
            country=country,
            country_code=country_code,
            state=state,
        )

    def test_empty_list(self) -> None:
        self.assertEqual(services.group_locations([], 'city'), [])

    def test_single_entry(self) -> None:
        loc = self._make_loc(1, city='Paris', country='France')
        groups = services.group_locations([loc], 'city')
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['label'], 'Paris, France')
        self.assertEqual(groups[0]['days'], 1)

    def test_consecutive_same_city_grouped(self) -> None:
        locs = [
            self._make_loc(1, city='Paris', country='France'),
            self._make_loc(2, city='Paris', country='France'),
            self._make_loc(3, city='Paris', country='France'),
        ]
        groups = services.group_locations(locs, 'city')
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['days'], 3)

    def test_different_cities_not_grouped(self) -> None:
        locs = [
            self._make_loc(1, city='Paris', country='France'),
            self._make_loc(2, city='Lyon', country='France'),
        ]
        groups = services.group_locations(locs, 'city')
        self.assertEqual(len(groups), 2)

    def test_country_mode_grouping(self) -> None:
        locs = [
            self._make_loc(1, city='Paris', country='France', country_code='FR'),
            self._make_loc(2, city='Lyon', country='France', country_code='FR'),
            self._make_loc(3, city='Berlin', country='Germany', country_code='DE'),
        ]
        groups = services.group_locations(locs, 'country')
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0]['label'], 'France')
        self.assertEqual(groups[0]['days'], 2)
        self.assertEqual(groups[1]['label'], 'Germany')
