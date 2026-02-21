"""Catan rules engine.

Provides functions for computing legal actions, longest road, largest army,
and victory conditions.
"""

from __future__ import annotations

from games.app.catan.models.actions import (
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
from games.app.catan.models.board import Board, Edge, PortType, ResourceType
from games.app.catan.models.game_state import GamePhase, GameState, PendingActionType
from games.app.catan.models.player import (
    CITY_COST,
    DEV_CARD_COST,
    ROAD_COST,
    SETTLEMENT_COST,
    Player,
)

# Type alias for the union of all action types (mirrors models.actions.Action).
type Action = (
    PlaceSettlement
    | PlaceRoad
    | PlaceCity
    | RollDice
    | BuildDevCard
    | PlayKnight
    | PlayRoadBuilding
    | PlayYearOfPlenty
    | PlayMonopoly
    | TradeWithBank
    | TradeWithPort
    | EndTurn
    | MoveRobber
    | StealResource
    | DiscardResources
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_legal_actions(game_state: GameState, player_index: int) -> list[Action]:
    """Return all legal actions for *player_index* given the current game state."""
    if game_state.phase == GamePhase.ENDED:
        return []

    pending = game_state.turn_state.pending_action
    active = game_state.turn_state.player_index

    # ---- Setup phases -------------------------------------------------------
    if game_state.phase in (GamePhase.SETUP_FORWARD, GamePhase.SETUP_BACKWARD):
        if player_index != active:
            return []
        return _setup_legal_actions(game_state, player_index)

    # ---- Main phase ---------------------------------------------------------
    return _main_legal_actions(game_state, player_index, active, pending)


def calculate_longest_road(board: Board, player_index: int) -> int:
    """Return the length of the longest continuous road for *player_index*.

    Uses DFS with backtracking over the player's road network.  A path is
    blocked at a vertex if an *opponent's* building occupies it.
    """
    player_edges = [
        e for e in board.edges if e.road and e.road.player_index == player_index
    ]
    if not player_edges:
        return 0

    max_length = 0
    for start_edge in player_edges:
        visited: set[int] = set()
        length = _dfs_road(board, player_index, start_edge.edge_id, visited)
        if length > max_length:
            max_length = length
    return max_length


def get_largest_army_holder(players: list[Player]) -> int | None:
    """Return the player_index of the player with the most knights (>= 3).

    Returns None if no player has played at least 3 knights.  In case of a
    strict tie the function returns None, deferring tie-breaking to the caller
    (the existing holder retains the card).
    """
    best_count = 2  # must exceed 2 to qualify
    holder: int | None = None
    for player in players:
        if player.knights_played > best_count:
            best_count = player.knights_played
            holder = player.player_index
        elif player.knights_played == best_count and holder is not None:
            # Tie among multiple players – no clear winner.
            holder = None
    return holder


def check_victory_condition(game_state: GameState) -> int | None:
    """Return the winner's player_index if any player has >= 10 VP, else None.

    VP breakdown:
      - settlements: 1 VP each (tracked in player.victory_points)
      - cities: +1 VP over settlement (tracked in player.victory_points)
      - VP dev cards: counted from dev_cards + new_dev_cards
      - longest road: 2 VP bonus (game_state.longest_road_owner)
      - largest army: 2 VP bonus (game_state.largest_army_owner)
    """
    for player in game_state.players:
        vp = player.victory_points
        vp += player.dev_cards.victory_point + player.new_dev_cards.victory_point
        if game_state.longest_road_owner == player.player_index:
            vp += 2
        if game_state.largest_army_owner == player.player_index:
            vp += 2
        if vp >= 10:
            return player.player_index
    return None


# ---------------------------------------------------------------------------
# Internal helpers – setup phase
# ---------------------------------------------------------------------------


def _setup_legal_actions(game_state: GameState, player_index: int) -> list[Action]:
    pending = game_state.turn_state.pending_action
    board = game_state.board

    if pending == PendingActionType.PLACE_SETTLEMENT:
        actions: list[Action] = []
        for vertex in board.vertices:
            if vertex.building is not None:
                continue
            if any(
                board.vertices[adj_id].building is not None
                for adj_id in vertex.adjacent_vertex_ids
            ):
                continue
            actions.append(
                PlaceSettlement(player_index=player_index, vertex_id=vertex.vertex_id)
            )
        return actions

    if pending == PendingActionType.PLACE_ROAD:
        return _setup_road_actions(board, player_index)

    return []


def _setup_road_actions(board: Board, player_index: int) -> list[Action]:
    """Return road placement actions adjacent to any own settlement (setup only)."""
    settlement_vertices: set[int] = {
        v.vertex_id
        for v in board.vertices
        if v.building and v.building.player_index == player_index
    }
    actions: list[Action] = []
    seen: set[int] = set()
    for vertex in board.vertices:
        if vertex.vertex_id not in settlement_vertices:
            continue
        for edge_id in vertex.adjacent_edge_ids:
            if edge_id in seen:
                continue
            seen.add(edge_id)
            if board.edges[edge_id].road is None:
                actions.append(PlaceRoad(player_index=player_index, edge_id=edge_id))
    return actions


# ---------------------------------------------------------------------------
# Internal helpers – main phase
# ---------------------------------------------------------------------------


def _main_legal_actions(
    game_state: GameState,
    player_index: int,
    active: int,
    pending: PendingActionType,
) -> list[Action]:
    if pending == PendingActionType.ROLL_DICE:
        if player_index != active:
            return []
        return [RollDice(player_index=player_index)]

    if pending == PendingActionType.MOVE_ROBBER:
        if player_index != active:
            return []
        return [
            MoveRobber(player_index=player_index, tile_index=i)
            for i in range(len(game_state.board.tiles))
            if i != game_state.board.robber_tile_index
        ]

    if pending == PendingActionType.STEAL_RESOURCE:
        if player_index != active:
            return []
        return _steal_actions(game_state, player_index)

    if pending == PendingActionType.DISCARD_RESOURCES:
        if player_index not in game_state.turn_state.discard_player_indices:
            return []
        player = game_state.players[player_index]
        if player.resources.total() <= 7:
            return []
        return [DiscardResources(player_index=player_index, resources={})]

    if pending == PendingActionType.BUILD_OR_TRADE:
        if player_index != active:
            return []
        return _build_or_trade_actions(game_state, player_index)

    return []


def _steal_actions(game_state: GameState, acting_player: int) -> list[Action]:
    """Return StealResource actions for players adjacent to the robber tile."""
    robber_tile = game_state.board.robber_tile_index
    candidates: set[int] = set()
    for vertex in game_state.board.vertices:
        if robber_tile not in vertex.adjacent_tile_indices:
            continue
        if vertex.building is None:
            continue
        idx = vertex.building.player_index
        if idx == acting_player:
            continue
        if game_state.players[idx].resources.total() > 0:
            candidates.add(idx)
    return [
        StealResource(player_index=acting_player, target_player_index=t)
        for t in sorted(candidates)
    ]


def _build_or_trade_actions(game_state: GameState, player_index: int) -> list[Action]:
    board = game_state.board
    player = game_state.players[player_index]
    inv = player.build_inventory
    res = player.resources
    actions: list[Action] = [EndTurn(player_index=player_index)]

    # ---- Roads --------------------------------------------------------------
    free_roads = game_state.turn_state.free_roads_remaining
    can_afford_road = res.can_afford(ROAD_COST) or free_roads > 0
    if inv.roads_remaining >= 1 and can_afford_road:
        valid_road_edges = _main_road_edges(board, player_index)
        for edge in valid_road_edges:
            actions.append(PlaceRoad(player_index=player_index, edge_id=edge.edge_id))

    # ---- Settlements --------------------------------------------------------
    if inv.settlements_remaining >= 1 and res.can_afford(SETTLEMENT_COST):
        for vertex in board.vertices:
            if not _can_place_settlement(board, player_index, vertex.vertex_id):
                continue
            actions.append(
                PlaceSettlement(player_index=player_index, vertex_id=vertex.vertex_id)
            )

    # ---- Cities -------------------------------------------------------------
    if inv.cities_remaining >= 1 and res.can_afford(CITY_COST):
        from games.app.catan.models.board import BuildingType

        for vertex in board.vertices:
            b = vertex.building
            if (
                b is not None
                and b.player_index == player_index
                and b.building_type == BuildingType.SETTLEMENT
            ):
                actions.append(
                    PlaceCity(player_index=player_index, vertex_id=vertex.vertex_id)
                )

    # ---- Dev cards ----------------------------------------------------------
    if res.can_afford(DEV_CARD_COST) and len(game_state.dev_card_deck) > 0:
        actions.append(BuildDevCard(player_index=player_index))

    # ---- Play dev cards (not new_dev_cards) ---------------------------------
    dev = player.dev_cards
    if dev.knight > 0:
        actions.append(PlayKnight(player_index=player_index))
    if dev.road_building > 0:
        actions.append(PlayRoadBuilding(player_index=player_index))
    if dev.year_of_plenty > 0:
        for r1 in ResourceType:
            for r2 in ResourceType:
                actions.append(
                    PlayYearOfPlenty(
                        player_index=player_index, resource1=r1, resource2=r2
                    )
                )
    if dev.monopoly > 0:
        for resource in ResourceType:
            actions.append(PlayMonopoly(player_index=player_index, resource=resource))

    # ---- Bank trades --------------------------------------------------------
    for resource in ResourceType:
        if res.get(resource) >= 4:
            for receiving in ResourceType:
                if receiving != resource:
                    actions.append(
                        TradeWithBank(
                            player_index=player_index,
                            giving=resource,
                            receiving=receiving,
                        )
                    )

    # ---- Port trades --------------------------------------------------------
    for port_type in set(player.ports_owned):
        if port_type == PortType.GENERIC:
            for resource in ResourceType:
                if res.get(resource) >= 3:
                    for receiving in ResourceType:
                        if receiving != resource:
                            actions.append(
                                TradeWithPort(
                                    player_index=player_index,
                                    giving=resource,
                                    giving_count=3,
                                    receiving=receiving,
                                )
                            )
        else:
            specific = ResourceType(port_type.value)
            if res.get(specific) >= 2:
                for receiving in ResourceType:
                    if receiving != specific:
                        actions.append(
                            TradeWithPort(
                                player_index=player_index,
                                giving=specific,
                                giving_count=2,
                                receiving=receiving,
                            )
                        )

    return actions


def _main_road_edges(board: Board, player_index: int) -> list[Edge]:
    """Return edges where player_index can legally build a road (main phase)."""
    valid: list[Edge] = []
    for edge in board.edges:
        if edge.road is not None:
            continue
        if can_place_road_at_edge(board, player_index, edge.edge_id):
            valid.append(edge)
    return valid


def can_place_road_at_edge(board: Board, player_index: int, edge_id: int) -> bool:
    """Return True if player_index can place a road on edge_id (main phase rules)."""
    edge = board.edges[edge_id]
    for vid in edge.vertex_ids:
        vertex = board.vertices[vid]
        # Own building at this vertex → can always extend from it.
        if vertex.building and vertex.building.player_index == player_index:
            return True
        # Opponent's building blocks this vertex as a connection point.
        if vertex.building is not None:
            continue
        # Empty vertex: check for adjacent own road.
        for adj_eid in vertex.adjacent_edge_ids:
            if adj_eid == edge_id:
                continue
            adj = board.edges[adj_eid]
            if adj.road and adj.road.player_index == player_index:
                return True
    return False


def _can_place_settlement(board: Board, player_index: int, vertex_id: int) -> bool:
    """Return True if a settlement can be placed at vertex_id (main phase rules)."""
    vertex = board.vertices[vertex_id]
    if vertex.building is not None:
        return False
    # Distance rule: no adjacent buildings.
    if any(
        board.vertices[adj].building is not None for adj in vertex.adjacent_vertex_ids
    ):
        return False
    # Must be connected to own road.
    for edge_id in vertex.adjacent_edge_ids:
        edge = board.edges[edge_id]
        if edge.road and edge.road.player_index == player_index:
            return True
    return False


# ---------------------------------------------------------------------------
# Internal helpers – longest road DFS
# ---------------------------------------------------------------------------


def _dfs_road(board: Board, player_index: int, edge_id: int, visited: set[int]) -> int:
    """DFS from edge_id; return length of longest road reachable from here."""
    visited.add(edge_id)
    edge = board.edges[edge_id]
    max_len = 1

    for vid in edge.vertex_ids:
        vertex = board.vertices[vid]
        # Opponent's building blocks traversal through this vertex.
        if vertex.building and vertex.building.player_index != player_index:
            continue
        for adj_eid in vertex.adjacent_edge_ids:
            if adj_eid in visited:
                continue
            adj = board.edges[adj_eid]
            if adj.road and adj.road.player_index == player_index:
                length = 1 + _dfs_road(board, player_index, adj_eid, visited)
                if length > max_len:
                    max_len = length

    visited.remove(edge_id)
    return max_len
