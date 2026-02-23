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

import fastapi
import pydantic

from ..engine import processor
from ..models import game_state, serializers, ws_messages
from . import room_manager

router = fastapi.APIRouter()

# Pydantic v2 TypeAdapter for the discriminated-union ClientMessage type.
_client_message_adapter: pydantic.TypeAdapter[ws_messages.ClientMessage] = (
    pydantic.TypeAdapter(ws_messages.ClientMessage)
)


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

    room = room_manager.room_manager.get_room(room_code)
    if room is None:
        await websocket.send_text(
            ws_messages.ErrorMessage(
                error=f'Room {room_code!r} does not exist'
            ).model_dump_json()
        )
        await websocket.close(code=1008)
        return

    slot = room_manager.room_manager.join_room(room_code, player_name, websocket)
    if slot is None:
        await websocket.send_text(
            ws_messages.ErrorMessage(
                error='Room is full or player name is taken'
            ).model_dump_json()
        )
        await websocket.close(code=1008)
        return

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
                await room_manager.room_manager.send_to_player(
                    room,
                    slot.player_index,
                    ws_messages.ErrorMessage(
                        error=f'Invalid message: {exc}'
                    ).model_dump_json(),
                )
                continue

            if isinstance(client_msg, ws_messages.SubmitAction):
                await _handle_submit_action(room, slot.player_index, client_msg)
            # JoinGame is redundant (join is via URL); RequestUndo is Phase 9.

    except fastapi.WebSocketDisconnect:
        room_manager.room_manager.disconnect_player(room_code, player_name)


async def _handle_submit_action(
    room: room_manager.GameRoom,
    player_index: int,
    msg: ws_messages.SubmitAction,
) -> None:
    """Validate and apply a :class:`SubmitAction` message, then broadcast."""

    if room.game_state is None:
        await room_manager.room_manager.send_to_player(
            room,
            player_index,
            ws_messages.ErrorMessage(
                error='Game has not started yet'
            ).model_dump_json(),
        )
        return

    result = processor.apply_action(room.game_state, msg.action)
    if not result.success:
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
        game_state=serializers.serialize_model(new_state)
    )
    await room_manager.room_manager.broadcast(room, state_update.model_dump_json())
