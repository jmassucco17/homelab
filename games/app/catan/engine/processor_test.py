"""Unit tests for the Catan action processor stub."""

from __future__ import annotations

import unittest

from games.app.catan.board_generator import generate_board
from games.app.catan.engine import processor
from games.app.catan.models import actions as actions_module
from games.app.catan.models import game_state as gs_module
from games.app.catan.models import player as player_module


class TestProcessorStub(unittest.TestCase):
    """Tests for the Phase 4 stub implementation of the action processor."""

    def setUp(self) -> None:
        """Build a minimal GameState and a sample action for testing."""
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
        self.action = actions_module.EndTurn(player_index=0)

    def test_apply_action_returns_action_result(self) -> None:
        """apply_action should return an ActionResult."""
        result = processor.apply_action(self.game_state, self.action)
        self.assertIsInstance(result, actions_module.ActionResult)

    def test_apply_action_stub_succeeds(self) -> None:
        """The stub always reports success."""
        result = processor.apply_action(self.game_state, self.action)
        self.assertTrue(result.success)

    def test_apply_action_stub_returns_unchanged_state(self) -> None:
        """The stub returns the original game state without modification."""
        result = processor.apply_action(self.game_state, self.action)
        self.assertEqual(result.updated_state, self.game_state)

    def test_apply_action_no_error_message(self) -> None:
        """The stub returns no error message on success."""
        result = processor.apply_action(self.game_state, self.action)
        self.assertIsNone(result.error_message)


if __name__ == '__main__':
    unittest.main()
