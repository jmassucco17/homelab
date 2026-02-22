"""Catan game room manager.

Manages in-memory game rooms for multiplayer Catan sessions.  Each room
holds the active :class:`GameState`, the list of connected players, and
the FastAPI :class:`WebSocket` handles needed for broadcasting.

Disconnection handling
----------------------
When a player's WebSocket closes, their slot is *held* for
:data:`RECONNECT_WINDOW_SECONDS`.  If they reconnect with the same name
before the window expires, their existing slot is restored.  After the
window closes the name is released and a new player can claim it.
"""

from __future__ import annotations

import datetime
import random
import string

import fastapi

from ..engine import turn_manager
from ..models import game_state as gs

# Seconds a disconnected player slot is held open for reconnection.
RECONNECT_WINDOW_SECONDS: int = 60

# Player colours assigned in join order (index 0–3).
_PLAYER_COLORS: list[str] = ['red', 'blue', 'white', 'orange']


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class PlayerSlot:
    """One player's seat in a game room."""

    def __init__(
        self,
        player_index: int,
        name: str,
        color: str,
        websocket: fastapi.WebSocket,
    ) -> None:
        self.player_index = player_index
        self.name = name
        self.color = color
        self.websocket: fastapi.WebSocket | None = websocket
        self.disconnected_at: datetime.datetime | None = None

    @property
    def is_connected(self) -> bool:
        """True if this player currently has an active WebSocket."""
        return self.websocket is not None

    def is_reconnect_window_open(self) -> bool:
        """True if the reconnection grace period has not yet elapsed."""
        if self.disconnected_at is None:
            return False
        elapsed = (
            datetime.datetime.now(datetime.UTC) - self.disconnected_at
        ).total_seconds()
        return elapsed < RECONNECT_WINDOW_SECONDS


class GameRoom:
    """A single multiplayer Catan game room."""

    def __init__(self, room_code: str) -> None:
        self.room_code = room_code
        self.players: list[PlayerSlot] = []
        self.game_state: gs.GameState | None = None
        self.created_at: datetime.datetime = datetime.datetime.now(datetime.UTC)

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def player_count(self) -> int:
        """Number of seats currently occupied."""
        return len(self.players)

    @property
    def phase(self) -> str:
        """Current game phase as a string; ``'lobby'`` before the game starts."""
        if self.game_state is None:
            return 'lobby'
        return self.game_state.phase.value

    # ------------------------------------------------------------------
    # Slot look-ups
    # ------------------------------------------------------------------

    def get_player_by_name(self, name: str) -> PlayerSlot | None:
        """Return the slot whose name matches, or ``None``."""
        return next((p for p in self.players if p.name == name), None)

    def get_player_by_index(self, player_index: int) -> PlayerSlot | None:
        """Return the slot at *player_index*, or ``None``."""
        return next((p for p in self.players if p.player_index == player_index), None)

    def can_join(self) -> bool:
        """True if a new player can still join (room not full, game not started)."""
        return len(self.players) < 4 and self.game_state is None


# ---------------------------------------------------------------------------
# Room manager
# ---------------------------------------------------------------------------


class RoomManager:
    """Singleton that owns all active :class:`GameRoom` instances."""

    def __init__(self) -> None:
        self._rooms: dict[str, GameRoom] = {}

    # ------------------------------------------------------------------
    # Room lifecycle
    # ------------------------------------------------------------------

    def create_room(self) -> str:
        """Create a new empty room and return its 4-character code."""
        for _ in range(100):
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            if code not in self._rooms:
                self._rooms[code] = GameRoom(code)
                return code
        raise RuntimeError('Could not generate a unique room code after 100 tries')

    def get_room(self, room_code: str) -> GameRoom | None:
        """Return the room with *room_code*, or ``None`` if not found."""
        return self._rooms.get(room_code)

    # ------------------------------------------------------------------
    # Player join / disconnect / reconnect
    # ------------------------------------------------------------------

    def join_room(
        self,
        room_code: str,
        player_name: str,
        websocket: fastapi.WebSocket,
    ) -> PlayerSlot | None:
        """Add a player to a room or reconnect a disconnected player.

        Returns the :class:`PlayerSlot` on success, or ``None`` when:

        * the room does not exist,
        * the game has already started and the name is not a known player,
        * the room is full, or
        * the name is taken by a player whose reconnect window has closed.
        """
        room = self._rooms.get(room_code)
        if room is None:
            return None

        # Reconnection path: same name, slot held within window.
        existing = room.get_player_by_name(player_name)
        if existing is not None:
            if existing.is_reconnect_window_open():
                existing.websocket = websocket
                existing.disconnected_at = None
                return existing
            # Name is taken but reconnect window has closed.
            return None

        if not room.can_join():
            return None

        color = _PLAYER_COLORS[len(room.players)]
        slot = PlayerSlot(
            player_index=len(room.players),
            name=player_name,
            color=color,
            websocket=websocket,
        )
        room.players.append(slot)
        return slot

    def disconnect_player(self, room_code: str, player_name: str) -> None:
        """Mark *player_name* as disconnected and start the reconnect window."""
        room = self._rooms.get(room_code)
        if room is None:
            return
        slot = room.get_player_by_name(player_name)
        if slot is not None:
            slot.websocket = None
            slot.disconnected_at = datetime.datetime.now(datetime.UTC)

    # ------------------------------------------------------------------
    # Messaging helpers
    # ------------------------------------------------------------------

    async def broadcast(self, room: GameRoom, message: str) -> None:
        """Send *message* to every currently connected player in *room*.

        Individual send errors are swallowed so a single broken connection
        does not prevent the remaining players from receiving the message.
        """
        for slot in room.players:
            if slot.websocket is not None:
                try:
                    await slot.websocket.send_text(message)
                except Exception:  # noqa: BLE001 — broken socket; player will reconnect
                    pass

    async def send_to_player(
        self, room: GameRoom, player_index: int, message: str
    ) -> None:
        """Send *message* to the specific player at *player_index*.

        Send errors are swallowed; the caller should not assume delivery.
        """
        slot = room.get_player_by_index(player_index)
        if slot is not None and slot.websocket is not None:
            try:
                await slot.websocket.send_text(message)
            except Exception:  # noqa: BLE001 — broken socket; player will reconnect
                pass

    # ------------------------------------------------------------------
    # Game initialisation
    # ------------------------------------------------------------------

    def start_game(self, room: GameRoom) -> gs.GameState:
        """Initialise a new :class:`GameState` for *room* and store it.

        Uses :func:`~games.app.catan.engine.turn_manager.create_initial_game_state`
        to create a properly configured state, including the setup-phase pending
        action and a shuffled development-card deck.
        """
        names = [slot.name for slot in room.players]
        colors = [slot.color for slot in room.players]
        state = turn_manager.create_initial_game_state(names, colors)
        room.game_state = state
        return state


# Module-level singleton consumed by the HTTP and WebSocket routers.
room_manager: RoomManager = RoomManager()
