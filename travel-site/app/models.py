"""Database models for the travel picture site."""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class Picture(SQLModel, table=True):
    """Model for storing travel pictures with metadata."""

    id: int | None = Field(default=None, primary_key=True)
    filename: str = Field(index=True)
    original_filename: str
    upload_date: datetime = Field(default_factory=lambda: datetime.now(UTC))
    date_taken: datetime | None = None
    latitude: float | None = None
    longitude: float | None = None
    location_name: str | None = None
    description: str | None = None
    file_size: int
    mime_type: str


class Location(SQLModel, table=True):
    """Model for storing location information."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    latitude: float
    longitude: float
    country: str | None = None
    city: str | None = None
    created_date: datetime = Field(default_factory=lambda: datetime.now(UTC))
