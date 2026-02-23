"""Hard (strategic) AI for Catan.

Applies more sophisticated heuristics:

- **Setup phase**: maximises expected resource income (pip score) while
  favouring resource diversity and port access.
- **Main phase**: builds settlements on high-VP spots, chases longest road
  or largest army depending on board position.
- **MoveRobber**: targets the leader (highest VP) while never self-robbing.
- **StealResource**: steals from the leader.
- **PlayKnight**: plays when robber is on own tile or to claim Largest Army.
- **Trading**: uses ports strategically; only trades that unlock a build.
- **Road placement**: extends toward high-value vertices or longest road.
"""

from __future__ import annotations

from ..engine import rules
from ..models import actions, board, game_state, player
from . import base

# Pip probability count per number token.
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


# ---------------------------------------------------------------------------
# Shared scoring helpers
# ---------------------------------------------------------------------------


def _vertex_pip_score(state: game_state.GameState, vertex: board.Vertex) -> int:
    """Return the sum of pip counts for tiles adjacent to vertex."""
    score = 0
    for tile_idx in vertex.adjacent_tile_indices:
        tile = state.board.tiles[tile_idx]
        if tile.number_token is not None:
            score += _PIP_COUNT.get(tile.number_token, 0)
    return score


def _vertex_resource_set(
    state: game_state.GameState, vertex: board.Vertex
) -> set[board.ResourceType]:
    """Return the set of resource types produced by tiles adjacent to vertex."""
    resources: set[board.ResourceType] = set()
    for tile_idx in vertex.adjacent_tile_indices:
        tile = state.board.tiles[tile_idx]
        if tile.tile_type in board.TILE_RESOURCE:
            resources.add(board.TILE_RESOURCE[tile.tile_type])
    return resources


def _player_resource_set(
    state: game_state.GameState, player_index: int
) -> set[board.ResourceType]:
    """Return all resource types currently produced by player_index's buildings."""
    resources: set[board.ResourceType] = set()
    for vertex in state.board.vertices:
        if vertex.building and vertex.building.player_index == player_index:
            resources.update(_vertex_resource_set(state, vertex))
    return resources


def _player_total_vp(state: game_state.GameState, player_index: int) -> int:
    """Return a player's estimated total VP including bonuses and VP cards."""
    p = state.players[player_index]
    vp = p.victory_points
    vp += p.dev_cards.victory_point + p.new_dev_cards.victory_point
    if state.longest_road_owner == player_index:
        vp += 2
    if state.largest_army_owner == player_index:
        vp += 2
    return vp


def _robber_on_own_tile(state: game_state.GameState, player_index: int) -> bool:
    """Return True if the robber is currently on a tile where player has a building."""
    robber_idx = state.board.robber_tile_index
    for vertex in state.board.vertices:
        if robber_idx not in vertex.adjacent_tile_indices:
            continue
        if vertex.building and vertex.building.player_index == player_index:
            return True
    return False


# ---------------------------------------------------------------------------
# Setup heuristics
# ---------------------------------------------------------------------------


def _score_setup_vertex(
    state: game_state.GameState,
    player_index: int,
    vertex: board.Vertex,
) -> tuple[int, int, int]:
    """Return (pip_score, diversity_bonus, port_bonus) for a setup vertex.

    - pip_score: total expected production.
    - diversity_bonus: new resource types added.
    - port_bonus: 1 if vertex has a port, else 0.
    """
    pip = _vertex_pip_score(state, vertex)
    owned = _player_resource_set(state, player_index)
    new_res = _vertex_resource_set(state, vertex) - owned
    diversity = len(new_res)
    port_bonus = 1 if vertex.port_type is not None else 0
    return (pip, diversity, port_bonus)


def _best_setup_settlement(
    state: game_state.GameState,
    player_index: int,
    legal: list[actions.Action],
) -> actions.Action:
    """Pick the setup settlement with the best (pip, diversity, port) score."""
    best_action = legal[0]
    best_score: tuple[int, int, int] = (-1, -1, -1)
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
    """Pick the road that leads toward the best unoccupied vertex."""
    best_action = legal[0]
    best_score: tuple[int, int, int] = (-1, -1, -1)
    for action in legal:
        if not isinstance(action, actions.PlaceRoad):
            continue
        edge = state.board.edges[action.edge_id]
        for vid in edge.vertex_ids:
            vertex = state.board.vertices[vid]
            if vertex.building is None:
                score = _score_setup_vertex(state, player_index, vertex)
                if score > best_score:
                    best_score = score
                    best_action = action
    return best_action


# ---------------------------------------------------------------------------
# Robber / steal helpers
# ---------------------------------------------------------------------------


def _best_move_robber(
    state: game_state.GameState,
    player_index: int,
    legal: list[actions.Action],
) -> actions.Action:
    """Place robber on the leader's tile, avoiding own tile."""
    # Find the leading opponent by VP.
    leader_idx: int | None = None
    leader_vp = -1
    for p in state.players:
        if p.player_index == player_index:
            continue
        vp = _player_total_vp(state, p.player_index)
        if vp > leader_vp:
            leader_vp = vp
            leader_idx = p.player_index

    best_action = legal[0]
    best_score = -1
    for action in legal:
        if not isinstance(action, actions.MoveRobber):
            continue
        tile_idx = action.tile_index
        score = 0
        for vertex in state.board.vertices:
            if tile_idx not in vertex.adjacent_tile_indices:
                continue
            if vertex.building is None:
                continue
            if vertex.building.player_index == player_index:
                # Penalise self-robbing.
                score -= 5
            elif vertex.building.player_index == leader_idx:
                score += 3
            else:
                score += 1
        if score > best_score:
            best_score = score
            best_action = action
    return best_action


def _best_steal(
    state: game_state.GameState,
    player_index: int,
    legal: list[actions.Action],
) -> actions.Action:
    """Steal from the player with the highest VP (leader)."""
    best_action = legal[0]
    best_score = (-1, -1)  # (vp, resources)
    for action in legal:
        if not isinstance(action, actions.StealResource):
            continue
        target = action.target_player_index
        vp = _player_total_vp(state, target)
        res = state.players[target].resources.total()
        score = (vp, res)
        if score > best_score:
            best_score = score
            best_action = action
    return best_action


# ---------------------------------------------------------------------------
# Discard helper
# ---------------------------------------------------------------------------


def _build_discard(
    state: game_state.GameState,
    player_index: int,
) -> actions.DiscardResources:
    """Discard excess resources, keeping the most strategically valuable ones.

    Keeps ore/wheat (for cities and dev cards) and wood/brick (for roads and
    settlements) in roughly equal measure. Discards over-stocked resources.
    """
    res = state.players[player_index].resources
    total = res.total()
    must_discard = total - total // 2

    # Discard excess starting from least-useful surplus.
    amounts: list[tuple[int, str]] = sorted(
        [
            (res.wood, 'wood'),
            (res.brick, 'brick'),
            (res.wheat, 'wheat'),
            (res.sheep, 'sheep'),
            (res.ore, 'ore'),
        ],
        reverse=True,
    )

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


# ---------------------------------------------------------------------------
# Knight / dev card helpers
# ---------------------------------------------------------------------------


def _should_play_knight(state: game_state.GameState, player_index: int) -> bool:
    """Return True if playing a Knight is strategically advisable.

    Plays knight if:
    - Robber is on own tile (defensive move), OR
    - Playing would give/retain Largest Army bonus.
    """
    if _robber_on_own_tile(state, player_index):
        return True
    my_knights = state.players[player_index].knights_played + 1  # after playing
    current_holder = state.largest_army_owner
    if current_holder is None:
        # Claim it if we'd reach threshold (≥3).
        return my_knights >= 3
    if current_holder == player_index:
        return True
    # Steal it.
    holder_knights = state.players[current_holder].knights_played
    return my_knights > holder_knights


# ---------------------------------------------------------------------------
# Road placement helpers
# ---------------------------------------------------------------------------


def _road_score(state: game_state.GameState, player_index: int, edge_id: int) -> int:
    """Score a road edge: reward proximity to high-value empty vertices."""
    edge = state.board.edges[edge_id]
    score = 0
    for vid in edge.vertex_ids:
        vertex = state.board.vertices[vid]
        if vertex.building is None:
            pip = _vertex_pip_score(state, vertex)
            score = max(score, pip)
    return score


# ---------------------------------------------------------------------------
# Main-phase build/trade logic
# ---------------------------------------------------------------------------


def _best_settlement(
    state: game_state.GameState,
    player_index: int,
    legal: list[actions.Action],
) -> actions.Action | None:
    """Return the PlaceSettlement action with the best pip+diversity score."""
    best: actions.Action | None = None
    best_score: tuple[int, int] = (-1, -1)
    for action in legal:
        if not isinstance(action, actions.PlaceSettlement):
            continue
        vertex = state.board.vertices[action.vertex_id]
        pip = _vertex_pip_score(state, vertex)
        owned = _player_resource_set(state, player_index)
        new_res = len(_vertex_resource_set(state, vertex) - owned)
        score = (pip, new_res)
        if score > best_score:
            best_score = score
            best = action
    return best


def _best_road(
    state: game_state.GameState,
    player_index: int,
    legal: list[actions.Action],
) -> actions.Action | None:
    """Return the PlaceRoad action with the best road score."""
    best: actions.Action | None = None
    best_score = -1
    for action in legal:
        if not isinstance(action, actions.PlaceRoad):
            continue
        score = _road_score(state, player_index, action.edge_id)
        if score > best_score:
            best_score = score
            best = action
    return best


def _trade_unlocks_build(
    state: game_state.GameState,
    player_index: int,
    trade: actions.TradeWithBank | actions.TradeWithPort,
) -> bool:
    """Return True if this trade enables a build action post-trade."""
    res = state.players[player_index].resources
    giving_count = trade.giving_count if isinstance(trade, actions.TradeWithPort) else 4
    simulated: dict[str, int] = {
        'wood': res.wood,
        'brick': res.brick,
        'wheat': res.wheat,
        'sheep': res.sheep,
        'ore': res.ore,
    }
    simulated[trade.giving.value] -= giving_count
    if simulated[trade.giving.value] < 0:
        return False
    simulated[trade.receiving.value] += 1

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


def _choose_main_action(
    state: game_state.GameState,
    player_index: int,
    legal: list[actions.Action],
) -> actions.Action:
    """Choose the best main-phase action using strategic heuristics.

    Priority:
    1. Play Knight (if strategically advisable)
    2. Best settlement (if available)
    3. Best city (if available)
    4. Build dev card (if available and targeting largest army)
    5. Best road (chase longest road or path to settlement)
    6. Trades that unlock a build
    7. Year of Plenty / Monopoly
    8. Road Building card
    9. EndTurn
    """
    my_p = state.players[player_index]
    my_vp = _player_total_vp(state, player_index)
    max_opp_vp = max(
        _player_total_vp(state, p.player_index)
        for p in state.players
        if p.player_index != player_index
    )

    # 1. Play Knight strategically.
    if my_p.dev_cards.knight > 0 and _should_play_knight(state, player_index):
        for action in legal:
            if isinstance(action, actions.PlayKnight):
                return action

    # 2. Best settlement.
    settlement = _best_settlement(state, player_index, legal)
    if settlement is not None:
        return settlement

    # 3. Best city.
    for action in legal:
        if isinstance(action, actions.PlaceCity):
            return action

    # 4. Dev card when chasing Largest Army.
    if my_p.dev_cards.knight + my_p.new_dev_cards.knight < 3:
        for action in legal:
            if isinstance(action, actions.BuildDevCard):
                return action

    # 5. Best road (if ahead on road count or chasing longest road).
    road = _best_road(state, player_index, legal)
    if road is not None:
        my_road_len = rules.calculate_longest_road(state.board, player_index)
        opp_road_len = max(
            rules.calculate_longest_road(state.board, p.player_index)
            for p in state.players
            if p.player_index != player_index
        )
        if my_road_len >= opp_road_len or my_vp < max_opp_vp:
            return road

    # 6. Beneficial trades.
    for action in legal:
        if isinstance(action, (actions.TradeWithBank, actions.TradeWithPort)):
            if _trade_unlocks_build(state, player_index, action):
                return action

    # 7. Year of Plenty: grab ore+wheat for a city.
    for action in legal:
        if isinstance(action, actions.PlayYearOfPlenty):
            if (
                action.resource1 == board.ResourceType.ORE
                and action.resource2 == board.ResourceType.WHEAT
            ):
                return action

    # 8. Monopoly: target the resource we need most.
    for action in legal:
        if isinstance(action, actions.PlayMonopoly):
            return action

    # 9. Road Building.
    for action in legal:
        if isinstance(action, actions.PlayRoadBuilding):
            return action

    # 10. Road even if not chasing.
    if road is not None:
        return road

    # 11. EndTurn.
    for action in legal:
        if isinstance(action, actions.EndTurn):
            return action

    return legal[0]


class HardAI(base.CatanAI):
    """Strategic AI that uses advanced heuristics for each decision."""

    def choose_action(
        self,
        state: game_state.GameState,
        player_index: int,
        legal_actions: list[actions.Action],
    ) -> actions.Action:
        """Choose a strategically sound action from legal_actions."""
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
            return _best_steal(state, player_index, legal_actions)

        if pending == game_state.PendingActionType.DISCARD_RESOURCES:
            return _build_discard(state, player_index)

        # --- Roll dice ---
        for action in legal_actions:
            if isinstance(action, actions.RollDice):
                return action

        # --- Main build/trade phase ---
        return _choose_main_action(state, player_index, legal_actions)
