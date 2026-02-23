"""Catan turn manager.

Handles game state initialization and turn-order advancement.
"""

from __future__ import annotations

import random

from .. import board_generator
from ..models import game_state, player


def create_initial_game_state(
    player_names: list[str],
    colors: list[str],
    seed: int | None = None,
    is_ai_list: list[bool] | None = None,
    ai_types: list[str | None] | None = None,
) -> game_state.GameState:
    """Create and return a fresh GameState ready for the setup phase.

    Args:
        player_names: Display names for each player (determines player count).
        colors: Hex/CSS colour strings for each player (same length as names).
        seed: Optional RNG seed for reproducible boards and deck order.
        is_ai_list: List of booleans indicating if each player is AI.
        ai_types: List of AI types ('easy', 'medium', 'hard') for each player.

    Returns:
        A :class:`GameState` in SETUP_FORWARD phase, player 0 to place first.
    """
    brd = board_generator.generate_board(seed=seed)

    # Use defaults if not provided
    _is_ai_list: list[bool] = (
        is_ai_list if is_ai_list is not None else [False] * len(player_names)
    )
    _ai_types: list[str | None] = (
        ai_types if ai_types is not None else [None] * len(player_names)
    )

    players = [
        player.Player(
            player_index=i,
            name=name,
            color=color,
            is_ai=_is_ai_list[i],
            ai_type=_ai_types[i],
        )
        for i, (name, color) in enumerate(zip(player_names, colors, strict=True))
    ]

    # Build and shuffle the development card deck.
    deck: list[player.DevCardType] = []
    for card_type, count in player.DEV_CARD_COUNTS.items():
        deck.extend([card_type] * count)
    rng = random.Random(seed)
    rng.shuffle(deck)

    turn_state = game_state.TurnState(
        player_index=0,
        pending_action=game_state.PendingActionType.PLACE_SETTLEMENT,
    )

    return game_state.GameState(
        players=players,
        board=brd,
        phase=game_state.GamePhase.SETUP_FORWARD,
        turn_state=turn_state,
        dev_card_deck=deck,
        turn_number=0,
    )


def advance_turn(state: game_state.GameState) -> game_state.GameState:
    """Advance the game to the next turn segment and return the modified state.

    Called after a road is placed during setup, or from the EndTurn processor
    during the main game.  Modifies ``state`` in place and returns it.
    """
    num_players = len(state.players)
    current = state.turn_state.player_index

    if state.phase == game_state.GamePhase.SETUP_FORWARD:
        if current == num_players - 1:
            # Switch direction: stay on same player, move backward.
            state.phase = game_state.GamePhase.SETUP_BACKWARD
            state.turn_state = game_state.TurnState(
                player_index=current,
                pending_action=game_state.PendingActionType.PLACE_SETTLEMENT,
            )
        else:
            state.turn_state = game_state.TurnState(
                player_index=current + 1,
                pending_action=game_state.PendingActionType.PLACE_SETTLEMENT,
            )

    elif state.phase == game_state.GamePhase.SETUP_BACKWARD:
        if current == 0:
            # Setup complete; begin the main game.
            state.phase = game_state.GamePhase.MAIN
            state.turn_number = 1
            state.turn_state = game_state.TurnState(
                player_index=0,
                pending_action=game_state.PendingActionType.ROLL_DICE,
            )
        else:
            state.turn_state = game_state.TurnState(
                player_index=current - 1,
                pending_action=game_state.PendingActionType.PLACE_SETTLEMENT,
            )

    elif state.phase == game_state.GamePhase.MAIN:
        next_player = (current + 1) % num_players
        if next_player == 0:
            state.turn_number += 1
        state.turn_state = game_state.TurnState(
            player_index=next_player,
            pending_action=game_state.PendingActionType.ROLL_DICE,
        )

    return state


def get_next_setup_player(
    current_index: int, num_players: int, phase: game_state.GamePhase
) -> tuple[int, game_state.GamePhase]:
    """Compute the next player index and phase during setup.

    Returns:
        A ``(next_player_index, next_phase)`` tuple.

    Raises:
        ValueError: If *phase* is not a setup phase.
    """
    if phase == game_state.GamePhase.SETUP_FORWARD:
        if current_index == num_players - 1:
            return current_index, game_state.GamePhase.SETUP_BACKWARD
        return current_index + 1, game_state.GamePhase.SETUP_FORWARD

    if phase == game_state.GamePhase.SETUP_BACKWARD:
        if current_index == 0:
            return 0, game_state.GamePhase.MAIN
        return current_index - 1, game_state.GamePhase.SETUP_BACKWARD

    raise ValueError(f'get_next_setup_player called with non-setup phase: {phase}')
