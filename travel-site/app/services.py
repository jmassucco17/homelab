"""Business logic services for the travel picture site."""

import os
import uuid
from datetime import datetime
from io import BytesIO
from typing import Any, BinaryIO

import exifread
import pillow_heif  # pyright: ignore[reportMissingTypeStubs]
from fastapi import UploadFile
from PIL import Image
from sqlmodel import Session, select

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

    def extract_metadata(self, file: BinaryIO) -> dict[str, Any]:
        """Extract EXIF metadata from an image file."""
        metadata: dict[str, Any] = {}

        try:
            tags = exifread.process_file(file)

            # Extract date taken
            if 'EXIF DateTimeOriginal' in tags:
                date_str = str(tags['EXIF DateTimeOriginal'])
                try:
                    metadata['date_taken'] = datetime.strptime(
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
        self, session: Session, file: UploadFile, description: str | None = None
    ) -> models.Picture:
        """Save uploaded picture with extracted metadata."""
        # Read file content
        content = await file.read()

        # Check if file is HEIC and convert to JPEG
        file_extension = os.path.splitext(file.filename or '')[1].lower()
        mime_type = file.content_type or 'image/jpeg'

        if file_extension in ['.heic', '.heif']:
            # Convert HEIC to JPEG
            img = Image.open(BytesIO(content))

            # Convert to RGB if necessary (HEIC can be in different color modes)
            if img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGB')

            # Save as JPEG
            output = BytesIO()
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
        picture = models.Picture(
            filename=unique_filename,
            original_filename=file.filename or '',
            date_taken=metadata.get('date_taken'),
            latitude=metadata.get('latitude'),
            longitude=metadata.get('longitude'),
            description=description,
            file_size=len(content),
            mime_type=mime_type,
        )

        session.add(picture)
        session.commit()
        session.refresh(picture)

        return picture

    def get_all_pictures(self, session: Session) -> list[models.Picture]:
        """Get all pictures ordered by date taken (newest first)."""
        statement = select(models.Picture).order_by(
            models.Picture.date_taken.desc().nulls_last(),  # type: ignore
            models.Picture.upload_date.desc(),  # type: ignore
        )
        return session.exec(statement).all()  # type: ignore

    def get_picture_by_id(
        self, session: Session, picture_id: int
    ) -> models.Picture | None:
        """Get a specific picture by ID."""
        return session.get(models.Picture, picture_id)

    def delete_picture(self, session: Session, picture_id: int) -> bool:
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


class LocationService:
    """Service for handling location data."""

    def create_location(
        self,
        session: Session,
        name: str,
        latitude: float,
        longitude: float,
        country: str | None = None,
        city: str | None = None,
    ) -> models.Location:
        """Create a new location."""
        location = models.Location(
            name=name,
            latitude=latitude,
            longitude=longitude,
            country=country,
            city=city,
        )

        session.add(location)
        session.commit()
        session.refresh(location)

        return location

    def get_all_locations(self, session: Session) -> list[models.Location]:
        """Get all locations."""
        statement = select(models.Location).order_by(models.Location.name)
        return session.exec(statement).all()  # type: ignore
