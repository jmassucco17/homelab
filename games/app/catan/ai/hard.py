"""Hard AI: advanced strategic Catan player."""

from __future__ import annotations

import random

from ..models.actions import Action, ActionType, StealResource
from ..models.board import TileType
from ..models.game_state import GameState
from .base import CatanAI
from .medium import PIPS, MediumCatanAI

# Resource diversity bonus: having different resources is more valuable
_RESOURCE_DIVERSITY_WEIGHT = 0.5

# Minimum own road length before pursuing longest road bonus
_MIN_ROAD_PURSUIT_LENGTH = 3
# Start pursuing longest road when within this many roads of the current holder
_ROAD_GAP_THRESHOLD = 2


def _vertex_score(game_state: GameState, vertex_id: int) -> float:
    """Score a vertex: pip count + resource diversity bonus."""
    board = game_state.board
    vertex = board.vertices[vertex_id]
    resources_seen: set[str] = set()
    pip_total = 0
    for tile_idx in vertex.adjacent_tile_indices:
        tile = board.tiles[tile_idx]
        if tile.number_token is not None and tile.tile_type != TileType.DESERT:
            pip_total += PIPS.get(tile.number_token, 0)
            resources_seen.add(tile.tile_type.value)
    diversity_bonus = len(resources_seen) * _RESOURCE_DIVERSITY_WEIGHT
    # Port bonus
    port_bonus = 2.0 if vertex.port_type is not None else 0.0
    return pip_total + diversity_bonus + port_bonus


class HardCatanAI(CatanAI):
    """Strategic AI with longest road, largest army, and adaptive trading."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self._medium = MediumCatanAI(seed=seed)

    def choose_action(
        self,
        game_state: GameState,
        player_index: int,
        legal_actions: list[Action],
    ) -> Action:
        if len(legal_actions) == 1:
            return legal_actions[0]

        # Delegate special actions to medium AI
        for atype in (
            ActionType.DISCARD_RESOURCES,
            ActionType.ROLL_DICE,
        ):
            matching = [a for a in legal_actions if a.action_type == atype]
            if matching:
                return self._medium.choose_action(
                    game_state, player_index, legal_actions
                )

        # Robber: target the leader, avoid own tiles
        robber_actions = [
            a for a in legal_actions if a.action_type == ActionType.MOVE_ROBBER
        ]
        if robber_actions:
            return self._choose_robber(game_state, player_index, robber_actions)

        # Steal: target player with most resources
        steal_actions = [a for a in legal_actions if isinstance(a, StealResource)]
        if steal_actions:
            return max(
                steal_actions,
                key=lambda a: game_state.players[
                    a.target_player_index
                ].resources.total(),
            )

        # Settlement: maximize vertex score
        settlements = [
            a for a in legal_actions if a.action_type == ActionType.PLACE_SETTLEMENT
        ]
        if settlements:
            return max(
                settlements,
                key=lambda a: _vertex_score(game_state, a.vertex_id),  # type: ignore[attr-defined]
            )

        # Pursue longest road if within reach
        my_road_len = game_state.players[player_index].longest_road_length
        current_holder = game_state.longest_road_owner
        holder_len = (
            game_state.players[current_holder].longest_road_length
            if current_holder is not None
            else 0
        )
        roads = [a for a in legal_actions if a.action_type == ActionType.PLACE_ROAD]
        threshold = max(_MIN_ROAD_PURSUIT_LENGTH, holder_len - _ROAD_GAP_THRESHOLD)
        if roads and (my_road_len >= threshold):
            return self._best_road(game_state, roads)

        # City
        cities = [a for a in legal_actions if a.action_type == ActionType.PLACE_CITY]
        if cities:
            return max(
                cities,
                key=lambda a: _vertex_score(game_state, a.vertex_id),  # type: ignore[attr-defined]
            )

        # Pursue largest army if within reach
        my_knights = game_state.players[player_index].knights_played
        current_army = game_state.largest_army_owner
        army_holder_knights = (
            game_state.players[current_army].knights_played
            if current_army is not None
            else 0
        )
        knight_actions = [
            a for a in legal_actions if a.action_type == ActionType.PLAY_KNIGHT
        ]
        if knight_actions and my_knights >= max(1, army_holder_knights - 2):
            return knight_actions[0]

        # Road building card
        rb_actions = [
            a for a in legal_actions if a.action_type == ActionType.PLAY_ROAD_BUILDING
        ]
        if rb_actions and roads:
            return rb_actions[0]

        # Roads (if not already handled)
        if roads:
            return self._best_road(game_state, roads)

        # Dev card
        dev_card = [
            a for a in legal_actions if a.action_type == ActionType.BUILD_DEV_CARD
        ]
        if dev_card:
            return dev_card[0]

        # Port trades strategically
        port_trades = [
            a for a in legal_actions if a.action_type == ActionType.TRADE_WITH_PORT
        ]
        if port_trades:
            return self._rng.choice(port_trades)

        # Bank trades
        bank_trades = [
            a for a in legal_actions if a.action_type == ActionType.TRADE_WITH_BANK
        ]
        has_build_action = any(
            a.action_type
            in (
                ActionType.PLACE_SETTLEMENT,
                ActionType.PLACE_ROAD,
                ActionType.PLACE_CITY,
            )
            for a in legal_actions
        )
        if bank_trades and not has_build_action:
            return self._rng.choice(bank_trades)

        end_turn = [a for a in legal_actions if a.action_type == ActionType.END_TURN]
        if end_turn:
            return end_turn[0]

        return self._rng.choice(legal_actions)

    def _choose_robber(
        self,
        game_state: GameState,
        player_index: int,
        robber_actions: list[Action],
    ) -> Action:
        """Target leader's tiles; avoid own tiles."""
        leader_idx = max(
            (i for i in range(len(game_state.players)) if i != player_index),
            key=lambda i: game_state.players[i].victory_points,
        )
        board = game_state.board
        # Prefer tiles with leader buildings but without own buildings
        scored: list[tuple[int, Action]] = []
        for action in robber_actions:
            tile_idx = action.tile_index  # type: ignore[attr-defined]
            tile_verts = [
                v for v in board.vertices if tile_idx in v.adjacent_tile_indices
            ]
            leader_count = sum(
                1
                for v in tile_verts
                if v.building is not None and v.building.player_index == leader_idx
            )
            own_count = sum(
                1
                for v in tile_verts
                if v.building is not None and v.building.player_index == player_index
            )
            scored.append((leader_count - own_count, action))
        scored.sort(key=lambda x: -x[0])
        return scored[0][1]

    def _best_road(self, game_state: GameState, roads: list[Action]) -> Action:
        """Choose road toward highest-score empty vertex."""
        board = game_state.board
        occupied = {v.vertex_id for v in board.vertices if v.building is not None}

        def road_score(action: Action) -> float:
            edge = board.edges[action.edge_id]  # type: ignore[attr-defined]
            best = 0.0
            for vid in edge.vertex_ids:
                if vid not in occupied:
                    best = max(best, _vertex_score(game_state, vid))
            return best

        return max(roads, key=road_score)
