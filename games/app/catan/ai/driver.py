"""AI driver: runs AI turns asynchronously with simulated delay."""

from __future__ import annotations

import asyncio
import typing

from ..engine.processor import apply_action
from ..engine.rules import get_legal_actions
from ..models.game_state import GameState
from .base import CatanAI


class AIDriver:
    """Manages AI player turns with configurable delays."""

    def __init__(
        self,
        ai_players: dict[int, CatanAI],
        delay_seconds: float = 1.5,
    ) -> None:
        self._ai_players = ai_players
        self._delay_seconds = delay_seconds

    def is_ai_turn(self, game_state: GameState) -> bool:
        return game_state.turn_state.player_index in self._ai_players

    async def run_ai_turn(
        self,
        game_state: GameState,
        on_action: typing.Callable[[GameState], typing.Awaitable[None]] | None = None,
    ) -> GameState:
        """Run a single AI action with simulated delay."""
        player_index = game_state.turn_state.player_index
        ai = self._ai_players[player_index]
        legal_actions = get_legal_actions(game_state, player_index)
        if not legal_actions:
            return game_state
        action = ai.choose_action(game_state, player_index, legal_actions)
        await asyncio.sleep(self._delay_seconds)
        result = apply_action(game_state, action)
        if result.success and result.updated_state is not None:
            game_state = result.updated_state
            if on_action is not None:
                await on_action(game_state)
        return game_state
