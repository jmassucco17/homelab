"""Integration tests for the Catan Phase 5 multiplayer backend.

Tests cover:

* HTTP routes: create room, room status, start-game validation.
* WebSocket flows: join, broadcast of PlayerJoined / GameStarted /
  GameStateUpdate / GameOver / ErrorMessage.

The rules engine and processor stubs (Phase 4) accept every action and
return the unchanged game state, which is sufficient to verify the
WebSocket protocol and room-management logic.
"""

from __future__ import annotations

import json
import unittest
import unittest.mock

import fastapi.testclient

from games.app import main
from games.app.catan.models.actions import ActionResult
from games.app.catan.models.game_state import GamePhase
from games.app.catan.models.ws_messages import ServerMessageType
from games.app.catan.server import room_manager as rm_module


def _fresh_client() -> tuple[fastapi.testclient.TestClient, rm_module.RoomManager]:
    """Return a TestClient and a fresh RoomManager to avoid cross-test state."""
    mgr = rm_module.RoomManager()
    rm_module.room_manager = mgr
    # Also patch the reference inside the already-imported routers so they
    # see the same fresh manager.
    import games.app.catan.server.ws_handler as wsh  # noqa: PLC0415
    import games.app.routers.catan as cat  # noqa: PLC0415

    wsh.room_manager = mgr
    cat.room_manager = mgr
    return fastapi.testclient.TestClient(main.app), mgr


# ---------------------------------------------------------------------------
# HTTP route tests
# ---------------------------------------------------------------------------


class TestCatanHTTPRoutes(unittest.TestCase):
    """Tests for Catan HTTP endpoints."""

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
        with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as _:
            pass
        with self.client.websocket_connect(f'/catan/ws/{code}/Bob') as _:
            pass
        # Give the room two players by directly using the manager.
        room = self.mgr.get_room(code)
        assert room is not None
        # Manually add two players without a live WebSocket to check the HTTP guard.
        from games.app.catan.server.room_manager import PlayerSlot  # noqa: PLC0415

        if room.player_count < 2:
            # Patch in a second player so we can test double-start.
            slot = PlayerSlot(
                player_index=1,
                name='Bob',
                color='blue',
                websocket=None,  # type: ignore[arg-type]
            )
            slot.disconnected_at = __import__('datetime').datetime.now()
            room.players.append(slot)
        self.mgr.start_game(room)
        resp = self.client.post(f'/catan/rooms/{code}/start')
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# WebSocket flow tests
# ---------------------------------------------------------------------------


class TestCatanWebSocket(unittest.TestCase):
    """Integration tests for the Catan WebSocket endpoint."""

    def setUp(self) -> None:
        self.client, self.mgr = _fresh_client()

    def _create_room(self) -> str:
        return self.client.post('/catan/rooms').json()['room_code']

    # ------------------------------------------------------------------
    # Error paths
    # ------------------------------------------------------------------

    def test_ws_room_not_found_sends_error(self) -> None:
        """Connecting to a nonexistent room gets an error message."""
        with self.client.websocket_connect('/catan/ws/ZZZZ/Alice') as ws:
            msg = json.loads(ws.receive_text())
            self.assertEqual(msg['message_type'], ServerMessageType.ERROR_MESSAGE)

    def test_ws_room_full_sends_error(self) -> None:
        """A 5th player attempting to join a full room gets an error."""
        code = self._create_room()
        with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as ws1:
            ws1.receive_text()  # Alice's PlayerJoined
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
                        # 5th player should be rejected.
                        with self.client.websocket_connect(
                            f'/catan/ws/{code}/Eve'
                        ) as ws5:
                            msg = json.loads(ws5.receive_text())
                            self.assertEqual(
                                msg['message_type'],
                                ServerMessageType.ERROR_MESSAGE,
                            )

    # ------------------------------------------------------------------
    # Join lifecycle
    # ------------------------------------------------------------------

    def test_ws_join_broadcasts_player_joined(self) -> None:
        """Joining a room broadcasts a PlayerJoined message."""
        code = self._create_room()
        with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as ws:
            msg = json.loads(ws.receive_text())
            self.assertEqual(msg['message_type'], ServerMessageType.PLAYER_JOINED)
            self.assertEqual(msg['player_name'], 'Alice')
            self.assertEqual(msg['player_index'], 0)
            self.assertEqual(msg['total_players'], 1)

    def test_ws_second_player_join_broadcasts_to_all(self) -> None:
        """When Bob joins, both Alice and Bob receive a PlayerJoined message."""
        code = self._create_room()
        with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as ws1:
            ws1.receive_text()  # Alice's own PlayerJoined
            with self.client.websocket_connect(f'/catan/ws/{code}/Bob') as ws2:
                # Alice receives Bob's PlayerJoined.
                alice_msg = json.loads(ws1.receive_text())
                self.assertEqual(
                    alice_msg['message_type'], ServerMessageType.PLAYER_JOINED
                )
                self.assertEqual(alice_msg['player_name'], 'Bob')
                self.assertEqual(alice_msg['player_index'], 1)
                # Bob receives their own PlayerJoined.
                bob_msg = json.loads(ws2.receive_text())
                self.assertEqual(
                    bob_msg['message_type'], ServerMessageType.PLAYER_JOINED
                )
                self.assertEqual(bob_msg['player_name'], 'Bob')

    def test_room_status_reflects_joined_players(self) -> None:
        """Room status shows joined players after WebSocket connections."""
        code = self._create_room()
        with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as ws1:
            ws1.receive_text()
            with self.client.websocket_connect(f'/catan/ws/{code}/Bob') as ws2:
                ws1.receive_text()  # Bob's PlayerJoined to Alice
                ws2.receive_text()  # Bob's PlayerJoined to Bob
                resp = self.client.get(f'/catan/rooms/{code}')
                data = resp.json()
                self.assertEqual(data['player_count'], 2)
                self.assertIn('Alice', data['players'])
                self.assertIn('Bob', data['players'])

    # ------------------------------------------------------------------
    # Game start lifecycle
    # ------------------------------------------------------------------

    def test_start_game_broadcasts_game_started(self) -> None:
        """Starting a game broadcasts GameStarted to all connected clients."""
        code = self._create_room()
        with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as ws1:
            ws1.receive_text()  # Alice's PlayerJoined
            with self.client.websocket_connect(f'/catan/ws/{code}/Bob') as ws2:
                ws1.receive_text()  # Bob's PlayerJoined (broadcast to Alice)
                ws2.receive_text()  # Bob's PlayerJoined (to Bob)

                start_resp = self.client.post(f'/catan/rooms/{code}/start')
                self.assertEqual(start_resp.status_code, 200)

                alice_started = json.loads(ws1.receive_text())
                self.assertEqual(
                    alice_started['message_type'], ServerMessageType.GAME_STARTED
                )
                self.assertIn('Alice', alice_started['player_names'])
                self.assertIn('Bob', alice_started['player_names'])

                bob_started = json.loads(ws2.receive_text())
                self.assertEqual(
                    bob_started['message_type'], ServerMessageType.GAME_STARTED
                )

    def test_start_game_broadcasts_initial_state_update(self) -> None:
        """After GameStarted, an initial GameStateUpdate is sent to all clients."""
        code = self._create_room()
        with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as ws1:
            ws1.receive_text()
            with self.client.websocket_connect(f'/catan/ws/{code}/Bob') as ws2:
                ws1.receive_text()
                ws2.receive_text()

                self.client.post(f'/catan/rooms/{code}/start')

                ws1.receive_text()  # GameStarted
                alice_update = json.loads(ws1.receive_text())
                self.assertEqual(
                    alice_update['message_type'], ServerMessageType.GAME_STATE_UPDATE
                )
                self.assertIn('game_state', alice_update)

                ws2.receive_text()  # GameStarted
                bob_update = json.loads(ws2.receive_text())
                self.assertEqual(
                    bob_update['message_type'], ServerMessageType.GAME_STATE_UPDATE
                )

    def test_room_phase_changes_to_setup_after_start(self) -> None:
        """Room status shows setup_forward phase after game starts."""
        code = self._create_room()
        with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as ws1:
            ws1.receive_text()
            with self.client.websocket_connect(f'/catan/ws/{code}/Bob') as ws2:
                ws1.receive_text()
                ws2.receive_text()

                self.client.post(f'/catan/rooms/{code}/start')

                # Drain broadcasts.
                ws1.receive_text()
                ws1.receive_text()
                ws2.receive_text()
                ws2.receive_text()

                resp = self.client.get(f'/catan/rooms/{code}')
                self.assertEqual(resp.json()['phase'], GamePhase.SETUP_FORWARD)

    # ------------------------------------------------------------------
    # Action submission
    # ------------------------------------------------------------------

    def test_submit_action_before_start_returns_error(self) -> None:
        """Submitting an action before the game starts returns an ErrorMessage."""
        code = self._create_room()
        with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as ws:
            ws.receive_text()  # PlayerJoined
            ws.send_text(
                json.dumps(
                    {
                        'message_type': 'submit_action',
                        'action': {'action_type': 'end_turn', 'player_index': 0},
                    }
                )
            )
            msg = json.loads(ws.receive_text())
            self.assertEqual(msg['message_type'], ServerMessageType.ERROR_MESSAGE)

    def test_submit_action_broadcasts_state_update(self) -> None:
        """A valid action (accepted by stub engine) broadcasts a GameStateUpdate."""
        code = self._create_room()
        with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as ws1:
            ws1.receive_text()
            with self.client.websocket_connect(f'/catan/ws/{code}/Bob') as ws2:
                ws1.receive_text()
                ws2.receive_text()

                self.client.post(f'/catan/rooms/{code}/start')

                # Drain GameStarted + GameStateUpdate for both.
                ws1.receive_text()
                ws1.receive_text()
                ws2.receive_text()
                ws2.receive_text()

                ws1.send_text(
                    json.dumps(
                        {
                            'message_type': 'submit_action',
                            'action': {'action_type': 'end_turn', 'player_index': 0},
                        }
                    )
                )

                alice_update = json.loads(ws1.receive_text())
                self.assertEqual(
                    alice_update['message_type'], ServerMessageType.GAME_STATE_UPDATE
                )
                bob_update = json.loads(ws2.receive_text())
                self.assertEqual(
                    bob_update['message_type'], ServerMessageType.GAME_STATE_UPDATE
                )

    def test_invalid_action_sends_error_to_acting_player_only(self) -> None:
        """A rejected action sends ErrorMessage only to the acting player."""
        code = self._create_room()
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

                # Patch the processor to reject this action.
                failed_result = ActionResult(
                    success=False, error_message='Not your turn'
                )
                with unittest.mock.patch(
                    'games.app.catan.engine.processor.apply_action',
                    return_value=failed_result,
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
                    error_msg = json.loads(ws1.receive_text())
                    self.assertEqual(
                        error_msg['message_type'], ServerMessageType.ERROR_MESSAGE
                    )
                    self.assertIn('Not your turn', error_msg['error'])

    def test_invalid_json_sends_error(self) -> None:
        """Sending malformed JSON returns an ErrorMessage."""
        code = self._create_room()
        with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as ws:
            ws.receive_text()
            ws.send_text('not valid json {{{')
            msg = json.loads(ws.receive_text())
            self.assertEqual(msg['message_type'], ServerMessageType.ERROR_MESSAGE)

    def test_invalid_message_type_sends_error(self) -> None:
        """Sending a message with an unknown type returns an ErrorMessage."""
        code = self._create_room()
        with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as ws:
            ws.receive_text()
            ws.send_text(json.dumps({'message_type': 'unknown_type'}))
            msg = json.loads(ws.receive_text())
            self.assertEqual(msg['message_type'], ServerMessageType.ERROR_MESSAGE)

    # ------------------------------------------------------------------
    # Game-over broadcast
    # ------------------------------------------------------------------

    def test_game_over_broadcast_when_engine_signals_end(self) -> None:
        """GameOver is broadcast when the processor returns a game in ENDED phase."""
        from games.app.catan.server.room_manager import GameRoom  # noqa: PLC0415

        code = self._create_room()
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

                room: GameRoom = self.mgr.get_room(code)  # type: ignore[assignment]
                assert room is not None
                winning_state = room.game_state.model_copy(  # type: ignore[union-attr]
                    update={'phase': GamePhase.ENDED, 'winner_index': 0}
                )
                winning_result = ActionResult(success=True, updated_state=winning_state)

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
                    alice_msg = json.loads(ws1.receive_text())
                    self.assertEqual(
                        alice_msg['message_type'], ServerMessageType.GAME_OVER
                    )
                    self.assertEqual(alice_msg['winner_player_index'], 0)
                    self.assertEqual(alice_msg['winner_name'], 'Alice')

                    bob_msg = json.loads(ws2.receive_text())
                    self.assertEqual(
                        bob_msg['message_type'], ServerMessageType.GAME_OVER
                    )


if __name__ == '__main__':
    unittest.main()
