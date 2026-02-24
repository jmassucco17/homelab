"""Unit tests for catan board data models."""

from __future__ import annotations

import unittest

import pydantic

from games.app.catan.models import board


class TestTileType(unittest.TestCase):
    """Tests for TileType enum."""

    def test_all_types_are_strings(self) -> None:
        """Every TileType value should be a non-empty lowercase string."""
        for tile_type in board.TileType:
            self.assertIsInstance(tile_type.value, str)

    def test_desert_has_no_resource(self) -> None:
        """Desert is not in the TILE_RESOURCE mapping."""
        self.assertNotIn(board.TileType.DESERT, board.TILE_RESOURCE)

    def test_non_desert_tiles_have_resources(self) -> None:
        """All non-desert tile types have a corresponding resource."""
        non_desert = [t for t in board.TileType if t != board.TileType.DESERT]
        for tile_type in non_desert:
            self.assertIn(tile_type, board.TILE_RESOURCE)


class TestCubeCoord(unittest.TestCase):
    """Tests for CubeCoord model."""

    def test_origin_neighbors_count(self) -> None:
        """The origin hex has exactly 6 neighbours."""
        coord = board.CubeCoord(q=0, r=0, s=0)
        self.assertEqual(len(coord.neighbors()), 6)

    def test_neighbors_satisfy_invariant(self) -> None:
        """All neighbour coords must satisfy q + r + s == 0."""
        coord = board.CubeCoord(q=1, r=-1, s=0)
        for n in coord.neighbors():
            self.assertEqual(n.q + n.r + n.s, 0)

    def test_frozen_model(self) -> None:
        """CubeCoord is immutable (frozen model)."""
        coord = board.CubeCoord(q=0, r=0, s=0)
        with self.assertRaises(pydantic.ValidationError):
            coord.q = 1  # type: ignore[misc]


class TestHexTile(unittest.TestCase):
    """Tests for HexTile model."""

    def test_desert_tile_has_no_number_token(self) -> None:
        """Desert tiles do not carry a number token."""
        tile = board.HexTile(
            coord=board.CubeCoord(q=0, r=0, s=0),
            tile_type=board.TileType.DESERT,
        )
        self.assertIsNone(tile.number_token)

    def test_non_desert_tile_with_number(self) -> None:
        """Non-desert tiles accept a number token."""
        tile = board.HexTile(
            coord=board.CubeCoord(q=1, r=-1, s=0),
            tile_type=board.TileType.FOREST,
            number_token=6,
        )
        self.assertEqual(tile.number_token, 6)


class TestVertex(unittest.TestCase):
    """Tests for Vertex model."""

    def test_vertex_defaults_to_no_building(self) -> None:
        """A newly created vertex has no building or port."""
        vertex = board.Vertex(
            vertex_id=0,
            adjacent_vertex_ids=[1, 2],
            adjacent_edge_ids=[0, 1],
            adjacent_tile_indices=[0],
        )
        self.assertIsNone(vertex.building)
        self.assertIsNone(vertex.port_type)

    def test_vertex_with_building(self) -> None:
        """A vertex can hold a Building."""
        building = board.Building(
            player_index=0,
            building_type=board.BuildingType.SETTLEMENT,
        )
        vertex = board.Vertex(
            vertex_id=1,
            adjacent_vertex_ids=[],
            adjacent_edge_ids=[],
            adjacent_tile_indices=[],
            building=building,
        )
        self.assertIsNotNone(vertex.building)
        assert vertex.building is not None
        self.assertEqual(vertex.building.player_index, 0)


class TestEdge(unittest.TestCase):
    """Tests for Edge model."""

    def test_edge_defaults_to_no_road(self) -> None:
        """A newly created edge has no road."""
        edge = board.Edge(
            edge_id=0,
            vertex_ids=(0, 1),
            adjacent_tile_indices=[0],
        )
        self.assertIsNone(edge.road)

    def test_edge_with_road(self) -> None:
        """An edge can hold a Road."""
        road = board.Road(player_index=2)
        edge = board.Edge(
            edge_id=5,
            vertex_ids=(3, 4),
            adjacent_tile_indices=[1, 2],
            road=road,
        )
        self.assertEqual(edge.road.player_index, 2)  # type: ignore[union-attr]


class TestPort(unittest.TestCase):
    """Tests for Port model."""

    def test_port_stores_vertex_ids(self) -> None:
        """A port stores the vertex IDs it connects."""
        port = board.Port(port_type=board.PortType.GENERIC, vertex_ids=[10, 11])
        self.assertEqual(port.vertex_ids, [10, 11])
        self.assertEqual(port.port_type, board.PortType.GENERIC)


if __name__ == '__main__':
    unittest.main()
