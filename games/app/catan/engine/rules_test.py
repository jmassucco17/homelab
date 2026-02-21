"""Unit tests for the Catan rules engine stub."""

from __future__ import annotations

import unittest

from games.app.catan.board_generator import generate_board
from games.app.catan.engine import rules
from games.app.catan.models import game_state as gs_module
from games.app.catan.models import player as player_module


class TestRulesStub(unittest.TestCase):
    """Tests for the Phase 4 stub implementation of the rules engine."""

    def setUp(self) -> None:
        """Build a minimal GameState for testing."""
        board = generate_board(seed=42)
        players = [
            player_module.Player(player_index=0, name='Alice', color='red'),
            player_module.Player(player_index=1, name='Bob', color='blue'),
        ]
        self.game_state = gs_module.GameState(
            players=players,
            board=board,
            turn_state=gs_module.TurnState(player_index=0),
        )

    def test_get_legal_actions_returns_list(self) -> None:
        """get_legal_actions should return a list."""
        result = rules.get_legal_actions(self.game_state, 0)
        self.assertIsInstance(result, list)

    def test_get_legal_actions_stub_returns_empty(self) -> None:
        """The stub always returns an empty list (Phase 4 fills this in)."""
        result = rules.get_legal_actions(self.game_state, 0)
        self.assertEqual(result, [])

    def test_get_legal_actions_any_player_index(self) -> None:
        """Returns empty list regardless of player index."""
        for idx in range(len(self.game_state.players)):
            self.assertEqual(rules.get_legal_actions(self.game_state, idx), [])


if __name__ == '__main__':
    unittest.main()
