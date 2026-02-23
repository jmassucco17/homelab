"""Catan rules engine.

Provides functions for computing legal actions, longest road, largest army,
and victory conditions.
"""

from __future__ import annotations

from ..models import actions, board, game_state, player

_SETUP_PHASES = (
    game_state.GamePhase.SETUP_FORWARD,
    game_state.GamePhase.SETUP_BACKWARD,
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_legal_actions(
    state: game_state.GameState, player_index: int
) -> list[actions.Action]:
    """Return all legal actions for *player_index* given the current game state."""
    if state.phase == game_state.GamePhase.ENDED:
        return []

    pending = state.turn_state.pending_action
    active = state.turn_state.player_index

    # ---- Setup phases -------------------------------------------------------
    if state.phase in _SETUP_PHASES:
        if player_index != active:
            return []
        return _setup_legal_actions(state, player_index)

    # ---- Main phase ---------------------------------------------------------
    return _main_legal_actions(state, player_index, active, pending)


def calculate_longest_road(board: board.Board, player_index: int) -> int:
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


_LARGEST_ARMY_THRESHOLD = 2  # player must exceed this to claim (i.e. ≥ 3 knights)


def get_largest_army_holder(players: list[player.Player]) -> int | None:
    """Return the player_index of the player with the most knights (>= 3).

    Returns None if no player has played at least 3 knights.  In case of a
    strict tie the function returns None, deferring tie-breaking to the caller
    (the existing holder retains the card).
    """
    best_count = _LARGEST_ARMY_THRESHOLD  # must exceed threshold
    holder: int | None = None
    for p in players:
        if p.knights_played > best_count:
            best_count = p.knights_played
            holder = p.player_index
        elif p.knights_played == best_count and holder is not None:
            # Tie among multiple players – no clear winner.
            holder = None
    return holder


def check_victory_condition(state: game_state.GameState) -> int | None:
    """Return the winner's player_index if any player has >= 10 VP, else None.

    VP breakdown:
      - settlements: 1 VP each (tracked in player.victory_points)
      - cities: +1 VP over settlement (tracked in player.victory_points)
      - VP dev cards: counted from dev_cards + new_dev_cards
      - longest road: 2 VP bonus (game_state.longest_road_owner)
      - largest army: 2 VP bonus (game_state.largest_army_owner)
    """
    for p in state.players:
        vp = p.victory_points
        vp += p.dev_cards.victory_point + p.new_dev_cards.victory_point
        if state.longest_road_owner == p.player_index:
            vp += 2
        if state.largest_army_owner == p.player_index:
            vp += 2
        if vp >= 10:
            return p.player_index
    return None


# ---------------------------------------------------------------------------
# Internal helpers – setup phase
# ---------------------------------------------------------------------------


def _setup_legal_actions(
    state: game_state.GameState, player_index: int
) -> list[actions.Action]:
    pending = state.turn_state.pending_action
    brd = state.board

    if pending == game_state.PendingActionType.PLACE_SETTLEMENT:
        result: list[actions.Action] = []
        for vertex in brd.vertices:
            if vertex.building is not None:
                continue
            if any(
                brd.vertices[adj_id].building is not None
                for adj_id in vertex.adjacent_vertex_ids
            ):
                continue
            result.append(
                actions.PlaceSettlement(
                    player_index=player_index, vertex_id=vertex.vertex_id
                )
            )
        return result

    if pending == game_state.PendingActionType.PLACE_ROAD:
        return _setup_road_actions(brd, player_index)

    return []


def _setup_road_actions(brd: board.Board, player_index: int) -> list[actions.Action]:
    """Return road placement actions adjacent to any own settlement (setup only)."""
    settlement_vertices: set[int] = {
        v.vertex_id
        for v in brd.vertices
        if v.building and v.building.player_index == player_index
    }
    result: list[actions.Action] = []
    seen: set[int] = set()
    for vertex in brd.vertices:
        if vertex.vertex_id not in settlement_vertices:
            continue
        for edge_id in vertex.adjacent_edge_ids:
            if edge_id in seen:
                continue
            seen.add(edge_id)
            if brd.edges[edge_id].road is None:
                result.append(
                    actions.PlaceRoad(player_index=player_index, edge_id=edge_id)
                )
    return result


# ---------------------------------------------------------------------------
# Internal helpers – main phase
# ---------------------------------------------------------------------------


def _main_legal_actions(
    state: game_state.GameState,
    player_index: int,
    active: int,
    pending: game_state.PendingActionType,
) -> list[actions.Action]:
    if pending == game_state.PendingActionType.ROLL_DICE:
        if player_index != active:
            return []
        return [actions.RollDice(player_index=player_index)]

    if pending == game_state.PendingActionType.MOVE_ROBBER:
        if player_index != active:
            return []
        return [
            actions.MoveRobber(player_index=player_index, tile_index=i)
            for i in range(len(state.board.tiles))
            if i != state.board.robber_tile_index
        ]

    if pending == game_state.PendingActionType.STEAL_RESOURCE:
        if player_index != active:
            return []
        return _steal_actions(state, player_index)

    if pending == game_state.PendingActionType.DISCARD_RESOURCES:
        if player_index not in state.turn_state.discard_player_indices:
            return []
        p = state.players[player_index]
        if p.resources.total() <= 7:
            return []
        return [actions.DiscardResources(player_index=player_index, resources={})]

    if pending == game_state.PendingActionType.BUILD_OR_TRADE:
        if player_index != active:
            return []
        return _build_or_trade_actions(state, player_index)

    return []


def _steal_actions(
    state: game_state.GameState, acting_player: int
) -> list[actions.Action]:
    """Return StealResource actions for players adjacent to the robber tile."""
    robber_tile = state.board.robber_tile_index
    candidates: set[int] = set()
    for vertex in state.board.vertices:
        if robber_tile not in vertex.adjacent_tile_indices:
            continue
        if vertex.building is None:
            continue
        idx = vertex.building.player_index
        if idx == acting_player:
            continue
        if state.players[idx].resources.total() > 0:
            candidates.add(idx)
    return [
        actions.StealResource(player_index=acting_player, target_player_index=t)
        for t in sorted(candidates)
    ]


def _build_or_trade_actions(
    state: game_state.GameState, player_index: int
) -> list[actions.Action]:
    brd = state.board
    p = state.players[player_index]
    inv = p.build_inventory
    res = p.resources
    result: list[actions.Action] = [actions.EndTurn(player_index=player_index)]

    # ---- Roads --------------------------------------------------------------
    free_roads = state.turn_state.free_roads_remaining
    can_afford_road = res.can_afford(player.ROAD_COST) or free_roads > 0
    if inv.roads_remaining >= 1 and can_afford_road:
        valid_road_edges = _main_road_edges(brd, player_index)
        for edge in valid_road_edges:
            result.append(
                actions.PlaceRoad(player_index=player_index, edge_id=edge.edge_id)
            )

    # ---- Settlements --------------------------------------------------------
    if inv.settlements_remaining >= 1 and res.can_afford(player.SETTLEMENT_COST):
        for vertex in brd.vertices:
            if not _can_place_settlement(brd, player_index, vertex.vertex_id):
                continue
            result.append(
                actions.PlaceSettlement(
                    player_index=player_index, vertex_id=vertex.vertex_id
                )
            )

    # ---- Cities -------------------------------------------------------------
    if inv.cities_remaining >= 1 and res.can_afford(player.CITY_COST):
        for vertex in brd.vertices:
            b = vertex.building
            if (
                b is not None
                and b.player_index == player_index
                and b.building_type == board.BuildingType.SETTLEMENT
            ):
                result.append(
                    actions.PlaceCity(
                        player_index=player_index, vertex_id=vertex.vertex_id
                    )
                )

    # ---- Dev cards ----------------------------------------------------------
    if res.can_afford(player.DEV_CARD_COST) and len(state.dev_card_deck) > 0:
        result.append(actions.BuildDevCard(player_index=player_index))

    # ---- Play dev cards (not new_dev_cards) ---------------------------------
    dev = p.dev_cards
    if dev.knight > 0:
        result.append(actions.PlayKnight(player_index=player_index))
    if dev.road_building > 0:
        result.append(actions.PlayRoadBuilding(player_index=player_index))
    if dev.year_of_plenty > 0:
        for r1 in board.ResourceType:
            for r2 in board.ResourceType:
                result.append(
                    actions.PlayYearOfPlenty(
                        player_index=player_index, resource1=r1, resource2=r2
                    )
                )
    if dev.monopoly > 0:
        for resource in board.ResourceType:
            result.append(
                actions.PlayMonopoly(player_index=player_index, resource=resource)
            )

    # ---- Bank trades --------------------------------------------------------
    for resource in board.ResourceType:
        if res.get(resource) >= 4:
            for receiving in board.ResourceType:
                if receiving != resource:
                    result.append(
                        actions.TradeWithBank(
                            player_index=player_index,
                            giving=resource,
                            receiving=receiving,
                        )
                    )

    # ---- Port trades --------------------------------------------------------
    for port_type in set(p.ports_owned):
        if port_type == board.PortType.GENERIC:
            for resource in board.ResourceType:
                if res.get(resource) >= 3:
                    for receiving in board.ResourceType:
                        if receiving != resource:
                            result.append(
                                actions.TradeWithPort(
                                    player_index=player_index,
                                    giving=resource,
                                    giving_count=3,
                                    receiving=receiving,
                                )
                            )
        else:
            specific = board.ResourceType(port_type.value)
            if res.get(specific) >= 2:
                for receiving in board.ResourceType:
                    if receiving != specific:
                        result.append(
                            actions.TradeWithPort(
                                player_index=player_index,
                                giving=specific,
                                giving_count=2,
                                receiving=receiving,
                            )
                        )

    return result


def _main_road_edges(brd: board.Board, player_index: int) -> list[board.Edge]:
    """Return edges where player_index can legally build a road (main phase)."""
    valid: list[board.Edge] = []
    for edge in brd.edges:
        if edge.road is not None:
            continue
        if can_place_road_at_edge(brd, player_index, edge.edge_id):
            valid.append(edge)
    return valid


def can_place_road_at_edge(brd: board.Board, player_index: int, edge_id: int) -> bool:
    """Return True if player_index can place a road on edge_id (main phase rules)."""
    edge = brd.edges[edge_id]
    for vid in edge.vertex_ids:
        vertex = brd.vertices[vid]
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
            adj = brd.edges[adj_eid]
            if adj.road and adj.road.player_index == player_index:
                return True
    return False


def _can_place_settlement(brd: board.Board, player_index: int, vertex_id: int) -> bool:
    """Return True if a settlement can be placed at vertex_id (main phase rules)."""
    vertex = brd.vertices[vertex_id]
    if vertex.building is not None:
        return False
    # Distance rule: no adjacent buildings.
    if any(
        brd.vertices[adj].building is not None for adj in vertex.adjacent_vertex_ids
    ):
        return False
    # Must be connected to own road.
    for edge_id in vertex.adjacent_edge_ids:
        edge = brd.edges[edge_id]
        if edge.road and edge.road.player_index == player_index:
            return True
    return False


# ---------------------------------------------------------------------------
# Internal helpers – longest road DFS
# ---------------------------------------------------------------------------


def _dfs_road(
    brd: board.Board, player_index: int, edge_id: int, visited: set[int]
) -> int:
    """DFS from edge_id; return length of longest road reachable from here."""
    visited.add(edge_id)
    edge = brd.edges[edge_id]
    max_len = 1

    for vid in edge.vertex_ids:
        vertex = brd.vertices[vid]
        # Opponent's building blocks traversal through this vertex.
        if vertex.building and vertex.building.player_index != player_index:
            continue
        for adj_eid in vertex.adjacent_edge_ids:
            if adj_eid in visited:
                continue
            adj = brd.edges[adj_eid]
            if adj.road and adj.road.player_index == player_index:
                length = 1 + _dfs_road(brd, player_index, adj_eid, visited)
                if length > max_len:
                    max_len = length

    visited.remove(edge_id)
    return max_len
