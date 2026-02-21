"""Unit tests for Catan board models and board generator."""

from __future__ import annotations

import unittest

import pydantic

from games.app.catan.board_generator import generate_board
from games.app.catan.models.board import (
    CubeCoord,
    PortType,
    ResourceType,
    TileType,
)
from games.app.catan.models.player import (
    DEV_CARD_COST,
    ROAD_COST,
    SETTLEMENT_COST,
    DevCardHand,
    DevCardType,
    Player,
    Resources,
)
from games.app.catan.models.serializers import (
    deserialize_board,
    serialize_model,
)


class TestCubeCoord(unittest.TestCase):
    """Tests for CubeCoord model."""

    def test_neighbors_count(self) -> None:
        """Every hex should have exactly 6 neighbours."""
        coord = CubeCoord(q=0, r=0, s=0)
        self.assertEqual(len(coord.neighbors()), 6)

    def test_neighbors_invariant(self) -> None:
        """All neighbour coords must satisfy q + r + s == 0."""
        coord = CubeCoord(q=1, r=-1, s=0)
        for n in coord.neighbors():
            self.assertEqual(n.q + n.r + n.s, 0)

    def test_frozen(self) -> None:
        """CubeCoord is immutable."""
        coord = CubeCoord(q=0, r=0, s=0)
        with self.assertRaises(pydantic.ValidationError):
            coord.q = 1  # type: ignore[misc]


class TestResources(unittest.TestCase):
    """Tests for the Resources model."""

    def test_total(self) -> None:
        res = Resources(wood=2, brick=1, wheat=0, sheep=3, ore=1)
        self.assertEqual(res.total(), 7)

    def test_can_afford_true(self) -> None:
        res = Resources(wood=2, brick=2)
        self.assertTrue(res.can_afford(ROAD_COST))

    def test_can_afford_false(self) -> None:
        res = Resources(wood=1)
        self.assertFalse(res.can_afford(ROAD_COST))

    def test_subtract(self) -> None:
        res = Resources(wood=3, brick=2)
        result = res.subtract(ROAD_COST)
        self.assertEqual(result.wood, 2)
        self.assertEqual(result.brick, 1)

    def test_add(self) -> None:
        a = Resources(wood=1, sheep=2)
        b = Resources(wood=2, ore=1)
        result = a.add(b)
        self.assertEqual(result.wood, 3)
        self.assertEqual(result.sheep, 2)
        self.assertEqual(result.ore, 1)

    def test_get(self) -> None:
        res = Resources(ore=5)
        self.assertEqual(res.get(ResourceType.ORE), 5)
        self.assertEqual(res.get(ResourceType.WOOD), 0)

    def test_can_afford_settlement(self) -> None:
        res = Resources(wood=1, brick=1, wheat=1, sheep=1)
        self.assertTrue(res.can_afford(SETTLEMENT_COST))

    def test_can_afford_dev_card(self) -> None:
        res = Resources(wheat=1, sheep=1, ore=1)
        self.assertTrue(res.can_afford(DEV_CARD_COST))
        res_no_ore = Resources(wheat=1, sheep=1)
        self.assertFalse(res_no_ore.can_afford(DEV_CARD_COST))


class TestDevCardHand(unittest.TestCase):
    """Tests for the DevCardHand model."""

    def test_total(self) -> None:
        hand = DevCardHand(knight=3, victory_point=1)
        self.assertEqual(hand.total(), 4)

    def test_get(self) -> None:
        hand = DevCardHand(monopoly=2)
        self.assertEqual(hand.get(DevCardType.MONOPOLY), 2)

    def test_add(self) -> None:
        hand = DevCardHand(knight=1)
        hand2 = hand.add(DevCardType.KNIGHT)
        self.assertEqual(hand2.knight, 2)
        self.assertEqual(hand.knight, 1)  # original unchanged

    def test_remove(self) -> None:
        hand = DevCardHand(road_building=2)
        hand2 = hand.remove(DevCardType.ROAD_BUILDING)
        self.assertEqual(hand2.road_building, 1)


class TestBoardGenerator(unittest.TestCase):
    """Tests for the board generation algorithm."""

    def setUp(self) -> None:
        # Use a fixed seed for reproducibility.
        self.board = generate_board(seed=42)

    def test_tile_count(self) -> None:
        """Standard board has exactly 19 tiles."""
        self.assertEqual(len(self.board.tiles), 19)

    def test_vertex_count(self) -> None:
        """Standard Catan board has exactly 54 vertices."""
        self.assertEqual(len(self.board.vertices), 54)

    def test_edge_count(self) -> None:
        """Standard Catan board has exactly 72 edges."""
        self.assertEqual(len(self.board.edges), 72)

    def test_port_count(self) -> None:
        """Standard board has exactly 9 ports."""
        self.assertEqual(len(self.board.ports), 9)

    def test_tile_type_distribution(self) -> None:
        """Tile types must match the standard distribution."""
        counts: dict[TileType, int] = {}
        for tile in self.board.tiles:
            counts[tile.tile_type] = counts.get(tile.tile_type, 0) + 1
        self.assertEqual(counts[TileType.FOREST], 4)
        self.assertEqual(counts[TileType.PASTURE], 4)
        self.assertEqual(counts[TileType.FIELDS], 4)
        self.assertEqual(counts[TileType.HILLS], 3)
        self.assertEqual(counts[TileType.MOUNTAINS], 3)
        self.assertEqual(counts[TileType.DESERT], 1)

    def test_number_token_distribution(self) -> None:
        """Number tokens must match the standard 18-token distribution."""
        expected = sorted([2, 3, 3, 4, 4, 5, 5, 6, 6, 8, 8, 9, 9, 10, 10, 11, 11, 12])
        actual = sorted(
            t.number_token for t in self.board.tiles if t.number_token is not None
        )
        self.assertEqual(actual, expected)

    def test_desert_has_no_number(self) -> None:
        """The desert tile must not have a number token."""
        desert = next(t for t in self.board.tiles if t.tile_type == TileType.DESERT)
        self.assertIsNone(desert.number_token)

    def test_robber_starts_on_desert(self) -> None:
        """Robber must start on the desert tile."""
        robber_tile = self.board.tiles[self.board.robber_tile_index]
        self.assertEqual(robber_tile.tile_type, TileType.DESERT)

    def test_vertex_ids_are_sequential(self) -> None:
        """Vertex IDs must be sequential from 0 to 53."""
        ids = sorted(v.vertex_id for v in self.board.vertices)
        self.assertEqual(ids, list(range(54)))

    def test_edge_ids_are_sequential(self) -> None:
        """Edge IDs must be sequential from 0 to 71."""
        ids = sorted(e.edge_id for e in self.board.edges)
        self.assertEqual(ids, list(range(72)))

    def test_edge_connects_two_distinct_vertices(self) -> None:
        """Every edge must connect two distinct vertex IDs."""
        for edge in self.board.edges:
            self.assertEqual(len(edge.vertex_ids), 2)
            self.assertNotEqual(edge.vertex_ids[0], edge.vertex_ids[1])

    def test_each_vertex_has_adjacent_tiles(self) -> None:
        """Every vertex must border at least one tile."""
        for vertex in self.board.vertices:
            self.assertGreater(len(vertex.adjacent_tile_indices), 0)

    def test_interior_vertices_border_three_tiles(self) -> None:
        """Interior vertices (those not on the perimeter) border exactly 3 tiles."""
        interior = [v for v in self.board.vertices if len(v.adjacent_tile_indices) == 3]
        # The standard Catan board has 24 interior vertices.
        self.assertEqual(len(interior), 24)

    def test_port_vertex_ids_valid(self) -> None:
        """Every port must reference valid vertex IDs."""
        valid_ids = {v.vertex_id for v in self.board.vertices}
        for port in self.board.ports:
            self.assertEqual(len(port.vertex_ids), 2)
            for vid in port.vertex_ids:
                self.assertIn(vid, valid_ids)

    def test_port_type_distribution(self) -> None:
        """Port types must match the standard distribution."""
        counts: dict[PortType, int] = {}
        for port in self.board.ports:
            counts[port.port_type] = counts.get(port.port_type, 0) + 1
        self.assertEqual(counts.get(PortType.GENERIC, 0), 4)
        specific_ports = {
            PortType.WOOD,
            PortType.BRICK,
            PortType.WHEAT,
            PortType.SHEEP,
            PortType.ORE,
        }
        for pt in specific_ports:
            self.assertEqual(counts.get(pt, 0), 1)

    def test_tile_coords_satisfy_invariant(self) -> None:
        """All tile cube coords must satisfy q + r + s == 0."""
        for tile in self.board.tiles:
            c = tile.coord
            self.assertEqual(c.q + c.r + c.s, 0)

    def test_deterministic_with_seed(self) -> None:
        """Two boards generated with the same seed must be identical."""
        b1 = generate_board(seed=7)
        b2 = generate_board(seed=7)
        self.assertEqual(
            [t.tile_type for t in b1.tiles],
            [t.tile_type for t in b2.tiles],
        )
        self.assertEqual(
            [t.number_token for t in b1.tiles],
            [t.number_token for t in b2.tiles],
        )

    def test_balanced_board(self) -> None:
        """Balanced board generation must still produce a valid board."""
        board = generate_board(balanced=True, seed=99)
        self.assertEqual(len(board.tiles), 19)
        self.assertEqual(len(board.vertices), 54)
        self.assertEqual(len(board.edges), 72)


class TestBoardSerialization(unittest.TestCase):
    """Tests for Board serialization round-trips."""

    def setUp(self) -> None:
        self.board = generate_board(seed=1)

    def test_serialize_model(self) -> None:
        """serialize_model must return a plain dict."""
        data = serialize_model(self.board)
        self.assertIsInstance(data, dict)
        self.assertIn('tiles', data)
        self.assertIn('vertices', data)
        self.assertIn('edges', data)

    def test_deserialize_board_round_trip(self) -> None:
        """Board must survive a serialize → deserialize round-trip."""
        data = serialize_model(self.board)
        restored = deserialize_board(data)
        self.assertEqual(len(restored.tiles), len(self.board.tiles))
        self.assertEqual(len(restored.vertices), len(self.board.vertices))
        self.assertEqual(len(restored.edges), len(self.board.edges))
        self.assertEqual(restored.robber_tile_index, self.board.robber_tile_index)


class TestPlayerModel(unittest.TestCase):
    """Tests for the Player model."""

    def _make_player(self) -> Player:
        return Player(player_index=0, name='Alice', color='red')

    def test_default_resources_zero(self) -> None:
        player = self._make_player()
        self.assertEqual(player.resources.total(), 0)

    def test_default_victory_points(self) -> None:
        player = self._make_player()
        self.assertEqual(player.victory_points, 0)

    def test_default_build_inventory(self) -> None:
        player = self._make_player()
        self.assertEqual(player.build_inventory.settlements_remaining, 5)
        self.assertEqual(player.build_inventory.cities_remaining, 4)
        self.assertEqual(player.build_inventory.roads_remaining, 15)

    def test_player_serialization(self) -> None:
        player = self._make_player()
        data = serialize_model(player)
        self.assertEqual(data['name'], 'Alice')
        self.assertEqual(data['color'], 'red')


if __name__ == '__main__':
    unittest.main()
