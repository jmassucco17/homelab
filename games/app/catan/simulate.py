"""Simulation runner: run N full AI-vs-AI games and report statistics."""

from __future__ import annotations

import statistics
import time

from .ai.easy import EasyCatanAI
from .engine.processor import apply_action
from .engine.rules import get_legal_actions
from .engine.turn_manager import create_initial_game_state
from .models.game_state import GamePhase, GameState, PendingActionType

_MAX_ACTIONS = 2000  # safety limit per game


def run_game(
    num_players: int = 2,
    seed: int | None = None,
) -> tuple[int | None, int]:
    """Run a single AI game to completion.

    Returns:
        (winner_index, action_count) - winner is None if limit exceeded.
    """
    names = [f'Player{i}' for i in range(num_players)]
    colors = ['red', 'blue', 'green', 'orange'][:num_players]
    ai_seed = seed
    ais = {i: EasyCatanAI(seed=ai_seed) for i in range(num_players)}

    state: GameState = create_initial_game_state(names, colors, seed=seed)
    action_count = 0

    while state.phase != GamePhase.ENDED and action_count < _MAX_ACTIONS:
        active_pi = state.turn_state.player_index
        if state.turn_state.pending_action == PendingActionType.DISCARD_RESOURCES:
            for pi in list(state.turn_state.discard_player_indices):
                actions = get_legal_actions(state, pi)
                if actions:
                    ai = ais[pi]
                    action = ai.choose_action(state, pi, actions)
                    result = apply_action(state, action)
                    if result.success and result.updated_state:
                        state = result.updated_state
                    action_count += 1
                    break
            else:
                # No discards needed but still in DISCARD state, move on
                break
        else:
            actions = get_legal_actions(state, active_pi)
            if not actions:
                break
            ai = ais[active_pi]
            action = ai.choose_action(state, active_pi, actions)
            result = apply_action(state, action)
            if result.success and result.updated_state:
                state = result.updated_state
            else:
                break
            action_count += 1

    return state.winner_index, action_count


def run_simulation(
    num_games: int = 100,
    num_players: int = 2,
    base_seed: int = 42,
) -> dict[str, object]:
    """Run multiple games and return aggregate statistics.

    Returns a dict with keys:
        - num_games: int
        - completed: int (games that ended with a winner)
        - timed_out: int (games that hit the action limit)
        - avg_actions: float
        - win_rates: dict[int, float] (by player/seat index)
        - duration_seconds: float
    """
    start = time.monotonic()
    action_counts: list[int] = []
    wins: dict[int, int] = {i: 0 for i in range(num_players)}
    completed = 0
    timed_out = 0

    for game_idx in range(num_games):
        seed = base_seed + game_idx
        winner, actions = run_game(num_players=num_players, seed=seed)
        action_counts.append(actions)
        if winner is not None:
            wins[winner] += 1
            completed += 1
        else:
            timed_out += 1

    duration = time.monotonic() - start
    avg_actions = statistics.mean(action_counts) if action_counts else 0.0
    win_rates = {i: wins[i] / num_games for i in range(num_players)}

    return {
        'num_games': num_games,
        'completed': completed,
        'timed_out': timed_out,
        'avg_actions': avg_actions,
        'win_rates': win_rates,
        'duration_seconds': duration,
    }


if __name__ == '__main__':
    stats = run_simulation(num_games=10)
    print(f'Games: {stats["num_games"]}')
    print(f'Completed: {stats["completed"]} / Timed out: {stats["timed_out"]}')
    print(f'Avg actions: {stats["avg_actions"]:.1f}')
    print(f'Win rates: {stats["win_rates"]}')
    print(f'Duration: {stats["duration_seconds"]:.2f}s')
