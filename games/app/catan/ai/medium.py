"""Medium AI: heuristic-based Catan player."""

from __future__ import annotations

import random

from ..models.actions import (
    Action,
    ActionType,
    DiscardResources,
)
from ..models.game_state import GameState
from .base import CatanAI

# Pip counts per number token
PIPS: dict[int, int] = {2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 8: 5, 9: 4, 10: 3, 11: 2, 12: 1}


def _vertex_pip_count(game_state: GameState, vertex_id: int) -> int:
    """Sum of pip values for all productive tiles adjacent to vertex."""
    board = game_state.board
    vertex = board.vertices[vertex_id]
    total = 0
    for tile_idx in vertex.adjacent_tile_indices:
        tile = board.tiles[tile_idx]
        if tile.number_token is not None:
            total += PIPS.get(tile.number_token, 0)
    return total


class MediumCatanAI(CatanAI):
    """Heuristic AI with building priority and basic resource management."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def choose_action(
        self,
        game_state: GameState,
        player_index: int,
        legal_actions: list[Action],
    ) -> Action:
        # Special mandatory actions: handle first
        if len(legal_actions) == 1:
            return legal_actions[0]

        # Discard: discard least useful resources
        discards = [
            a for a in legal_actions if a.action_type == ActionType.DISCARD_RESOURCES
        ]
        if discards:
            return self._choose_discard(discards)  # type: ignore[arg-type]

        # Roll dice if available
        roll_actions = [
            a for a in legal_actions if a.action_type == ActionType.ROLL_DICE
        ]
        if roll_actions:
            # Play knight first if behind and have one
            knight_actions = [
                a for a in legal_actions if a.action_type == ActionType.PLAY_KNIGHT
            ]
            if knight_actions:
                my_vp = game_state.players[player_index].victory_points
                max_opp = max(
                    p.victory_points
                    for i, p in enumerate(game_state.players)
                    if i != player_index
                )
                if my_vp < max_opp:
                    return knight_actions[0]
            return roll_actions[0]

        # Move robber: target the leader
        robber_actions = [
            a for a in legal_actions if a.action_type == ActionType.MOVE_ROBBER
        ]
        if robber_actions:
            return self._choose_robber(game_state, player_index, robber_actions)  # type: ignore[arg-type]

        # Steal resource
        steal_actions = [
            a for a in legal_actions if a.action_type == ActionType.STEAL_RESOURCE
        ]
        if steal_actions:
            return self._rng.choice(steal_actions)

        # Build priority: settlement > road > city > dev card
        settlements = [
            a for a in legal_actions if a.action_type == ActionType.PLACE_SETTLEMENT
        ]
        if settlements:
            return self._best_settlement(game_state, settlements)  # type: ignore[arg-type]

        roads = [a for a in legal_actions if a.action_type == ActionType.PLACE_ROAD]
        if roads:
            return self._best_road(game_state, player_index, roads)

        cities = [a for a in legal_actions if a.action_type == ActionType.PLACE_CITY]
        if cities:
            return self._best_settlement(game_state, cities)  # type: ignore[arg-type]

        # Play knight
        knight_actions = [
            a for a in legal_actions if a.action_type == ActionType.PLAY_KNIGHT
        ]
        if knight_actions:
            my_vp = game_state.players[player_index].victory_points
            max_opp = max(
                p.victory_points
                for i, p in enumerate(game_state.players)
                if i != player_index
            )
            if my_vp < max_opp:
                return knight_actions[0]

        # Trade if can't build and have 4+ of something
        trades = [
            a
            for a in legal_actions
            if a.action_type in (ActionType.TRADE_WITH_BANK, ActionType.TRADE_WITH_PORT)
        ]
        has_build = any(
            a.action_type
            in (
                ActionType.PLACE_SETTLEMENT,
                ActionType.PLACE_ROAD,
                ActionType.PLACE_CITY,
                ActionType.BUILD_DEV_CARD,
            )
            for a in legal_actions
        )
        if trades and not has_build:
            return self._rng.choice(trades)

        # End turn if nothing better
        non_end = [
            a
            for a in legal_actions
            if a.action_type
            not in (
                ActionType.END_TURN,
                ActionType.TRADE_WITH_BANK,
                ActionType.TRADE_WITH_PORT,
            )
        ]
        end_turn = [a for a in legal_actions if a.action_type == ActionType.END_TURN]
        if end_turn and not (roads or settlements or cities or non_end):
            return end_turn[0]

        return self._rng.choice(legal_actions)

    def _choose_discard(self, discards: list[DiscardResources]) -> DiscardResources:
        """Pick the first discard option (could be smarter)."""
        return discards[0]

    def _choose_robber(
        self,
        game_state: GameState,
        player_index: int,
        robber_actions: list[Action],
    ) -> Action:
        """Target the leader's tiles."""
        leader_idx = max(
            (i for i in range(len(game_state.players)) if i != player_index),
            key=lambda i: game_state.players[i].victory_points,
        )
        board = game_state.board
        for action in robber_actions:
            tile_idx = action.tile_index  # type: ignore[attr-defined]
            tile_verts = [
                v for v in board.vertices if tile_idx in v.adjacent_tile_indices
            ]
            if any(
                v.building is not None and v.building.player_index == leader_idx
                for v in tile_verts
            ):
                return action
        return self._rng.choice(robber_actions)

    def _best_settlement(self, game_state: GameState, actions: list[Action]) -> Action:
        """Choose settlement/city location with highest pip count."""
        return max(
            actions,
            key=lambda a: _vertex_pip_count(game_state, a.vertex_id),  # type: ignore[attr-defined]
        )

    def _best_road(
        self, game_state: GameState, player_index: int, roads: list[Action]
    ) -> Action:
        """Choose road toward the highest-pip empty vertex."""
        board = game_state.board
        occupied = {v.vertex_id for v in board.vertices if v.building is not None}

        def road_score(action: Action) -> int:
            edge = board.edges[action.edge_id]  # type: ignore[attr-defined]
            best = 0
            for vid in edge.vertex_ids:
                if vid not in occupied:
                    best = max(best, _vertex_pip_count(game_state, vid))
            return best

        return max(roads, key=road_score)
