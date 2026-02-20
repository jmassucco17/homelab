"""Unit tests for routes.py."""

import unittest

from travel.app.photos import models, routes


class TestSerializePicture(unittest.TestCase):
    """Tests for serialize_picture helper function."""

    def test_serialize_picture_without_location(self) -> None:
        """Test serializing a picture that has no associated location."""
        picture = models.Picture(
            filename='test.jpg',
            original_filename='original.jpg',
            file_size=1024,
            mime_type='image/jpeg',
        )
        result = routes.serialize_picture(picture)
        self.assertIsInstance(result, dict)
        self.assertEqual(result['filename'], 'test.jpg')
        self.assertEqual(result['original_filename'], 'original.jpg')
        self.assertIsNone(result['location'])

    def test_serialize_picture_with_location(self) -> None:
        """Test serializing a picture that has an associated location."""
        location = models.PhotoLocation(
            name='Rome',
            latitude=41.9028,
            longitude=12.4964,
            location_name='Rome, Italy',
        )
        picture = models.Picture(
            filename='colosseum.jpg',
            original_filename='colosseum.jpg',
            file_size=2048,
            mime_type='image/jpeg',
            location=location,
        )
        result = routes.serialize_picture(picture)
        self.assertIsNotNone(result['location'])
        self.assertEqual(result['location']['name'], 'Rome')
        self.assertAlmostEqual(result['location']['latitude'], 41.9028)


if __name__ == '__main__':
    unittest.main()
