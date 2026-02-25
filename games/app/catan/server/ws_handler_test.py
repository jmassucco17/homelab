"""Integration tests for the Catan WebSocket handler."""

from __future__ import annotations

import json
import unittest
import unittest.mock

import fastapi.testclient

from games.app import main
from games.app.catan.engine import turn_manager
from games.app.catan.models import actions as actions_module
from games.app.catan.models import game_state as gs_module
from games.app.catan.models import ws_messages
from games.app.catan.server import room_manager as rm_module
from games.app.catan.server import ws_handler


def _fresh_client() -> tuple[fastapi.testclient.TestClient, rm_module.RoomManager]:
    """Return a TestClient with a fresh RoomManager to prevent cross-test state.

    Patching ``rm_module.room_manager`` is sufficient because both
    ``ws_handler`` and the catan router access the singleton via
    ``room_manager.room_manager`` (module-attribute lookup at call time).
    """
    mgr = rm_module.RoomManager()
    rm_module.room_manager = mgr
    return fastapi.testclient.TestClient(main.app), mgr


class TestCatanWebSocket(unittest.TestCase):
    """Integration tests for the /catan/ws WebSocket endpoint."""

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
            self.assertEqual(
                msg['message_type'], ws_messages.ServerMessageType.ERROR_MESSAGE
            )

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
                                ws_messages.ServerMessageType.ERROR_MESSAGE,
                            )

    # ------------------------------------------------------------------
    # Join lifecycle
    # ------------------------------------------------------------------

    def test_ws_join_broadcasts_player_joined(self) -> None:
        """Joining a room broadcasts a PlayerJoined message."""
        code = self._create_room()
        with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as ws:
            msg = json.loads(ws.receive_text())
            self.assertEqual(
                msg['message_type'], ws_messages.ServerMessageType.PLAYER_JOINED
            )
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
                    alice_msg['message_type'],
                    ws_messages.ServerMessageType.PLAYER_JOINED,
                )
                self.assertEqual(alice_msg['player_name'], 'Bob')
                self.assertEqual(alice_msg['player_index'], 1)
                # Bob receives their own PlayerJoined.
                bob_msg = json.loads(ws2.receive_text())
                self.assertEqual(
                    bob_msg['message_type'], ws_messages.ServerMessageType.PLAYER_JOINED
                )
                self.assertEqual(bob_msg['player_name'], 'Bob')

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
                    alice_started['message_type'],
                    ws_messages.ServerMessageType.GAME_STARTED,
                )
                self.assertIn('Alice', alice_started['player_names'])
                self.assertIn('Bob', alice_started['player_names'])

                bob_started = json.loads(ws2.receive_text())
                self.assertEqual(
                    bob_started['message_type'],
                    ws_messages.ServerMessageType.GAME_STARTED,
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
                    alice_update['message_type'],
                    ws_messages.ServerMessageType.GAME_STATE_UPDATE,
                )
                self.assertIn('game_state', alice_update)

                ws2.receive_text()  # GameStarted
                bob_update = json.loads(ws2.receive_text())
                self.assertEqual(
                    bob_update['message_type'],
                    ws_messages.ServerMessageType.GAME_STATE_UPDATE,
                )

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
            self.assertEqual(
                msg['message_type'], ws_messages.ServerMessageType.ERROR_MESSAGE
            )

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
                    alice_update['message_type'],
                    ws_messages.ServerMessageType.GAME_STATE_UPDATE,
                )
                bob_update = json.loads(ws2.receive_text())
                self.assertEqual(
                    bob_update['message_type'],
                    ws_messages.ServerMessageType.GAME_STATE_UPDATE,
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
                failed_result = actions_module.ActionResult(
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
                        error_msg['message_type'],
                        ws_messages.ServerMessageType.ERROR_MESSAGE,
                    )
                    self.assertIn('Not your turn', error_msg['error'])

    def test_invalid_json_sends_error(self) -> None:
        """Sending malformed JSON returns an ErrorMessage."""
        code = self._create_room()
        with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as ws:
            ws.receive_text()
            ws.send_text('not valid json {{{')
            msg = json.loads(ws.receive_text())
            self.assertEqual(
                msg['message_type'], ws_messages.ServerMessageType.ERROR_MESSAGE
            )

    def test_invalid_message_type_sends_error(self) -> None:
        """Sending a message with an unknown type returns an ErrorMessage."""
        code = self._create_room()
        with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as ws:
            ws.receive_text()
            ws.send_text(json.dumps({'message_type': 'unknown_type'}))
            msg = json.loads(ws.receive_text())
            self.assertEqual(
                msg['message_type'], ws_messages.ServerMessageType.ERROR_MESSAGE
            )

    # ------------------------------------------------------------------
    # Game-over broadcast
    # ------------------------------------------------------------------

    def test_game_over_broadcast_when_engine_signals_end(self) -> None:
        """GameOver is broadcast when the processor returns a game in ENDED phase."""
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
                    alice_msg = json.loads(ws1.receive_text())
                    self.assertEqual(
                        alice_msg['message_type'],
                        ws_messages.ServerMessageType.GAME_OVER,
                    )
                    self.assertEqual(alice_msg['winner_player_index'], 0)
                    self.assertEqual(alice_msg['winner_name'], 'Alice')

                    bob_msg = json.loads(ws2.receive_text())
                    self.assertEqual(
                        bob_msg['message_type'], ws_messages.ServerMessageType.GAME_OVER
                    )

    # ------------------------------------------------------------------
    # AI turn execution
    # ------------------------------------------------------------------

    def test_ai_turn_executes_after_human_action(self) -> None:
        """AI turns execute automatically after a human player's action."""
        code = self._create_room()
        with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as ws:
            ws.receive_text()  # Alice's PlayerJoined

            # Add an AI player
            resp = self.client.post(f'/catan/rooms/{code}/add-ai?difficulty=easy')
            self.assertEqual(resp.status_code, 200)
            ws.receive_text()  # AI's PlayerJoined

            room = self.mgr.get_room(code)
            assert room is not None

            # Start the game
            self.client.post(f'/catan/rooms/{code}/start')
            ws.receive_text()  # GameStarted
            ws.receive_text()  # Initial GameStateUpdate

            # Mock AI turn execution to avoid complex game logic
            with unittest.mock.patch(
                'games.app.catan.server.ws_handler.execute_ai_turns_if_needed'
            ) as mock_ai_turns:
                # Make the mock return immediately (it's async)
                mock_ai_turns.return_value = None
                ws.send_text(
                    json.dumps(
                        {
                            'message_type': 'submit_action',
                            'action': {'action_type': 'end_turn', 'player_index': 0},
                        }
                    )
                )
                # Should receive GameStateUpdate
                ws.receive_text()
                # Verify AI turn execution was called
                mock_ai_turns.assert_called_once()

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def test_connect_logs_player_info(self) -> None:
        """Connecting logs the player name and room code at INFO level."""
        code = self._create_room()
        with self.assertLogs('games.app.catan.server.ws_handler', level='INFO') as cm:
            with self.client.websocket_connect(f'/catan/ws/{code}/Alice'):
                pass
        joined_logs = [m for m in cm.output if 'Alice' in m and 'connected' in m]
        self.assertTrue(joined_logs, 'Expected a connect log entry for Alice')

    def test_disconnect_logs_player_info(self) -> None:
        """Disconnecting logs the player name and room code at INFO level."""
        code = self._create_room()
        with self.assertLogs('games.app.catan.server.ws_handler', level='INFO') as cm:
            with self.client.websocket_connect(f'/catan/ws/{code}/Alice'):
                pass
        disconnect_logs = [m for m in cm.output if 'Alice' in m and 'disconnected' in m]
        self.assertTrue(disconnect_logs, 'Expected a disconnect log entry for Alice')

    def test_invalid_message_logs_warning(self) -> None:
        """Sending an invalid message is logged at WARNING level."""
        code = self._create_room()
        with self.assertLogs(
            'games.app.catan.server.ws_handler', level='WARNING'
        ) as cm:
            with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as ws:
                ws.receive_text()
                ws.send_text('not valid json {{{')
                ws.receive_text()
        warning_logs = [
            m for m in cm.output if 'WARNING' in m and 'invalid message' in m
        ]
        self.assertTrue(warning_logs, 'Expected a warning log for invalid message')

    def test_submit_action_logs_action_type(self) -> None:
        """Submitting an action logs the action type and player at INFO level."""
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

                with self.assertLogs(
                    'games.app.catan.server.ws_handler', level='INFO'
                ) as cm:
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
                    ws1.receive_text()

                action_logs = [m for m in cm.output if 'end_turn' in m and 'Alice' in m]
                self.assertTrue(
                    action_logs, 'Expected an INFO log for end_turn action by Alice'
                )


class TestSerializeStateForBroadcast(unittest.TestCase):
    """Unit tests for serialize_state_for_broadcast."""

    def _make_move_robber_state(self) -> gs_module.GameState:
        """Return a game state with pending_action == MOVE_ROBBER."""
        base = turn_manager.create_initial_game_state(
            ['Alice', 'Bob'], ['red', 'blue'], seed=42
        )
        new_turn = base.turn_state.model_copy(
            update={'pending_action': gs_module.PendingActionType.MOVE_ROBBER}
        )
        return base.model_copy(
            update={'phase': gs_module.GamePhase.MAIN, 'turn_state': new_turn}
        )

    def test_move_robber_includes_legal_tile_indices(self) -> None:
        """legal_tile_indices is populated (excluding robber tile) for move_robber."""
        state = self._make_move_robber_state()
        data = ws_handler.serialize_state_for_broadcast(state)

        robber_tile = state.board.robber_tile_index
        tile_count = len(state.board.tiles)
        self.assertIn('legal_tile_indices', data)
        self.assertEqual(len(data['legal_tile_indices']), tile_count - 1)
        self.assertNotIn(robber_tile, data['legal_tile_indices'])

    def test_move_robber_clears_vertex_and_edge_highlights(self) -> None:
        """legal_vertex_ids and legal_edge_ids are empty when pending is move_robber."""
        state = self._make_move_robber_state()
        data = ws_handler.serialize_state_for_broadcast(state)

        self.assertEqual(data['legal_vertex_ids'], [])
        self.assertEqual(data['legal_edge_ids'], [])

    def test_setup_phase_includes_legal_vertex_ids(self) -> None:
        """legal_vertex_ids is populated during the setup placement phase."""
        state = turn_manager.create_initial_game_state(
            ['Alice', 'Bob'], ['red', 'blue'], seed=42
        )
        self.assertEqual(
            state.turn_state.pending_action,
            gs_module.PendingActionType.PLACE_SETTLEMENT,
        )
        data = ws_handler.serialize_state_for_broadcast(state)

        self.assertIn('legal_vertex_ids', data)
        self.assertGreater(len(data['legal_vertex_ids']), 0)
        self.assertEqual(data['legal_edge_ids'], [])
        self.assertEqual(data['legal_tile_indices'], [])

    def test_game_state_update_includes_legal_tile_indices(self) -> None:
        """GameStateUpdate includes legal_tile_indices when pending is move_robber."""
        client, mgr = _fresh_client()
        code = client.post('/catan/rooms').json()['room_code']
        with client.websocket_connect(f'/catan/ws/{code}/Alice') as ws1:
            ws1.receive_text()
            with client.websocket_connect(f'/catan/ws/{code}/Bob') as ws2:
                ws1.receive_text()
                ws2.receive_text()

                client.post(f'/catan/rooms/{code}/start')
                ws1.receive_text()  # GameStarted
                update_msg = json.loads(ws1.receive_text())  # GameStateUpdate
                ws2.receive_text()
                ws2.receive_text()

                self.assertEqual(
                    update_msg['message_type'],
                    ws_messages.ServerMessageType.GAME_STATE_UPDATE,
                )
                self.assertIn('legal_tile_indices', update_msg['game_state'])
                self.assertIn('legal_vertex_ids', update_msg['game_state'])
                self.assertIn('legal_edge_ids', update_msg['game_state'])


if __name__ == '__main__':
    unittest.main()
