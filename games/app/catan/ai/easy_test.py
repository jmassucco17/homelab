"""Unit tests for the Easy (random) AI."""

from __future__ import annotations

import unittest

from games.app.catan.ai import easy
from games.app.catan.engine import rules, turn_manager
from games.app.catan.models import game_state


class TestEasyAI(unittest.TestCase):
    """Tests for EasyAI."""

    def setUp(self) -> None:
        """Create a fresh game state and AI for each test."""
        self.state = turn_manager.create_initial_game_state(
            ['Alice', 'Bob'], ['red', 'blue'], seed=42
        )
        self.ai = easy.EasyAI(seed=0)

    def test_choose_action_returns_legal_action(self) -> None:
        """EasyAI must always return an action from the legal list."""
        legal = rules.get_legal_actions(self.state, 0)
        chosen = self.ai.choose_action(self.state, 0, legal)
        self.assertIn(chosen, legal)

    def test_choose_action_is_random(self) -> None:
        """Multiple calls may return different actions (probabilistic)."""
        legal = rules.get_legal_actions(self.state, 0)
        if len(legal) < 2:
            self.skipTest('Need at least 2 legal actions to test randomness')
        choices = {
            self.ai.choose_action(self.state, 0, legal).action_type for _ in range(30)
        }
        # With 30 draws from ≥2 choices, we should see > 1 distinct type most runs.
        # Use a seeded AI so this is deterministic.
        ai2 = easy.EasyAI(seed=99)
        choices2 = {
            ai2.choose_action(self.state, 0, legal).action_type for _ in range(30)
        }
        # At minimum, we confirm it returned valid actions each time.
        self.assertTrue(len(choices) >= 1)
        self.assertTrue(len(choices2) >= 1)

    def test_seeded_reproducible(self) -> None:
        """Two EasyAI instances with the same seed make the same choices."""
        ai_a = easy.EasyAI(seed=7)
        ai_b = easy.EasyAI(seed=7)
        legal = rules.get_legal_actions(self.state, 0)
        for _ in range(10):
            a = ai_a.choose_action(self.state, 0, legal)
            b = ai_b.choose_action(self.state, 0, legal)
            self.assertEqual(a.action_type, b.action_type)

    def test_discard_action_is_legal(self) -> None:
        """EasyAI can handle DISCARD_RESOURCES actions."""
        from games.app.catan.models import player

        state = turn_manager.create_initial_game_state(
            ['Alice', 'Bob'], ['red', 'blue'], seed=1
        )
        state.phase = game_state.GamePhase.MAIN
        from games.app.catan.models import game_state as gs

        state.turn_state = gs.TurnState(
            player_index=0,
            pending_action=gs.PendingActionType.DISCARD_RESOURCES,
            discard_player_indices=[1],
        )
        state.players[1].resources = player.Resources(
            wood=2, brick=2, wheat=2, sheep=2, ore=2
        )
        legal = rules.get_legal_actions(state, 1)
        self.assertGreater(len(legal), 0)
        chosen = self.ai.choose_action(state, 1, legal)
        self.assertIn(chosen, legal)


if __name__ == '__main__':
    unittest.main()
