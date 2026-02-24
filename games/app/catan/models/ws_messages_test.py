"""Unit tests for catan WebSocket message models."""

from __future__ import annotations

import unittest

import pydantic

from games.app.catan.models import actions, ws_messages


class TestClientMessageType(unittest.TestCase):
    """Tests for ClientMessageType enum."""

    def test_all_types_are_strings(self) -> None:
        """Every ClientMessageType value should be a non-empty string."""
        for msg_type in ws_messages.ClientMessageType:
            self.assertIsInstance(msg_type.value, str)
            self.assertTrue(msg_type.value)


class TestServerMessageType(unittest.TestCase):
    """Tests for ServerMessageType enum."""

    def test_all_types_are_strings(self) -> None:
        """Every ServerMessageType value should be a non-empty string."""
        for msg_type in ws_messages.ServerMessageType:
            self.assertIsInstance(msg_type.value, str)


class TestJoinGame(unittest.TestCase):
    """Tests for JoinGame client message."""

    def test_construction(self) -> None:
        """JoinGame sets message_type automatically."""
        msg = ws_messages.JoinGame(player_name='Alice', room_code='ABC1')
        self.assertEqual(msg.player_name, 'Alice')
        self.assertEqual(msg.room_code, 'ABC1')
        self.assertEqual(msg.message_type, ws_messages.ClientMessageType.JOIN_GAME)


class TestSubmitAction(unittest.TestCase):
    """Tests for SubmitAction client message."""

    def test_construction(self) -> None:
        """SubmitAction wraps an Action."""
        action = actions.EndTurn(player_index=0)
        msg = ws_messages.SubmitAction(action=action)
        self.assertEqual(msg.action.player_index, 0)
        self.assertEqual(msg.message_type, ws_messages.ClientMessageType.SUBMIT_ACTION)


class TestRequestUndo(unittest.TestCase):
    """Tests for RequestUndo client message."""

    def test_construction(self) -> None:
        """RequestUndo has no additional fields."""
        msg = ws_messages.RequestUndo()
        self.assertEqual(msg.message_type, ws_messages.ClientMessageType.REQUEST_UNDO)


class TestClientMessageDiscrimination(unittest.TestCase):
    """Tests for ClientMessage discriminated union."""

    def test_deserialize_join_game(self) -> None:
        """A dict with message_type=join_game deserializes to JoinGame."""
        data = {
            'message_type': 'join_game',
            'player_name': 'Bob',
            'room_code': 'XYZ9',
        }
        msg: ws_messages.ClientMessage = pydantic.TypeAdapter(  # type: ignore[assignment]
            ws_messages.ClientMessage
        ).validate_python(data)
        self.assertIsInstance(msg, ws_messages.JoinGame)  # type: ignore[arg-type]
        assert isinstance(msg, ws_messages.JoinGame)
        self.assertEqual(msg.player_name, 'Bob')


class TestServerMessages(unittest.TestCase):
    """Tests for server-to-client message models."""

    def test_error_message(self) -> None:
        """ErrorMessage stores the error text."""
        msg = ws_messages.ErrorMessage(error='Something went wrong.')
        self.assertEqual(msg.error, 'Something went wrong.')
        self.assertEqual(msg.message_type, ws_messages.ServerMessageType.ERROR_MESSAGE)

    def test_player_joined(self) -> None:
        """PlayerJoined stores player info."""
        msg = ws_messages.PlayerJoined(
            player_name='Carol',
            player_index=2,
            total_players=4,
        )
        self.assertEqual(msg.player_name, 'Carol')
        self.assertEqual(msg.total_players, 4)

    def test_game_started(self) -> None:
        """GameStarted stores player names and turn order."""
        msg = ws_messages.GameStarted(
            player_names=['Alice', 'Bob'],
            turn_order=[0, 1],
        )
        self.assertEqual(len(msg.player_names), 2)
        self.assertEqual(msg.turn_order, [0, 1])

    def test_game_over(self) -> None:
        """GameOver stores winner info and final VP counts."""
        msg = ws_messages.GameOver(
            winner_player_index=1,
            winner_name='Bob',
            final_victory_points=[8, 10],
        )
        self.assertEqual(msg.winner_player_index, 1)
        self.assertEqual(msg.final_victory_points, [8, 10])

    def test_trade_proposed_optional_target(self) -> None:
        """TradeProposed can have None target_player for broadcast."""
        msg = ws_messages.TradeProposed(
            trade_id='abc123',
            offering_player=0,
            offering={'wood': 2},
            requesting={'ore': 1},
            target_player=None,
        )
        self.assertIsNone(msg.target_player)

    def test_trade_accepted(self) -> None:
        """TradeAccepted records both players."""
        msg = ws_messages.TradeAccepted(
            trade_id='t1',
            offering_player=0,
            accepting_player=1,
        )
        self.assertEqual(msg.accepting_player, 1)

    def test_trade_rejected(self) -> None:
        """TradeRejected records the rejecting player."""
        msg = ws_messages.TradeRejected(trade_id='t2', rejecting_player=2)
        self.assertEqual(msg.rejecting_player, 2)

    def test_trade_cancelled(self) -> None:
        """TradeCancelled records the offering player."""
        msg = ws_messages.TradeCancelled(trade_id='t3', offering_player=0)
        self.assertEqual(msg.offering_player, 0)


if __name__ == '__main__':
    unittest.main()
