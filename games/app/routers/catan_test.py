"""Unit tests for the Catan router (Phase 6 — frontend routing)."""

import unittest

import fastapi.testclient

from games.app import main


class TestCatanRouter(unittest.TestCase):
    """Tests for the Catan game router."""

    def setUp(self) -> None:
        """Set up test client."""
        self.client = fastapi.testclient.TestClient(main.app)

    # -------------------------------------------------------------------------
    # GET /catan  — lobby page
    # -------------------------------------------------------------------------

    def test_catan_lobby_returns_html(self) -> None:
        """GET /catan returns a 200 HTML response."""
        response = self.client.get('/catan')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])

    def test_catan_lobby_has_create_room_button(self) -> None:
        """Lobby page contains the create-room button."""
        response = self.client.get('/catan')
        self.assertIn('create-room-btn', response.text)

    def test_catan_lobby_has_join_room_input(self) -> None:
        """Lobby page contains a join-by-code input."""
        response = self.client.get('/catan')
        self.assertIn('join-room-code', response.text)

    def test_catan_lobby_loads_catan_script(self) -> None:
        """Lobby page references catan.js."""
        response = self.client.get('/catan')
        self.assertIn('catan.js', response.text)

    def test_catan_lobby_has_player_name_input(self) -> None:
        """Lobby page contains a player-name input."""
        response = self.client.get('/catan')
        self.assertIn('player-name-input', response.text)

    # -------------------------------------------------------------------------
    # GET /catan/game  — game page
    # -------------------------------------------------------------------------

    def test_catan_game_returns_html(self) -> None:
        """GET /catan/game returns a 200 HTML response."""
        response = self.client.get('/catan/game')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])

    def test_catan_game_has_board_canvas(self) -> None:
        """Game page contains the board canvas element."""
        response = self.client.get('/catan/game')
        self.assertIn('catan-board-canvas', response.text)

    def test_catan_game_has_waiting_room(self) -> None:
        """Game page contains the waiting-room section."""
        response = self.client.get('/catan/game')
        self.assertIn('waiting-room', response.text)

    def test_catan_game_has_side_panel(self) -> None:
        """Game page contains the UI side panel."""
        response = self.client.get('/catan/game')
        self.assertIn('catan-ui-container', response.text)

    def test_catan_game_has_action_log(self) -> None:
        """Game page contains the action-history log."""
        response = self.client.get('/catan/game')
        self.assertIn('catan-action-log', response.text)

    def test_catan_game_loads_catan_script(self) -> None:
        """Game page references catan.js."""
        response = self.client.get('/catan/game')
        self.assertIn('catan.js', response.text)

    # -------------------------------------------------------------------------
    # POST /catan/rooms  — room creation
    # -------------------------------------------------------------------------

    def test_create_room_returns_room_code(self) -> None:
        """POST /catan/rooms returns a room_code field."""
        response = self.client.post('/catan/rooms')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('room_code', data)

    def test_create_room_code_is_four_uppercase_letters(self) -> None:
        """Room code is exactly 4 uppercase letters."""
        response = self.client.post('/catan/rooms')
        code = response.json()['room_code']
        self.assertEqual(len(code), 4)
        self.assertTrue(code.isalpha())
        self.assertEqual(code, code.upper())

    def test_create_room_codes_are_different(self) -> None:
        """Each call to POST /catan/rooms returns a different code."""
        # With 26^4 = 456976 possibilities, 10 calls being all unique is virtually
        # guaranteed.
        codes = {
            self.client.post('/catan/rooms').json()['room_code'] for _ in range(10)
        }
        self.assertGreater(len(codes), 1)

    # -------------------------------------------------------------------------
    # GET /catan/rooms/{room_code}  — room status
    # -------------------------------------------------------------------------

    def test_get_room_returns_status(self) -> None:
        """GET /catan/rooms/{code} returns room status fields."""
        response = self.client.get('/catan/rooms/ABCD')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('room_code', data)
        self.assertIn('player_count', data)
        self.assertIn('phase', data)

    def test_get_room_normalises_code_to_uppercase(self) -> None:
        """GET /catan/rooms/ returns the room code in uppercase."""
        response = self.client.get('/catan/rooms/abcd')
        self.assertEqual(response.json()['room_code'], 'ABCD')


if __name__ == '__main__':
    unittest.main()
