from datetime import datetime
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


class Map(SQLModel, table=True):
    """Represents a travel map with multiple locations."""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=200, index=True)
    description: Optional[str] = Field(default=None, max_length=1000)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    locations: list["Location"] = Relationship(
        back_populates="map",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "order_by": "Location.order_index"},
    )


class Location(SQLModel, table=True):
    """Represents a location within a travel map."""

    id: Optional[int] = Field(default=None, primary_key=True)
    map_id: int = Field(foreign_key="map.id", index=True)
    order_index: int = Field(default=0)

    name: str = Field(max_length=200)
    latitude: float
    longitude: float

    nickname: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)

    created_at: datetime = Field(default_factory=datetime.utcnow)

    map: Map = Relationship(back_populates="locations")
