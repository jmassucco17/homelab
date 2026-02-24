"""Abstract base class for Catan AI players."""

from __future__ import annotations

import abc

from ..models import actions, game_state


class CatanAI(abc.ABC):
    """Abstract base for AI difficulty levels.

    Subclasses implement :meth:`choose_action` to select one legal action
    each time the game engine asks the AI to act.
    """

    @abc.abstractmethod
    def choose_action(
        self,
        state: game_state.GameState,
        player_index: int,
        legal_actions: list[actions.Action],
    ) -> actions.Action:
        """Choose one action from legal_actions for the given game state.

        Must return exactly one element from legal_actions (not a new action).
        """
