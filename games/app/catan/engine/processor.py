"""Catan action processor — stub for Phase 4 implementation.

Phase 4 will replace this with a full action-application engine.  Phase 5
(WebSocket server) imports this interface so the server layer can wire up
without blocking on Phase 4.
"""

from __future__ import annotations

from ..models.actions import Action, ActionResult
from ..models.game_state import GameState


def apply_action(game_state: GameState, action: Action) -> ActionResult:
    """Apply *action* to *game_state* and return the result.

    Stub: accepts every action with no state change.  Phase 4 will provide
    the full implementation (resource deduction, board mutation, victory
    detection, etc.).
    """
    _ = action
    return ActionResult(success=True, updated_state=game_state)
