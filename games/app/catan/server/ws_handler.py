"""WebSocket handler for Catan multiplayer sessions.

Registers the ``/catan/ws/{room_code}/{player_name}`` WebSocket endpoint.
Each connecting client is either added to an existing room as a new player
or reconnected to their existing seat.

Message flow
------------
* Client connects → server broadcasts :class:`~.ws_messages.PlayerJoined`.
* Client sends :class:`~.ws_messages.SubmitAction` → server validates via
  the rules engine, applies via the processor, then broadcasts
  :class:`~.ws_messages.GameStateUpdate` to all room members.
* Invalid action → server sends :class:`~.ws_messages.ErrorMessage` to the
  acting player only.
* Game ends → server broadcasts :class:`~.ws_messages.GameOver`.
* Client disconnects → slot is held; player may reconnect at any time.
"""

from __future__ import annotations

import json
import logging

import fastapi
import pydantic

from ..ai import driver
from ..engine import processor, rules, trade
from ..models import actions, game_state, serializers, ws_messages
from . import room_manager

logger = logging.getLogger(__name__)

router = fastapi.APIRouter()


def serialize_state_for_broadcast(state: game_state.GameState) -> dict:
    """Serialize game state and augment with legal-action highlights.

    Computes legal actions for the active player and adds ``legal_vertex_ids``,
    ``legal_edge_ids``, and ``legal_tile_indices`` to the serialized dict so the
    client can highlight valid placement positions on the board.
    """
    data = serializers.serialize_model(state)
    active_player = state.turn_state.player_index
    legal = rules.get_legal_actions(state, active_player)
    data['legal_vertex_ids'] = [
        a.vertex_id
        for a in legal
        if isinstance(a, (actions.PlaceSettlement, actions.PlaceCity))
    ]
    data['legal_edge_ids'] = [
        a.edge_id for a in legal if isinstance(a, actions.PlaceRoad)
    ]
    data['legal_tile_indices'] = [
        a.tile_index for a in legal if isinstance(a, actions.MoveRobber)
    ]
    return data


# Pydantic v2 TypeAdapter for the discriminated-union ClientMessage type.
_client_message_adapter: pydantic.TypeAdapter[ws_messages.ClientMessage] = (
    pydantic.TypeAdapter(ws_messages.ClientMessage)
)


@router.websocket('/catan/observe/{room_code}')
async def catan_observe(
    websocket: fastapi.WebSocket,
    room_code: str,
) -> None:
    """WebSocket endpoint for observing a Catan game session.

    Observers receive all server broadcasts (game state updates, player
    events, etc.) but cannot send game actions.  If the game is already in
    progress the current state is sent immediately on connect.
    """
    await websocket.accept()

    room = room_manager.room_manager.get_room(room_code)
    if room is None:
        await websocket.send_text(
            ws_messages.ErrorMessage(
                error=f'Room {room_code!r} does not exist'
            ).model_dump_json()
        )
        await websocket.close(code=1008)
        return

    room_manager.room_manager.add_observer(room_code, websocket)

    # Send the current game state immediately if the game has already started.
    if room.game_state is not None:
        state_update = ws_messages.GameStateUpdate(
            game_state=serializers.serialize_model(room.game_state)
        )
        await websocket.send_text(state_update.model_dump_json())

    try:
        while True:
            # Observers only receive; drain any unexpected client messages.
            await websocket.receive_text()
    except fastapi.WebSocketDisconnect:
        room_manager.room_manager.remove_observer(room_code, websocket)


@router.websocket('/catan/ws/{room_code}/{player_name}')
async def catan_ws(
    websocket: fastapi.WebSocket,
    room_code: str,
    player_name: str,
) -> None:
    """WebSocket endpoint for a Catan game session.

    The room must already exist (created via ``POST /catan/rooms``).  Players
    identify themselves by name in the URL; the first four distinct names
    get seats 0–3.  Subsequent connections with the same name reconnect to
    the existing seat if it is currently vacant.
    """
    # Always accept before sending any message (WebSocket protocol requires it).
    await websocket.accept()
    logger.info('[%s] Player %r connected', room_code, player_name)

    room = room_manager.room_manager.get_room(room_code)
    if room is None:
        logger.warning('[%s] Player %r: room not found', room_code, player_name)
        await websocket.send_text(
            ws_messages.ErrorMessage(
                error=f'Room {room_code!r} does not exist'
            ).model_dump_json()
        )
        await websocket.close(code=1008)
        return

    slot = room_manager.room_manager.join_room(room_code, player_name, websocket)
    if slot is None:
        logger.warning(
            '[%s] Player %r: room full or name taken', room_code, player_name
        )
        await websocket.send_text(
            ws_messages.ErrorMessage(
                error='Room is full or player name is taken'
            ).model_dump_json()
        )
        await websocket.close(code=1008)
        return

    logger.info(
        '[%s] Player %r joined as index %d (%d total)',
        room_code,
        player_name,
        slot.player_index,
        room.player_count,
    )

    # Announce the new (or reconnected) player to everyone in the room.
    joined_msg = ws_messages.PlayerJoined(
        player_name=player_name,
        player_index=slot.player_index,
        total_players=room.player_count,
    )
    await room_manager.room_manager.broadcast(room, joined_msg.model_dump_json())

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                client_msg: ws_messages.ClientMessage = (
                    _client_message_adapter.validate_python(data)
                )
            except (json.JSONDecodeError, pydantic.ValidationError) as exc:
                logger.warning(
                    '[%s] Player %r sent invalid message: %s',
                    room_code,
                    player_name,
                    exc,
                )
                await room_manager.room_manager.send_to_player(
                    room,
                    slot.player_index,
                    ws_messages.ErrorMessage(
                        error=f'Invalid message: {exc}'
                    ).model_dump_json(),
                )
                continue

            if isinstance(client_msg, ws_messages.SubmitAction):
                action_type = client_msg.action.action_type
                logger.info(
                    '[%s] Player %r (index %d) submitted action: %s',
                    room_code,
                    player_name,
                    slot.player_index,
                    action_type,
                )
                await _handle_submit_action(room, slot.player_index, client_msg)
            # JoinGame is redundant (join is via URL); RequestUndo is Phase 9.

    except fastapi.WebSocketDisconnect:
        logger.info('[%s] Player %r disconnected', room_code, player_name)
        room_manager.room_manager.disconnect_player(room_code, player_name)


async def _handle_submit_action(
    room: room_manager.GameRoom,
    player_index: int,
    msg: ws_messages.SubmitAction,
) -> None:
    """Validate and apply a :class:`SubmitAction` message, then broadcast."""

    if room.game_state is None:
        logger.warning(
            '[%s] Player index %d submitted action before game started',
            room.room_code,
            player_index,
        )
        await room_manager.room_manager.send_to_player(
            room,
            player_index,
            ws_messages.ErrorMessage(
                error='Game has not started yet'
            ).model_dump_json(),
        )
        return

    # Handle trade offers specially (they don't go through the processor)
    if isinstance(msg.action, actions.TradeOffer):
        await _handle_trade_offer(room, msg.action)
        return

    # Handle trade responses specially
    if isinstance(msg.action, actions.AcceptTrade):
        await _handle_accept_trade(room, msg.action)
        return

    if isinstance(msg.action, actions.RejectTrade):
        await _handle_reject_trade(room, msg.action)
        return

    if isinstance(msg.action, actions.CancelTrade):
        await _handle_cancel_trade(room, msg.action)
        return

    result = processor.apply_action(room.game_state, msg.action)
    if not result.success:
        logger.warning(
            '[%s] Player index %d action %s failed: %s',
            room.room_code,
            player_index,
            msg.action.action_type,
            result.error_message,
        )
        await room_manager.room_manager.send_to_player(
            room,
            player_index,
            ws_messages.ErrorMessage(
                error=result.error_message or 'Invalid action'
            ).model_dump_json(),
        )
        return

    new_state = result.updated_state
    if new_state is None:
        return
    room.game_state = new_state

    # Check for game-over before broadcasting the state update.
    if new_state.phase == game_state.GamePhase.ENDED:
        winner_index = new_state.winner_index
        if winner_index is not None:
            winner_slot = room.get_player_by_index(winner_index)
            if winner_slot is None:
                # This indicates a bug in the game logic; broadcast without name.
                winner_name = ''
            else:
                winner_name = winner_slot.name
            logger.info(
                '[%s] Game over — winner: %r (index %d)',
                room.room_code,
                winner_name,
                winner_index,
            )
            game_over_msg = ws_messages.GameOver(
                winner_player_index=winner_index,
                winner_name=winner_name,
                final_victory_points=[p.victory_points for p in new_state.players],
            )
            await room_manager.room_manager.broadcast(
                room, game_over_msg.model_dump_json()
            )
            return

    state_update = ws_messages.GameStateUpdate(
        game_state=serialize_state_for_broadcast(new_state)
    )
    await room_manager.room_manager.broadcast(room, state_update.model_dump_json())

    # Execute AI turns if the current player is an AI
    await execute_ai_turns_if_needed(room)


async def execute_ai_turns_if_needed(room: room_manager.GameRoom) -> None:
    """Execute AI turns for the current player if they are an AI.

    Continues executing AI turns until a human player's turn or game ends.
    Broadcasts state updates after each AI turn.
    """
    if room.game_state is None or room.game_state.phase == game_state.GamePhase.ENDED:
        return

    # Keep executing AI turns while the current player is an AI
    while True:
        current_player_index = room.game_state.turn_state.player_index
        current_slot = room.get_player_by_index(current_player_index)

        if current_slot is None or not current_slot.is_ai:
            break

        # Get the AI instance for this player
        ai_instance = room.ai_instances.get(current_player_index)
        if ai_instance is None:
            break

        # Execute one AI turn
        room.game_state = await driver.run_ai_turn(
            room.game_state, current_player_index, ai_instance
        )

        # Check for game over
        if room.game_state.phase == game_state.GamePhase.ENDED:
            winner_index = room.game_state.winner_index
            if winner_index is not None:
                winner_slot = room.get_player_by_index(winner_index)
                winner_name = winner_slot.name if winner_slot else ''
                game_over_msg = ws_messages.GameOver(
                    winner_player_index=winner_index,
                    winner_name=winner_name,
                    final_victory_points=[
                        p.victory_points for p in room.game_state.players
                    ],
                )
                await room_manager.room_manager.broadcast(
                    room, game_over_msg.model_dump_json()
                )
            return

        # Broadcast the updated state
        state_update = ws_messages.GameStateUpdate(
            game_state=serialize_state_for_broadcast(room.game_state)
        )
        await room_manager.room_manager.broadcast(room, state_update.model_dump_json())


async def _handle_trade_offer(
    room: room_manager.GameRoom, action: actions.TradeOffer
) -> None:
    """Handle a trade offer action and broadcast the trade proposal."""
    if room.game_state is None:
        return

    success, error_msg, pending_trade = trade.create_trade_offer(
        room.game_state, action
    )
    if not success or pending_trade is None:
        await room_manager.room_manager.send_to_player(
            room,
            action.player_index,
            ws_messages.ErrorMessage(error=error_msg).model_dump_json(),
        )
        return

    # Store the pending trade in the room
    room.pending_trade = pending_trade

    # Update the game state with the active trade ID
    room.game_state.turn_state.active_trade_id = pending_trade.trade_id

    # Broadcast the trade proposal to all players
    trade_msg = ws_messages.TradeProposed(
        trade_id=pending_trade.trade_id,
        offering_player=pending_trade.offering_player,
        offering=pending_trade.offering,
        requesting=pending_trade.requesting,
        target_player=pending_trade.target_player,
    )
    await room_manager.room_manager.broadcast(room, trade_msg.model_dump_json())


async def _handle_accept_trade(
    room: room_manager.GameRoom, action: actions.AcceptTrade
) -> None:
    """Handle a trade acceptance action and execute the trade."""
    if room.game_state is None or room.pending_trade is None:
        await room_manager.room_manager.send_to_player(
            room,
            action.player_index,
            ws_messages.ErrorMessage(error='No active trade offer').model_dump_json(),
        )
        return

    if room.pending_trade.trade_id != action.trade_id:
        await room_manager.room_manager.send_to_player(
            room,
            action.player_index,
            ws_messages.ErrorMessage(error='Trade ID mismatch').model_dump_json(),
        )
        return

    success, error_msg, new_state = trade.accept_trade(
        room.game_state, room.pending_trade, action.player_index
    )
    if not success or new_state is None:
        await room_manager.room_manager.send_to_player(
            room,
            action.player_index,
            ws_messages.ErrorMessage(error=error_msg).model_dump_json(),
        )
        return

    # Store offering player before clearing pending trade
    offering_player = room.pending_trade.offering_player

    # Update game state and clear pending trade
    room.game_state = new_state
    room.pending_trade = None

    # Broadcast trade accepted message
    trade_msg = ws_messages.TradeAccepted(
        trade_id=action.trade_id,
        offering_player=offering_player,
        accepting_player=action.player_index,
    )
    await room_manager.room_manager.broadcast(room, trade_msg.model_dump_json())

    # Broadcast updated game state
    state_update = ws_messages.GameStateUpdate(
        game_state=serialize_state_for_broadcast(room.game_state)
    )
    await room_manager.room_manager.broadcast(room, state_update.model_dump_json())


async def _handle_reject_trade(
    room: room_manager.GameRoom, action: actions.RejectTrade
) -> None:
    """Handle a trade rejection action."""
    if room.pending_trade is None:
        return

    if room.pending_trade.trade_id != action.trade_id:
        return

    room.pending_trade = trade.reject_trade(room.pending_trade, action.player_index)

    # Broadcast trade rejected message
    trade_msg = ws_messages.TradeRejected(
        trade_id=action.trade_id,
        rejecting_player=action.player_index,
    )
    await room_manager.room_manager.broadcast(room, trade_msg.model_dump_json())


async def _handle_cancel_trade(
    room: room_manager.GameRoom, action: actions.CancelTrade
) -> None:
    """Handle a trade cancellation action."""
    if room.pending_trade is None:
        return

    if room.pending_trade.trade_id != action.trade_id:
        return

    if room.pending_trade.offering_player != action.player_index:
        await room_manager.room_manager.send_to_player(
            room,
            action.player_index,
            ws_messages.ErrorMessage(
                error='Only the offering player can cancel a trade'
            ).model_dump_json(),
        )
        return

    room.pending_trade = trade.cancel_trade(room.pending_trade)

    # Clear the active trade ID from game state
    if room.game_state:
        room.game_state.turn_state.active_trade_id = None

    # Broadcast trade cancelled message
    trade_msg = ws_messages.TradeCancelled(
        trade_id=action.trade_id,
        offering_player=action.player_index,
    )
    await room_manager.room_manager.broadcast(room, trade_msg.model_dump_json())

    # Clear the pending trade
    room.pending_trade = None
