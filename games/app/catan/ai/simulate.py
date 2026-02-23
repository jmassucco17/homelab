"""AI vs AI simulation runner.

Run full Catan games between AI agents and report:

- Average game length (in actions)
- Win rates by player index / seat position
- Confirmation that games always complete (no infinite loops)

Usage::

    python -m games.app.catan.ai.simulate

By default runs 50 games with 2 players using Easy AI for speed.  Set
``NUM_GAMES``, ``NUM_PLAYERS``, or supply ``--hard`` / ``--medium`` via CLI
to vary the experiment.
"""

from __future__ import annotations

import argparse
import sys
import time

from games.app.catan.ai import base as ai_base
from games.app.catan.ai import easy, hard, medium
from games.app.catan.engine import processor, rules, turn_manager
from games.app.catan.models import game_state

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

_DEFAULT_NUM_GAMES = 50
_DEFAULT_NUM_PLAYERS = 2
_DEFAULT_AI_TYPE = 'easy'
_MAX_ACTIONS_PER_GAME = 5000  # hard cap to detect infinite loops

_PLAYER_COLORS = ['red', 'blue', 'green', 'orange']


# ---------------------------------------------------------------------------
# Game runner
# ---------------------------------------------------------------------------


def make_ais(
    ai_type: str,
    num_players: int,
    seed_offset: int = 0,
) -> list[ai_base.CatanAI]:
    """Create one AI per player of the requested difficulty.

    Returns a list of length *num_players*.
    """
    mapping: dict[str, type[ai_base.CatanAI]] = {
        'easy': easy.EasyAI,
        'medium': medium.MediumAI,
        'hard': hard.HardAI,
    }
    cls = mapping[ai_type]
    result: list[ai_base.CatanAI] = []
    for i in range(num_players):
        # Only EasyAI accepts a seed kwarg; others are deterministic by design.
        if ai_type == 'easy':
            result.append(easy.EasyAI(seed=seed_offset + i))
        else:
            result.append(cls())
    return result


def run_one_game(
    ais: list[ai_base.CatanAI],
    seed: int,
) -> tuple[int | None, int]:
    """Run a single game to completion and return (winner_index, action_count).

    Returns ``(None, action_count)`` if the game hit :data:`_MAX_ACTIONS_PER_GAME`.
    """
    num_players = len(ais)
    names = [f'Player{i}' for i in range(num_players)]
    colors = _PLAYER_COLORS[:num_players]
    state = turn_manager.create_initial_game_state(names, colors, seed=seed)

    action_count = 0
    while state.phase != game_state.GamePhase.ENDED:
        if action_count >= _MAX_ACTIONS_PER_GAME:
            return None, action_count

        acted = False
        for p_idx in range(num_players):
            legal = rules.get_legal_actions(state, p_idx)
            if not legal:
                continue
            action = ais[p_idx].choose_action(state, p_idx, legal)
            result = processor.apply_action(state, action)
            if result.success and result.updated_state is not None:
                state = result.updated_state
                action_count += 1
                acted = True
                break

        if not acted:
            # No player could act – stuck state.
            return None, action_count

    return state.winner_index, action_count


# ---------------------------------------------------------------------------
# Statistics helper
# ---------------------------------------------------------------------------


def _print_report(
    wins: list[int],
    action_counts: list[int],
    timeouts: int,
    num_games: int,
    elapsed: float,
) -> None:
    """Print a summary report to stdout."""
    total_finished = num_games - timeouts
    num_players = len(wins)
    print('=' * 50)
    print('Catan AI Simulation Results')
    print('=' * 50)
    print(f'Games played:    {num_games}')
    print(f'Games finished:  {total_finished}')
    print(f'Timed out:       {timeouts}')
    print(f'Elapsed:         {elapsed:.1f}s')
    if total_finished > 0:
        avg_actions = sum(action_counts) / len(action_counts)
        print(f'Avg actions/game:{avg_actions:.1f}')
    print()
    print('Win rates by seat:')
    for i in range(num_players):
        pct = (wins[i] / total_finished * 100) if total_finished > 0 else 0.0
        print(f'  Player {i}: {wins[i]:4d} wins  ({pct:.1f}%)')
    print('=' * 50)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_simulation(
    num_games: int = _DEFAULT_NUM_GAMES,
    num_players: int = _DEFAULT_NUM_PLAYERS,
    ai_type: str = _DEFAULT_AI_TYPE,
    start_seed: int = 0,
    verbose: bool = False,
) -> dict[str, object]:
    """Run *num_games* simulated Catan games and return a results dict.

    Returns a dict with keys:
    - ``wins``: list of win counts per player index.
    - ``action_counts``: list of actions per completed game.
    - ``timeouts``: number of games that hit the action cap.
    - ``elapsed``: total wall-clock time in seconds.
    """
    ais = make_ais(ai_type, num_players, seed_offset=start_seed)
    wins: list[int] = [0] * num_players
    action_counts: list[int] = []
    timeouts = 0

    t0 = time.monotonic()
    for game_idx in range(num_games):
        winner, actions_taken = run_one_game(ais, seed=start_seed + game_idx)
        if winner is None:
            timeouts += 1
        else:
            wins[winner] += 1
            action_counts.append(actions_taken)
        if verbose:
            status = f'winner={winner}' if winner is not None else 'TIMEOUT'
            print(f'  game {game_idx + 1:4d}: {status} ({actions_taken} actions)')
    elapsed = time.monotonic() - t0

    _print_report(wins, action_counts, timeouts, num_games, elapsed)
    return {
        'wins': wins,
        'action_counts': action_counts,
        'timeouts': timeouts,
        'elapsed': elapsed,
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description='Catan AI simulation runner')
    parser.add_argument(
        '--games', type=int, default=_DEFAULT_NUM_GAMES, help='Number of games to run'
    )
    parser.add_argument(
        '--players', type=int, default=_DEFAULT_NUM_PLAYERS, help='Number of players'
    )
    parser.add_argument(
        '--ai',
        choices=['easy', 'medium', 'hard'],
        default=_DEFAULT_AI_TYPE,
        help='AI difficulty level',
    )
    parser.add_argument('--seed', type=int, default=0, help='Starting RNG seed')
    parser.add_argument(
        '-v', '--verbose', action='store_true', help='Print per-game results'
    )
    return parser.parse_args(argv)


if __name__ == '__main__':
    args = _parse_args(sys.argv[1:])
    run_simulation(
        num_games=args.games,
        num_players=args.players,
        ai_type=args.ai,
        start_seed=args.seed,
        verbose=args.verbose,
    )
