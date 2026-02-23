"""Unit tests for the Catan AI base class."""

from __future__ import annotations

import unittest

from games.app.catan.ai import base
from games.app.catan.engine import turn_manager
from games.app.catan.models import actions, game_state


class _ConcreteAI(base.CatanAI):
    """Minimal concrete AI that always picks the first legal action."""

    def choose_action(
        self,
        state: game_state.GameState,
        player_index: int,
        legal_actions: list[actions.Action],
    ) -> actions.Action:
        """Return the first available action."""
        return legal_actions[0]


class TestCatanAIBase(unittest.TestCase):
    """Tests for the abstract CatanAI interface."""

    def test_cannot_instantiate_abstract(self) -> None:
        """CatanAI cannot be instantiated directly."""
        with self.assertRaises(TypeError):
            base.CatanAI()  # type: ignore[abstract]

    def test_concrete_subclass_choose_action(self) -> None:
        """A concrete subclass must implement choose_action."""
        ai = _ConcreteAI()
        state = turn_manager.create_initial_game_state(
            ['Alice', 'Bob'], ['red', 'blue'], seed=1
        )
        from games.app.catan.engine import rules

        legal = rules.get_legal_actions(state, 0)
        self.assertGreater(len(legal), 0)
        chosen = ai.choose_action(state, 0, legal)
        self.assertIn(chosen, legal)


if __name__ == '__main__':
    unittest.main()
