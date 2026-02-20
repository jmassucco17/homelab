"""Database models for the travel picture site."""

from datetime import UTC, datetime

from sqlmodel import Field, Relationship, SQLModel


class PhotoLocation(SQLModel, table=True):
    """Model for storing location information."""

    __tablename__ = 'photos_location'  # type: ignore[misc]

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    latitude: float
    longitude: float
    location_name: str | None = None
    created_date: datetime = Field(default_factory=lambda: datetime.now(UTC))
    pictures: list['Picture'] = Relationship(back_populates='location')


class Picture(SQLModel, table=True):
    """Model for storing travel pictures with metadata."""

    __tablename__ = 'photos_picture'  # type: ignore[misc]

    id: int | None = Field(default=None, primary_key=True)
    filename: str = Field(index=True)
    original_filename: str
    upload_date: datetime = Field(default_factory=lambda: datetime.now(UTC))
    date_taken: datetime | None = None
    location_id: int | None = Field(default=None, foreign_key='photos_location.id')
    location: PhotoLocation | None = Relationship(back_populates='pictures')
    description: str | None = None
    file_size: int
    mime_type: str
