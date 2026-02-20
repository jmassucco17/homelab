"""Unit tests for services.py."""

import dataclasses
import io
import os
import tempfile
import unittest
from unittest import mock

import sqlalchemy
import sqlalchemy.pool
import sqlmodel

from travel.photos.app import models, services


def make_in_memory_engine() -> sqlalchemy.Engine:
    """Create an in-memory SQLite engine for testing."""
    engine = sqlmodel.create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=sqlalchemy.pool.StaticPool,
    )
    sqlmodel.SQLModel.metadata.create_all(engine)
    return engine


@dataclasses.dataclass
class FakeRatio:
    """Minimal GPS ratio value for testing."""

    num: int
    den: int


@dataclasses.dataclass
class FakeTag:
    """Minimal GPS tag value for testing."""

    values: list[FakeRatio]


class TestPictureServiceExtractMetadata(unittest.TestCase):
    """Tests for PictureService.extract_metadata."""

    def setUp(self) -> None:
        """Set up PictureService with a temp upload directory."""
        self.tmpdir = tempfile.mkdtemp()
        self.service = services.PictureService(upload_dir=self.tmpdir)

    def test_extract_metadata_no_exif(self) -> None:
        """Test that extract_metadata returns empty dict for files without EXIF."""
        file_bytes = io.BytesIO(b'not a real image')
        result = self.service.extract_metadata(file_bytes)
        self.assertIsInstance(result, dict)

    def test_extract_metadata_returns_dict(self) -> None:
        """Test that extract_metadata always returns a dict."""
        file_bytes = io.BytesIO(b'')
        result = self.service.extract_metadata(file_bytes)
        self.assertIsInstance(result, dict)


class TestPictureServiceConvertToDegrees(unittest.TestCase):
    """Tests for PictureService._convert_to_degrees."""

    def setUp(self) -> None:
        """Set up PictureService with a temp upload directory."""
        self.tmpdir = tempfile.mkdtemp()
        self.service = services.PictureService(upload_dir=self.tmpdir)

    def test_convert_to_degrees(self) -> None:
        """Test GPS DMS to decimal conversion."""
        # 48 degrees, 30 minutes, 0 seconds = 48.5 degrees
        tag = FakeTag([FakeRatio(48, 1), FakeRatio(30, 1), FakeRatio(0, 1)])
        result = self.service._convert_to_degrees(tag)  # pyright: ignore[reportPrivateUsage]
        self.assertAlmostEqual(result, 48.5)

    def test_convert_to_degrees_with_seconds(self) -> None:
        """Test GPS DMS to decimal conversion with non-zero seconds."""
        # 10 degrees, 0 minutes, 3600 seconds = 11.0 degrees
        tag = FakeTag([FakeRatio(10, 1), FakeRatio(0, 1), FakeRatio(3600, 1)])
        result = self.service._convert_to_degrees(tag)  # pyright: ignore[reportPrivateUsage]
        self.assertAlmostEqual(result, 11.0)


class TestPictureServiceInit(unittest.TestCase):
    """Tests for PictureService initialization."""

    def test_creates_upload_dir(self) -> None:
        """Test that PictureService creates the upload directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            upload_dir = os.path.join(tmpdir, 'new_uploads')
            self.assertFalse(os.path.exists(upload_dir))
            services.PictureService(upload_dir=upload_dir)
            self.assertTrue(os.path.exists(upload_dir))

    def test_default_upload_dir_uses_env(self) -> None:
        """Test that default upload_dir respects DATA_DIR env variable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.dict(os.environ, {'DATA_DIR': tmpdir}):
                service = services.PictureService()
                expected = os.path.join(tmpdir, 'uploads')
                self.assertEqual(service.upload_dir, expected)


class TestPictureServiceDatabase(unittest.TestCase):
    """Tests for PictureService database operations."""

    def setUp(self) -> None:
        """Set up in-memory database and PictureService."""
        self.engine = make_in_memory_engine()
        self.session = sqlmodel.Session(self.engine)
        self.tmpdir = tempfile.mkdtemp()
        self.service = services.PictureService(upload_dir=self.tmpdir)

    def tearDown(self) -> None:
        """Close session after each test."""
        self.session.close()

    def _create_picture(self, filename: str = 'test.jpg') -> models.Picture:
        """Helper to create a picture in the database."""
        picture = models.Picture(
            filename=filename,
            original_filename='original.jpg',
            file_size=1024,
            mime_type='image/jpeg',
        )
        self.session.add(picture)
        self.session.commit()
        self.session.refresh(picture)
        return picture

    def test_get_all_pictures_empty(self) -> None:
        """Test get_all_pictures returns empty list when no pictures."""
        result = self.service.get_all_pictures(self.session)
        self.assertEqual(result, [])

    def test_get_all_pictures_returns_pictures(self) -> None:
        """Test get_all_pictures returns all pictures."""
        self._create_picture('a.jpg')
        self._create_picture('b.jpg')
        result = self.service.get_all_pictures(self.session)
        self.assertEqual(len(result), 2)

    def test_get_picture_by_id_found(self) -> None:
        """Test get_picture_by_id returns picture when it exists."""
        picture = self._create_picture('found.jpg')
        assert picture.id is not None
        result = self.service.get_picture_by_id(self.session, picture.id)
        self.assertIsNotNone(result)
        self.assertEqual(result.filename, 'found.jpg')  # type: ignore[union-attr]

    def test_get_picture_by_id_not_found(self) -> None:
        """Test get_picture_by_id returns None for unknown id."""
        result = self.service.get_picture_by_id(self.session, 9999)
        self.assertIsNone(result)

    def test_delete_picture_removes_record(self) -> None:
        """Test delete_picture removes the picture from the database."""
        picture = self._create_picture('todelete.jpg')
        assert picture.id is not None
        picture_id = picture.id
        success = self.service.delete_picture(self.session, picture_id)
        self.assertTrue(success)
        self.assertIsNone(self.session.get(models.Picture, picture_id))

    def test_delete_picture_not_found(self) -> None:
        """Test delete_picture returns False for unknown id."""
        result = self.service.delete_picture(self.session, 9999)
        self.assertFalse(result)

    def test_update_picture_description(self) -> None:
        """Test update_picture_description updates the description."""
        picture = self._create_picture('update.jpg')
        assert picture.id is not None
        updated = self.service.update_picture_description(
            self.session,
            picture.id,
            'New description',
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated.description, 'New description')  # type: ignore[union-attr]

    def test_update_picture_description_not_found(self) -> None:
        """Test update_picture_description returns None for unknown id."""
        result = self.service.update_picture_description(self.session, 9999, 'desc')
        self.assertIsNone(result)


class TestLocationService(unittest.TestCase):
    """Tests for LocationService."""

    def setUp(self) -> None:
        """Set up in-memory database and LocationService."""
        self.engine = make_in_memory_engine()
        self.session = sqlmodel.Session(self.engine)
        self.service = services.LocationService()

    def tearDown(self) -> None:
        """Close session after each test."""
        self.session.close()

    def test_create_location_without_coords_returns_none(self) -> None:
        """Test that create_location returns None when coordinates are missing."""
        result = self.service.create_location(
            session=self.session,
            name='Unknown',
            latitude=None,
            longitude=None,
        )
        self.assertIsNone(result)

    def test_create_location_with_only_latitude_returns_none(self) -> None:
        """Test that create_location returns None with only latitude."""
        result = self.service.create_location(
            session=self.session,
            name='Unknown',
            latitude=48.8566,
            longitude=None,
        )
        self.assertIsNone(result)

    def test_get_all_locations_empty(self) -> None:
        """Test get_all_locations returns empty list when no locations."""
        result = self.service.get_all_locations(self.session)
        self.assertEqual(result, [])

    def test_get_all_locations_sorted_by_name(self) -> None:
        """Test get_all_locations returns locations sorted by name."""
        for name in ['Zurich', 'Amsterdam', 'Berlin']:
            location = models.PhotoLocation(name=name, latitude=0.0, longitude=0.0)
            self.session.add(location)
        self.session.commit()

        result = self.service.get_all_locations(self.session)
        names = [loc.name for loc in result]
        self.assertEqual(names, sorted(names))


if __name__ == '__main__':
    unittest.main()
