"""Easy (random) AI for Catan.

Always selects a uniformly random legal action. Useful as a baseline and
for stress-testing the game engine.
"""

from __future__ import annotations

import random

from ..engine import trade as trade_module
from ..models import actions, game_state
from . import base


class EasyAI(base.CatanAI):
    """Random-action AI: picks uniformly at random from the legal moves."""

    def __init__(self, seed: int | None = None) -> None:
        """Initialise with an optional RNG seed for reproducibility."""
        self._rng = random.Random(seed)

    def choose_action(
        self,
        state: game_state.GameState,
        player_index: int,
        legal_actions: list[actions.Action],
    ) -> actions.Action:
        """Return a uniformly random action from legal_actions."""
        return self._rng.choice(legal_actions)

    def respond_to_trade(
        self,
        state: game_state.GameState,
        player_index: int,
        pending_trade: trade_module.PendingTrade,
    ) -> actions.AcceptTrade | actions.RejectTrade:
        """Randomly accept or reject a trade offer with equal probability."""
        if self._rng.random() < 0.5:
            return actions.AcceptTrade(
                player_index=player_index, trade_id=pending_trade.trade_id
            )
        return actions.RejectTrade(
            player_index=player_index, trade_id=pending_trade.trade_id
        )
