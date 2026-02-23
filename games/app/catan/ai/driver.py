"""Async driver for running AI turns in a Catan game.

The driver applies one AI agent's actions until that agent has no more
legal moves or the turn ends (EndTurn action applied).  It is designed to
be called from an async context such as a WebSocket handler.
"""

from __future__ import annotations

import asyncio

from ..engine import processor, rules
from ..models import actions, game_state
from . import base

# Simulated thinking delay between AI actions (seconds).
AI_DELAY_SECONDS: float = 1.5


async def run_ai_turn(
    state: game_state.GameState,
    player_index: int,
    ai: base.CatanAI,
) -> game_state.GameState:
    """Run one AI agent's turn, applying actions until the turn is over.

    Applies actions for *player_index* as long as:
    - The game has not ended.
    - *player_index* has at least one legal action.

    A single :data:`AI_DELAY_SECONDS` sleep is inserted at the start to
    simulate thinking time.  The loop exits immediately after an
    :class:`~games.app.catan.models.actions.EndTurn` action is applied.

    Returns the updated game state after all actions are applied.
    """
    await asyncio.sleep(AI_DELAY_SECONDS)
    while state.phase != game_state.GamePhase.ENDED:
        legal = rules.get_legal_actions(state, player_index)
        if not legal:
            break
        action = ai.choose_action(state, player_index, legal)
        result = processor.apply_action(state, action)
        if not result.success:
            break
        assert result.updated_state is not None
        state = result.updated_state
        if isinstance(action, actions.EndTurn):
            break
    return state
