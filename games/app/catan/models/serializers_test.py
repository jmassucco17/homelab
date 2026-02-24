"""Unit tests for catan model serialization helpers."""

from __future__ import annotations

import json
import unittest

from games.app.catan.board_generator import generate_board
from games.app.catan.engine import turn_manager
from games.app.catan.models import player, serializers


def _make_player() -> player.Player:
    """Return a simple Player instance for testing."""
    return player.Player(player_index=0, name='Alice', color='red')


def _make_game_state() -> object:
    """Return a minimal 2-player GameState for testing."""
    return turn_manager.create_initial_game_state(
        ['Alice', 'Bob'], ['red', 'blue'], seed=42
    )


class TestSerializeModel(unittest.TestCase):
    """Tests for serialize_model."""

    def test_returns_dict(self) -> None:
        """serialize_model returns a plain Python dict."""
        p = _make_player()
        data = serializers.serialize_model(p)
        self.assertIsInstance(data, dict)

    def test_dict_contains_expected_keys(self) -> None:
        """Serialized player dict contains core field keys."""
        p = _make_player()
        data = serializers.serialize_model(p)
        self.assertIn('name', data)
        self.assertIn('color', data)
        self.assertIn('resources', data)


class TestSerializeToJson(unittest.TestCase):
    """Tests for serialize_to_json."""

    def test_returns_string(self) -> None:
        """serialize_to_json returns a JSON string."""
        p = _make_player()
        result = serializers.serialize_to_json(p)
        self.assertIsInstance(result, str)

    def test_valid_json(self) -> None:
        """serialize_to_json output is valid JSON."""
        p = _make_player()
        result = serializers.serialize_to_json(p)
        parsed = json.loads(result)
        self.assertEqual(parsed['name'], 'Alice')


class TestDeserializeBoard(unittest.TestCase):
    """Tests for deserialize_board."""

    def test_round_trip(self) -> None:
        """Board survives a serialize → deserialize round-trip."""
        board = generate_board(seed=1)
        data = serializers.serialize_model(board)
        restored = serializers.deserialize_board(data)
        self.assertEqual(len(restored.tiles), len(board.tiles))
        self.assertEqual(len(restored.vertices), len(board.vertices))
        self.assertEqual(len(restored.edges), len(board.edges))


class TestDeserializeGameState(unittest.TestCase):
    """Tests for deserialize_game_state."""

    def test_round_trip(self) -> None:
        """GameState survives a serialize → deserialize round-trip."""
        state = _make_game_state()
        data = serializers.serialize_model(state)  # type: ignore[arg-type]
        restored = serializers.deserialize_game_state(data)
        self.assertEqual(len(restored.players), 2)


class TestDeserializePlayer(unittest.TestCase):
    """Tests for deserialize_player."""

    def test_round_trip(self) -> None:
        """Player survives a serialize → deserialize round-trip."""
        p = _make_player()
        data = serializers.serialize_model(p)
        restored = serializers.deserialize_player(data)
        self.assertEqual(restored.name, 'Alice')
        self.assertEqual(restored.color, 'red')


class TestGameStateJson(unittest.TestCase):
    """Tests for game_state_to_json and game_state_from_json."""

    def test_to_json_returns_string(self) -> None:
        """game_state_to_json returns a JSON string."""
        state = _make_game_state()
        result = serializers.game_state_to_json(state)  # type: ignore[arg-type]
        self.assertIsInstance(result, str)

    def test_from_json_round_trip(self) -> None:
        """GameState survives a to_json → from_json round-trip."""
        state = _make_game_state()
        json_str = serializers.game_state_to_json(state)  # type: ignore[arg-type]
        restored = serializers.game_state_from_json(json_str)
        self.assertEqual(len(restored.players), 2)
        self.assertEqual(restored.players[0].name, 'Alice')


if __name__ == '__main__':
    unittest.main()
