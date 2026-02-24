"""Abstract base class for Catan AI players."""

from __future__ import annotations

import abc

from ..engine import trade as trade_module
from ..models import actions, game_state


class CatanAI(abc.ABC):
    """Abstract base for AI difficulty levels.

    Subclasses implement :meth:`choose_action` to select one legal action
    each time the game engine asks the AI to act, and :meth:`respond_to_trade`
    to accept or reject a pending trade offer from another player.
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

    @abc.abstractmethod
    def respond_to_trade(
        self,
        state: game_state.GameState,
        player_index: int,
        pending_trade: trade_module.PendingTrade,
    ) -> actions.AcceptTrade | actions.RejectTrade:
        """Decide whether to accept or reject a pending trade offer.

        Returns either an AcceptTrade or RejectTrade action for the given
        player_index in response to pending_trade.
        """
