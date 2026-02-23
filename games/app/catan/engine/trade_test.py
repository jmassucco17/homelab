"""Tests for Catan trading logic."""

from __future__ import annotations

import unittest

from games.app.catan import board_generator
from games.app.catan.engine import trade
from games.app.catan.models import actions, board
from games.app.catan.models import game_state as game_state_module
from games.app.catan.models import player as player_module


def _make_player(
    index: int = 0,
    resources: player_module.Resources | None = None,
    ports: list[board.PortType] | None = None,
) -> player_module.Player:
    return player_module.Player(
        player_index=index,
        name=f'Player{index}',
        color='red',
        resources=resources or player_module.Resources(),
        ports_owned=ports or [],
    )


def _make_game_state(
    players: list[player_module.Player], active_player: int = 0
) -> game_state_module.GameState:
    return game_state_module.GameState(
        players=players,
        board=board_generator.generate_board(),
        phase=game_state_module.GamePhase.MAIN,
        turn_state=game_state_module.TurnState(player_index=active_player),
    )


class TestBankTradeRatio(unittest.TestCase):
    def test_no_port_returns_4(self) -> None:
        player = _make_player(ports=[])
        self.assertEqual(trade.get_bank_trade_ratio(board.ResourceType.WOOD, player), 4)

    def test_generic_port_returns_3(self) -> None:
        player = _make_player(ports=[board.PortType.GENERIC])
        self.assertEqual(trade.get_bank_trade_ratio(board.ResourceType.WOOD, player), 3)

    def test_matching_specific_port_returns_2(self) -> None:
        player = _make_player(ports=[board.PortType.WOOD])
        self.assertEqual(trade.get_bank_trade_ratio(board.ResourceType.WOOD, player), 2)

    def test_non_matching_specific_port_returns_4(self) -> None:
        player = _make_player(ports=[board.PortType.BRICK])
        self.assertEqual(trade.get_bank_trade_ratio(board.ResourceType.WOOD, player), 4)

    def test_specific_port_beats_generic(self) -> None:
        player = _make_player(ports=[board.PortType.GENERIC, board.PortType.ORE])
        self.assertEqual(trade.get_bank_trade_ratio(board.ResourceType.ORE, player), 2)


class TestCanBankTrade(unittest.TestCase):
    def test_insufficient_resources_returns_false(self) -> None:
        player = _make_player(resources=player_module.Resources(wood=3))
        ok, msg = trade.can_bank_trade(
            player, board.ResourceType.WOOD, board.ResourceType.BRICK
        )
        self.assertFalse(ok)
        self.assertIn('Need 4', msg)

    def test_sufficient_resources_returns_true(self) -> None:
        player = _make_player(resources=player_module.Resources(wood=4))
        ok, _ = trade.can_bank_trade(
            player, board.ResourceType.WOOD, board.ResourceType.BRICK
        )
        self.assertTrue(ok)

    def test_same_resource_returns_false(self) -> None:
        player = _make_player(resources=player_module.Resources(wood=4))
        ok, msg = trade.can_bank_trade(
            player, board.ResourceType.WOOD, board.ResourceType.WOOD
        )
        self.assertFalse(ok)
        self.assertIn('itself', msg)

    def test_generic_port_reduces_required_amount(self) -> None:
        player = _make_player(
            resources=player_module.Resources(wood=3), ports=[board.PortType.GENERIC]
        )
        ok, _ = trade.can_bank_trade(
            player, board.ResourceType.WOOD, board.ResourceType.ORE
        )
        self.assertTrue(ok)


class TestApplyBankTrade(unittest.TestCase):
    def test_4_to_1_no_port(self) -> None:
        player = _make_player(resources=player_module.Resources(wood=4))
        updated = trade.apply_bank_trade(
            player, board.ResourceType.WOOD, board.ResourceType.ORE
        )
        self.assertEqual(updated.resources.wood, 0)
        self.assertEqual(updated.resources.ore, 1)

    def test_3_to_1_generic_port(self) -> None:
        player = _make_player(
            resources=player_module.Resources(wheat=5), ports=[board.PortType.GENERIC]
        )
        updated = trade.apply_bank_trade(
            player, board.ResourceType.WHEAT, board.ResourceType.SHEEP
        )
        self.assertEqual(updated.resources.wheat, 2)
        self.assertEqual(updated.resources.sheep, 1)

    def test_2_to_1_specific_port(self) -> None:
        player = _make_player(
            resources=player_module.Resources(ore=2), ports=[board.PortType.ORE]
        )
        updated = trade.apply_bank_trade(
            player, board.ResourceType.ORE, board.ResourceType.BRICK
        )
        self.assertEqual(updated.resources.ore, 0)
        self.assertEqual(updated.resources.brick, 1)


class TestPortTrade(unittest.TestCase):
    def test_can_port_trade_generic_success(self) -> None:
        player = _make_player(
            resources=player_module.Resources(wood=3), ports=[board.PortType.GENERIC]
        )
        ok, _ = trade.can_port_trade(
            player, board.ResourceType.WOOD, 3, board.ResourceType.ORE
        )
        self.assertTrue(ok)

    def test_can_port_trade_specific_success(self) -> None:
        player = _make_player(
            resources=player_module.Resources(brick=2), ports=[board.PortType.BRICK]
        )
        ok, _ = trade.can_port_trade(
            player, board.ResourceType.BRICK, 2, board.ResourceType.WHEAT
        )
        self.assertTrue(ok)

    def test_can_port_trade_missing_specific_port(self) -> None:
        player = _make_player(resources=player_module.Resources(brick=2), ports=[])
        ok, msg = trade.can_port_trade(
            player, board.ResourceType.BRICK, 2, board.ResourceType.WHEAT
        )
        self.assertFalse(ok)
        self.assertIn('port', msg)

    def test_can_port_trade_missing_generic_port(self) -> None:
        player = _make_player(resources=player_module.Resources(brick=3), ports=[])
        ok, msg = trade.can_port_trade(
            player, board.ResourceType.BRICK, 3, board.ResourceType.WHEAT
        )
        self.assertFalse(ok)
        self.assertIn('port', msg)

    def test_can_port_trade_insufficient_resources(self) -> None:
        player = _make_player(
            resources=player_module.Resources(wood=1), ports=[board.PortType.GENERIC]
        )
        ok, msg = trade.can_port_trade(
            player, board.ResourceType.WOOD, 3, board.ResourceType.ORE
        )
        self.assertFalse(ok)
        self.assertIn('Need', msg)

    def test_apply_port_trade_generic(self) -> None:
        player = _make_player(
            resources=player_module.Resources(wood=3), ports=[board.PortType.GENERIC]
        )
        updated = trade.apply_port_trade(
            player, board.ResourceType.WOOD, 3, board.ResourceType.ORE
        )
        self.assertEqual(updated.resources.wood, 0)
        self.assertEqual(updated.resources.ore, 1)

    def test_apply_port_trade_specific(self) -> None:
        player = _make_player(
            resources=player_module.Resources(sheep=2), ports=[board.PortType.SHEEP]
        )
        updated = trade.apply_port_trade(
            player, board.ResourceType.SHEEP, 2, board.ResourceType.BRICK
        )
        self.assertEqual(updated.resources.sheep, 0)
        self.assertEqual(updated.resources.brick, 1)

    def test_same_resource_rejected(self) -> None:
        player = _make_player(
            resources=player_module.Resources(wood=3), ports=[board.PortType.GENERIC]
        )
        ok, msg = trade.can_port_trade(
            player, board.ResourceType.WOOD, 3, board.ResourceType.WOOD
        )
        self.assertFalse(ok)
        self.assertIn('itself', msg)


class TestCreateTradeOffer(unittest.TestCase):
    def _action(
        self,
        player_index: int = 0,
        offering: dict[str, int] | None = None,
        requesting: dict[str, int] | None = None,
    ) -> actions.TradeOffer:
        return actions.TradeOffer(
            player_index=player_index,
            offering=offering or {'wood': 1},
            requesting=requesting or {'ore': 1},
        )

    def test_valid_offer(self) -> None:
        players = [_make_player(0, player_module.Resources(wood=2)), _make_player(1)]
        state = _make_game_state(players, active_player=0)
        ok, _, pending = trade.create_trade_offer(state, self._action())
        self.assertTrue(ok)
        self.assertIsNotNone(pending)
        assert pending is not None
        self.assertEqual(pending.offering_player, 0)
        self.assertEqual(pending.status, trade.TradeStatus.PENDING)

    def test_insufficient_resources(self) -> None:
        players = [_make_player(0, player_module.Resources(wood=0)), _make_player(1)]
        state = _make_game_state(players, active_player=0)
        ok, msg, pending = trade.create_trade_offer(state, self._action())
        self.assertFalse(ok)
        self.assertIn('Insufficient', msg)
        self.assertIsNone(pending)

    def test_wrong_phase(self) -> None:
        players = [_make_player(0, player_module.Resources(wood=2)), _make_player(1)]
        state = _make_game_state(players, active_player=0)
        state = state.model_copy(
            update={'phase': game_state_module.GamePhase.SETUP_FORWARD}
        )
        ok, msg, pending = trade.create_trade_offer(state, self._action())
        self.assertFalse(ok)
        self.assertIn('main phase', msg)
        self.assertIsNone(pending)

    def test_not_active_player(self) -> None:
        players = [
            _make_player(0, player_module.Resources(wood=2)),
            _make_player(1, player_module.Resources(wood=2)),
        ]
        state = _make_game_state(players, active_player=0)
        ok, msg, pending = trade.create_trade_offer(state, self._action(player_index=1))
        self.assertFalse(ok)
        self.assertIn('active player', msg)
        self.assertIsNone(pending)


class TestAcceptTrade(unittest.TestCase):
    def _pending(self) -> trade.PendingTrade:
        return trade.PendingTrade(
            trade_id='test-id',
            offering_player=0,
            offering={'wood': 1},
            requesting={'ore': 1},
            target_player=None,
        )

    def test_happy_path(self) -> None:
        players = [
            _make_player(0, player_module.Resources(wood=2)),
            _make_player(1, player_module.Resources(ore=2)),
        ]
        state = _make_game_state(players)
        pending = self._pending()
        ok, _, new_state = trade.accept_trade(state, pending, accepting_player=1)
        self.assertTrue(ok)
        assert new_state is not None
        self.assertEqual(new_state.players[0].resources.wood, 1)
        self.assertEqual(new_state.players[0].resources.ore, 1)
        self.assertEqual(new_state.players[1].resources.ore, 1)
        self.assertEqual(new_state.players[1].resources.wood, 1)

    def test_offerer_insufficient(self) -> None:
        players = [
            _make_player(0, player_module.Resources(wood=0)),
            _make_player(1, player_module.Resources(ore=2)),
        ]
        state = _make_game_state(players)
        pending = self._pending()
        ok, msg, new_state = trade.accept_trade(state, pending, accepting_player=1)
        self.assertFalse(ok)
        self.assertIn('Offering player', msg)
        self.assertIsNone(new_state)

    def test_accepter_insufficient(self) -> None:
        players = [
            _make_player(0, player_module.Resources(wood=2)),
            _make_player(1, player_module.Resources(ore=0)),
        ]
        state = _make_game_state(players)
        pending = self._pending()
        ok, msg, new_state = trade.accept_trade(state, pending, accepting_player=1)
        self.assertFalse(ok)
        self.assertIn('Accepting player', msg)
        self.assertIsNone(new_state)

    def test_cancelled_trade_rejected(self) -> None:
        players = [
            _make_player(0, player_module.Resources(wood=2)),
            _make_player(1, player_module.Resources(ore=2)),
        ]
        state = _make_game_state(players)
        pending = self._pending().model_copy(
            update={'status': trade.TradeStatus.CANCELLED}
        )
        ok, msg, _ = trade.accept_trade(state, pending, accepting_player=1)
        self.assertFalse(ok)
        self.assertIn('no longer pending', msg)


class TestRejectAndCancelTrade(unittest.TestCase):
    def _pending(self) -> trade.PendingTrade:
        return trade.PendingTrade(
            trade_id='test-id',
            offering_player=0,
            offering={'wood': 1},
            requesting={'ore': 1},
            target_player=None,
        )

    def test_reject_trade_records_player(self) -> None:
        pending = self._pending()
        updated = trade.reject_trade(pending, rejecting_player=1)
        self.assertIn(1, updated.rejected_by)
        self.assertEqual(updated.status, trade.TradeStatus.PENDING)

    def test_reject_trade_idempotent(self) -> None:
        pending = self._pending()
        updated = trade.reject_trade(trade.reject_trade(pending, 1), 1)
        self.assertEqual(updated.rejected_by.count(1), 1)

    def test_cancel_trade(self) -> None:
        pending = self._pending()
        updated = trade.cancel_trade(pending)
        self.assertEqual(updated.status, trade.TradeStatus.CANCELLED)


if __name__ == '__main__':
    unittest.main()
