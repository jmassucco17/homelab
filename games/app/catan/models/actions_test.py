"""Unit tests for catan action models."""

from __future__ import annotations

import unittest

import pydantic

from games.app.catan.models import actions, board


class TestActionType(unittest.TestCase):
    """Tests for ActionType enum."""

    def test_all_action_types_are_strings(self) -> None:
        """Every ActionType value should be a non-empty string."""
        for action_type in actions.ActionType:
            self.assertIsInstance(action_type.value, str)
            self.assertTrue(action_type.value)


class TestPlaceSettlement(unittest.TestCase):
    """Tests for PlaceSettlement action."""

    def test_construction(self) -> None:
        """PlaceSettlement sets action_type automatically."""
        action = actions.PlaceSettlement(player_index=0, vertex_id=5)
        self.assertEqual(action.player_index, 0)
        self.assertEqual(action.vertex_id, 5)
        self.assertEqual(action.action_type, actions.ActionType.PLACE_SETTLEMENT)

    def test_missing_fields_raise(self) -> None:
        """Missing required fields raise a ValidationError."""
        with self.assertRaises(pydantic.ValidationError):
            actions.PlaceSettlement(player_index=0)  # type: ignore[call-arg]


class TestPlaceRoad(unittest.TestCase):
    """Tests for PlaceRoad action."""

    def test_construction(self) -> None:
        """PlaceRoad sets action_type automatically."""
        action = actions.PlaceRoad(player_index=1, edge_id=10)
        self.assertEqual(action.edge_id, 10)
        self.assertEqual(action.action_type, actions.ActionType.PLACE_ROAD)


class TestPlayYearOfPlenty(unittest.TestCase):
    """Tests for PlayYearOfPlenty action."""

    def test_construction_with_two_resources(self) -> None:
        """PlayYearOfPlenty requires two resource types."""
        action = actions.PlayYearOfPlenty(
            player_index=0,
            resource1=board.ResourceType.WOOD,
            resource2=board.ResourceType.ORE,
        )
        self.assertEqual(action.resource1, board.ResourceType.WOOD)
        self.assertEqual(action.resource2, board.ResourceType.ORE)


class TestTradeOffer(unittest.TestCase):
    """Tests for TradeOffer action."""

    def test_construction_with_target_player(self) -> None:
        """TradeOffer with a specific target player."""
        action = actions.TradeOffer(
            player_index=0,
            offering={'wood': 2},
            requesting={'ore': 1},
            target_player=1,
        )
        self.assertEqual(action.offering, {'wood': 2})
        self.assertEqual(action.requesting, {'ore': 1})
        self.assertEqual(action.target_player, 1)

    def test_construction_broadcast(self) -> None:
        """TradeOffer without target defaults to broadcast."""
        action = actions.TradeOffer(
            player_index=0,
            offering={'wheat': 1},
            requesting={'brick': 1},
        )
        self.assertIsNone(action.target_player)


class TestActionResult(unittest.TestCase):
    """Tests for ActionResult model."""

    def test_success_result(self) -> None:
        """Successful result has no error message."""
        result = actions.ActionResult(success=True, updated_state={'phase': 'main'})
        self.assertTrue(result.success)
        self.assertIsNone(result.error_message)

    def test_failure_result(self) -> None:
        """Failed result carries an error message and no state."""
        result = actions.ActionResult(success=False, error_message='Invalid move.')
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, 'Invalid move.')
        self.assertIsNone(result.updated_state)


class TestDiscriminatedUnion(unittest.TestCase):
    """Tests for the Action discriminated union deserialization."""

    def test_deserialize_place_settlement(self) -> None:
        """A dict with action_type=place_settlement deserializes correctly."""
        data = {'action_type': 'place_settlement', 'player_index': 0, 'vertex_id': 3}
        action: actions.Action = pydantic.TypeAdapter(  # type: ignore[assignment]
            actions.Action
        ).validate_python(data)
        self.assertIsInstance(action, actions.PlaceSettlement)  # type: ignore[arg-type]
        assert isinstance(action, actions.PlaceSettlement)
        self.assertEqual(action.vertex_id, 3)

    def test_deserialize_end_turn(self) -> None:
        """A dict with action_type=end_turn deserializes to EndTurn."""
        data = {'action_type': 'end_turn', 'player_index': 1}
        action: actions.Action = pydantic.TypeAdapter(  # type: ignore[assignment]
            actions.Action
        ).validate_python(data)
        self.assertIsInstance(action, actions.EndTurn)  # type: ignore[arg-type]


if __name__ == '__main__':
    unittest.main()
