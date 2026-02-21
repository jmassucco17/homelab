"""Turn manager: game initialisation and setup-phase turn ordering."""

from __future__ import annotations

import random

from ..board_generator import generate_board
from ..models.game_state import GamePhase, GameState, PendingActionType, TurnState
from ..models.player import DEV_CARD_COUNTS, DevCardType, Player


def create_initial_game_state(
    player_names: list[str],
    player_colors: list[str],
    seed: int | None = None,
) -> GameState:
    """Create a fresh game state ready for the setup phase."""
    rng = random.Random(seed)
    board = generate_board(seed=seed)

    players = [
        Player(player_index=i, name=name, color=color)
        for i, (name, color) in enumerate(zip(player_names, player_colors, strict=True))
    ]

    deck: list[DevCardType] = []
    for card_type, count in DEV_CARD_COUNTS.items():
        deck.extend([card_type] * count)
    rng.shuffle(deck)

    return GameState(
        players=players,
        board=board,
        phase=GamePhase.SETUP_FORWARD,
        turn_state=TurnState(
            player_index=0,
            pending_action=PendingActionType.PLACE_SETTLEMENT,
        ),
        dev_card_deck=deck,
    )


def get_next_setup_player_index(
    current_index: int,
    num_players: int,
    phase: GamePhase,
) -> tuple[int, GamePhase]:
    """Return (next_player_index, new_phase) for setup turn advancement."""
    if phase == GamePhase.SETUP_FORWARD:
        if current_index < num_players - 1:
            return current_index + 1, GamePhase.SETUP_FORWARD
        return num_players - 1, GamePhase.SETUP_BACKWARD
    # SETUP_BACKWARD
    if current_index > 0:
        return current_index - 1, GamePhase.SETUP_BACKWARD
    return 0, GamePhase.MAIN
