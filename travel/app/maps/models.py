"""Database models for the travel maps feature."""

import datetime

import sqlmodel


class Map(sqlmodel.SQLModel, table=True):
    """Represents a travel map with multiple locations."""

    __tablename__ = 'maps_map'  # type: ignore[misc]

    id: int | None = sqlmodel.Field(default=None, primary_key=True)
    name: str = sqlmodel.Field(max_length=200, index=True)
    description: str | None = sqlmodel.Field(default=None, max_length=1000)
    created_at: datetime.datetime = sqlmodel.Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )
    updated_at: datetime.datetime = sqlmodel.Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    locations: list['MapLocation'] = sqlmodel.Relationship(
        back_populates='map',
        sa_relationship_kwargs={
            'cascade': 'all, delete-orphan',
            'order_by': 'maps_location.c.order_index',
        },
    )


class MapLocation(sqlmodel.SQLModel, table=True):
    """Represents a location within a travel map."""

    __tablename__ = 'maps_location'  # type: ignore[misc]

    id: int | None = sqlmodel.Field(default=None, primary_key=True)
    map_id: int = sqlmodel.Field(foreign_key='maps_map.id', index=True)
    order_index: int = sqlmodel.Field(default=0)

    name: str = sqlmodel.Field(max_length=200)
    latitude: float
    longitude: float

    nickname: str | None = sqlmodel.Field(default=None, max_length=100)
    description: str | None = sqlmodel.Field(default=None, max_length=500)

    created_at: datetime.datetime = sqlmodel.Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    map: Map = sqlmodel.Relationship(back_populates='locations')
