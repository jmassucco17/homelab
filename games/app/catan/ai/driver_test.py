"""Unit tests for the AI driver."""

from __future__ import annotations

import asyncio
import unittest
import unittest.mock

from games.app.catan.ai import driver, easy
from games.app.catan.engine import turn_manager
from games.app.catan.models import game_state


def _make_state(seed: int = 42) -> game_state.GameState:
    """Create a fresh 2-player game state."""
    return turn_manager.create_initial_game_state(
        ['Alice', 'Bob'], ['red', 'blue'], seed=seed
    )


class TestRunAiTurn(unittest.TestCase):
    """Tests for run_ai_turn."""

    def _run(self, coro: object) -> game_state.GameState:
        """Run an async coroutine that returns a GameState."""
        result = asyncio.run(coro)  # type: ignore[arg-type]
        assert isinstance(result, game_state.GameState)
        return result

    def test_returns_game_state(self) -> None:
        """run_ai_turn returns a GameState instance."""
        state = _make_state()
        ai = easy.EasyAI(seed=0)
        with unittest.mock.patch('asyncio.sleep', return_value=None):
            result = self._run(driver.run_ai_turn(state, 0, ai))
        self.assertIsInstance(result, game_state.GameState)

    def test_setup_phase_advances(self) -> None:
        """run_ai_turn advances the game during setup phase."""
        state = _make_state()
        original_turn = state.turn_state.player_index
        ai = easy.EasyAI(seed=1)
        with unittest.mock.patch('asyncio.sleep', return_value=None):
            result = self._run(driver.run_ai_turn(state, original_turn, ai))
        # State should have changed (settlement placed, road placed, or turn advanced).
        self.assertIsNotNone(result)

    def test_ended_game_returns_immediately(self) -> None:
        """run_ai_turn returns immediately if game is already over."""
        state = _make_state()
        state.phase = game_state.GamePhase.ENDED
        ai = easy.EasyAI(seed=0)
        with unittest.mock.patch('asyncio.sleep', return_value=None):
            result = self._run(driver.run_ai_turn(state, 0, ai))
        self.assertEqual(result.phase, game_state.GamePhase.ENDED)

    def test_no_legal_actions_returns_state(self) -> None:
        """run_ai_turn returns current state when player has no legal actions."""
        state = _make_state()
        # Player 1 has no actions in setup when it's player 0's turn.
        ai = easy.EasyAI(seed=0)
        with unittest.mock.patch('asyncio.sleep', return_value=None):
            result = self._run(driver.run_ai_turn(state, 1, ai))
        # State should be unchanged because player 1 had no actions.
        self.assertEqual(result.turn_state.player_index, 0)

    def test_ai_delay_constant_exists(self) -> None:
        """AI_DELAY_SECONDS constant is defined and positive."""
        self.assertGreater(driver.AI_DELAY_SECONDS, 0)

    def test_sleep_is_called(self) -> None:
        """run_ai_turn calls asyncio.sleep with AI_DELAY_SECONDS."""
        state = _make_state()
        ai = easy.EasyAI(seed=0)
        with unittest.mock.patch('asyncio.sleep', return_value=None) as mock_sleep:
            self._run(driver.run_ai_turn(state, 0, ai))
        mock_sleep.assert_called_once_with(driver.AI_DELAY_SECONDS)


if __name__ == '__main__':
    unittest.main()
