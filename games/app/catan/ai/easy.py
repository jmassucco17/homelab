"""Easy AI: always picks a random legal action."""

from __future__ import annotations

import random

from ..models.actions import Action
from ..models.game_state import GameState
from .base import CatanAI


class EasyCatanAI(CatanAI):
    """Random-action AI for sanity testing."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def choose_action(
        self,
        game_state: GameState,
        player_index: int,
        legal_actions: list[Action],
    ) -> Action:
        return self._rng.choice(legal_actions)
