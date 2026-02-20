"""Unit tests for models.py database models."""

import unittest
from datetime import UTC, datetime

from travel.photos.app import models


class TestLocation(unittest.TestCase):
    """Tests for Location model."""

    def test_location_fields(self) -> None:
        """Test that Location model stores fields correctly."""
        location = models.Location(
            name='Paris',
            latitude=48.8566,
            longitude=2.3522,
            location_name='Paris, France',
        )
        self.assertEqual(location.name, 'Paris')
        self.assertAlmostEqual(location.latitude, 48.8566)
        self.assertAlmostEqual(location.longitude, 2.3522)
        self.assertEqual(location.location_name, 'Paris, France')
        self.assertIsNone(location.id)

    def test_location_optional_fields(self) -> None:
        """Test that Location model optional fields default to None."""
        location = models.Location(
            name='Unknown',
            latitude=0.0,
            longitude=0.0,
        )
        self.assertIsNone(location.location_name)
        self.assertIsNone(location.id)

    def test_location_created_date_defaults_to_now(self) -> None:
        """Test that created_date defaults to current UTC time."""
        before = datetime.now(UTC)
        location = models.Location(
            name='Test',
            latitude=0.0,
            longitude=0.0,
        )
        after = datetime.now(UTC)
        self.assertGreaterEqual(location.created_date, before)
        self.assertLessEqual(location.created_date, after)


class TestPicture(unittest.TestCase):
    """Tests for Picture model."""

    def test_picture_fields(self) -> None:
        """Test that Picture model stores fields correctly."""
        picture = models.Picture(
            filename='abc123.jpg',
            original_filename='vacation.jpg',
            file_size=204800,
            mime_type='image/jpeg',
        )
        self.assertEqual(picture.filename, 'abc123.jpg')
        self.assertEqual(picture.original_filename, 'vacation.jpg')
        self.assertEqual(picture.file_size, 204800)
        self.assertEqual(picture.mime_type, 'image/jpeg')
        self.assertIsNone(picture.id)
        self.assertIsNone(picture.location_id)
        self.assertIsNone(picture.description)
        self.assertIsNone(picture.date_taken)

    def test_picture_upload_date_defaults_to_now(self) -> None:
        """Test that upload_date defaults to current UTC time."""
        before = datetime.now(UTC)
        picture = models.Picture(
            filename='test.jpg',
            original_filename='test.jpg',
            file_size=1024,
            mime_type='image/jpeg',
        )
        after = datetime.now(UTC)
        self.assertGreaterEqual(picture.upload_date, before)
        self.assertLessEqual(picture.upload_date, after)

    def test_picture_with_all_fields(self) -> None:
        """Test Picture model with all optional fields set."""
        date_taken = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
        picture = models.Picture(
            filename='abc123.jpg',
            original_filename='sunset.jpg',
            date_taken=date_taken,
            location_id=1,
            description='Beautiful sunset',
            file_size=512000,
            mime_type='image/jpeg',
        )
        self.assertEqual(picture.date_taken, date_taken)
        self.assertEqual(picture.location_id, 1)
        self.assertEqual(picture.description, 'Beautiful sunset')


if __name__ == '__main__':
    unittest.main()
