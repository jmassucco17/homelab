from datetime import UTC, datetime

from sqlmodel import Field, Relationship, SQLModel


class Map(SQLModel, table=True):
    """Represents a travel map with multiple locations."""

    __tablename__ = 'maps_map'  # type: ignore[misc]

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=200, index=True)
    description: str | None = Field(default=None, max_length=1000)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    locations: list['MapLocation'] = Relationship(
        back_populates='map',
        sa_relationship_kwargs={
            'cascade': 'all, delete-orphan',
            'order_by': 'maps_location.c.order_index',
        },
    )


class MapLocation(SQLModel, table=True):
    """Represents a location within a travel map."""

    __tablename__ = 'maps_location'  # type: ignore[misc]

    id: int | None = Field(default=None, primary_key=True)
    map_id: int = Field(foreign_key='maps_map.id', index=True)
    order_index: int = Field(default=0)

    name: str = Field(max_length=200)
    latitude: float
    longitude: float

    nickname: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=500)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    map: Map = Relationship(back_populates='locations')
