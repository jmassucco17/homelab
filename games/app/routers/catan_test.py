"""Integration tests for the Catan HTTP router."""

from __future__ import annotations

import unittest
import unittest.mock

import fastapi.testclient

from games.app import main
from games.app.catan.server import room_manager as rm_module


def _fresh_client() -> tuple[fastapi.testclient.TestClient, rm_module.RoomManager]:
    """Return a TestClient with a fresh RoomManager to prevent cross-test state.

    Patching ``rm_module.room_manager`` is sufficient because both
    ``ws_handler`` and the catan router access the singleton via
    ``room_manager.room_manager`` (module-attribute lookup at call time).
    """
    mgr = rm_module.RoomManager()
    rm_module.room_manager = mgr
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

    def test_catan_lobby_script_has_version_param(self) -> None:
        """Lobby page appends a ?v= cache-busting parameter to catan.js."""
        resp = self.client.get('/catan')
        self.assertIn('catan.js?v=', resp.text)

    def test_catan_lobby_has_catan_lobby_id(self) -> None:
        """Lobby page has id='catan-lobby' so catan.js can detect the page."""
        resp = self.client.get('/catan')
        self.assertIn('id="catan-lobby"', resp.text)

    def test_catan_lobby_has_player_name_input(self) -> None:
        """Lobby page has the shared player-name input field."""
        resp = self.client.get('/catan')
        self.assertIn('player-name-input', resp.text)

    def test_catan_lobby_has_join_room_inputs(self) -> None:
        """Lobby page has the join-room code input and button."""
        resp = self.client.get('/catan')
        self.assertIn('join-room-code', resp.text)
        self.assertIn('join-room-btn', resp.text)

    def test_catan_lobby_script_is_module(self) -> None:
        """Lobby page loads catan.js as a module so ES imports work."""
        resp = self.client.get('/catan')
        self.assertIn('type="module"', resp.text)

    def test_catan_lobby_has_active_games_section(self) -> None:
        """Lobby page has the active-games section for viewing running games."""
        resp = self.client.get('/catan')
        self.assertIn('active-games-list', resp.text)
        self.assertIn('active-games-empty', resp.text)

    def test_catan_game_returns_html(self) -> None:
        """GET /catan/game renders an HTML page."""
        resp = self.client.get('/catan/game')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/html', resp.headers['content-type'])
        self.assertIn('<html', resp.text.lower())

    def test_catan_game_has_board_canvas(self) -> None:
        """Game page contains the board canvas element."""
        resp = self.client.get('/catan/game')
        self.assertIn('catan-board-canvas', resp.text)

    def test_catan_game_has_waiting_room(self) -> None:
        """Game page contains the waiting-room section."""
        resp = self.client.get('/catan/game')
        self.assertIn('waiting-room', resp.text)

    def test_catan_game_has_side_panel(self) -> None:
        """Game page contains the UI side panel."""
        resp = self.client.get('/catan/game')
        self.assertIn('catan-ui-container', resp.text)

    def test_catan_game_loads_catan_script(self) -> None:
        """Game page references catan.js."""
        resp = self.client.get('/catan/game')
        self.assertIn('catan.js', resp.text)

    def test_catan_game_script_has_version_param(self) -> None:
        """Game page appends a ?v= cache-busting parameter to catan.js."""
        resp = self.client.get('/catan/game')
        self.assertIn('catan.js?v=', resp.text)

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


class TestAddAIEndpoint(unittest.TestCase):
    """Tests for the POST /catan/rooms/{room_code}/add-ai endpoint."""

    def setUp(self) -> None:
        self.client, self.mgr = _fresh_client()

    def test_add_ai_to_room(self) -> None:
        """Adding AI to a room returns success."""
        code = self.client.post('/catan/rooms').json()['room_code']
        resp = self.client.post(f'/catan/rooms/{code}/add-ai?difficulty=easy')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'added')
        self.assertIn('AI, easy', data['player_name'])
        self.assertEqual(data['player_index'], 0)
        self.assertEqual(data['total_players'], 1)

    def test_add_ai_unknown_room(self) -> None:
        """Adding AI to unknown room returns 404."""
        resp = self.client.post('/catan/rooms/ZZZZ/add-ai?difficulty=easy')
        self.assertEqual(resp.status_code, 404)

    def test_add_ai_invalid_difficulty(self) -> None:
        """Adding AI with invalid difficulty returns 400."""
        code = self.client.post('/catan/rooms').json()['room_code']
        resp = self.client.post(f'/catan/rooms/{code}/add-ai?difficulty=invalid')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Invalid difficulty', resp.json()['detail'])

    def test_add_ai_to_full_room(self) -> None:
        """Adding AI to a full room (4 players) returns 400."""
        code = self.client.post('/catan/rooms').json()['room_code']
        with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as ws1:
            ws1.receive_text()
            with self.client.websocket_connect(f'/catan/ws/{code}/Bob') as ws2:
                ws1.receive_text()
                ws2.receive_text()
                with self.client.websocket_connect(f'/catan/ws/{code}/Carol') as ws3:
                    ws1.receive_text()
                    ws2.receive_text()
                    ws3.receive_text()
                    with self.client.websocket_connect(f'/catan/ws/{code}/Dave') as ws4:
                        ws1.receive_text()
                        ws2.receive_text()
                        ws3.receive_text()
                        ws4.receive_text()
                        resp = self.client.post(
                            f'/catan/rooms/{code}/add-ai?difficulty=easy'
                        )
                        self.assertEqual(resp.status_code, 400)

    def test_add_ai_after_game_started(self) -> None:
        """Adding AI after game has started returns 400."""
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

                resp = self.client.post(f'/catan/rooms/{code}/add-ai?difficulty=easy')
                self.assertEqual(resp.status_code, 400)
                self.assertIn(
                    'Cannot add AI after game has started', resp.json()['detail']
                )

    def test_add_ai_broadcasts_player_joined(self) -> None:
        """Adding AI broadcasts PlayerJoined to connected clients."""
        code = self.client.post('/catan/rooms').json()['room_code']
        with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as ws:
            ws.receive_text()  # Alice's PlayerJoined

            resp = self.client.post(f'/catan/rooms/{code}/add-ai?difficulty=medium')
            self.assertEqual(resp.status_code, 200)

            # Alice should receive AI's PlayerJoined
            import json

            msg = json.loads(ws.receive_text())
            self.assertEqual(msg['message_type'], 'player_joined')
            self.assertIn('AI, medium', msg['player_name'])
            self.assertEqual(msg['player_index'], 1)

    def test_add_multiple_ai_players(self) -> None:
        """Can add multiple AI players with different difficulties."""
        code = self.client.post('/catan/rooms').json()['room_code']

        resp1 = self.client.post(f'/catan/rooms/{code}/add-ai?difficulty=easy')
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp1.json()['player_index'], 0)

        resp2 = self.client.post(f'/catan/rooms/{code}/add-ai?difficulty=medium')
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()['player_index'], 1)

        resp3 = self.client.post(f'/catan/rooms/{code}/add-ai?difficulty=hard')
        self.assertEqual(resp3.status_code, 200)
        self.assertEqual(resp3.json()['player_index'], 2)

        # Verify room status
        room_resp = self.client.get(f'/catan/rooms/{code}')
        self.assertEqual(room_resp.json()['player_count'], 3)

    def test_add_ai_default_difficulty_is_easy(self) -> None:
        """Not specifying difficulty defaults to easy."""
        code = self.client.post('/catan/rooms').json()['room_code']
        resp = self.client.post(f'/catan/rooms/{code}/add-ai')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('AI, easy', data['player_name'])


class TestListRoomsEndpoint(unittest.TestCase):
    """Tests for GET /catan/rooms."""

    def setUp(self) -> None:
        self.client, self.mgr = _fresh_client()

    def test_list_rooms_empty(self) -> None:
        """GET /catan/rooms returns an empty list when no rooms exist."""
        resp = self.client.get('/catan/rooms')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_list_rooms_shows_created_room(self) -> None:
        """GET /catan/rooms lists a newly created room."""
        code = self.client.post('/catan/rooms').json()['room_code']
        resp = self.client.get('/catan/rooms')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['room_code'], code)
        self.assertEqual(data[0]['phase'], 'lobby')
        self.assertEqual(data[0]['players'], [])

    def test_list_rooms_shows_player_names(self) -> None:
        """GET /catan/rooms lists player names for each room."""
        code = self.client.post('/catan/rooms').json()['room_code']
        with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as ws:
            ws.receive_text()  # drain PlayerJoined
            resp = self.client.get('/catan/rooms')
            rooms = resp.json()
            self.assertEqual(len(rooms), 1)
            self.assertIn('Alice', rooms[0]['players'])

    def test_list_rooms_shows_multiple_rooms(self) -> None:
        """GET /catan/rooms lists all active rooms."""
        code1 = self.client.post('/catan/rooms').json()['room_code']
        code2 = self.client.post('/catan/rooms').json()['room_code']
        resp = self.client.get('/catan/rooms')
        codes = {r['room_code'] for r in resp.json()}
        self.assertIn(code1, codes)
        self.assertIn(code2, codes)


class TestObserverEndpoint(unittest.TestCase):
    """Tests for the /catan/observe/{room_code} WebSocket endpoint."""

    def setUp(self) -> None:
        self.client, self.mgr = _fresh_client()

    def test_observer_rejects_unknown_room(self) -> None:
        """Observer WS receives an error message for an unknown room code."""
        import json

        with self.client.websocket_connect('/catan/observe/ZZZZ') as ws:
            msg = json.loads(ws.receive_text())
            self.assertEqual(msg['message_type'], 'error_message')
            self.assertIn('ZZZZ', msg['error'])

    def test_observer_connects_to_lobby_room(self) -> None:
        """Observer can connect to a room that has not yet started."""
        code = self.client.post('/catan/rooms').json()['room_code']
        # Should not raise; no immediate message is expected (no game state yet)
        with self.client.websocket_connect(f'/catan/observe/{code}'):
            pass  # connection opens and closes cleanly

    def test_observer_receives_player_joined(self) -> None:
        """Observer receives PlayerJoined broadcasts."""
        import json

        code = self.client.post('/catan/rooms').json()['room_code']
        with self.client.websocket_connect(f'/catan/observe/{code}') as obs:
            # A player joins — observer should receive the broadcast
            with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as ws:
                ws.receive_text()  # drain Alice's own PlayerJoined
                msg = json.loads(obs.receive_text())
                self.assertEqual(msg['message_type'], 'player_joined')
                self.assertEqual(msg['player_name'], 'Alice')

    def test_observer_receives_game_state_on_connect_after_start(self) -> None:
        """Observer gets the current state immediately when joining a started game."""
        import json

        code = self.client.post('/catan/rooms').json()['room_code']
        with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as ws1:
            ws1.receive_text()
            with self.client.websocket_connect(f'/catan/ws/{code}/Bob') as ws2:
                ws1.receive_text()
                ws2.receive_text()
                self.client.post(f'/catan/rooms/{code}/start')
                # Drain GameStarted + GameStateUpdate for both players
                ws1.receive_text()
                ws1.receive_text()
                ws2.receive_text()
                ws2.receive_text()

                # Observer connects after game started — should get state immediately
                with self.client.websocket_connect(f'/catan/observe/{code}') as obs:
                    msg = json.loads(obs.receive_text())
                    self.assertEqual(msg['message_type'], 'game_state_update')
                    self.assertIn('game_state', msg)

    def test_observer_receives_game_over(self) -> None:
        """Observer receives the GameOver broadcast when the game ends."""
        import json
        import unittest.mock

        from games.app.catan.models import actions as actions_module
        from games.app.catan.models import game_state as gs_module

        code = self.client.post('/catan/rooms').json()['room_code']
        with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as ws1:
            ws1.receive_text()
            with self.client.websocket_connect(f'/catan/ws/{code}/Bob') as ws2:
                ws1.receive_text()
                ws2.receive_text()
                self.client.post(f'/catan/rooms/{code}/start')
                ws1.receive_text()
                ws1.receive_text()
                ws2.receive_text()
                ws2.receive_text()

                with self.client.websocket_connect(f'/catan/observe/{code}') as obs:
                    obs.receive_text()  # drain initial game_state_update

                    room = self.mgr.get_room(code)
                    assert room is not None
                    winning_state = room.game_state.model_copy(  # type: ignore[union-attr]
                        update={
                            'phase': gs_module.GamePhase.ENDED,
                            'winner_index': 0,
                        }
                    )
                    winning_result = actions_module.ActionResult(
                        success=True, updated_state=winning_state
                    )

                    with unittest.mock.patch(
                        'games.app.catan.engine.processor.apply_action',
                        return_value=winning_result,
                    ):
                        ws1.send_text(
                            json.dumps(
                                {
                                    'message_type': 'submit_action',
                                    'action': {
                                        'action_type': 'end_turn',
                                        'player_index': 0,
                                    },
                                }
                            )
                        )
                        # Drain player messages
                        ws1.receive_text()
                        ws2.receive_text()

                        # Observer should also receive the game_over broadcast
                        obs_msg = json.loads(obs.receive_text())
                        self.assertEqual(obs_msg['message_type'], 'game_over')
                        self.assertEqual(obs_msg['winner_player_index'], 0)
                        self.assertEqual(obs_msg['winner_name'], 'Alice')


if __name__ == '__main__':
    unittest.main()
