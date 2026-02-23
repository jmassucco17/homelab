"""Database models for the travel picture site."""

import datetime

import sqlmodel


class PhotoLocation(sqlmodel.SQLModel, table=True):
    """Model for storing location information."""

    __tablename__ = 'photos_location'  # type: ignore[misc]

    id: int | None = sqlmodel.Field(default=None, primary_key=True)
    name: str = sqlmodel.Field(index=True)
    latitude: float
    longitude: float
    location_name: str | None = None
    created_date: datetime.datetime = sqlmodel.Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )
    pictures: list['Picture'] = sqlmodel.Relationship(back_populates='location')


class Picture(sqlmodel.SQLModel, table=True):
    """Model for storing travel pictures with metadata."""

    __tablename__ = 'photos_picture'  # type: ignore[misc]

    id: int | None = sqlmodel.Field(default=None, primary_key=True)
    filename: str = sqlmodel.Field(index=True)
    original_filename: str
    upload_date: datetime.datetime = sqlmodel.Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )
    date_taken: datetime.datetime | None = None
    location_id: int | None = sqlmodel.Field(
        default=None, foreign_key='photos_location.id'
    )
    location: PhotoLocation | None = sqlmodel.Relationship(back_populates='pictures')
    description: str | None = None
    file_size: int
    mime_type: str
