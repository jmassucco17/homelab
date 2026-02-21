"""Rules engine: legal action generation for each game state."""

from __future__ import annotations

import itertools

from ..models.actions import (
    Action,
    BuildDevCard,
    DiscardResources,
    EndTurn,
    MoveRobber,
    PlaceCity,
    PlaceRoad,
    PlaceSettlement,
    PlayKnight,
    PlayMonopoly,
    PlayRoadBuilding,
    PlayYearOfPlenty,
    RollDice,
    StealResource,
    TradeWithBank,
    TradeWithPort,
)
from ..models.board import Board, BuildingType, PortType, ResourceType
from ..models.game_state import GamePhase, GameState, PendingActionType
from ..models.player import (
    CITY_COST,
    DEV_CARD_COST,
    ROAD_COST,
    SETTLEMENT_COST,
    Resources,
)


def get_legal_actions(game_state: GameState, player_index: int) -> list[Action]:
    """Return all legal actions for the given player in the current game state."""
    state = game_state
    phase = state.phase
    turn_state = state.turn_state

    if phase == GamePhase.ENDED:
        return []

    # Non-active players can only discard if required
    if turn_state.player_index != player_index:
        if (
            turn_state.pending_action == PendingActionType.DISCARD_RESOURCES
            and player_index in turn_state.discard_player_indices
        ):
            return _legal_discard_actions(state, player_index)
        return []

    if phase in (GamePhase.SETUP_FORWARD, GamePhase.SETUP_BACKWARD):
        return _legal_setup_actions(state, player_index)

    pending = turn_state.pending_action

    if pending == PendingActionType.ROLL_DICE:
        return _legal_roll_dice_actions(state, player_index)
    if pending == PendingActionType.MOVE_ROBBER:
        return _legal_move_robber_actions(state, player_index)
    if pending == PendingActionType.STEAL_RESOURCE:
        return _legal_steal_actions(state, player_index)
    if pending == PendingActionType.DISCARD_RESOURCES:
        if player_index in turn_state.discard_player_indices:
            return _legal_discard_actions(state, player_index)
        return []
    if pending == PendingActionType.PLACE_ROAD:
        return _legal_free_road_actions(state, player_index)
    if pending == PendingActionType.BUILD_OR_TRADE:
        return _legal_build_or_trade_actions(state, player_index)

    return []


# ---------------------------------------------------------------------------
# Setup phase
# ---------------------------------------------------------------------------


def _legal_setup_actions(state: GameState, player_index: int) -> list[Action]:
    """Return legal actions during setup phases."""
    pending = state.turn_state.pending_action
    board = state.board

    if pending == PendingActionType.PLACE_SETTLEMENT:
        occupied = {v.vertex_id for v in board.vertices if v.building is not None}
        actions: list[Action] = []
        for vertex in board.vertices:
            if vertex.building is not None:
                continue
            if any(adj in occupied for adj in vertex.adjacent_vertex_ids):
                continue
            actions.append(
                PlaceSettlement(player_index=player_index, vertex_id=vertex.vertex_id)
            )
        return actions

    if pending == PendingActionType.PLACE_ROAD:
        player_verts = {
            v.vertex_id
            for v in board.vertices
            if v.building is not None and v.building.player_index == player_index
        }
        actions = []
        for edge in board.edges:
            if edge.road is not None:
                continue
            if any(vid in player_verts for vid in edge.vertex_ids):
                actions.append(
                    PlaceRoad(player_index=player_index, edge_id=edge.edge_id)
                )
        return actions

    return []


# ---------------------------------------------------------------------------
# Main phase helpers
# ---------------------------------------------------------------------------


def _legal_roll_dice_actions(state: GameState, player_index: int) -> list[Action]:
    """Legal actions when player must roll."""
    actions: list[Action] = [RollDice(player_index=player_index)]
    player = state.players[player_index]
    if player.dev_cards.knight > 0:
        actions.append(PlayKnight(player_index=player_index))
    return actions


def _legal_move_robber_actions(state: GameState, player_index: int) -> list[Action]:
    """Legal robber destinations (all tiles except current)."""
    current = state.board.robber_tile_index
    return [
        MoveRobber(player_index=player_index, tile_index=i)
        for i in range(len(state.board.tiles))
        if i != current
    ]


def _legal_steal_actions(state: GameState, player_index: int) -> list[Action]:
    """Legal steal targets: opponents with buildings adjacent to robber tile."""
    board = state.board
    robber_idx = board.robber_tile_index
    adjacent_verts = [
        v for v in board.vertices if robber_idx in v.adjacent_tile_indices
    ]
    eligible: set[int] = set()
    for v in adjacent_verts:
        if v.building is not None and v.building.player_index != player_index:
            eligible.add(v.building.player_index)
    return [
        StealResource(player_index=player_index, target_player_index=t)
        for t in eligible
    ]


def _legal_discard_actions(state: GameState, player_index: int) -> list[Action]:
    """Legal discard combos: exactly total//2 resources."""
    player = state.players[player_index]
    total = player.resources.total()
    count = total // 2
    combos = _enumerate_discard_combos(player.resources, count)
    return [DiscardResources(player_index=player_index, resources=c) for c in combos]


def _enumerate_discard_combos(resources: Resources, count: int) -> list[dict[str, int]]:
    """All valid multisets of exactly `count` resources from the player's hand."""
    if count <= 0:
        return [{}]
    seen: set[tuple[tuple[str, int], ...]] = set()
    result: list[dict[str, int]] = []
    for combo in itertools.combinations_with_replacement(list(ResourceType), count):
        counts: dict[str, int] = {}
        for rt in combo:
            counts[rt.value] = counts.get(rt.value, 0) + 1
        if all(resources.get(ResourceType(r)) >= v for r, v in counts.items()):
            key = tuple(sorted(counts.items()))
            if key not in seen:
                seen.add(key)
                result.append(counts)
    return result


def _legal_free_road_actions(state: GameState, player_index: int) -> list[Action]:
    """Legal road placements from Road Building card."""
    player = state.players[player_index]
    if player.build_inventory.roads_remaining <= 0:
        return []
    board = state.board
    reachable = _player_road_reachable_vertices(board, player_index)
    return [
        PlaceRoad(player_index=player_index, edge_id=e.edge_id)
        for e in board.edges
        if e.road is None and any(vid in reachable for vid in e.vertex_ids)
    ]


def _legal_build_or_trade_actions(state: GameState, player_index: int) -> list[Action]:
    """All legal build/trade/dev-card actions."""
    player = state.players[player_index]
    board = state.board
    actions: list[Action] = [EndTurn(player_index=player_index)]

    # --- Settlements ---
    if (
        player.resources.can_afford(SETTLEMENT_COST)
        and player.build_inventory.settlements_remaining > 0
    ):
        occupied = {v.vertex_id for v in board.vertices if v.building is not None}
        road_verts = _player_road_reachable_vertices(board, player_index)
        for v in board.vertices:
            if v.building is not None:
                continue
            if any(adj in occupied for adj in v.adjacent_vertex_ids):
                continue
            if v.vertex_id not in road_verts:
                continue
            actions.append(
                PlaceSettlement(player_index=player_index, vertex_id=v.vertex_id)
            )

    # --- Roads ---
    if (
        player.resources.can_afford(ROAD_COST)
        and player.build_inventory.roads_remaining > 0
    ):
        reachable = _player_road_reachable_vertices(board, player_index)
        for e in board.edges:
            if e.road is not None:
                continue
            if any(vid in reachable for vid in e.vertex_ids):
                actions.append(PlaceRoad(player_index=player_index, edge_id=e.edge_id))

    # --- Cities ---
    if (
        player.resources.can_afford(CITY_COST)
        and player.build_inventory.cities_remaining > 0
    ):
        for v in board.vertices:
            if (
                v.building is not None
                and v.building.player_index == player_index
                and v.building.building_type == BuildingType.SETTLEMENT
            ):
                actions.append(
                    PlaceCity(player_index=player_index, vertex_id=v.vertex_id)
                )

    # --- Dev card ---
    if player.resources.can_afford(DEV_CARD_COST) and len(state.dev_card_deck) > 0:
        actions.append(BuildDevCard(player_index=player_index))

    # --- Bank trades ---
    for giving in ResourceType:
        if player.resources.get(giving) >= 4:
            for receiving in ResourceType:
                if receiving != giving:
                    actions.append(
                        TradeWithBank(
                            player_index=player_index,
                            giving=giving,
                            receiving=receiving,
                        )
                    )

    # --- Port trades ---
    for port_type in set(player.ports_owned):
        if port_type == PortType.GENERIC:
            for giving in ResourceType:
                if player.resources.get(giving) >= 3:
                    for receiving in ResourceType:
                        if receiving != giving:
                            actions.append(
                                TradeWithPort(
                                    player_index=player_index,
                                    giving=giving,
                                    giving_count=3,
                                    receiving=receiving,
                                )
                            )
        else:
            giving = ResourceType(port_type.value)
            if player.resources.get(giving) >= 2:
                for receiving in ResourceType:
                    if receiving != giving:
                        actions.append(
                            TradeWithPort(
                                player_index=player_index,
                                giving=giving,
                                giving_count=2,
                                receiving=receiving,
                            )
                        )

    # --- Dev card plays ---
    if player.dev_cards.knight > 0:
        actions.append(PlayKnight(player_index=player_index))
    if player.dev_cards.road_building > 0:
        actions.append(PlayRoadBuilding(player_index=player_index))
    if player.dev_cards.year_of_plenty > 0:
        for r1, r2 in itertools.combinations_with_replacement(list(ResourceType), 2):
            actions.append(
                PlayYearOfPlenty(player_index=player_index, resource1=r1, resource2=r2)
            )
    if player.dev_cards.monopoly > 0:
        for r in ResourceType:
            actions.append(PlayMonopoly(player_index=player_index, resource=r))

    return actions


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _player_road_reachable_vertices(board: Board, player_index: int) -> set[int]:
    """Vertices reachable by the player's roads or own settlements/cities."""
    verts: set[int] = set()
    for v in board.vertices:
        if v.building is not None and v.building.player_index == player_index:
            verts.add(v.vertex_id)
    for e in board.edges:
        if e.road is not None and e.road.player_index == player_index:
            verts.update(e.vertex_ids)
    return verts
