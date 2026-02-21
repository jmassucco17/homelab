"""Catan action processor.

Applies a single game action to a GameState and returns the result.
This is a pure function: the original state is never modified.
"""

from __future__ import annotations

import random

from games.app.catan.models.actions import (
    AcceptTrade,
    ActionResult,
    BuildDevCard,
    CancelTrade,
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
    RejectTrade,
    RollDice,
    StealResource,
    TradeWithBank,
    TradeWithPort,
)
from games.app.catan.models.board import (
    TILE_RESOURCE,
    Building,
    BuildingType,
    Road,
    TileType,
)
from games.app.catan.models.game_state import GamePhase, GameState, PendingActionType
from games.app.catan.models.player import (
    CITY_COST,
    DEV_CARD_COST,
    ROAD_COST,
    DevCardType,
    Resources,
)

# Type alias matching models.actions.Action.
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
    | AcceptTrade
    | RejectTrade
    | CancelTrade
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_action(game_state: GameState, action: Action) -> ActionResult:
    """Apply *action* to *game_state* and return an :class:`ActionResult`.

    The original state is never modified; a deep copy is made first.
    On failure an :class:`ActionResult` with ``success=False`` is returned.
    """
    state = game_state.model_copy(deep=True)

    try:
        _dispatch(state, action)
    except ValueError as exc:
        return ActionResult(success=False, error_message=str(exc))

    # Check for a winner after every action.
    from games.app.catan.engine.rules import check_victory_condition

    if state.phase != GamePhase.ENDED:
        winner = check_victory_condition(state)
        if winner is not None:
            state.phase = GamePhase.ENDED
            state.winner_index = winner

    return ActionResult(success=True, updated_state=state)


# ---------------------------------------------------------------------------
# Internal dispatch
# ---------------------------------------------------------------------------


def _dispatch(state: GameState, action: Action) -> None:
    """Mutate *state* in place according to *action* type."""
    if isinstance(action, PlaceSettlement):
        _apply_place_settlement(state, action)
    elif isinstance(action, PlaceRoad):
        _apply_place_road(state, action)
    elif isinstance(action, PlaceCity):
        _apply_place_city(state, action)
    elif isinstance(action, RollDice):
        _apply_roll_dice(state, action)
    elif isinstance(action, BuildDevCard):
        _apply_build_dev_card(state, action)
    elif isinstance(action, PlayKnight):
        _apply_play_knight(state, action)
    elif isinstance(action, PlayRoadBuilding):
        _apply_play_road_building(state, action)
    elif isinstance(action, PlayYearOfPlenty):
        _apply_play_year_of_plenty(state, action)
    elif isinstance(action, PlayMonopoly):
        _apply_play_monopoly(state, action)
    elif isinstance(action, TradeWithBank):
        _apply_trade_with_bank(state, action)
    elif isinstance(action, TradeWithPort):
        _apply_trade_with_port(state, action)
    elif isinstance(action, EndTurn):
        _apply_end_turn(state, action)
    elif isinstance(action, MoveRobber):
        _apply_move_robber(state, action)
    elif isinstance(action, StealResource):
        _apply_steal_resource(state, action)
    elif isinstance(action, DiscardResources):
        _apply_discard_resources(state, action)
    else:
        # AcceptTrade, RejectTrade, CancelTrade – just clear the active trade.
        state.turn_state.active_trade_id = None


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------


def _apply_place_settlement(state: GameState, action: PlaceSettlement) -> None:
    vertex = state.board.vertices[action.vertex_id]
    if vertex.building is not None:
        raise ValueError(f'Vertex {action.vertex_id} is already occupied.')
    for adj_id in vertex.adjacent_vertex_ids:
        if state.board.vertices[adj_id].building is not None:
            raise ValueError('Settlement violates the distance rule.')

    vertex.building = Building(
        player_index=action.player_index,
        building_type=BuildingType.SETTLEMENT,
    )

    player = state.players[action.player_index]
    player.build_inventory.settlements_remaining -= 1
    player.victory_points += 1

    # Award any port accessible from this vertex.
    for port in state.board.ports:
        if (
            action.vertex_id in port.vertex_ids
            and port.port_type not in player.ports_owned
        ):
            player.ports_owned.append(port.port_type)

    # During setup, next action is to place a road.
    if state.phase in (GamePhase.SETUP_FORWARD, GamePhase.SETUP_BACKWARD):
        state.turn_state.pending_action = PendingActionType.PLACE_ROAD


def _apply_place_road(state: GameState, action: PlaceRoad) -> None:
    from games.app.catan.engine.rules import can_place_road_at_edge
    from games.app.catan.engine.turn_manager import advance_turn

    edge = state.board.edges[action.edge_id]
    if edge.road is not None:
        raise ValueError(f'Edge {action.edge_id} already has a road.')

    player = state.players[action.player_index]
    if player.build_inventory.roads_remaining < 1:
        raise ValueError('No roads remaining.')

    # During setup, any edge adjacent to own settlement is valid.
    if state.phase in (GamePhase.SETUP_FORWARD, GamePhase.SETUP_BACKWARD):
        _validate_setup_road(state, action)
    else:
        if not can_place_road_at_edge(state.board, action.player_index, action.edge_id):
            raise ValueError(f'Edge {action.edge_id} is not reachable by this player.')

        # Free road from Road Building card takes priority over paying cost.
        if state.turn_state.free_roads_remaining > 0:
            state.turn_state.free_roads_remaining -= 1
        else:
            if not player.resources.can_afford(ROAD_COST):
                raise ValueError('Insufficient resources to build a road.')
            player.resources = player.resources.subtract(ROAD_COST)

    edge.road = Road(player_index=action.player_index)
    player.build_inventory.roads_remaining -= 1

    # Recalculate longest road.
    from games.app.catan.engine.rules import calculate_longest_road

    new_length = calculate_longest_road(state.board, action.player_index)
    player.longest_road_length = new_length
    _update_longest_road(state)

    # During setup, advance to the next turn segment.
    if state.phase in (GamePhase.SETUP_FORWARD, GamePhase.SETUP_BACKWARD):
        advance_turn(state)


def _validate_setup_road(state: GameState, action: PlaceRoad) -> None:
    """Validate that the road edge is adjacent to an own settlement (setup)."""
    edge = state.board.edges[action.edge_id]
    for vid in edge.vertex_ids:
        vertex = state.board.vertices[vid]
        if (
            vertex.building is not None
            and vertex.building.player_index == action.player_index
        ):
            return
    raise ValueError('Setup road must be adjacent to own settlement.')


def _apply_place_city(state: GameState, action: PlaceCity) -> None:
    vertex = state.board.vertices[action.vertex_id]
    if (
        vertex.building is None
        or vertex.building.player_index != action.player_index
        or vertex.building.building_type != BuildingType.SETTLEMENT
    ):
        raise ValueError(f'No own settlement at vertex {action.vertex_id}.')

    player = state.players[action.player_index]
    if player.build_inventory.cities_remaining < 1:
        raise ValueError('No cities remaining.')
    if not player.resources.can_afford(CITY_COST):
        raise ValueError('Insufficient resources to build a city.')

    vertex.building = Building(
        player_index=action.player_index,
        building_type=BuildingType.CITY,
    )
    player.resources = player.resources.subtract(CITY_COST)
    player.build_inventory.cities_remaining -= 1
    player.build_inventory.settlements_remaining += 1
    player.victory_points += 1  # was 1 for settlement, now 2 total


def _apply_roll_dice(state: GameState, action: RollDice) -> None:
    roll = random.randint(1, 6) + random.randint(1, 6)
    state.dice_roll_history.append(roll)
    state.turn_state.roll_value = roll
    state.turn_state.has_rolled = True

    if roll == 7:
        # Find players who must discard.
        must_discard = [
            p.player_index for p in state.players if p.resources.total() > 7
        ]
        if must_discard:
            state.turn_state.discard_player_indices = must_discard
            state.turn_state.pending_action = PendingActionType.DISCARD_RESOURCES
        else:
            state.turn_state.pending_action = PendingActionType.MOVE_ROBBER
    else:
        _distribute_resources(state, roll)
        state.turn_state.pending_action = PendingActionType.BUILD_OR_TRADE


def _distribute_resources(state: GameState, roll: int) -> None:
    """Award resources to all players with buildings on tiles matching *roll*."""
    for tile_idx, tile in enumerate(state.board.tiles):
        if tile.number_token != roll:
            continue
        if tile_idx == state.board.robber_tile_index:
            continue
        if tile.tile_type == TileType.DESERT:
            continue
        resource = TILE_RESOURCE.get(tile.tile_type)
        if resource is None:
            continue
        for vertex in state.board.vertices:
            if tile_idx not in vertex.adjacent_tile_indices:
                continue
            if vertex.building is None:
                continue
            amount = (
                1 if vertex.building.building_type == BuildingType.SETTLEMENT else 2
            )
            p = state.players[vertex.building.player_index]
            current = p.resources.get(resource)
            p.resources = p.resources.with_resource(resource, current + amount)


def _apply_build_dev_card(state: GameState, action: BuildDevCard) -> None:
    player = state.players[action.player_index]
    if not player.resources.can_afford(DEV_CARD_COST):
        raise ValueError('Insufficient resources to buy a dev card.')
    if not state.dev_card_deck:
        raise ValueError('No development cards remaining in the deck.')

    player.resources = player.resources.subtract(DEV_CARD_COST)
    card_type = DevCardType(state.dev_card_deck.pop())
    player.new_dev_cards = player.new_dev_cards.add(card_type)


def _apply_play_knight(state: GameState, action: PlayKnight) -> None:
    player = state.players[action.player_index]
    if player.dev_cards.knight < 1:
        raise ValueError('No Knight card in hand.')

    player.dev_cards = player.dev_cards.remove(DevCardType.KNIGHT)
    player.knights_played += 1

    # Check if largest army changes.
    from games.app.catan.engine.rules import get_largest_army_holder

    new_holder = get_largest_army_holder(state.players)
    _update_largest_army(state, new_holder)

    state.turn_state.pending_action = PendingActionType.MOVE_ROBBER


def _apply_play_road_building(state: GameState, action: PlayRoadBuilding) -> None:
    player = state.players[action.player_index]
    if player.dev_cards.road_building < 1:
        raise ValueError('No Road Building card in hand.')

    player.dev_cards = player.dev_cards.remove(DevCardType.ROAD_BUILDING)
    free = min(2, player.build_inventory.roads_remaining)
    state.turn_state.free_roads_remaining = free


def _apply_play_year_of_plenty(state: GameState, action: PlayYearOfPlenty) -> None:
    player = state.players[action.player_index]
    if player.dev_cards.year_of_plenty < 1:
        raise ValueError('No Year of Plenty card in hand.')

    player.dev_cards = player.dev_cards.remove(DevCardType.YEAR_OF_PLENTY)
    gained = Resources()
    gained = gained.with_resource(action.resource1, gained.get(action.resource1) + 1)
    gained = gained.with_resource(action.resource2, gained.get(action.resource2) + 1)
    player.resources = player.resources.add(gained)


def _apply_play_monopoly(state: GameState, action: PlayMonopoly) -> None:
    player = state.players[action.player_index]
    if player.dev_cards.monopoly < 1:
        raise ValueError('No Monopoly card in hand.')

    player.dev_cards = player.dev_cards.remove(DevCardType.MONOPOLY)
    total_stolen = 0
    for other in state.players:
        if other.player_index == action.player_index:
            continue
        amount = other.resources.get(action.resource)
        if amount > 0:
            other.resources = other.resources.with_resource(action.resource, 0)
            total_stolen += amount
    current = player.resources.get(action.resource)
    player.resources = player.resources.with_resource(
        action.resource, current + total_stolen
    )


def _apply_trade_with_bank(state: GameState, action: TradeWithBank) -> None:
    player = state.players[action.player_index]
    if player.resources.get(action.giving) < 4:
        raise ValueError(f'Need at least 4 {action.giving} for a bank trade.')

    give_dict = {action.giving.value: 4}
    player.resources = player.resources.subtract(give_dict)
    current = player.resources.get(action.receiving)
    player.resources = player.resources.with_resource(action.receiving, current + 1)


def _apply_trade_with_port(state: GameState, action: TradeWithPort) -> None:
    player = state.players[action.player_index]
    if player.resources.get(action.giving) < action.giving_count:
        raise ValueError(
            f'Need at least {action.giving_count} {action.giving} for a port trade.'
        )

    give_dict = {action.giving.value: action.giving_count}
    player.resources = player.resources.subtract(give_dict)
    current = player.resources.get(action.receiving)
    player.resources = player.resources.with_resource(action.receiving, current + 1)


def _apply_end_turn(state: GameState, action: EndTurn) -> None:
    from games.app.catan.engine.turn_manager import advance_turn
    from games.app.catan.models.player import DevCardHand

    # Move newly purchased dev cards to the playable hand.
    player = state.players[action.player_index]
    for card_type in DevCardType:
        count = player.new_dev_cards.get(card_type)
        if count > 0:
            player.dev_cards = player.dev_cards.add(card_type, count)
    player.new_dev_cards = DevCardHand()

    advance_turn(state)


def _apply_move_robber(state: GameState, action: MoveRobber) -> None:
    if action.tile_index == state.board.robber_tile_index:
        raise ValueError('Robber must move to a different tile.')

    state.board.robber_tile_index = action.tile_index

    # Find adjacent players who have resources (excluding the acting player).
    candidates: set[int] = set()
    for vertex in state.board.vertices:
        if action.tile_index not in vertex.adjacent_tile_indices:
            continue
        if vertex.building is None:
            continue
        idx = vertex.building.player_index
        if idx == action.player_index:
            continue
        if state.players[idx].resources.total() > 0:
            candidates.add(idx)

    if candidates:
        state.turn_state.pending_action = PendingActionType.STEAL_RESOURCE
    else:
        state.turn_state.pending_action = PendingActionType.BUILD_OR_TRADE


def _apply_steal_resource(state: GameState, action: StealResource) -> None:
    target = state.players[action.target_player_index]
    total = target.resources.total()
    if total == 0:
        raise ValueError('Target player has no resources to steal.')

    # Pick a random resource from the target.
    from games.app.catan.models.board import ResourceType

    pool: list[str] = []
    for res_type in ResourceType:
        pool.extend([res_type.value] * getattr(target.resources, res_type.value))

    chosen = random.choice(pool)
    target.resources = target.resources.subtract({chosen: 1})

    actor = state.players[action.player_index]
    actor.resources = actor.resources.add(Resources(**{chosen: 1}))

    state.turn_state.pending_action = PendingActionType.BUILD_OR_TRADE


def _apply_discard_resources(state: GameState, action: DiscardResources) -> None:
    if action.player_index not in state.turn_state.discard_player_indices:
        raise ValueError('This player does not need to discard.')

    player = state.players[action.player_index]
    # Validate the player has the specified resources.
    for res_name, amount in action.resources.items():
        if getattr(player.resources, res_name, 0) < amount:
            raise ValueError(f'Player does not have {amount} {res_name} to discard.')

    player.resources = player.resources.subtract(action.resources)

    state.turn_state.discard_player_indices.remove(action.player_index)

    if not state.turn_state.discard_player_indices:
        state.turn_state.pending_action = PendingActionType.MOVE_ROBBER


_LONGEST_ROAD_THRESHOLD = 4  # player must exceed this length to claim (i.e. ≥ 5 roads)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _update_longest_road(state: GameState) -> None:
    """Recompute and update the longest road owner in *state*."""
    best_length = _LONGEST_ROAD_THRESHOLD  # must exceed threshold to claim
    best_owner: int | None = None
    for player in state.players:
        if player.longest_road_length > best_length:
            best_length = player.longest_road_length
            best_owner = player.player_index
        elif (
            player.longest_road_length == best_length
            and best_owner is not None
            and player.longest_road_length > _LONGEST_ROAD_THRESHOLD
        ):
            # Tie: current holder keeps it (handled below).
            pass

    # If no one qualifies, clear the award.
    if best_owner is None:
        state.longest_road_owner = None
        return

    # Preserve the current holder in a tie.
    current_holder = state.longest_road_owner
    if current_holder is not None:
        holder_length = state.players[current_holder].longest_road_length
        if holder_length >= best_length:
            best_owner = current_holder

    state.longest_road_owner = best_owner


def _update_largest_army(state: GameState, new_holder: int | None) -> None:
    """Update the largest army owner, preserving the current holder on ties."""
    if new_holder is None:
        # No one qualifies yet; leave unchanged.
        return
    current = state.largest_army_owner
    if current is None:
        state.largest_army_owner = new_holder
    else:
        current_knights = state.players[current].knights_played
        new_knights = state.players[new_holder].knights_played
        if new_knights > current_knights:
            state.largest_army_owner = new_holder
