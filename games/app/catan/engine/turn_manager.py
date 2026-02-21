"""Catan turn manager.

Handles game state initialization and turn-order advancement.
"""

from __future__ import annotations

import random

from games.app.catan.models.game_state import (
    GamePhase,
    GameState,
    PendingActionType,
    TurnState,
)
from games.app.catan.models.player import DEV_CARD_COUNTS, Player


def create_initial_game_state(
    player_names: list[str],
    colors: list[str],
    seed: int | None = None,
) -> GameState:
    """Create and return a fresh GameState ready for the setup phase.

    Args:
        player_names: Display names for each player (determines player count).
        colors: Hex/CSS colour strings for each player (same length as names).
        seed: Optional RNG seed for reproducible boards and deck order.

    Returns:
        A :class:`GameState` in SETUP_FORWARD phase, player 0 to place first.
    """
    from games.app.catan.board_generator import generate_board

    board = generate_board(seed=seed)

    players = [
        Player(player_index=i, name=name, color=color)
        for i, (name, color) in enumerate(zip(player_names, colors, strict=True))
    ]

    # Build and shuffle the development card deck.
    from games.app.catan.models.player import DevCardType as _DevCardType

    deck: list[_DevCardType] = []
    for card_type, count in DEV_CARD_COUNTS.items():
        deck.extend([card_type] * count)
    rng = random.Random(seed)
    rng.shuffle(deck)

    turn_state = TurnState(
        player_index=0,
        pending_action=PendingActionType.PLACE_SETTLEMENT,
    )

    return GameState(
        players=players,
        board=board,
        phase=GamePhase.SETUP_FORWARD,
        turn_state=turn_state,
        dev_card_deck=deck,
        turn_number=0,
    )


def advance_turn(game_state: GameState) -> GameState:
    """Advance the game to the next turn segment and return the modified state.

    Called after a road is placed during setup, or from the EndTurn processor
    during the main game.  Modifies ``game_state`` in place and returns it.
    """
    num_players = len(game_state.players)
    current = game_state.turn_state.player_index

    if game_state.phase == GamePhase.SETUP_FORWARD:
        if current == num_players - 1:
            # Switch direction: stay on same player, move backward.
            game_state.phase = GamePhase.SETUP_BACKWARD
            game_state.turn_state = TurnState(
                player_index=current,
                pending_action=PendingActionType.PLACE_SETTLEMENT,
            )
        else:
            game_state.turn_state = TurnState(
                player_index=current + 1,
                pending_action=PendingActionType.PLACE_SETTLEMENT,
            )

    elif game_state.phase == GamePhase.SETUP_BACKWARD:
        if current == 0:
            # Setup complete; begin the main game.
            game_state.phase = GamePhase.MAIN
            game_state.turn_number = 1
            game_state.turn_state = TurnState(
                player_index=0,
                pending_action=PendingActionType.ROLL_DICE,
            )
        else:
            game_state.turn_state = TurnState(
                player_index=current - 1,
                pending_action=PendingActionType.PLACE_SETTLEMENT,
            )

    elif game_state.phase == GamePhase.MAIN:
        next_player = (current + 1) % num_players
        if next_player == 0:
            game_state.turn_number += 1
        game_state.turn_state = TurnState(
            player_index=next_player,
            pending_action=PendingActionType.ROLL_DICE,
        )

    return game_state


def get_next_setup_player(
    current_index: int, num_players: int, phase: GamePhase
) -> tuple[int, GamePhase]:
    """Compute the next player index and phase during setup.

    Returns:
        A ``(next_player_index, next_phase)`` tuple.

    Raises:
        ValueError: If *phase* is not a setup phase.
    """
    if phase == GamePhase.SETUP_FORWARD:
        if current_index == num_players - 1:
            return current_index, GamePhase.SETUP_BACKWARD
        return current_index + 1, GamePhase.SETUP_FORWARD

    if phase == GamePhase.SETUP_BACKWARD:
        if current_index == 0:
            return 0, GamePhase.MAIN
        return current_index - 1, GamePhase.SETUP_BACKWARD

    raise ValueError(f'get_next_setup_player called with non-setup phase: {phase}')
