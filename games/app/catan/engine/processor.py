"""Action processor: applies validated actions to produce new game states."""

from __future__ import annotations

import collections
import copy
import random

from ..models.actions import (
    Action,
    ActionResult,
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
from ..models.board import (
    TILE_RESOURCE,
    Board,
    Building,
    BuildingType,
    ResourceType,
    Road,
    TileType,
)
from ..models.game_state import GamePhase, GameState, PendingActionType, TurnState
from ..models.player import DevCardHand, DevCardType, Resources
from .rules import get_legal_actions
from .turn_manager import get_next_setup_player_index


def apply_action(game_state: GameState, action: Action) -> ActionResult:
    """Apply an action to game_state and return the result.

    Returns a new GameState on success; the original is not mutated.
    """
    # Validate legality
    legal = get_legal_actions(game_state, action.player_index)
    if not _is_action_in_legal_list(action, legal):
        return ActionResult(
            success=False,
            error_message=f'Action {action.action_type} is not legal',
        )

    state = copy.deepcopy(game_state)

    try:
        state = _dispatch(state, action)
    except (ValueError, KeyError, IndexError, AttributeError) as exc:
        return ActionResult(success=False, error_message=str(exc))

    return ActionResult(success=True, updated_state=state)


# ---------------------------------------------------------------------------
# Legality check helper
# ---------------------------------------------------------------------------


def _is_action_in_legal_list(action: Action, legal: list[Action]) -> bool:
    """Check if the action matches any entry in the legal list."""
    action_data = action.model_dump()
    for la in legal:
        if la.model_dump() == action_data:
            return True
    return False


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def _dispatch(state: GameState, action: Action) -> GameState:
    """Route to the appropriate handler and return the updated state."""
    match action:
        case PlaceSettlement():
            return _apply_place_settlement(state, action)
        case PlaceRoad():
            return _apply_place_road(state, action)
        case PlaceCity():
            return _apply_place_city(state, action)
        case RollDice():
            return _apply_roll_dice(state, action)
        case BuildDevCard():
            return _apply_build_dev_card(state, action)
        case PlayKnight():
            return _apply_play_knight(state, action)
        case PlayRoadBuilding():
            return _apply_play_road_building(state, action)
        case PlayYearOfPlenty():
            return _apply_play_year_of_plenty(state, action)
        case PlayMonopoly():
            return _apply_play_monopoly(state, action)
        case MoveRobber():
            return _apply_move_robber(state, action)
        case StealResource():
            return _apply_steal_resource(state, action)
        case DiscardResources():
            return _apply_discard_resources(state, action)
        case EndTurn():
            return _apply_end_turn(state, action)
        case TradeWithBank():
            return _apply_trade_with_bank(state, action)
        case TradeWithPort():
            return _apply_trade_with_port(state, action)
        case _:
            raise ValueError(f'Unhandled action type: {action.action_type}')


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------


def _apply_place_settlement(state: GameState, action: PlaceSettlement) -> GameState:
    pi = action.player_index
    vid = action.vertex_id
    player = state.players[pi]
    vertex = state.board.vertices[vid]

    # Charge resources only in main phase
    if state.phase == GamePhase.MAIN:
        player.resources = player.resources.subtract(
            {'wood': 1, 'brick': 1, 'wheat': 1, 'sheep': 1}
        )

    # Place building
    vertex.building = Building(player_index=pi, building_type=BuildingType.SETTLEMENT)
    player.build_inventory.settlements_remaining -= 1
    player.victory_points += 1

    # Collect port if present
    if vertex.port_type is not None and vertex.port_type not in player.ports_owned:
        player.ports_owned.append(vertex.port_type)

    # Advance turn state
    if state.phase in (GamePhase.SETUP_FORWARD, GamePhase.SETUP_BACKWARD):
        # In SETUP_BACKWARD, collect resources from adjacent tiles
        if state.phase == GamePhase.SETUP_BACKWARD:
            for tile_idx in vertex.adjacent_tile_indices:
                tile = state.board.tiles[tile_idx]
                if (
                    tile.tile_type != TileType.DESERT
                    and tile.tile_type in TILE_RESOURCE
                ):
                    resource = TILE_RESOURCE[tile.tile_type]
                    player.resources = player.resources.add(
                        Resources(**{resource.value: 1})
                    )
        state.turn_state.pending_action = PendingActionType.PLACE_ROAD
    # In MAIN phase, stay in BUILD_OR_TRADE (already there)

    return _check_win(state, pi)


def _apply_place_road(state: GameState, action: PlaceRoad) -> GameState:
    pi = action.player_index
    eid = action.edge_id
    player = state.players[pi]
    edge = state.board.edges[eid]

    is_setup = state.phase in (GamePhase.SETUP_FORWARD, GamePhase.SETUP_BACKWARD)
    is_free = state.turn_state.free_roads_remaining > 0

    # Charge resources if in main phase and not a free road
    if state.phase == GamePhase.MAIN and not is_free:
        player.resources = player.resources.subtract({'wood': 1, 'brick': 1})

    # Place road
    edge.road = Road(player_index=pi)
    player.build_inventory.roads_remaining -= 1

    # Decrement free road counter
    if is_free:
        state.turn_state.free_roads_remaining -= 1

    # Recalculate longest road
    state = _update_longest_road(state, pi)

    # Advance turn state
    if is_setup:
        # Advance to next setup player
        next_idx, next_phase = get_next_setup_player_index(
            pi, len(state.players), state.phase
        )
        state.phase = next_phase
        if next_phase == GamePhase.MAIN:
            state.turn_state = TurnState(
                player_index=0,
                pending_action=PendingActionType.ROLL_DICE,
            )
        else:
            state.turn_state = TurnState(
                player_index=next_idx,
                pending_action=PendingActionType.PLACE_SETTLEMENT,
            )
        state.turn_number += 1
    elif is_free and state.turn_state.free_roads_remaining == 0:
        state.turn_state.pending_action = PendingActionType.BUILD_OR_TRADE

    return _check_win(state, pi)


def _apply_place_city(state: GameState, action: PlaceCity) -> GameState:
    pi = action.player_index
    vid = action.vertex_id
    player = state.players[pi]
    vertex = state.board.vertices[vid]

    player.resources = player.resources.subtract({'wheat': 2, 'ore': 3})
    vertex.building = Building(player_index=pi, building_type=BuildingType.CITY)
    player.build_inventory.cities_remaining -= 1
    player.build_inventory.settlements_remaining += 1  # city replaces settlement
    player.victory_points += 1  # settlement was 1, city is 2, net +1

    return _check_win(state, pi)


def _apply_roll_dice(state: GameState, action: RollDice) -> GameState:
    rng = random.Random()
    roll = rng.randint(1, 6) + rng.randint(1, 6)
    state.dice_roll_history.append(roll)
    state.turn_state.roll_value = roll
    state.turn_state.has_rolled = True

    if roll == 7:
        # Determine who must discard
        must_discard = [
            i for i, p in enumerate(state.players) if p.resources.total() > 7
        ]
        state.turn_state.discard_player_indices = must_discard
        if must_discard:
            state.turn_state.pending_action = PendingActionType.DISCARD_RESOURCES
        else:
            state.turn_state.pending_action = PendingActionType.MOVE_ROBBER
    else:
        _distribute_resources(state, roll)
        state.turn_state.pending_action = PendingActionType.BUILD_OR_TRADE

    return state


def _distribute_resources(state: GameState, roll: int) -> None:
    """Give resources to players based on dice roll (mutates state)."""
    board = state.board
    for tile_idx, tile in enumerate(board.tiles):
        if tile.number_token != roll:
            continue
        if tile_idx == board.robber_tile_index:
            continue
        if tile.tile_type not in TILE_RESOURCE:
            continue
        resource = TILE_RESOURCE[tile.tile_type]
        for vertex in board.vertices:
            if tile_idx not in vertex.adjacent_tile_indices:
                continue
            if vertex.building is None:
                continue
            bldg = vertex.building
            amount = 2 if bldg.building_type == BuildingType.CITY else 1
            p = state.players[bldg.player_index]
            p.resources = p.resources.add(Resources(**{resource.value: amount}))


def _apply_build_dev_card(state: GameState, action: BuildDevCard) -> GameState:
    pi = action.player_index
    player = state.players[pi]
    player.resources = player.resources.subtract({'wheat': 1, 'sheep': 1, 'ore': 1})
    card = state.dev_card_deck.pop(0)
    player.new_dev_cards = player.new_dev_cards.add(card)
    if card == DevCardType.VICTORY_POINT:
        player.victory_points += 1
    return _check_win(state, pi)


def _apply_play_knight(state: GameState, action: PlayKnight) -> GameState:
    pi = action.player_index
    player = state.players[pi]
    player.dev_cards = player.dev_cards.remove(DevCardType.KNIGHT)
    player.knights_played += 1
    state = _update_largest_army(state, pi)
    state.turn_state.pending_action = PendingActionType.MOVE_ROBBER
    return _check_win(state, pi)


def _apply_play_road_building(state: GameState, action: PlayRoadBuilding) -> GameState:
    pi = action.player_index
    player = state.players[pi]
    player.dev_cards = player.dev_cards.remove(DevCardType.ROAD_BUILDING)
    state.turn_state.free_roads_remaining = 2
    state.turn_state.pending_action = PendingActionType.PLACE_ROAD
    return state


def _apply_play_year_of_plenty(state: GameState, action: PlayYearOfPlenty) -> GameState:
    pi = action.player_index
    player = state.players[pi]
    player.dev_cards = player.dev_cards.remove(DevCardType.YEAR_OF_PLENTY)
    player.resources = player.resources.add(
        Resources(**{action.resource1.value: 1, action.resource2.value: 1})
    )
    return state


def _apply_play_monopoly(state: GameState, action: PlayMonopoly) -> GameState:
    pi = action.player_index
    player = state.players[pi]
    player.dev_cards = player.dev_cards.remove(DevCardType.MONOPOLY)
    resource = action.resource
    for i, other in enumerate(state.players):
        if i == pi:
            continue
        stolen = other.resources.get(resource)
        if stolen > 0:
            other.resources = other.resources.with_resource(resource, 0)
            player.resources = player.resources.add(
                Resources(**{resource.value: stolen})
            )
    return state


def _apply_move_robber(state: GameState, action: MoveRobber) -> GameState:
    pi = action.player_index
    state.board.robber_tile_index = action.tile_index
    # Check for eligible steal targets
    robber_idx = action.tile_index
    adjacent_verts = [
        v for v in state.board.vertices if robber_idx in v.adjacent_tile_indices
    ]
    eligible: set[int] = set()
    for v in adjacent_verts:
        if v.building is not None and v.building.player_index != pi:
            eligible.add(v.building.player_index)
    if eligible:
        state.turn_state.pending_action = PendingActionType.STEAL_RESOURCE
    elif state.turn_state.has_rolled:
        state.turn_state.pending_action = PendingActionType.BUILD_OR_TRADE
    else:
        state.turn_state.pending_action = PendingActionType.ROLL_DICE
    return state


def _apply_steal_resource(state: GameState, action: StealResource) -> GameState:
    pi = action.player_index
    target = state.players[action.target_player_index]
    total = target.resources.total()
    if total > 0:
        available: list[ResourceType] = []
        for rt in ResourceType:
            available.extend([rt] * target.resources.get(rt))
        stolen = random.choice(available)
        target.resources = target.resources.with_resource(
            stolen, target.resources.get(stolen) - 1
        )
        state.players[pi].resources = state.players[pi].resources.add(
            Resources(**{stolen.value: 1})
        )
    if state.turn_state.has_rolled:
        state.turn_state.pending_action = PendingActionType.BUILD_OR_TRADE
    else:
        state.turn_state.pending_action = PendingActionType.ROLL_DICE
    return state


def _apply_discard_resources(state: GameState, action: DiscardResources) -> GameState:
    pi = action.player_index
    player = state.players[pi]
    cost = {k: v for k, v in action.resources.items() if v > 0}
    player.resources = player.resources.subtract(cost)
    state.turn_state.discard_player_indices = [
        x for x in state.turn_state.discard_player_indices if x != pi
    ]
    if not state.turn_state.discard_player_indices:
        state.turn_state.pending_action = PendingActionType.MOVE_ROBBER
    return state


def _apply_end_turn(state: GameState, action: EndTurn) -> GameState:
    pi = action.player_index
    player = state.players[pi]
    # Merge new_dev_cards into dev_cards
    player.dev_cards = _dev_card_hand_add_all(player.dev_cards, player.new_dev_cards)
    player.new_dev_cards = DevCardHand()

    state.turn_number += 1
    next_pi = (pi + 1) % len(state.players)
    state.turn_state = TurnState(
        player_index=next_pi,
        pending_action=PendingActionType.ROLL_DICE,
    )
    return _check_win(state, pi)


def _apply_trade_with_bank(state: GameState, action: TradeWithBank) -> GameState:
    pi = action.player_index
    player = state.players[pi]
    player.resources = player.resources.subtract({action.giving.value: 4})
    player.resources = player.resources.add(Resources(**{action.receiving.value: 1}))
    return state


def _apply_trade_with_port(state: GameState, action: TradeWithPort) -> GameState:
    pi = action.player_index
    player = state.players[pi]
    player.resources = player.resources.subtract(
        {action.giving.value: action.giving_count}
    )
    player.resources = player.resources.add(Resources(**{action.receiving.value: 1}))
    return state


# ---------------------------------------------------------------------------
# Longest road
# ---------------------------------------------------------------------------


def _calculate_longest_road(board: Board, player_index: int) -> int:
    """DFS to find the longest road length for a player."""
    adj: dict[int, list[tuple[int, int]]] = collections.defaultdict(list)
    for e in board.edges:
        if e.road is None or e.road.player_index != player_index:
            continue
        v0, v1 = e.vertex_ids
        adj[v0].append((e.edge_id, v1))
        adj[v1].append((e.edge_id, v0))
    if not adj:
        return 0

    def dfs(v: int, used: set[int]) -> int:
        best = len(used)
        for eid, nv in adj[v]:
            if eid in used:
                continue
            nvert = board.vertices[nv]
            if (
                nvert.building is not None
                and nvert.building.player_index != player_index
            ):
                continue
            used.add(eid)
            result = dfs(nv, used)
            best = max(best, result)
            used.discard(eid)
        return best

    return max(dfs(v, set()) for v in adj)


def _update_longest_road(state: GameState, player_index: int) -> GameState:
    """Recalculate longest road and update award if needed."""
    player = state.players[player_index]
    length = _calculate_longest_road(state.board, player_index)
    player.longest_road_length = length

    current_holder = state.longest_road_owner
    if length >= 5:
        if current_holder is None:
            state.longest_road_owner = player_index
            player.victory_points += 2
        elif current_holder != player_index:
            holder_length = state.players[current_holder].longest_road_length
            if length > holder_length:
                state.players[current_holder].victory_points -= 2
                state.longest_road_owner = player_index
                player.victory_points += 2
    return state


# ---------------------------------------------------------------------------
# Largest army
# ---------------------------------------------------------------------------


def _update_largest_army(state: GameState, player_index: int) -> GameState:
    """Check and update Largest Army award."""
    player = state.players[player_index]
    current_holder = state.largest_army_owner
    knights = player.knights_played
    if knights >= 3:
        if current_holder is None:
            state.largest_army_owner = player_index
            player.victory_points += 2
        elif current_holder != player_index:
            if knights > state.players[current_holder].knights_played:
                state.players[current_holder].victory_points -= 2
                state.largest_army_owner = player_index
                player.victory_points += 2
    return state


# ---------------------------------------------------------------------------
# Win condition
# ---------------------------------------------------------------------------


def _check_win(state: GameState, player_index: int) -> GameState:
    """Set phase to ENDED if active player has ≥10 VP."""
    if state.players[player_index].victory_points >= 10:
        state.phase = GamePhase.ENDED
        state.winner_index = player_index
    return state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dev_card_hand_add_all(hand: DevCardHand, new_hand: DevCardHand) -> DevCardHand:
    """Merge new_hand into hand."""
    result = hand
    for card_type in DevCardType:
        count = new_hand.get(card_type)
        if count > 0:
            result = result.add(card_type, count)
    return result
