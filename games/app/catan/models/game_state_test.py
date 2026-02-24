"""Unit tests for catan game state models."""

from __future__ import annotations

import unittest

from games.app.catan.models import game_state


class TestGamePhase(unittest.TestCase):
    """Tests for GamePhase enum."""

    def test_all_phases_are_strings(self) -> None:
        """Every GamePhase value should be a non-empty string."""
        for phase in game_state.GamePhase:
            self.assertIsInstance(phase.value, str)
            self.assertTrue(phase.value)


class TestPendingActionType(unittest.TestCase):
    """Tests for PendingActionType enum."""

    def test_all_pending_actions_are_strings(self) -> None:
        """Every PendingActionType value should be a non-empty string."""
        for pending in game_state.PendingActionType:
            self.assertIsInstance(pending.value, str)


class TestTurnState(unittest.TestCase):
    """Tests for TurnState model."""

    def test_defaults(self) -> None:
        """TurnState defaults: no roll, not rolled, ROLL_DICE pending."""
        ts = game_state.TurnState(player_index=0)
        self.assertIsNone(ts.roll_value)
        self.assertFalse(ts.has_rolled)
        self.assertEqual(ts.pending_action, game_state.PendingActionType.ROLL_DICE)
        self.assertEqual(ts.free_roads_remaining, 0)
        self.assertEqual(ts.year_of_plenty_remaining, 0)
        self.assertEqual(ts.discard_player_indices, [])
        self.assertIsNone(ts.active_trade_id)

    def test_custom_pending_action(self) -> None:
        """TurnState can be created with a custom pending action."""
        ts = game_state.TurnState(
            player_index=1,
            pending_action=game_state.PendingActionType.MOVE_ROBBER,
        )
        self.assertEqual(ts.pending_action, game_state.PendingActionType.MOVE_ROBBER)

    def test_discard_player_indices_mutable_default(self) -> None:
        """Two TurnState instances do not share the same discard list."""
        ts1 = game_state.TurnState(player_index=0)
        ts2 = game_state.TurnState(player_index=1)
        ts1.discard_player_indices.append(0)
        self.assertNotIn(0, ts2.discard_player_indices)


class TestGameState(unittest.TestCase):
    """Tests for GameState model."""

    def _make_minimal_game_state(self) -> game_state.GameState:
        """Build a minimal GameState for testing."""
        from games.app.catan.board_generator import generate_board
        from games.app.catan.models import player

        players = [
            player.Player(player_index=i, name=f'P{i}', color='red') for i in range(2)
        ]
        return game_state.GameState(
            players=players,
            board=generate_board(seed=1),
            turn_state=game_state.TurnState(player_index=0),
        )

    def test_initial_phase(self) -> None:
        """A new GameState starts in SETUP_FORWARD phase."""
        state = self._make_minimal_game_state()
        self.assertEqual(state.phase, game_state.GamePhase.SETUP_FORWARD)

    def test_no_winner_initially(self) -> None:
        """winner_index and longest/largest army owners are None initially."""
        state = self._make_minimal_game_state()
        self.assertIsNone(state.winner_index)
        self.assertIsNone(state.longest_road_owner)
        self.assertIsNone(state.largest_army_owner)

    def test_dev_card_deck_defaults_empty(self) -> None:
        """dev_card_deck defaults to an empty list."""
        state = self._make_minimal_game_state()
        self.assertEqual(state.dev_card_deck, [])

    def test_dice_roll_history_defaults_empty(self) -> None:
        """dice_roll_history defaults to an empty list."""
        state = self._make_minimal_game_state()
        self.assertEqual(state.dice_roll_history, [])


if __name__ == '__main__':
    unittest.main()
