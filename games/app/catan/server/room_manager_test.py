"""Unit tests for the Catan room manager."""

from __future__ import annotations

import datetime
import unittest
import unittest.mock

import fastapi

from games.app.catan.server import room_manager as rm_module


class TestRoomManager(unittest.TestCase):
    """Unit tests for RoomManager."""

    def setUp(self) -> None:
        """Create a fresh RoomManager for each test."""
        self.mgr = rm_module.RoomManager()

    def test_create_room_returns_four_char_code(self) -> None:
        """create_room returns a 4-character alphanumeric code."""
        code = self.mgr.create_room()
        self.assertEqual(len(code), 4)
        self.assertTrue(code.isalnum())

    def test_create_room_stores_room(self) -> None:
        """Created room is retrievable by code."""
        code = self.mgr.create_room()
        room = self.mgr.get_room(code)
        self.assertIsNotNone(room)

    def test_create_multiple_rooms_unique_codes(self) -> None:
        """Each created room gets a distinct code."""
        codes = {self.mgr.create_room() for _ in range(10)}
        self.assertEqual(len(codes), 10)

    def test_get_room_unknown_code_returns_none(self) -> None:
        """get_room returns None for an unknown code."""
        self.assertIsNone(self.mgr.get_room('ZZZZ'))

    def test_initial_room_phase_is_lobby(self) -> None:
        """A freshly created room has 'lobby' phase."""
        code = self.mgr.create_room()
        room = self.mgr.get_room(code)
        assert room is not None
        self.assertEqual(room.phase, 'lobby')

    def test_initial_room_player_count_is_zero(self) -> None:
        """A freshly created room has no players."""
        code = self.mgr.create_room()
        room = self.mgr.get_room(code)
        assert room is not None
        self.assertEqual(room.player_count, 0)


class TestPlayerSlot(unittest.TestCase):
    """Unit tests for PlayerSlot."""

    def _make_slot(self) -> rm_module.PlayerSlot:
        """Return a connected PlayerSlot with a mock WebSocket."""
        ws = unittest.mock.MagicMock(spec=fastapi.WebSocket)
        return rm_module.PlayerSlot(
            player_index=0, name='Alice', color='red', websocket=ws
        )

    def test_is_connected_true_when_ws_present(self) -> None:
        """Slot is connected when websocket is set."""
        slot = self._make_slot()
        self.assertTrue(slot.is_connected)

    def test_is_connected_false_when_ws_none(self) -> None:
        """Slot is disconnected when websocket is None."""
        slot = self._make_slot()
        slot.websocket = None
        self.assertFalse(slot.is_connected)

    def test_reconnect_window_open_within_60s(self) -> None:
        """Reconnect window is open if less than 60 s have elapsed."""
        slot = self._make_slot()
        slot.websocket = None
        slot.disconnected_at = datetime.datetime.now(datetime.UTC)
        self.assertTrue(slot.is_reconnect_window_open())

    def test_reconnect_window_closed_after_60s(self) -> None:
        """Reconnect window is closed after 60 s have elapsed."""
        slot = self._make_slot()
        slot.websocket = None
        slot.disconnected_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(
            seconds=rm_module.RECONNECT_WINDOW_SECONDS + 1
        )
        self.assertFalse(slot.is_reconnect_window_open())

    def test_reconnect_window_false_when_not_disconnected(self) -> None:
        """Reconnect window is not open when slot has never disconnected."""
        slot = self._make_slot()
        self.assertFalse(slot.is_reconnect_window_open())


class TestRoomManagerJoin(unittest.TestCase):
    """Tests for RoomManager.join_room."""

    def setUp(self) -> None:
        self.mgr = rm_module.RoomManager()
        self.code = self.mgr.create_room()
        self.ws = unittest.mock.MagicMock(spec=fastapi.WebSocket)

    def test_join_room_unknown_returns_none(self) -> None:
        """join_room with unknown code returns None."""
        result = self.mgr.join_room('ZZZZ', 'Alice', self.ws)
        self.assertIsNone(result)

    def test_join_room_assigns_sequential_indices(self) -> None:
        """First player gets index 0, second gets 1."""
        ws2 = unittest.mock.MagicMock(spec=fastapi.WebSocket)
        slot0 = self.mgr.join_room(self.code, 'Alice', self.ws)
        slot1 = self.mgr.join_room(self.code, 'Bob', ws2)
        assert slot0 is not None and slot1 is not None
        self.assertEqual(slot0.player_index, 0)
        self.assertEqual(slot1.player_index, 1)

    def test_join_room_full_returns_none(self) -> None:
        """Attempting to join a full room (4 players) returns None."""
        for i in range(4):
            ws = unittest.mock.MagicMock(spec=fastapi.WebSocket)
            self.mgr.join_room(self.code, f'P{i}', ws)
        ws_extra = unittest.mock.MagicMock(spec=fastapi.WebSocket)
        result = self.mgr.join_room(self.code, 'Extra', ws_extra)
        self.assertIsNone(result)

    def test_duplicate_name_outside_window_returns_none(self) -> None:
        """Joining with an existing name whose window is closed returns None."""
        slot = self.mgr.join_room(self.code, 'Alice', self.ws)
        assert slot is not None
        slot.websocket = None
        slot.disconnected_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(
            seconds=rm_module.RECONNECT_WINDOW_SECONDS + 1
        )
        ws2 = unittest.mock.MagicMock(spec=fastapi.WebSocket)
        self.assertIsNone(self.mgr.join_room(self.code, 'Alice', ws2))

    def test_reconnect_within_window_restores_slot(self) -> None:
        """Rejoining within the reconnect window updates the websocket."""
        slot = self.mgr.join_room(self.code, 'Alice', self.ws)
        assert slot is not None
        slot.websocket = None
        slot.disconnected_at = datetime.datetime.now(datetime.UTC)
        ws2 = unittest.mock.MagicMock(spec=fastapi.WebSocket)
        reconnected = self.mgr.join_room(self.code, 'Alice', ws2)
        self.assertIs(reconnected, slot)
        self.assertIs(slot.websocket, ws2)
        self.assertIsNone(slot.disconnected_at)


class TestRoomManagerDisconnect(unittest.TestCase):
    """Tests for RoomManager.disconnect_player."""

    def setUp(self) -> None:
        self.mgr = rm_module.RoomManager()
        self.code = self.mgr.create_room()
        self.ws = unittest.mock.MagicMock(spec=fastapi.WebSocket)
        self.mgr.join_room(self.code, 'Alice', self.ws)

    def test_disconnect_clears_websocket(self) -> None:
        """disconnect_player sets websocket to None."""
        self.mgr.disconnect_player(self.code, 'Alice')
        room = self.mgr.get_room(self.code)
        assert room is not None
        slot = room.get_player_by_name('Alice')
        assert slot is not None
        self.assertIsNone(slot.websocket)

    def test_disconnect_sets_timestamp(self) -> None:
        """disconnect_player records a UTC disconnection timestamp."""
        self.mgr.disconnect_player(self.code, 'Alice')
        room = self.mgr.get_room(self.code)
        assert room is not None
        slot = room.get_player_by_name('Alice')
        assert slot is not None
        self.assertIsNotNone(slot.disconnected_at)
        assert slot.disconnected_at is not None
        self.assertIsNotNone(slot.disconnected_at.tzinfo)

    def test_disconnect_unknown_room_noop(self) -> None:
        """disconnect_player on unknown room does nothing."""
        self.mgr.disconnect_player('ZZZZ', 'Alice')  # should not raise

    def test_disconnect_unknown_player_noop(self) -> None:
        """disconnect_player on unknown player name does nothing."""
        self.mgr.disconnect_player(self.code, 'NoSuchPlayer')  # should not raise


class TestRoomManagerStartGame(unittest.TestCase):
    """Tests for RoomManager.start_game."""

    def setUp(self) -> None:
        self.mgr = rm_module.RoomManager()
        self.code = self.mgr.create_room()
        for name in ('Alice', 'Bob'):
            ws = unittest.mock.MagicMock(spec=fastapi.WebSocket)
            self.mgr.join_room(self.code, name, ws)

    def test_start_game_sets_game_state(self) -> None:
        """start_game populates room.game_state."""
        room = self.mgr.get_room(self.code)
        assert room is not None
        self.mgr.start_game(room)
        self.assertIsNotNone(room.game_state)

    def test_start_game_creates_correct_player_count(self) -> None:
        """GameState has the same number of players as the room."""
        room = self.mgr.get_room(self.code)
        assert room is not None
        state = self.mgr.start_game(room)
        self.assertEqual(len(state.players), 2)

    def test_start_game_shuffles_dev_card_deck(self) -> None:
        """GameState has a non-empty shuffled dev-card deck."""
        room = self.mgr.get_room(self.code)
        assert room is not None
        state = self.mgr.start_game(room)
        self.assertGreater(len(state.dev_card_deck), 0)

    def test_start_game_phase_changes_from_lobby(self) -> None:
        """Room phase is no longer 'lobby' after starting."""
        room = self.mgr.get_room(self.code)
        assert room is not None
        self.assertEqual(room.phase, 'lobby')
        self.mgr.start_game(room)
        self.assertNotEqual(room.phase, 'lobby')


if __name__ == '__main__':
    unittest.main()
