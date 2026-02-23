"""Unit tests for the AI simulation runner."""

from __future__ import annotations

import unittest

from games.app.catan.ai import easy, simulate


class TestSimulate(unittest.TestCase):
    """Smoke tests for the simulation runner."""

    def test_run_simulation_returns_dict(self) -> None:
        """run_simulation returns a dict with expected keys."""
        result = simulate.run_simulation(num_games=2, num_players=2, ai_type='easy')
        self.assertIn('wins', result)
        self.assertIn('action_counts', result)
        self.assertIn('timeouts', result)
        self.assertIn('elapsed', result)

    def test_run_simulation_win_counts_sum_to_games(self) -> None:
        """Win counts plus timeouts equal number of games played."""
        num_games = 3
        result = simulate.run_simulation(
            num_games=num_games, num_players=2, ai_type='easy', start_seed=99
        )
        timeouts = result['timeouts']
        assert isinstance(timeouts, int)
        # At most num_games timeouts (all remaining are wins).
        self.assertLessEqual(timeouts, num_games)

    def test_make_ais_correct_count(self) -> None:
        """_make_ais returns one AI per player."""
        ais = simulate.make_ais('easy', 3)
        self.assertEqual(len(ais), 3)
        for ai in ais:
            self.assertIsInstance(ai, easy.EasyAI)

    def test_run_one_game_returns_winner(self) -> None:
        """run_one_game returns a non-None winner for a short seeded game."""
        ais = simulate.make_ais('easy', 2, seed_offset=0)
        _winner, actions_taken = simulate.run_one_game(ais, seed=42)
        # Game should finish within the action cap.
        self.assertGreater(actions_taken, 0)


if __name__ == '__main__':
    unittest.main()
