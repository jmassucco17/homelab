"""Unit tests for the Catan AI base class."""

from __future__ import annotations

import unittest

from games.app.catan.ai import base
from games.app.catan.engine import trade as trade_module
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

    def respond_to_trade(
        self,
        state: game_state.GameState,
        player_index: int,
        pending_trade: trade_module.PendingTrade,
    ) -> actions.AcceptTrade | actions.RejectTrade:
        """Always reject trade offers."""
        return actions.RejectTrade(
            player_index=player_index, trade_id=pending_trade.trade_id
        )


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

    def test_subclass_missing_respond_to_trade_cannot_instantiate(self) -> None:
        """A subclass that omits respond_to_trade cannot be instantiated."""

        class _IncompleteAI(base.CatanAI):
            def choose_action(
                self,
                state: game_state.GameState,
                player_index: int,
                legal_actions: list[actions.Action],
            ) -> actions.Action:
                return legal_actions[0]

        with self.assertRaises(TypeError):
            _IncompleteAI()  # type: ignore[abstract]

    def test_concrete_subclass_respond_to_trade(self) -> None:
        """A concrete subclass must implement respond_to_trade."""
        ai = _ConcreteAI()
        state = turn_manager.create_initial_game_state(
            ['Alice', 'Bob'], ['red', 'blue'], seed=1
        )
        pending = trade_module.PendingTrade(
            trade_id='abc',
            offering_player=0,
            offering={'wood': 1},
            requesting={'ore': 1},
            target_player=None,
        )
        response = ai.respond_to_trade(state, 1, pending)
        self.assertIsInstance(response, actions.RejectTrade)
        self.assertEqual(response.player_index, 1)
        self.assertEqual(response.trade_id, 'abc')


if __name__ == '__main__':
    unittest.main()
