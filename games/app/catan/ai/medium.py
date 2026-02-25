"""Medium (priority-based) AI for Catan.

Uses a set of hand-crafted heuristics to make reasonable decisions:

- **Setup phase**: prefer vertices with a high pip score and resource
  diversity (resources not yet produced by own settlements).
- **Main phase**: settlement > city > road > dev card > end turn.
  Trades are only made when they unlock a build action.
- **MoveRobber**: target the tile with the most opponent buildings.
- **StealResource**: steal from the player with the most resources.
- **DiscardResources**: discard the most-abundant resources first.
- **PlayKnight**: play when holding one and the score gap is small (≤2) or
  when already leading in knights.
"""

from __future__ import annotations

from ..engine import trade as trade_module
from ..models import actions, board, game_state, player
from . import base

# Pip probability count per number token (proportional to dice probability).
_PIP_COUNT: dict[int, int] = {
    2: 1,
    3: 2,
    4: 3,
    5: 4,
    6: 5,
    8: 5,
    9: 4,
    10: 3,
    11: 2,
    12: 1,
}

# Standard bank trade ratio (4 of one resource for 1 of another).
_BANK_TRADE_RATIO = 4

# Build action priority order (lower index = higher priority).
_BUILD_PRIORITY: list[type] = [
    actions.PlaceSettlement,
    actions.PlaceCity,
    actions.PlaceRoad,
    actions.BuildDevCard,
]


def vertex_pip_score(state: game_state.GameState, vertex: board.Vertex) -> int:
    """Return the total pip score for a board vertex.

    Sums the pip counts of all adjacent non-desert tiles.
    """
    score = 0
    for tile_idx in vertex.adjacent_tile_indices:
        tile = state.board.tiles[tile_idx]
        if tile.number_token is not None:
            score += _PIP_COUNT.get(tile.number_token, 0)
    return score


def vertex_resource_diversity(
    state: game_state.GameState,
    player_index: int,
    vertex: board.Vertex,
) -> int:
    """Return the number of new resource types this vertex would add.

    Counts resource types produced by the vertex's adjacent tiles that are
    not already produced by any of the player's existing settlements/cities.
    """
    owned_resources: set[board.ResourceType] = set()
    for v in state.board.vertices:
        if v.building and v.building.player_index == player_index:
            for tile_idx in v.adjacent_tile_indices:
                tile = state.board.tiles[tile_idx]
                if tile.tile_type in board.TILE_RESOURCE:
                    owned_resources.add(board.TILE_RESOURCE[tile.tile_type])

    new_resources: set[board.ResourceType] = set()
    for tile_idx in vertex.adjacent_tile_indices:
        tile = state.board.tiles[tile_idx]
        if tile.tile_type in board.TILE_RESOURCE:
            res = board.TILE_RESOURCE[tile.tile_type]
            if res not in owned_resources:
                new_resources.add(res)
    return len(new_resources)


def _score_setup_vertex(
    state: game_state.GameState,
    player_index: int,
    vertex: board.Vertex,
) -> tuple[int, int]:
    """Return (pip_score, diversity_score) for ranking setup placements."""
    return (
        vertex_pip_score(state, vertex),
        vertex_resource_diversity(state, player_index, vertex),
    )


def _best_setup_settlement(
    state: game_state.GameState,
    player_index: int,
    legal: list[actions.Action],
) -> actions.Action:
    """Pick the PlaceSettlement with the highest pip + diversity score."""
    best_action = legal[0]
    best_score: tuple[int, int] = (-1, -1)
    for action in legal:
        if not isinstance(action, actions.PlaceSettlement):
            continue
        vertex = state.board.vertices[action.vertex_id]
        score = _score_setup_vertex(state, player_index, vertex)
        if score > best_score:
            best_score = score
            best_action = action
    return best_action


def _best_setup_road(
    state: game_state.GameState,
    player_index: int,
    legal: list[actions.Action],
) -> actions.Action:
    """Pick a road that extends toward the highest-value unoccupied vertex."""
    best_action = legal[0]
    best_score = -1
    for action in legal:
        if not isinstance(action, actions.PlaceRoad):
            continue
        edge = state.board.edges[action.edge_id]
        # Score the road by the best reachable vertex from either endpoint.
        score = 0
        for vid in edge.vertex_ids:
            vertex = state.board.vertices[vid]
            if vertex.building is None:
                pip = vertex_pip_score(state, vertex)
                score = max(score, pip)
        if score > best_score:
            best_score = score
            best_action = action
    return best_action


def _best_move_robber(
    state: game_state.GameState,
    player_index: int,
    legal: list[actions.Action],
) -> actions.Action:
    """Place robber on the tile with the most opponent buildings."""
    best_action = legal[0]
    best_count = -1
    for action in legal:
        if not isinstance(action, actions.MoveRobber):
            continue
        tile_idx = action.tile_index
        count = 0
        for vertex in state.board.vertices:
            if tile_idx not in vertex.adjacent_tile_indices:
                continue
            if vertex.building and vertex.building.player_index != player_index:
                count += 1
        if count > best_count:
            best_count = count
            best_action = action
    return best_action


def _best_steal(
    state: game_state.GameState,
    legal: list[actions.Action],
) -> actions.Action:
    """Steal from the opponent with the most resources."""
    best_action = legal[0]
    best_total = -1
    for action in legal:
        if not isinstance(action, actions.StealResource):
            continue
        total = state.players[action.target_player_index].resources.total()
        if total > best_total:
            best_total = total
            best_action = action
    return best_action


def _build_discard(
    state: game_state.GameState,
    player_index: int,
) -> actions.DiscardResources:
    """Build a DiscardResources action that discards the most-abundant cards."""
    res = state.players[player_index].resources
    total = res.total()
    must_discard = total - total // 2

    # Build a sorted list: most-abundant resources first.
    amounts: list[tuple[int, str]] = [
        (res.wood, 'wood'),
        (res.brick, 'brick'),
        (res.wheat, 'wheat'),
        (res.sheep, 'sheep'),
        (res.ore, 'ore'),
    ]
    amounts.sort(reverse=True)

    to_discard: dict[str, int] = {}
    remaining = must_discard
    for count, name in amounts:
        if remaining <= 0:
            break
        give = min(count, remaining)
        if give > 0:
            to_discard[name] = give
            remaining -= give

    return actions.DiscardResources(player_index=player_index, resources=to_discard)


def _choose_main_action(
    state: game_state.GameState,
    player_index: int,
    legal: list[actions.Action],
) -> actions.Action:
    """Choose the highest-priority main-phase action.

    Priority: settlement > city > road > dev card > trades > end turn.
    Knights are played when score gap is small or when leading in knights.
    """
    # Handle knight play: play if VP gap ≤2 or already ahead in knights.
    my_vp = state.players[player_index].victory_points
    max_opp_vp = max(
        p.victory_points for p in state.players if p.player_index != player_index
    )
    my_knights = state.players[player_index].knights_played
    max_opp_knights = max(
        p.knights_played for p in state.players if p.player_index != player_index
    )
    should_play_knight = (abs(my_vp - max_opp_vp) <= 2) or (
        my_knights >= max_opp_knights
    )

    for priority_type in _BUILD_PRIORITY:
        for action in legal:
            if isinstance(action, priority_type):
                return action

    # Consider playing a knight.
    if should_play_knight:
        for action in legal:
            if isinstance(action, actions.PlayKnight):
                return action

    # Accept a trade that gets a needed resource (unlocks a build).
    for action in legal:
        if isinstance(action, (actions.TradeWithBank, actions.TradeWithPort)):
            if trade_unlocks_build(state, player_index, action):
                return action

    # Fall back to EndTurn.
    for action in legal:
        if isinstance(action, actions.EndTurn):
            return action

    return legal[0]


def trade_unlocks_build(
    state: game_state.GameState,
    player_index: int,
    trade: actions.TradeWithBank | actions.TradeWithPort,
) -> bool:
    """Return True if executing this trade gets us closer to a build action.

    Simulates a post-trade resource set and checks if any build cost is met.
    """
    res = state.players[player_index].resources
    giving_count = (
        trade.giving_count
        if isinstance(trade, actions.TradeWithPort)
        else _BANK_TRADE_RATIO
    )
    # Simulate the trade.
    new_giving = res.get(trade.giving) - giving_count
    if new_giving < 0:
        return False
    new_receiving = res.get(trade.receiving) + 1
    simulated: dict[str, int] = {
        'wood': res.wood,
        'brick': res.brick,
        'wheat': res.wheat,
        'sheep': res.sheep,
        'ore': res.ore,
    }
    simulated[trade.giving.value] = new_giving
    simulated[trade.receiving.value] = new_receiving

    inv = state.players[player_index].build_inventory
    build_costs: list[dict[str, int]] = []
    if inv.roads_remaining > 0:
        build_costs.append(player.ROAD_COST)
    if inv.settlements_remaining > 0:
        build_costs.append(player.SETTLEMENT_COST)
    if inv.cities_remaining > 0:
        build_costs.append(player.CITY_COST)
    build_costs.append(player.DEV_CARD_COST)

    sim_res = player.Resources(**simulated)
    return any(sim_res.can_afford(cost) for cost in build_costs)


class MediumAI(base.CatanAI):
    """Priority-based AI that follows a simple but sensible strategy."""

    def choose_action(
        self,
        state: game_state.GameState,
        player_index: int,
        legal_actions: list[actions.Action],
    ) -> actions.Action:
        """Choose an action using priority heuristics."""
        if not legal_actions:
            raise ValueError('No legal actions provided')

        pending = state.turn_state.pending_action

        # --- Setup phase ---
        if state.phase in (
            game_state.GamePhase.SETUP_FORWARD,
            game_state.GamePhase.SETUP_BACKWARD,
        ):
            if pending == game_state.PendingActionType.PLACE_SETTLEMENT:
                return _best_setup_settlement(state, player_index, legal_actions)
            if pending == game_state.PendingActionType.PLACE_ROAD:
                return _best_setup_road(state, player_index, legal_actions)

        # --- Forced actions ---
        if pending == game_state.PendingActionType.MOVE_ROBBER:
            return _best_move_robber(state, player_index, legal_actions)

        if pending == game_state.PendingActionType.STEAL_RESOURCE:
            return _best_steal(state, legal_actions)

        if pending == game_state.PendingActionType.DISCARD_RESOURCES:
            return _build_discard(state, player_index)

        # --- Roll dice ---
        for action in legal_actions:
            if isinstance(action, actions.RollDice):
                return action

        # --- Main build/trade phase ---
        return _choose_main_action(state, player_index, legal_actions)

    def respond_to_trade(
        self,
        state: game_state.GameState,
        player_index: int,
        pending_trade: trade_module.PendingTrade,
    ) -> actions.AcceptTrade | actions.RejectTrade:
        """Accept a trade if the AI has the requested resources and it is beneficial.

        Accepts when the AI holds all requested resources and the resources
        received would help unlock a build action (road, settlement, city, or
        dev card).  Rejects otherwise.
        """
        p = state.players[player_index]
        # Must have all the resources being requested from us.
        if not p.resources.can_afford(pending_trade.requesting):
            return actions.RejectTrade(
                player_index=player_index, trade_id=pending_trade.trade_id
            )

        # Simulate receiving what the offering player gives us.
        simulated: dict[str, int] = {
            'wood': p.resources.wood,
            'brick': p.resources.brick,
            'wheat': p.resources.wheat,
            'sheep': p.resources.sheep,
            'ore': p.resources.ore,
        }
        for res_name, amount in pending_trade.requesting.items():
            simulated[res_name] -= amount
        for res_name, amount in pending_trade.offering.items():
            simulated[res_name] += amount

        inv = p.build_inventory
        build_costs: list[dict[str, int]] = []
        if inv.roads_remaining > 0:
            build_costs.append(player.ROAD_COST)
        if inv.settlements_remaining > 0:
            build_costs.append(player.SETTLEMENT_COST)
        if inv.cities_remaining > 0:
            build_costs.append(player.CITY_COST)
        build_costs.append(player.DEV_CARD_COST)

        sim_res = player.Resources(**simulated)
        if any(sim_res.can_afford(cost) for cost in build_costs):
            return actions.AcceptTrade(
                player_index=player_index, trade_id=pending_trade.trade_id
            )
        return actions.RejectTrade(
            player_index=player_index, trade_id=pending_trade.trade_id
        )
