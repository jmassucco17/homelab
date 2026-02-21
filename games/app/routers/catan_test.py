"""Integration tests for the Catan HTTP router."""

from __future__ import annotations

import datetime
import unittest
import unittest.mock

import fastapi.testclient

from games.app import main
from games.app.catan.server import room_manager as rm_module


def _fresh_client() -> tuple[fastapi.testclient.TestClient, rm_module.RoomManager]:
    """Return a TestClient with a fresh RoomManager to prevent cross-test state."""
    mgr = rm_module.RoomManager()
    rm_module.room_manager = mgr
    import games.app.catan.server.ws_handler as wsh  # noqa: PLC0415
    import games.app.routers.catan as cat  # noqa: PLC0415

    wsh.room_manager = mgr
    cat.room_manager = mgr
    return fastapi.testclient.TestClient(main.app), mgr


class TestCatanRouter(unittest.TestCase):
    """Tests for the Catan HTTP routes."""

    def setUp(self) -> None:
        self.client, self.mgr = _fresh_client()

    def test_catan_lobby_returns_html(self) -> None:
        """GET /catan renders an HTML page."""
        resp = self.client.get('/catan')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/html', resp.headers['content-type'])
        self.assertIn('<html', resp.text.lower())

    def test_catan_lobby_contains_create_button(self) -> None:
        """Lobby page includes a create-room button."""
        resp = self.client.get('/catan')
        self.assertIn('btn-create-room', resp.text)

    def test_catan_lobby_loads_catan_script(self) -> None:
        """Lobby page references the catan.js script."""
        resp = self.client.get('/catan')
        self.assertIn('catan.js', resp.text)

    def test_create_room_returns_code(self) -> None:
        """POST /catan/rooms returns a 4-character room code."""
        resp = self.client.post('/catan/rooms')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('room_code', data)
        self.assertEqual(len(data['room_code']), 4)

    def test_create_multiple_rooms_unique_codes(self) -> None:
        """Multiple rooms get distinct codes."""
        codes = {self.client.post('/catan/rooms').json()['room_code'] for _ in range(5)}
        self.assertEqual(len(codes), 5)

    def test_room_status_not_found(self) -> None:
        """GET /catan/rooms/<unknown> returns 404."""
        resp = self.client.get('/catan/rooms/ZZZZ')
        self.assertEqual(resp.status_code, 404)

    def test_room_status_initial_state(self) -> None:
        """A freshly created room starts in lobby phase with 0 players."""
        code = self.client.post('/catan/rooms').json()['room_code']
        resp = self.client.get(f'/catan/rooms/{code}')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['room_code'], code)
        self.assertEqual(data['player_count'], 0)
        self.assertEqual(data['phase'], 'lobby')
        self.assertEqual(data['players'], [])

    def test_start_game_room_not_found(self) -> None:
        """POST /catan/rooms/<unknown>/start returns 404."""
        resp = self.client.post('/catan/rooms/ZZZZ/start')
        self.assertEqual(resp.status_code, 404)

    def test_start_game_requires_two_players(self) -> None:
        """Starting a room with fewer than 2 players returns 400."""
        code = self.client.post('/catan/rooms').json()['room_code']
        resp = self.client.post(f'/catan/rooms/{code}/start')
        self.assertEqual(resp.status_code, 400)

    def test_start_game_already_started(self) -> None:
        """Starting an already-started game returns 400."""
        code = self.client.post('/catan/rooms').json()['room_code']
        room = self.mgr.get_room(code)
        assert room is not None
        # Add two players directly so we can call start_game without live WebSockets.
        for i, (name, color) in enumerate([('Alice', 'red'), ('Bob', 'blue')]):
            ws_mock = unittest.mock.MagicMock()
            slot = rm_module.PlayerSlot(
                player_index=i, name=name, color=color, websocket=ws_mock
            )
            slot.websocket = None
            slot.disconnected_at = datetime.datetime.now(datetime.UTC)
            room.players.append(slot)
        self.mgr.start_game(room)
        resp = self.client.post(f'/catan/rooms/{code}/start')
        self.assertEqual(resp.status_code, 400)

    def test_room_status_reflects_joined_players(self) -> None:
        """Room status shows joined players after WebSocket connections."""
        code = self.client.post('/catan/rooms').json()['room_code']
        with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as ws1:
            ws1.receive_text()
            with self.client.websocket_connect(f'/catan/ws/{code}/Bob') as ws2:
                ws1.receive_text()
                ws2.receive_text()
                resp = self.client.get(f'/catan/rooms/{code}')
                data = resp.json()
                self.assertEqual(data['player_count'], 2)
                self.assertIn('Alice', data['players'])
                self.assertIn('Bob', data['players'])

    def test_room_phase_changes_to_setup_after_start(self) -> None:
        """Room status shows setup_forward phase after game starts."""
        code = self.client.post('/catan/rooms').json()['room_code']
        with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as ws1:
            ws1.receive_text()
            with self.client.websocket_connect(f'/catan/ws/{code}/Bob') as ws2:
                ws1.receive_text()
                ws2.receive_text()

                self.client.post(f'/catan/rooms/{code}/start')

                # Drain GameStarted + GameStateUpdate.
                ws1.receive_text()
                ws1.receive_text()
                ws2.receive_text()
                ws2.receive_text()

                resp = self.client.get(f'/catan/rooms/{code}')
                self.assertEqual(resp.json()['phase'], 'setup_forward')


if __name__ == '__main__':
    unittest.main()
