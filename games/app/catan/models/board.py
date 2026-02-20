"""Catan board data models.

Defines the hexagonal grid representation using cube coordinates, tile types,
ports, vertices, edges, and the overall Board structure.
"""

from __future__ import annotations

import enum

import pydantic


class TileType(enum.StrEnum):
    """Terrain tile types and the resource each produces."""

    FOREST = 'forest'  # produces wood
    PASTURE = 'pasture'  # produces sheep
    FIELDS = 'fields'  # produces wheat
    HILLS = 'hills'  # produces brick
    MOUNTAINS = 'mountains'  # produces ore
    DESERT = 'desert'  # produces nothing


class ResourceType(enum.StrEnum):
    """The five tradeable resource types."""

    WOOD = 'wood'
    BRICK = 'brick'
    WHEAT = 'wheat'
    SHEEP = 'sheep'
    ORE = 'ore'


# Map from tile type to the resource it produces (desert excluded).
TILE_RESOURCE: dict[TileType, ResourceType] = {
    TileType.FOREST: ResourceType.WOOD,
    TileType.PASTURE: ResourceType.SHEEP,
    TileType.FIELDS: ResourceType.WHEAT,
    TileType.HILLS: ResourceType.BRICK,
    TileType.MOUNTAINS: ResourceType.ORE,
}


class PortType(enum.StrEnum):
    """Port types: generic 3:1 or specific resource 2:1."""

    GENERIC = 'generic'
    WOOD = 'wood'
    BRICK = 'brick'
    WHEAT = 'wheat'
    SHEEP = 'sheep'
    ORE = 'ore'


class BuildingType(enum.StrEnum):
    """Settlement or upgraded city."""

    SETTLEMENT = 'settlement'
    CITY = 'city'


class CubeCoord(pydantic.BaseModel):
    """Cube coordinates for a hex tile. Invariant: q + r + s == 0."""

    model_config = pydantic.ConfigDict(frozen=True)

    q: int
    r: int
    s: int

    def neighbors(self) -> list[CubeCoord]:
        """Return the 6 neighbouring cube coordinates in order."""
        directions: list[tuple[int, int, int]] = [
            (1, -1, 0),
            (1, 0, -1),
            (0, 1, -1),
            (-1, 1, 0),
            (-1, 0, 1),
            (0, -1, 1),
        ]
        return [
            CubeCoord(q=self.q + dq, r=self.r + dr, s=self.s + ds)
            for dq, dr, ds in directions
        ]


class HexTile(pydantic.BaseModel):
    """A single terrain hex tile on the Catan board."""

    coord: CubeCoord
    tile_type: TileType
    number_token: int | None = None  # None for desert; 2–12 excluding 7


class Building(pydantic.BaseModel):
    """A settlement or city placed on a vertex."""

    player_index: int
    building_type: BuildingType


class Road(pydantic.BaseModel):
    """A road placed on an edge."""

    player_index: int


class Port(pydantic.BaseModel):
    """A trading port accessible from exactly two adjacent perimeter vertices."""

    port_type: PortType
    vertex_ids: list[int]  # exactly 2 vertex IDs where this port can be accessed


class Vertex(pydantic.BaseModel):
    """An intersection point where settlements and cities can be placed.

    Each vertex is shared by up to three hex tiles and connects to up to three
    edges and three adjacent vertices.
    """

    vertex_id: int
    adjacent_vertex_ids: list[int]  # vertices connected by an edge (distance rule)
    adjacent_edge_ids: list[int]  # edges that touch this vertex
    adjacent_tile_indices: list[int]  # indices into Board.tiles for bordering tiles
    building: Building | None = None
    port_type: PortType | None = None  # port accessible from this vertex, if any


class Edge(pydantic.BaseModel):
    """A side of a hex tile where roads can be placed.

    Each edge connects exactly two vertices and borders up to two hex tiles.
    """

    edge_id: int
    vertex_ids: tuple[int, int]  # the two vertices this edge connects
    adjacent_tile_indices: list[int]  # indices into Board.tiles for bordering tiles
    road: Road | None = None


class Board(pydantic.BaseModel):
    """The complete Catan board state, including tiles, vertices, edges, and ports."""

    tiles: list[HexTile]
    vertices: list[Vertex]
    edges: list[Edge]
    ports: list[Port]
    robber_tile_index: int  # index into tiles; starts on the desert
