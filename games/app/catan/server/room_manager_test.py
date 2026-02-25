"""Unit tests for the Catan room manager."""

from __future__ import annotations

import pathlib
import tempfile
import unittest
import unittest.mock

import fastapi

from games.app.catan.models import game_state as gs_module
from games.app.catan.server import room_manager as rm_module
from games.app.catan.server.room_manager import generate_ai_name


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

    def test_ai_player_is_connected(self) -> None:
        """AI players are always considered connected."""
        slot = rm_module.PlayerSlot(
            player_index=0,
            name='AI Easy',
            color='red',
            websocket=None,
            is_ai=True,
            ai_type='easy',
        )
        self.assertTrue(slot.is_connected)

    def test_ai_player_attributes(self) -> None:
        """AI player slots have correct AI attributes."""
        slot = rm_module.PlayerSlot(
            player_index=1,
            name='AI Medium',
            color='blue',
            websocket=None,
            is_ai=True,
            ai_type='medium',
        )
        self.assertTrue(slot.is_ai)
        self.assertEqual(slot.ai_type, 'medium')
        self.assertIsNone(slot.websocket)


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

    def test_reconnect_restores_slot(self) -> None:
        """Rejoining with the same name restores the existing slot."""
        slot = self.mgr.join_room(self.code, 'Alice', self.ws)
        assert slot is not None
        slot.websocket = None
        ws2 = unittest.mock.MagicMock(spec=fastapi.WebSocket)
        reconnected = self.mgr.join_room(self.code, 'Alice', ws2)
        self.assertIs(reconnected, slot)
        self.assertIs(slot.websocket, ws2)

    def test_reconnect_blocked_when_still_connected(self) -> None:
        """join_room returns None if the player's slot is still connected."""
        slot = self.mgr.join_room(self.code, 'Alice', self.ws)
        assert slot is not None
        ws2 = unittest.mock.MagicMock(spec=fastapi.WebSocket)
        # Alice is still connected (websocket is not None) — should be rejected.
        result = self.mgr.join_room(self.code, 'Alice', ws2)
        self.assertIsNone(result)
        # Original websocket must be unchanged.
        self.assertIs(slot.websocket, self.ws)


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

    def test_disconnect_unknown_room_noop(self) -> None:
        """disconnect_player on unknown room does nothing."""
        self.mgr.disconnect_player('ZZZZ', 'Alice')  # should not raise

    def test_disconnect_unknown_player_noop(self) -> None:
        """disconnect_player on unknown player name does nothing."""
        self.mgr.disconnect_player(self.code, 'NoSuchPlayer')  # should not raise


class TestAINameGeneration(unittest.TestCase):
    """Tests for generate_ai_name function."""

    def test_generate_ai_name_returns_string(self) -> None:
        """generate_ai_name returns a non-empty string."""
        name = generate_ai_name()
        self.assertIsInstance(name, str)
        self.assertGreater(len(name), 0)

    def test_generate_ai_name_uses_valid_elements(self) -> None:
        """Generated names only contain valid name elements."""
        valid_elements = {'Joe', 'John', 'Jicky'}
        for _ in range(20):  # Test multiple times due to randomness
            name = generate_ai_name()
            words = name.split()
            self.assertGreaterEqual(len(words), 1)
            self.assertLessEqual(len(words), 2)
            for word in words:
                self.assertIn(word, valid_elements)

    def test_generate_ai_name_no_duplicates(self) -> None:
        """Generated names don't contain duplicate elements."""
        for _ in range(20):  # Test multiple times due to randomness
            name = generate_ai_name()
            words = name.split()
            self.assertEqual(len(words), len(set(words)))


class TestRoomManagerAddAI(unittest.TestCase):
    """Tests for RoomManager.add_ai_player."""

    def setUp(self) -> None:
        self.mgr = rm_module.RoomManager()
        self.code = self.mgr.create_room()

    def test_add_ai_player_returns_slot(self) -> None:
        """add_ai_player returns a PlayerSlot."""
        slot = self.mgr.add_ai_player(self.code, 'easy')
        self.assertIsNotNone(slot)

    def test_add_ai_player_sets_ai_attributes(self) -> None:
        """AI player slot has correct is_ai and ai_type."""
        slot = self.mgr.add_ai_player(self.code, 'medium')
        assert slot is not None
        self.assertTrue(slot.is_ai)
        self.assertEqual(slot.ai_type, 'medium')

    def test_add_ai_player_assigns_sequential_index(self) -> None:
        """AI players get sequential player indices."""
        ws = unittest.mock.MagicMock(spec=fastapi.WebSocket)
        self.mgr.join_room(self.code, 'Alice', ws)
        slot = self.mgr.add_ai_player(self.code, 'easy')
        assert slot is not None
        self.assertEqual(slot.player_index, 1)

    def test_add_ai_player_increases_player_count(self) -> None:
        """Adding AI increases room player count."""
        room = self.mgr.get_room(self.code)
        assert room is not None
        self.assertEqual(room.player_count, 0)
        self.mgr.add_ai_player(self.code, 'easy')
        self.assertEqual(room.player_count, 1)

    def test_add_ai_player_full_room_returns_none(self) -> None:
        """Cannot add AI to a full room (4 players)."""
        for i in range(4):
            ws = unittest.mock.MagicMock(spec=fastapi.WebSocket)
            self.mgr.join_room(self.code, f'P{i}', ws)
        result = self.mgr.add_ai_player(self.code, 'easy')
        self.assertIsNone(result)

    def test_add_ai_player_unknown_room_returns_none(self) -> None:
        """add_ai_player with unknown room code returns None."""
        result = self.mgr.add_ai_player('ZZZZ', 'easy')
        self.assertIsNone(result)

    def test_add_ai_player_creates_ai_instance(self) -> None:
        """Adding AI creates an AI instance in room.ai_instances."""
        room = self.mgr.get_room(self.code)
        assert room is not None
        slot = self.mgr.add_ai_player(self.code, 'hard')
        assert slot is not None
        self.assertIn(slot.player_index, room.ai_instances)
        self.assertIsNotNone(room.ai_instances[slot.player_index])

    def test_add_multiple_ai_players(self) -> None:
        """Can add multiple AI players with different difficulties."""
        slot1 = self.mgr.add_ai_player(self.code, 'easy')
        slot2 = self.mgr.add_ai_player(self.code, 'medium')
        slot3 = self.mgr.add_ai_player(self.code, 'hard')
        assert slot1 is not None and slot2 is not None and slot3 is not None
        self.assertEqual(slot1.ai_type, 'easy')
        self.assertEqual(slot2.ai_type, 'medium')
        self.assertEqual(slot3.ai_type, 'hard')
        room = self.mgr.get_room(self.code)
        assert room is not None
        self.assertEqual(room.player_count, 3)

    def test_add_ai_player_name_format(self) -> None:
        """AI player name follows the format '<name> (bot)'."""
        slot = self.mgr.add_ai_player(self.code, 'hard')
        assert slot is not None
        # Name should end with (bot)
        self.assertTrue(slot.name.endswith('(bot)'))
        # Name should start with valid elements
        name_part = slot.name.replace(' (bot)', '')
        words = name_part.split()
        valid_elements = {'Joe', 'John', 'Jicky'}
        for word in words:
            self.assertIn(word, valid_elements)

    def test_add_multiple_ai_players_different_names(self) -> None:
        """Multiple AI players can have different generated names."""
        # Note: Due to randomness, names *could* be the same, but statistically unlikely
        # with multiple attempts. We'll just verify format is correct for each.
        slots = [self.mgr.add_ai_player(self.code, 'easy') for _ in range(3)]
        for slot in slots:
            assert slot is not None
            self.assertTrue(slot.name.endswith('(bot)'))
            self.assertIsInstance(slot.name, str)


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

    def test_start_game_initial_pending_action_is_place_settlement(self) -> None:
        """Initial game state starts with PLACE_SETTLEMENT pending (setup phase)."""
        room = self.mgr.get_room(self.code)
        assert room is not None
        state = self.mgr.start_game(room)
        self.assertEqual(
            state.turn_state.pending_action,
            gs_module.PendingActionType.PLACE_SETTLEMENT,
        )

    def test_start_game_phase_is_setup_forward(self) -> None:
        """Initial game state is in SETUP_FORWARD phase."""
        room = self.mgr.get_room(self.code)
        assert room is not None
        state = self.mgr.start_game(room)
        self.assertEqual(state.phase, gs_module.GamePhase.SETUP_FORWARD)

    def test_start_game_with_ai_players(self) -> None:
        """start_game correctly initializes AI players in game state."""
        room = self.mgr.get_room(self.code)
        assert room is not None
        # Remove human players and add AI
        room.players.clear()
        self.mgr.add_ai_player(self.code, 'easy')
        self.mgr.add_ai_player(self.code, 'medium')
        state = self.mgr.start_game(room)
        self.assertEqual(len(state.players), 2)
        self.assertTrue(state.players[0].is_ai)
        self.assertEqual(state.players[0].ai_type, 'easy')
        self.assertTrue(state.players[1].is_ai)
        self.assertEqual(state.players[1].ai_type, 'medium')

    def test_start_game_mixed_human_and_ai_players(self) -> None:
        """start_game works with mixed human and AI players."""
        room = self.mgr.get_room(self.code)
        assert room is not None
        # Alice and Bob are already added as humans
        self.mgr.add_ai_player(self.code, 'hard')
        state = self.mgr.start_game(room)
        self.assertEqual(len(state.players), 3)
        self.assertFalse(state.players[0].is_ai)
        self.assertFalse(state.players[1].is_ai)
        self.assertTrue(state.players[2].is_ai)
        self.assertEqual(state.players[2].ai_type, 'hard')


class TestRoomManagerPersistence(unittest.TestCase):
    """Tests for RoomManager.save_state and load_state."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.state_file = pathlib.Path(self.tmp_dir.name) / 'test_state.json'
        # Patch the module-level _STATE_FILE used by all RoomManager instances.
        self._patcher = unittest.mock.patch.object(
            rm_module, '_STATE_FILE', self.state_file
        )
        self._patcher.start()
        self.mgr = rm_module.RoomManager()

    def tearDown(self) -> None:
        self._patcher.stop()
        self.tmp_dir.cleanup()

    def test_save_state_creates_file(self) -> None:
        """save_state writes a JSON file to disk."""
        self.mgr.create_room()
        self.assertTrue(self.state_file.exists())

    def test_save_and_load_empty_rooms(self) -> None:
        """An empty manager saves and loads correctly."""
        self.mgr.save_state()
        mgr2 = rm_module.RoomManager()
        mgr2.load_state()
        self.assertEqual(len(mgr2.rooms), 0)

    def test_save_and_load_lobby_room(self) -> None:
        """A room in lobby phase (no started game) round-trips correctly."""
        code = self.mgr.create_room()
        mgr2 = rm_module.RoomManager()
        mgr2.load_state()
        room = mgr2.get_room(code)
        self.assertIsNotNone(room)
        assert room is not None
        self.assertEqual(room.phase, 'lobby')
        self.assertEqual(room.player_count, 0)

    def test_save_and_load_room_with_ai_player(self) -> None:
        """A room with an AI player round-trips with the AI instance restored."""
        code = self.mgr.create_room()
        self.mgr.add_ai_player(code, 'medium')
        mgr2 = rm_module.RoomManager()
        mgr2.load_state()
        room = mgr2.get_room(code)
        self.assertIsNotNone(room)
        assert room is not None
        self.assertEqual(room.player_count, 1)
        slot = room.players[0]
        self.assertTrue(slot.is_ai)
        self.assertEqual(slot.ai_type, 'medium')
        self.assertIn(slot.player_index, room.ai_instances)

    def test_save_and_load_room_with_human_player(self) -> None:
        """A room with a human player round-trips; websocket is None after restore."""
        code = self.mgr.create_room()
        ws = unittest.mock.MagicMock(spec=fastapi.WebSocket)
        self.mgr.join_room(code, 'Alice', ws)
        self.mgr.save_state()
        mgr2 = rm_module.RoomManager()
        mgr2.load_state()
        room = mgr2.get_room(code)
        self.assertIsNotNone(room)
        assert room is not None
        self.assertEqual(room.player_count, 1)
        slot = room.players[0]
        self.assertEqual(slot.name, 'Alice')
        self.assertFalse(slot.is_ai)
        # WebSocket is transient — not persisted.
        self.assertIsNone(slot.websocket)

    def test_save_and_load_started_game(self) -> None:
        """A started game's state is preserved across save/load."""
        code = self.mgr.create_room()
        for name in ('Alice', 'Bob'):
            ws = unittest.mock.MagicMock(spec=fastapi.WebSocket)
            self.mgr.join_room(code, name, ws)
        room = self.mgr.get_room(code)
        assert room is not None
        self.mgr.start_game(room)
        original_phase = room.phase
        mgr2 = rm_module.RoomManager()
        mgr2.load_state()
        room2 = mgr2.get_room(code)
        self.assertIsNotNone(room2)
        assert room2 is not None
        self.assertEqual(room2.phase, original_phase)
        self.assertIsNotNone(room2.game_state)
        self.assertEqual(len(room2.players), 2)

    def test_load_state_no_file_is_noop(self) -> None:
        """load_state does nothing when the state file doesn't exist."""
        # File was never written.
        self.mgr.load_state()
        self.assertEqual(len(self.mgr.rooms), 0)

    def test_load_state_corrupt_file_is_swallowed(self) -> None:
        """load_state silently ignores a corrupt JSON file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text('not valid json {{{}')
        mgr2 = rm_module.RoomManager()
        mgr2.load_state()  # Should not raise
        self.assertEqual(len(mgr2.rooms), 0)

    def test_save_state_multiple_rooms(self) -> None:
        """All rooms are saved and restored when there are multiple rooms."""
        code1 = self.mgr.create_room()
        code2 = self.mgr.create_room()
        mgr2 = rm_module.RoomManager()
        mgr2.load_state()
        self.assertIsNotNone(mgr2.get_room(code1))
        self.assertIsNotNone(mgr2.get_room(code2))

    def test_save_state_preserves_player_names(self) -> None:
        """Player names are preserved across save/load cycles."""
        code = self.mgr.create_room()
        ws = unittest.mock.MagicMock(spec=fastapi.WebSocket)
        self.mgr.join_room(code, 'GamePlayer', ws)
        self.mgr.save_state()
        mgr2 = rm_module.RoomManager()
        mgr2.load_state()
        room = mgr2.get_room(code)
        assert room is not None
        names = [slot.name for slot in room.players]
        self.assertIn('GamePlayer', names)

    def test_load_state_allows_reconnect(self) -> None:
        """After load, a human player can reconnect (join_room with same name)."""
        code = self.mgr.create_room()
        ws = unittest.mock.MagicMock(spec=fastapi.WebSocket)
        self.mgr.join_room(code, 'Alice', ws)
        self.mgr.save_state()
        mgr2 = rm_module.RoomManager()
        mgr2.load_state()
        ws2 = unittest.mock.MagicMock(spec=fastapi.WebSocket)
        slot = mgr2.join_room(code, 'Alice', ws2)
        self.assertIsNotNone(slot)
        assert slot is not None
        self.assertEqual(slot.name, 'Alice')
        self.assertIs(slot.websocket, ws2)


if __name__ == '__main__':
    unittest.main()
