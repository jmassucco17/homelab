"""Integration tests for the Catan WebSocket handler."""

from __future__ import annotations

import json
import unittest
import unittest.mock

import fastapi.testclient

from games.app import main
from games.app.catan.models import actions as actions_module
from games.app.catan.models import game_state as gs_module
from games.app.catan.models import ws_messages
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
    # AI trade responses
    # ------------------------------------------------------------------

    def test_ai_player_responds_to_trade_offer(self) -> None:
        """AI players immediately broadcast a response to a trade proposal."""
        code = self._create_room()
        with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as ws:
            ws.receive_text()  # Alice's PlayerJoined
            # Always-reject AI so the test is deterministic.
            resp = self.client.post(f'/catan/rooms/{code}/add-ai?difficulty=easy')
            self.assertEqual(resp.status_code, 200)
            ws.receive_text()  # AI's PlayerJoined

            room = self.mgr.get_room(code)
            assert room is not None
            self.client.post(f'/catan/rooms/{code}/start')
            ws.receive_text()  # GameStarted
            ws.receive_text()  # GameStateUpdate

            # Force MAIN phase state with player 0 active and resources for trade.
            room.game_state = room.game_state.model_copy(  # type: ignore[union-attr]
                update={
                    'phase': gs_module.GamePhase.MAIN,
                    'turn_state': gs_module.TurnState(
                        player_index=0,
                        pending_action=gs_module.PendingActionType.BUILD_OR_TRADE,
                    ),
                }
            )
            from games.app.catan.models import player as player_module

            new_players = list(room.game_state.players)
            new_players[0] = room.game_state.players[0].model_copy(
                update={'resources': player_module.Resources(wood=2)}
            )
            new_players[1] = room.game_state.players[1].model_copy(
                update={'resources': player_module.Resources(ore=2)}
            )
            room.game_state = room.game_state.model_copy(
                update={'players': new_players}
            )

            # Patch the AI to always reject so we can assert deterministically.
            ai_instance = list(room.ai_instances.values())[0]
            with unittest.mock.patch.object(
                ai_instance,
                'respond_to_trade',
                return_value=actions_module.RejectTrade(
                    player_index=1, trade_id='__PLACEHOLDER__'
                ),
            ) as mock_respond:
                # Make the return value use the actual trade_id.
                def _reject(state: object, pidx: int, pt: object) -> object:
                    return actions_module.RejectTrade(
                        player_index=pidx,
                        trade_id=pt.trade_id,  # type: ignore[union-attr]
                    )

                mock_respond.side_effect = _reject

                ws.send_text(
                    json.dumps(
                        {
                            'message_type': 'submit_action',
                            'action': {
                                'action_type': 'trade_offer',
                                'player_index': 0,
                                'offering': {'wood': 1},
                                'requesting': {'ore': 1},
                            },
                        }
                    )
                )
                # First broadcast: TradeProposed
                msg1 = json.loads(ws.receive_text())
                self.assertEqual(
                    msg1['message_type'], ws_messages.ServerMessageType.TRADE_PROPOSED
                )
                # Second broadcast: TradeRejected (AI's response)
                msg2 = json.loads(ws.receive_text())
                self.assertEqual(
                    msg2['message_type'], ws_messages.ServerMessageType.TRADE_REJECTED
                )
                mock_respond.assert_called_once()

    def test_trade_cancelled_when_all_ai_players_reject(self) -> None:
        """Trade is cancelled automatically when all AI players reject it."""
        code = self._create_room()
        with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as ws:
            ws.receive_text()  # Alice's PlayerJoined
            self.client.post(f'/catan/rooms/{code}/add-ai?difficulty=easy')
            ws.receive_text()  # AI's PlayerJoined

            room = self.mgr.get_room(code)
            assert room is not None
            self.client.post(f'/catan/rooms/{code}/start')
            ws.receive_text()  # GameStarted
            ws.receive_text()  # GameStateUpdate

            # Force a MAIN-phase state.
            room.game_state = room.game_state.model_copy(  # type: ignore[union-attr]
                update={
                    'phase': gs_module.GamePhase.MAIN,
                    'turn_state': gs_module.TurnState(
                        player_index=0,
                        pending_action=gs_module.PendingActionType.BUILD_OR_TRADE,
                    ),
                }
            )
            from games.app.catan.models import player as player_module

            new_players = list(room.game_state.players)
            new_players[0] = room.game_state.players[0].model_copy(
                update={'resources': player_module.Resources(wood=2)}
            )
            room.game_state = room.game_state.model_copy(
                update={'players': new_players}
            )

            # Patch AI to always reject.
            ai_instance = list(room.ai_instances.values())[0]

            def _reject(state: object, pidx: int, pt: object) -> object:
                return actions_module.RejectTrade(
                    player_index=pidx,
                    trade_id=pt.trade_id,  # type: ignore[union-attr]
                )

            with unittest.mock.patch.object(
                ai_instance, 'respond_to_trade', side_effect=_reject
            ):
                ws.send_text(
                    json.dumps(
                        {
                            'message_type': 'submit_action',
                            'action': {
                                'action_type': 'trade_offer',
                                'player_index': 0,
                                'offering': {'wood': 1},
                                'requesting': {'ore': 1},
                            },
                        }
                    )
                )
                # Drain the TradeProposed and TradeRejected broadcasts.
                ws.receive_text()  # TradeProposed
                ws.receive_text()  # TradeRejected
                # Final broadcast: TradeCancelled (auto-cancel after all reject).
                cancelled_msg = json.loads(ws.receive_text())
                self.assertEqual(
                    cancelled_msg['message_type'],
                    ws_messages.ServerMessageType.TRADE_CANCELLED,
                )
                # Pending trade is cleared after cancellation.
                self.assertIsNone(room.pending_trade)

    def test_trade_executes_when_ai_accepts(self) -> None:
        """Trade is executed when an AI player accepts it."""
        code = self._create_room()
        with self.client.websocket_connect(f'/catan/ws/{code}/Alice') as ws:
            ws.receive_text()  # Alice's PlayerJoined
            self.client.post(f'/catan/rooms/{code}/add-ai?difficulty=easy')
            ws.receive_text()  # AI's PlayerJoined

            room = self.mgr.get_room(code)
            assert room is not None
            self.client.post(f'/catan/rooms/{code}/start')
            ws.receive_text()  # GameStarted
            ws.receive_text()  # GameStateUpdate

            # Force MAIN phase with both players holding necessary resources.
            room.game_state = room.game_state.model_copy(  # type: ignore[union-attr]
                update={
                    'phase': gs_module.GamePhase.MAIN,
                    'turn_state': gs_module.TurnState(
                        player_index=0,
                        pending_action=gs_module.PendingActionType.BUILD_OR_TRADE,
                    ),
                }
            )
            from games.app.catan.models import player as player_module

            new_players = list(room.game_state.players)
            new_players[0] = room.game_state.players[0].model_copy(
                update={'resources': player_module.Resources(wood=2)}
            )
            new_players[1] = room.game_state.players[1].model_copy(
                update={'resources': player_module.Resources(ore=2)}
            )
            room.game_state = room.game_state.model_copy(
                update={'players': new_players}
            )

            # Patch AI to always accept.
            ai_instance = list(room.ai_instances.values())[0]

            def _accept(state: object, pidx: int, pt: object) -> object:
                return actions_module.AcceptTrade(
                    player_index=pidx,
                    trade_id=pt.trade_id,  # type: ignore[union-attr]
                )

            with unittest.mock.patch.object(
                ai_instance, 'respond_to_trade', side_effect=_accept
            ):
                ws.send_text(
                    json.dumps(
                        {
                            'message_type': 'submit_action',
                            'action': {
                                'action_type': 'trade_offer',
                                'player_index': 0,
                                'offering': {'wood': 1},
                                'requesting': {'ore': 1},
                            },
                        }
                    )
                )
                # TradeProposed
                ws.receive_text()
                # TradeAccepted broadcast
                accepted_msg = json.loads(ws.receive_text())
                self.assertEqual(
                    accepted_msg['message_type'],
                    ws_messages.ServerMessageType.TRADE_ACCEPTED,
                )
                # GameStateUpdate after resources exchanged
                state_update = json.loads(ws.receive_text())
                self.assertEqual(
                    state_update['message_type'],
                    ws_messages.ServerMessageType.GAME_STATE_UPDATE,
                )
                # Pending trade is cleared after acceptance.
                self.assertIsNone(room.pending_trade)


if __name__ == '__main__':
    unittest.main()
