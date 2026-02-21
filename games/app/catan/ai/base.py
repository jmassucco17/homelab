"""Abstract base class for Catan AI players."""

from __future__ import annotations

import abc

from ..models.actions import Action
from ..models.game_state import GameState


class CatanAI(abc.ABC):
    """Abstract AI player interface."""

    @abc.abstractmethod
    def choose_action(
        self,
        game_state: GameState,
        player_index: int,
        legal_actions: list[Action],
    ) -> Action:
        """Choose an action from the list of legal actions."""
