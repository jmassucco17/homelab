"""Catan rules engine — stub for Phase 4 implementation.

Phase 4 will replace this with a full legal-action generator.  Phase 5
(WebSocket server) imports this interface so the server layer can wire up
without blocking on Phase 4.
"""

from __future__ import annotations

from ..models.actions import Action
from ..models.game_state import GameState


def get_legal_actions(game_state: GameState, player_index: int) -> list[Action]:
    """Return the list of legal actions for *player_index* in *game_state*.

    Stub: always returns an empty list.  Phase 4 will provide the full
    implementation (placement rules, build-cost checks, robber logic, etc.).
    """
    _ = game_state, player_index
    return []
