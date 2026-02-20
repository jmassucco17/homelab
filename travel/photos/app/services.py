"""Business logic services for the travel picture site."""

import datetime
import io
import os
import uuid
from typing import Any, BinaryIO

import exifread
import fastapi
import pillow_heif  # pyright: ignore[reportMissingTypeStubs]
import sqlmodel
from geopy import geocoders  # pyright: ignore[reportMissingTypeStubs]
from PIL import Image
from sqlalchemy.orm import selectinload

from . import models

# Register HEIF opener for PIL
pillow_heif.register_heif_opener()  # type: ignore


class PictureService:
    """Service for handling picture upload and metadata extraction."""

    def __init__(self, upload_dir: str | None = None):
        """Initialize the service with upload directory."""
        if upload_dir is None:
            data_dir = os.environ.get('DATA_DIR', 'data')
            upload_dir = os.path.join(data_dir, 'uploads')
        self.upload_dir = upload_dir
        os.makedirs(upload_dir, exist_ok=True)

    def extract_metadata(
        self,
        file: BinaryIO,
    ) -> dict[str, Any]:
        """Extract EXIF metadata from an image file."""
        metadata: dict[str, Any] = {}

        try:
            tags = exifread.process_file(file)

            # Extract date taken
            if 'EXIF DateTimeOriginal' in tags:
                date_str = str(tags['EXIF DateTimeOriginal'])
                try:
                    metadata['date_taken'] = datetime.datetime.strptime(
                        date_str, '%Y:%m:%d %H:%M:%S'
                    )
                except ValueError:
                    pass

            # Extract GPS coordinates
            gps_latitude = tags.get('GPS GPSLatitude')
            gps_latitude_ref = tags.get('GPS GPSLatitudeRef')
            gps_longitude = tags.get('GPS GPSLongitude')
            gps_longitude_ref = tags.get('GPS GPSLongitudeRef')

            if all([gps_latitude, gps_latitude_ref, gps_longitude, gps_longitude_ref]):
                lat = self._convert_to_degrees(gps_latitude)
                if str(gps_latitude_ref) == 'S':
                    lat = -lat

                lon = self._convert_to_degrees(gps_longitude)
                if str(gps_longitude_ref) == 'W':
                    lon = -lon

                metadata['latitude'] = lat
                metadata['longitude'] = lon

        except Exception:
            # If metadata extraction fails, continue without it
            pass

        return metadata

    def _convert_to_degrees(self, value: Any) -> float:
        """Convert GPS coordinates from DMS to decimal degrees."""
        degrees = float(value.values[0].num) / float(value.values[0].den)
        minutes = float(value.values[1].num) / float(value.values[1].den)
        seconds = float(value.values[2].num) / float(value.values[2].den)

        return degrees + (minutes / 60.0) + (seconds / 3600.0)

    async def save_picture(
        self,
        session: sqlmodel.Session,
        location_service: 'LocationService',
        file: fastapi.UploadFile,
        description: str | None = None,
    ) -> models.Picture:
        """Save uploaded picture with extracted metadata."""
        # Read file content
        content = await file.read()

        # Check if file is HEIC and convert to JPEG
        file_extension = os.path.splitext(file.filename or '')[1].lower()
        mime_type = file.content_type or 'image/jpeg'

        if file_extension in ['.heic', '.heif']:
            # Convert HEIC to JPEG
            img = Image.open(io.BytesIO(content))

            # Convert to RGB if necessary (HEIC can be in different color modes)
            if img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGB')

            # Save as JPEG
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=95)
            content = output.getvalue()

            # Update extension and mime type
            file_extension = '.jpg'
            mime_type = 'image/jpeg'

        # Generate unique filename
        unique_filename = f'{uuid.uuid4()}{file_extension}'
        file_path = os.path.join(self.upload_dir, unique_filename)

        # Save file to disk
        with open(file_path, 'wb') as f:
            f.write(content)

        # Extract metadata from original file
        file.file.seek(0)  # Reset file pointer
        metadata = self.extract_metadata(file.file)

        # Create database record
        location = location_service.create_location(
            session=session,
            name='TBD',
            latitude=metadata.get('latitude'),
            longitude=metadata.get('longitude'),
        )
        picture = models.Picture(
            filename=unique_filename,
            original_filename=file.filename or '',
            date_taken=metadata.get('date_taken'),
            location_id=location.id if location else None,
            location=location,
            description=description,
            file_size=len(content),
            mime_type=mime_type,
        )

        session.add(picture)
        session.commit()
        session.refresh(picture)

        return picture

    def get_all_pictures(
        self,
        session: sqlmodel.Session,
    ) -> list[models.Picture]:
        """Get all pictures ordered by date taken (newest first)."""
        statement = (
            sqlmodel.select(models.Picture)
            .options(selectinload(models.Picture.location))  # type: ignore
            .order_by(
                models.Picture.date_taken.desc().nulls_last(),  # type: ignore
                models.Picture.upload_date.desc(),  # type: ignore
            )
        )
        return list(session.exec(statement).all())

    def get_picture_by_id(
        self,
        session: sqlmodel.Session,
        picture_id: int,
    ) -> models.Picture | None:
        """Get a specific picture by ID."""
        statement = (
            sqlmodel.select(models.Picture)
            .options(selectinload(models.Picture.location))  # type: ignore
            .where(models.Picture.id == picture_id)
        )
        return session.exec(statement).first()

    def delete_picture(
        self,
        session: sqlmodel.Session,
        picture_id: int,
    ) -> bool:
        """Delete a picture from database and filesystem."""
        picture = session.get(models.Picture, picture_id)
        if not picture:
            return False

        # Delete file from filesystem
        file_path = os.path.join(self.upload_dir, picture.filename)
        if os.path.exists(file_path):
            os.remove(file_path)

        # Delete from database
        session.delete(picture)
        session.commit()

        return True

    def update_picture_description(
        self,
        session: sqlmodel.Session,
        picture_id: int,
        description: str | None,
    ) -> models.Picture | None:
        """Update a picture's description."""
        statement = (
            sqlmodel.select(models.Picture)
            .options(selectinload(models.Picture.location))  # type: ignore
            .where(models.Picture.id == picture_id)
        )
        picture = session.exec(statement).first()

        if not picture:
            return None

        picture.description = description
        session.add(picture)
        session.commit()
        session.refresh(picture)

        return picture


class LocationService:
    """Service for handling location data."""

    def create_location(
        self,
        session: sqlmodel.Session,
        name: str,
        latitude: float | None,
        longitude: float | None,
    ) -> models.PhotoLocation | None:
        """Create a new location."""
        if latitude is None or longitude is None:
            return None

        # Determine city and country
        geolocator = geocoders.Nominatim(user_agent='james_massucco_travel_blog')
        try:
            location_result = geolocator.reverse(  # type: ignore
                (latitude, longitude),
                exactly_one=True,
                # addressdetails=True,
            )
        except Exception:
            location_result = None
        # Convert geopy Location object to string using its address attribute
        location_name: str | None = (
            str(location_result.address) if location_result else None  # type: ignore
        )

        location = models.PhotoLocation(
            name=name,
            latitude=latitude,
            longitude=longitude,
            location_name=location_name,
        )

        session.add(location)
        session.commit()
        session.refresh(location)

        return location

    def get_all_locations(
        self,
        session: sqlmodel.Session,
    ) -> list[models.PhotoLocation]:
        """Get all locations."""
        statement = sqlmodel.select(models.PhotoLocation).order_by(
            models.PhotoLocation.name
        )
        return list(session.exec(statement).all())
