"""Unit tests for the Catan game engine (rules, processor, turn manager)."""

from __future__ import annotations

import unittest

from games.app.catan.board_generator import generate_board
from games.app.catan.engine.processor import apply_action
from games.app.catan.engine.rules import (
    calculate_longest_road,
    check_victory_condition,
    get_largest_army_holder,
    get_legal_actions,
)
from games.app.catan.engine.turn_manager import (
    advance_turn,
    create_initial_game_state,
    get_next_setup_player,
)
from games.app.catan.models.actions import (
    DiscardResources,
    EndTurn,
    PlaceRoad,
    PlaceSettlement,
    RollDice,
)
from games.app.catan.models.board import Building, BuildingType, Road
from games.app.catan.models.game_state import (
    GamePhase,
    GameState,
    PendingActionType,
    TurnState,
)
from games.app.catan.models.player import DevCardHand, Player, Resources

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_2p_state(seed: int = 42) -> GameState:
    """Create a fresh 2-player game state for testing."""
    return create_initial_game_state(['Alice', 'Bob'], ['red', 'blue'], seed=seed)


def _place_setup_settlement(state: GameState, vertex_id: int) -> GameState:
    """Apply a PlaceSettlement action and assert it succeeded."""
    player_idx = state.turn_state.player_index
    result = apply_action(
        state, PlaceSettlement(player_index=player_idx, vertex_id=vertex_id)
    )
    assert result.success, result.error_message
    return result.updated_state


def _place_setup_road(state: GameState, edge_id: int) -> GameState:
    """Apply a PlaceRoad action and assert it succeeded."""
    player_idx = state.turn_state.player_index
    result = apply_action(state, PlaceRoad(player_index=player_idx, edge_id=edge_id))
    assert result.success, result.error_message
    return result.updated_state


# ---------------------------------------------------------------------------
# Rules engine tests
# ---------------------------------------------------------------------------


class TestRulesEngine(unittest.TestCase):
    """Tests for get_legal_actions, calculate_longest_road, etc."""

    def setUp(self) -> None:
        self.state = _make_2p_state()

    def test_setup_settlement_all_vertices_initially(self) -> None:
        """At the start all 54 vertices should be available."""
        actions = get_legal_actions(self.state, 0)
        settlement_actions = [a for a in actions if isinstance(a, PlaceSettlement)]
        self.assertEqual(len(settlement_actions), 54)

    def test_setup_nonactive_player_no_actions(self) -> None:
        """A non-active player has no legal actions during setup."""
        actions = get_legal_actions(self.state, 1)
        self.assertEqual(actions, [])

    def test_setup_distance_rule_reduces_choices(self) -> None:
        """After placing a settlement, adjacent vertices are excluded."""
        # Place at vertex 0.
        state = _place_setup_settlement(self.state, 0)
        # Need to be in PLACE_ROAD pending, advance to PLACE_SETTLEMENT again.
        # Find a valid road edge and place it.
        board = state.board
        road_edge = board.vertices[0].adjacent_edge_ids[0]
        state = _place_setup_road(state, road_edge)
        # Now it's player 1's turn; advance back to player 0 to test distance.
        # For simplicity, check that vertex 0 and its neighbours are excluded
        # from global legal placements (both players combined viewpoint).
        actions_p1 = get_legal_actions(state, 1)
        settlement_ids = {
            a.vertex_id for a in actions_p1 if isinstance(a, PlaceSettlement)
        }
        self.assertNotIn(0, settlement_ids)
        for adj_id in board.vertices[0].adjacent_vertex_ids:
            self.assertNotIn(adj_id, settlement_ids)

    def test_setup_place_road_adjacent_to_own_settlement(self) -> None:
        """Setup road actions are only adjacent to own settlement."""
        # Place settlement at vertex 0 → pending becomes PLACE_ROAD.
        state = _place_setup_settlement(self.state, 0)
        actions = get_legal_actions(state, 0)
        road_actions = [a for a in actions if isinstance(a, PlaceRoad)]
        board = state.board
        expected_edges = set(board.vertices[0].adjacent_edge_ids)
        actual_edges = {a.edge_id for a in road_actions}
        self.assertEqual(actual_edges, expected_edges)

    def test_roll_dice_is_only_action_on_main_turn(self) -> None:
        """During ROLL_DICE pending, only RollDice is returned for active player."""
        # Fast-forward through setup.
        state = _make_2p_state()
        state.phase = GamePhase.MAIN
        state.turn_state = TurnState(
            player_index=0, pending_action=PendingActionType.ROLL_DICE
        )
        actions = get_legal_actions(state, 0)
        self.assertEqual(len(actions), 1)
        self.assertIsInstance(actions[0], RollDice)

    def test_roll_dice_no_actions_for_non_active(self) -> None:
        """Non-active player gets no actions during ROLL_DICE."""
        state = _make_2p_state()
        state.phase = GamePhase.MAIN
        state.turn_state = TurnState(
            player_index=0, pending_action=PendingActionType.ROLL_DICE
        )
        self.assertEqual(get_legal_actions(state, 1), [])

    def test_longest_road_empty(self) -> None:
        """Player with no roads has road length 0."""
        board = generate_board(seed=1)
        self.assertEqual(calculate_longest_road(board, 0), 0)

    def test_longest_road_chain(self) -> None:
        """A simple chain of 3 roads scores 3."""
        board = generate_board(seed=1)
        # Build a 3-road chain: edge0 – vertex – edge1 – vertex – edge2.
        e0 = board.edges[0]
        # From edge0, pick a vertex and find the next edge.
        v_shared = e0.vertex_ids[1]
        next_edges = [
            eid
            for eid in board.vertices[v_shared].adjacent_edge_ids
            if eid != e0.edge_id
        ]
        if not next_edges:
            self.skipTest('Board geometry does not support this test case.')
        e1_id = next_edges[0]
        e1 = board.edges[e1_id]
        v2 = e1.vertex_ids[0] if e1.vertex_ids[1] == v_shared else e1.vertex_ids[1]
        next_edges2 = [
            eid
            for eid in board.vertices[v2].adjacent_edge_ids
            if eid not in {e0.edge_id, e1_id}
        ]
        if not next_edges2:
            self.skipTest('Board geometry does not support 3-road chain here.')
        e2_id = next_edges2[0]

        board.edges[e0.edge_id].road = Road(player_index=0)
        board.edges[e1_id].road = Road(player_index=0)
        board.edges[e2_id].road = Road(player_index=0)

        self.assertEqual(calculate_longest_road(board, 0), 3)

    def test_longest_road_opponent_blocks(self) -> None:
        """Opponent building in the middle of a road chain breaks it."""
        board = generate_board(seed=1)
        e0 = board.edges[0]
        v_mid = e0.vertex_ids[1]
        next_edges = [
            eid for eid in board.vertices[v_mid].adjacent_edge_ids if eid != e0.edge_id
        ]
        if not next_edges:
            self.skipTest('Board geometry insufficient.')
        e1_id = next_edges[0]

        board.edges[e0.edge_id].road = Road(player_index=0)
        board.edges[e1_id].road = Road(player_index=0)
        # Place opponent building at the shared vertex.
        board.vertices[v_mid].building = Building(
            player_index=1, building_type=BuildingType.SETTLEMENT
        )

        # Each segment is isolated: max road is 1.
        self.assertEqual(calculate_longest_road(board, 0), 1)

    def test_victory_condition_no_winner(self) -> None:
        """No winner when all players have < 10 VP."""
        state = _make_2p_state()
        self.assertIsNone(check_victory_condition(state))

    def test_victory_condition_winner(self) -> None:
        """Returns the player_index when a player reaches 10 VP."""
        state = _make_2p_state()
        state.players[1].victory_points = 10
        self.assertEqual(check_victory_condition(state), 1)

    def test_victory_condition_longest_road_counts(self) -> None:
        """Longest road bonus contributes to victory."""
        state = _make_2p_state()
        state.players[0].victory_points = 8
        state.longest_road_owner = 0
        self.assertEqual(check_victory_condition(state), 0)

    def test_largest_army_holder_none_below_threshold(self) -> None:
        """get_largest_army_holder returns None if no player has >= 3 knights."""
        players = [Player(player_index=i, name=str(i), color='red') for i in range(2)]
        players[0].knights_played = 2
        self.assertIsNone(get_largest_army_holder(players))

    def test_largest_army_holder_awarded(self) -> None:
        """Player with most knights (>= 3) gets the award."""
        players = [Player(player_index=i, name=str(i), color='red') for i in range(2)]
        players[0].knights_played = 3
        players[1].knights_played = 2
        self.assertEqual(get_largest_army_holder(players), 0)

    def test_discard_legal_action(self) -> None:
        """Player in discard_player_indices with >7 cards gets DiscardResources."""
        state = _make_2p_state()
        state.phase = GamePhase.MAIN
        state.turn_state = TurnState(
            player_index=0,
            pending_action=PendingActionType.DISCARD_RESOURCES,
            discard_player_indices=[1],
        )
        state.players[1].resources = Resources(
            wood=2, brick=2, wheat=2, sheep=2, ore=2
        )  # 10 cards
        actions = get_legal_actions(state, 1)
        self.assertEqual(len(actions), 1)
        self.assertIsInstance(actions[0], DiscardResources)

    def test_ended_game_no_actions(self) -> None:
        """No legal actions in ENDED phase."""
        state = _make_2p_state()
        state.phase = GamePhase.ENDED
        self.assertEqual(get_legal_actions(state, 0), [])


# ---------------------------------------------------------------------------
# Action processor tests
# ---------------------------------------------------------------------------


class TestActionProcessor(unittest.TestCase):
    """Tests for apply_action."""

    def test_place_settlement_setup(self) -> None:
        """PlaceSettlement places building, decrements inventory, adds VP."""
        state = _make_2p_state()
        result = apply_action(state, PlaceSettlement(player_index=0, vertex_id=5))
        self.assertTrue(result.success)
        new = result.updated_state
        self.assertEqual(new.board.vertices[5].building.player_index, 0)
        self.assertEqual(new.players[0].build_inventory.settlements_remaining, 4)
        self.assertEqual(new.players[0].victory_points, 1)

    def test_place_settlement_sets_place_road_pending(self) -> None:
        """After setup settlement, pending action is PLACE_ROAD."""
        state = _make_2p_state()
        result = apply_action(state, PlaceSettlement(player_index=0, vertex_id=5))
        self.assertTrue(result.success)
        self.assertEqual(
            result.updated_state.turn_state.pending_action,
            PendingActionType.PLACE_ROAD,
        )

    def test_place_settlement_distance_rule_rejected(self) -> None:
        """Can't place settlement adjacent to existing building."""
        state = _make_2p_state()
        result1 = apply_action(state, PlaceSettlement(player_index=0, vertex_id=0))
        self.assertTrue(result1.success)
        state2 = result1.updated_state
        adjacent_vertex = state2.board.vertices[0].adjacent_vertex_ids[0]
        # Try placing at adjacent vertex (should fail after road placed).
        result2 = apply_action(
            state2, PlaceSettlement(player_index=0, vertex_id=adjacent_vertex)
        )
        self.assertFalse(result2.success)

    def test_place_road_setup_advances_turn(self) -> None:
        """After placing a road in setup, turn advances to next player."""
        state = _make_2p_state()
        state = _place_setup_settlement(state, 0)
        road_edge = state.board.vertices[0].adjacent_edge_ids[0]
        result = apply_action(state, PlaceRoad(player_index=0, edge_id=road_edge))
        self.assertTrue(result.success)
        # After setup road, player 1 should be up.
        self.assertEqual(result.updated_state.turn_state.player_index, 1)

    def test_place_road_decrements_inventory(self) -> None:
        """Placing a road decrements roads_remaining."""
        state = _make_2p_state()
        state = _place_setup_settlement(state, 0)
        road_edge = state.board.vertices[0].adjacent_edge_ids[0]
        result = apply_action(state, PlaceRoad(player_index=0, edge_id=road_edge))
        self.assertTrue(result.success)
        self.assertEqual(
            result.updated_state.players[0].build_inventory.roads_remaining, 14
        )

    def test_roll_dice_sets_roll_value(self) -> None:
        """RollDice records a roll between 2 and 12 inclusive."""
        state = _make_2p_state()
        state.phase = GamePhase.MAIN
        state.turn_state = TurnState(
            player_index=0, pending_action=PendingActionType.ROLL_DICE
        )
        result = apply_action(state, RollDice(player_index=0))
        self.assertTrue(result.success)
        roll = result.updated_state.turn_state.roll_value
        self.assertIsNotNone(roll)
        self.assertGreaterEqual(roll, 2)
        self.assertLessEqual(roll, 12)

    def test_roll_7_moves_to_move_robber(self) -> None:
        """Rolling 7 sets pending to MOVE_ROBBER (when no one needs to discard)."""
        import unittest.mock

        state = _make_2p_state()
        state.phase = GamePhase.MAIN
        state.turn_state = TurnState(
            player_index=0, pending_action=PendingActionType.ROLL_DICE
        )
        # Force a roll of 7.
        with unittest.mock.patch('random.randint', side_effect=[4, 3]):
            result = apply_action(state, RollDice(player_index=0))
        self.assertTrue(result.success)
        self.assertEqual(
            result.updated_state.turn_state.pending_action,
            PendingActionType.MOVE_ROBBER,
        )

    def test_roll_7_large_hand_triggers_discard(self) -> None:
        """When a player holds >7 cards, rolling 7 requires discarding."""
        import unittest.mock

        state = _make_2p_state()
        state.phase = GamePhase.MAIN
        state.turn_state = TurnState(
            player_index=0, pending_action=PendingActionType.ROLL_DICE
        )
        state.players[1].resources = Resources(
            wood=2, brick=2, wheat=2, sheep=2, ore=2
        )  # 10 cards
        with unittest.mock.patch('random.randint', side_effect=[4, 3]):
            result = apply_action(state, RollDice(player_index=0))
        self.assertTrue(result.success)
        self.assertEqual(
            result.updated_state.turn_state.pending_action,
            PendingActionType.DISCARD_RESOURCES,
        )
        self.assertIn(1, result.updated_state.turn_state.discard_player_indices)

    def test_discard_clears_player_from_list(self) -> None:
        """Discarding removes player from discard_player_indices."""
        state = _make_2p_state()
        state.phase = GamePhase.MAIN
        state.turn_state = TurnState(
            player_index=0,
            pending_action=PendingActionType.DISCARD_RESOURCES,
            discard_player_indices=[1],
        )
        state.players[1].resources = Resources(wood=4, brick=4, wheat=2)  # 10 cards
        result = apply_action(
            state,
            DiscardResources(player_index=1, resources={'wood': 3, 'brick': 2}),
        )
        self.assertTrue(result.success)
        self.assertNotIn(1, result.updated_state.turn_state.discard_player_indices)

    def test_discard_all_done_moves_to_move_robber(self) -> None:
        """After last player discards, pending becomes MOVE_ROBBER."""
        state = _make_2p_state()
        state.phase = GamePhase.MAIN
        state.turn_state = TurnState(
            player_index=0,
            pending_action=PendingActionType.DISCARD_RESOURCES,
            discard_player_indices=[1],
        )
        state.players[1].resources = Resources(wood=4, brick=4, wheat=2)
        result = apply_action(
            state,
            DiscardResources(player_index=1, resources={'wood': 3, 'brick': 2}),
        )
        self.assertTrue(result.success)
        self.assertEqual(
            result.updated_state.turn_state.pending_action,
            PendingActionType.MOVE_ROBBER,
        )

    def test_resource_distribution_on_roll(self) -> None:
        """Rolling a tile's number awards resources to adjacent buildings."""
        state = _make_2p_state()
        state.phase = GamePhase.MAIN
        # Find a non-desert tile with a number token.
        board = state.board
        target_tile = next(
            (t for t in board.tiles if t.number_token is not None),
            None,
        )
        self.assertIsNotNone(target_tile)
        tile_idx = board.tiles.index(target_tile)

        # Place player 0's settlement on a vertex adjacent to that tile.
        from games.app.catan.models.board import TileType as _TileType  # noqa: F401

        adj_vertices = [
            v for v in board.vertices if tile_idx in v.adjacent_tile_indices
        ]
        self.assertGreater(len(adj_vertices), 0)
        target_vertex = adj_vertices[0]
        board.vertices[target_vertex.vertex_id].building = Building(
            player_index=0, building_type=BuildingType.SETTLEMENT
        )

        # Make sure the robber is not on the target tile.
        if board.robber_tile_index == tile_idx:
            # Move robber away (find desert or any other tile).
            for i, _t in enumerate(board.tiles):
                if i != tile_idx:
                    board.robber_tile_index = i
                    break

        roll = target_tile.number_token
        import unittest.mock

        state.turn_state = TurnState(
            player_index=0, pending_action=PendingActionType.ROLL_DICE
        )
        with unittest.mock.patch(
            'random.randint',
            side_effect=[roll - 1, 1],  # sum == roll
        ):
            result = apply_action(state, RollDice(player_index=0))

        self.assertTrue(result.success)
        from games.app.catan.models.board import TILE_RESOURCE

        expected_resource = TILE_RESOURCE.get(target_tile.tile_type)
        if expected_resource is not None:
            total_received = result.updated_state.players[0].resources.get(
                expected_resource
            )
            self.assertGreater(total_received, 0)

    def test_original_state_not_modified(self) -> None:
        """apply_action must not mutate the original game state."""
        state = _make_2p_state()
        original_player0_vp = state.players[0].victory_points
        apply_action(state, PlaceSettlement(player_index=0, vertex_id=0))
        self.assertEqual(state.players[0].victory_points, original_player0_vp)

    def test_victory_detected_on_apply(self) -> None:
        """apply_action sets phase=ENDED when a player reaches 10 VP."""
        state = _make_2p_state()
        state.players[0].victory_points = 9
        state.phase = GamePhase.MAIN
        state.turn_state = TurnState(
            player_index=0, pending_action=PendingActionType.BUILD_OR_TRADE
        )
        # Give player resources for a settlement and connect a road.
        from games.app.catan.models.player import Resources as Res

        state.players[0].resources = Res(wood=1, brick=1, wheat=1, sheep=1)
        # Place an existing road so player can build settlement.
        board = state.board
        edge = board.edges[0]
        board.edges[0].road = Road(player_index=0)
        # Find a connected, empty vertex.
        for vid in edge.vertex_ids:
            vertex = board.vertices[vid]
            if vertex.building is None and all(
                board.vertices[adj].building is None
                for adj in vertex.adjacent_vertex_ids
            ):
                target_vid = vid
                break
        else:
            self.skipTest('No valid vertex found for this test.')
        result = apply_action(
            state, PlaceSettlement(player_index=0, vertex_id=target_vid)
        )
        self.assertTrue(result.success)
        self.assertEqual(result.updated_state.phase, GamePhase.ENDED)
        self.assertEqual(result.updated_state.winner_index, 0)

    def test_end_turn_moves_new_dev_cards(self) -> None:
        """EndTurn moves new_dev_cards into dev_cards."""
        state = _make_2p_state()
        state.phase = GamePhase.MAIN
        state.turn_state = TurnState(
            player_index=0, pending_action=PendingActionType.BUILD_OR_TRADE
        )
        state.players[0].new_dev_cards = DevCardHand(knight=1)
        result = apply_action(state, EndTurn(player_index=0))
        self.assertTrue(result.success)
        # dev_cards should now have the knight; new_dev_cards cleared.
        self.assertEqual(result.updated_state.players[0].dev_cards.knight, 1)
        self.assertEqual(result.updated_state.players[0].new_dev_cards.knight, 0)


# ---------------------------------------------------------------------------
# Turn manager tests
# ---------------------------------------------------------------------------


class TestTurnManager(unittest.TestCase):
    """Tests for create_initial_game_state, advance_turn, etc."""

    def test_create_initial_state_player_count(self) -> None:
        """Initial state has the correct number of players."""
        state = create_initial_game_state(['A', 'B', 'C'], ['r', 'g', 'b'])
        self.assertEqual(len(state.players), 3)

    def test_create_initial_state_phase(self) -> None:
        """Initial state starts in SETUP_FORWARD phase."""
        state = _make_2p_state()
        self.assertEqual(state.phase, GamePhase.SETUP_FORWARD)

    def test_create_initial_state_pending_action(self) -> None:
        """Player 0 starts with PLACE_SETTLEMENT pending."""
        state = _make_2p_state()
        self.assertEqual(
            state.turn_state.pending_action, PendingActionType.PLACE_SETTLEMENT
        )
        self.assertEqual(state.turn_state.player_index, 0)

    def test_create_initial_state_deck_size(self) -> None:
        """Dev card deck starts with 25 cards."""
        state = _make_2p_state()
        self.assertEqual(len(state.dev_card_deck), 25)

    def test_setup_forward_advances_player(self) -> None:
        """In SETUP_FORWARD, advance_turn moves to the next player."""
        state = _make_2p_state()
        state.turn_state = TurnState(
            player_index=0, pending_action=PendingActionType.PLACE_SETTLEMENT
        )
        advance_turn(state)
        self.assertEqual(state.turn_state.player_index, 1)
        self.assertEqual(state.phase, GamePhase.SETUP_FORWARD)

    def test_setup_forward_last_player_switches_backward(self) -> None:
        """Last player in SETUP_FORWARD flips phase to SETUP_BACKWARD."""
        state = _make_2p_state()
        state.turn_state = TurnState(
            player_index=1, pending_action=PendingActionType.PLACE_SETTLEMENT
        )
        advance_turn(state)
        self.assertEqual(state.phase, GamePhase.SETUP_BACKWARD)
        self.assertEqual(state.turn_state.player_index, 1)

    def test_setup_backward_decrements_player(self) -> None:
        """In SETUP_BACKWARD, advance_turn moves to the previous player."""
        state = _make_2p_state()
        state.phase = GamePhase.SETUP_BACKWARD
        state.turn_state = TurnState(
            player_index=1, pending_action=PendingActionType.PLACE_SETTLEMENT
        )
        advance_turn(state)
        self.assertEqual(state.turn_state.player_index, 0)
        self.assertEqual(state.phase, GamePhase.SETUP_BACKWARD)

    def test_setup_backward_first_player_starts_main(self) -> None:
        """Player 0 finishing SETUP_BACKWARD transitions to MAIN phase."""
        state = _make_2p_state()
        state.phase = GamePhase.SETUP_BACKWARD
        state.turn_state = TurnState(
            player_index=0, pending_action=PendingActionType.PLACE_SETTLEMENT
        )
        advance_turn(state)
        self.assertEqual(state.phase, GamePhase.MAIN)
        self.assertEqual(state.turn_state.player_index, 0)
        self.assertEqual(state.turn_state.pending_action, PendingActionType.ROLL_DICE)
        self.assertEqual(state.turn_number, 1)

    def test_main_advance_cycles_players(self) -> None:
        """In MAIN phase, advance_turn cycles player indices."""
        state = _make_2p_state()
        state.phase = GamePhase.MAIN
        state.turn_number = 1
        state.turn_state = TurnState(
            player_index=0, pending_action=PendingActionType.BUILD_OR_TRADE
        )
        advance_turn(state)
        self.assertEqual(state.turn_state.player_index, 1)

    def test_main_advance_wraps_and_increments_turn(self) -> None:
        """In MAIN phase, wrapping from last to first player increments turn_number."""
        state = _make_2p_state()
        state.phase = GamePhase.MAIN
        state.turn_number = 1
        state.turn_state = TurnState(
            player_index=1, pending_action=PendingActionType.BUILD_OR_TRADE
        )
        advance_turn(state)
        self.assertEqual(state.turn_state.player_index, 0)
        self.assertEqual(state.turn_number, 2)

    def test_get_next_setup_player_forward(self) -> None:
        """get_next_setup_player increments index in SETUP_FORWARD."""
        idx, phase = get_next_setup_player(0, 4, GamePhase.SETUP_FORWARD)
        self.assertEqual(idx, 1)
        self.assertEqual(phase, GamePhase.SETUP_FORWARD)

    def test_get_next_setup_player_forward_last(self) -> None:
        """Last player in SETUP_FORWARD switches to SETUP_BACKWARD."""
        idx, phase = get_next_setup_player(3, 4, GamePhase.SETUP_FORWARD)
        self.assertEqual(idx, 3)
        self.assertEqual(phase, GamePhase.SETUP_BACKWARD)

    def test_get_next_setup_player_backward(self) -> None:
        """get_next_setup_player decrements index in SETUP_BACKWARD."""
        idx, phase = get_next_setup_player(2, 4, GamePhase.SETUP_BACKWARD)
        self.assertEqual(idx, 1)
        self.assertEqual(phase, GamePhase.SETUP_BACKWARD)

    def test_get_next_setup_player_backward_first(self) -> None:
        """Player 0 finishing SETUP_BACKWARD returns MAIN phase."""
        idx, phase = get_next_setup_player(0, 4, GamePhase.SETUP_BACKWARD)
        self.assertEqual(idx, 0)
        self.assertEqual(phase, GamePhase.MAIN)

    def test_full_2p_setup_sequence(self) -> None:
        """Full 2-player snake-draft setup yields MAIN phase for player 0."""
        state = _make_2p_state()
        # Order: 0 → 1 → 1 → 0 (snake draft).
        for player_idx, vertex_idx in [(0, 0), (1, 10), (1, 20), (0, 30)]:
            self.assertEqual(state.turn_state.player_index, player_idx)
            # Place settlement.
            state = _place_setup_settlement(state, vertex_idx)
            # Place road on first adjacent edge.
            edge_id = state.board.vertices[vertex_idx].adjacent_edge_ids[0]
            state = _place_setup_road(state, edge_id)

        self.assertEqual(state.phase, GamePhase.MAIN)
        self.assertEqual(state.turn_state.player_index, 0)
        self.assertEqual(state.turn_state.pending_action, PendingActionType.ROLL_DICE)


if __name__ == '__main__':
    unittest.main()
