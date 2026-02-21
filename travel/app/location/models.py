"""Models for daily location tracking."""

import datetime
from datetime import UTC

from sqlmodel import Field, SQLModel


class DailyLocation(SQLModel, table=True):
    """Stores one location entry per calendar day."""

    __tablename__ = 'location_daily'  # type: ignore[misc]

    id: int | None = Field(default=None, primary_key=True)
    date: datetime.date = Field(index=True, unique=True)
    latitude: float
    longitude: float
    city: str | None = Field(default=None, max_length=200)
    state: str | None = Field(default=None, max_length=200)
    country: str | None = Field(default=None, max_length=200)
    country_code: str | None = Field(default=None, max_length=10)
    raw_geocode: str | None = Field(default=None)
    fetched_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(UTC)
    )
