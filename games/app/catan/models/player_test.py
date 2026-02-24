"""Unit tests for catan player data models."""

from __future__ import annotations

import unittest

from games.app.catan.models import player


class TestResources(unittest.TestCase):
    """Tests for Resources model."""

    def test_total(self) -> None:
        """total() sums all resource counts."""
        res = player.Resources(wood=1, brick=2, wheat=3, sheep=4, ore=5)
        self.assertEqual(res.total(), 15)

    def test_empty_total(self) -> None:
        """Default Resources has total of 0."""
        self.assertEqual(player.Resources().total(), 0)

    def test_can_afford_true(self) -> None:
        """can_afford returns True when resources cover the cost."""
        res = player.Resources(wood=2, brick=2)
        self.assertTrue(res.can_afford(player.ROAD_COST))

    def test_can_afford_false(self) -> None:
        """can_afford returns False when resources are insufficient."""
        res = player.Resources(wood=1)
        self.assertFalse(res.can_afford(player.ROAD_COST))

    def test_subtract(self) -> None:
        """subtract returns a new Resources with the cost removed."""
        res = player.Resources(wood=3, brick=2)
        result = res.subtract(player.ROAD_COST)
        self.assertEqual(result.wood, 2)
        self.assertEqual(result.brick, 1)
        # Original is unchanged.
        self.assertEqual(res.wood, 3)

    def test_add(self) -> None:
        """add combines two Resources."""
        a = player.Resources(wood=1, sheep=2)
        b = player.Resources(wood=2, ore=1)
        result = a.add(b)
        self.assertEqual(result.wood, 3)
        self.assertEqual(result.sheep, 2)
        self.assertEqual(result.ore, 1)

    def test_get(self) -> None:
        """get returns the count for a given ResourceType."""
        from games.app.catan.models import board

        res = player.Resources(ore=4)
        self.assertEqual(res.get(board.ResourceType.ORE), 4)
        self.assertEqual(res.get(board.ResourceType.WHEAT), 0)

    def test_with_resource(self) -> None:
        """with_resource returns a new Resources with one field replaced."""
        from games.app.catan.models import board

        res = player.Resources(ore=2)
        new_res = res.with_resource(board.ResourceType.ORE, 10)
        self.assertEqual(new_res.ore, 10)
        self.assertEqual(res.ore, 2)


class TestDevCardHand(unittest.TestCase):
    """Tests for DevCardHand model."""

    def test_total_empty(self) -> None:
        """Default hand has 0 total cards."""
        self.assertEqual(player.DevCardHand().total(), 0)

    def test_total_mixed(self) -> None:
        """total() sums all card types."""
        hand = player.DevCardHand(knight=3, victory_point=2)
        self.assertEqual(hand.total(), 5)

    def test_get(self) -> None:
        """get returns count for a specific card type."""
        hand = player.DevCardHand(monopoly=2)
        self.assertEqual(hand.get(player.DevCardType.MONOPOLY), 2)
        self.assertEqual(hand.get(player.DevCardType.KNIGHT), 0)

    def test_add_increases_count(self) -> None:
        """add returns a new hand with the count incremented."""
        hand = player.DevCardHand(knight=1)
        new_hand = hand.add(player.DevCardType.KNIGHT)
        self.assertEqual(new_hand.knight, 2)
        # Original unchanged.
        self.assertEqual(hand.knight, 1)

    def test_remove_decreases_count(self) -> None:
        """remove returns a new hand with the count decremented."""
        hand = player.DevCardHand(road_building=2)
        new_hand = hand.remove(player.DevCardType.ROAD_BUILDING)
        self.assertEqual(new_hand.road_building, 1)


class TestDevCardCounts(unittest.TestCase):
    """Tests for the standard dev card deck composition."""

    def test_total_deck_size(self) -> None:
        """Standard deck contains exactly 25 cards."""
        total = sum(player.DEV_CARD_COUNTS.values())
        self.assertEqual(total, 25)

    def test_knight_count(self) -> None:
        """There are 14 Knight cards in a standard deck."""
        self.assertEqual(player.DEV_CARD_COUNTS[player.DevCardType.KNIGHT], 14)


class TestBuildInventory(unittest.TestCase):
    """Tests for BuildInventory model."""

    def test_default_inventory(self) -> None:
        """Default inventory has standard piece counts."""
        inv = player.BuildInventory()
        self.assertEqual(inv.settlements_remaining, 5)
        self.assertEqual(inv.cities_remaining, 4)
        self.assertEqual(inv.roads_remaining, 15)


class TestPlayer(unittest.TestCase):
    """Tests for Player model."""

    def test_default_player(self) -> None:
        """A new player starts with empty resources and 0 VP."""
        p = player.Player(player_index=0, name='Alice', color='red')
        self.assertEqual(p.resources.total(), 0)
        self.assertEqual(p.victory_points, 0)
        self.assertFalse(p.is_ai)
        self.assertIsNone(p.ai_type)

    def test_ai_player(self) -> None:
        """An AI player can be flagged and given a type."""
        p = player.Player(
            player_index=1, name='Bot', color='blue', is_ai=True, ai_type='easy'
        )
        self.assertTrue(p.is_ai)
        self.assertEqual(p.ai_type, 'easy')

    def test_default_build_inventory(self) -> None:
        """Player starts with full building inventory."""
        p = player.Player(player_index=0, name='Bob', color='green')
        self.assertEqual(p.build_inventory.roads_remaining, 15)


if __name__ == '__main__':
    unittest.main()
