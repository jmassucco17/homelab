"""Unit tests for location tracking routes."""

import datetime
import json
import unittest
from unittest.mock import patch

import sqlalchemy
import sqlalchemy.pool
import sqlmodel
from fastapi.testclient import TestClient

from travel.app import main
from travel.app.location import database as location_db
from travel.app.location import services
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


class TestLocationRoutes(unittest.TestCase):
    """Tests for location routes through the combined app."""

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
        overrides[location_db.get_session] = override_get_session
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        """Restore original dependency overrides."""
        main.app.dependency_overrides.clear()

    def test_location_index_page_loads(self) -> None:
        """Test that the location page is accessible."""
        response = self.client.get('/location/')
        self.assertEqual(response.status_code, 200)

    def test_location_index_empty_state(self) -> None:
        """Test that the empty state message is shown with no data."""
        response = self.client.get('/location/')
        self.assertIn('No location history yet', response.text)

    def test_location_index_with_today(self) -> None:
        """Test that today's entry is highlighted."""
        today = datetime.date.today()
        with sqlmodel.Session(self.engine) as session:
            services.upsert_location(
                session,
                today,
                48.8566,
                2.3522,
                city='Paris',
                country='France',
                country_code='FR',
            )

        response = self.client.get('/location/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Paris', response.text)
        self.assertIn('France', response.text)

    def test_location_page_shows_history(self) -> None:
        """Test that historical entries appear in the table."""
        with sqlmodel.Session(self.engine) as session:
            services.upsert_location(
                session,
                datetime.date(2025, 3, 1),
                35.6762,
                139.6503,
                city='Tokyo',
                country='Japan',
                country_code='JP',
            )

        response = self.client.get('/location/')
        self.assertIn('Tokyo', response.text)

    def test_location_country_mode(self) -> None:
        """Test that country mode groups by country."""
        with sqlmodel.Session(self.engine) as session:
            services.upsert_location(
                session,
                datetime.date(2025, 3, 1),
                48.8566,
                2.3522,
                city='Paris',
                country='France',
                country_code='FR',
            )
            services.upsert_location(
                session,
                datetime.date(2025, 3, 2),
                45.7640,
                4.8357,
                city='Lyon',
                country='France',
                country_code='FR',
            )

        response = self.client.get('/location/?mode=country')
        self.assertEqual(response.status_code, 200)
        self.assertIn('France', response.text)

    def test_add_location_via_api(self) -> None:
        """Test manually adding a location."""
        with patch.object(
            services,
            'reverse_geocode',
            return_value={
                'city': 'Rome',
                'country': 'Italy',
                'country_code': 'IT',
                'state': None,
                'raw': None,
            },
        ):
            response = self.client.post(
                '/location/api/locations',
                json={'date': '2025-05-15', 'latitude': 41.9028, 'longitude': 12.4964},
            )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['date'], '2025-05-15')
        self.assertEqual(data['city'], 'Rome')

    def test_add_location_invalid_date(self) -> None:
        """Test that an invalid date returns 400."""
        response = self.client.post(
            '/location/api/locations',
            json={'date': 'not-a-date', 'latitude': 0.0, 'longitude': 0.0},
        )
        self.assertEqual(response.status_code, 400)

    def test_import_takeout_file(self) -> None:
        """Test importing a Takeout Semantic Location History JSON file."""
        takeout_data = {
            'timelineObjects': [
                {
                    'placeVisit': {
                        'duration': {'startTimestamp': '2025-04-10T08:00:00Z'},
                        'centerLatE7': 356762000,
                        'centerLngE7': 1396503000,
                    }
                }
            ]
        }
        with patch.object(
            services,
            'reverse_geocode',
            return_value={
                'city': 'Tokyo',
                'country': 'Japan',
                'country_code': 'JP',
                'state': None,
                'raw': None,
            },
        ):
            response = self.client.post(
                '/location/api/import',
                files={
                    'file': (
                        '2025_APRIL.json',
                        json.dumps(takeout_data),
                        'application/json',
                    )
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['imported'], 1)

    def test_import_non_json_file_rejected(self) -> None:
        """Test that a non-.json file is rejected with 400."""
        response = self.client.post(
            '/location/api/import',
            files={'file': ('data.txt', b'hello', 'text/plain')},
        )
        self.assertEqual(response.status_code, 400)

    def test_import_invalid_json_rejected(self) -> None:
        """Test that a malformed JSON file is rejected with 400."""
        response = self.client.post(
            '/location/api/import',
            files={'file': ('data.json', b'not json{{{', 'application/json')},
        )
        self.assertEqual(response.status_code, 400)
