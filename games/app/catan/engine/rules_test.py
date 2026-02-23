"""Unit tests for the Catan rules engine."""

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
from games.app.catan.engine.turn_manager import create_initial_game_state
from games.app.catan.models.actions import (
    DiscardResources,
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
from games.app.catan.models.player import Player, Resources

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
    assert result.updated_state is not None
    return result.updated_state


def _place_setup_road(state: GameState, edge_id: int) -> GameState:
    """Apply a PlaceRoad action and assert it succeeded."""
    player_idx = state.turn_state.player_index
    result = apply_action(state, PlaceRoad(player_index=player_idx, edge_id=edge_id))
    assert result.success, result.error_message
    assert result.updated_state is not None
    return result.updated_state


# ---------------------------------------------------------------------------
# Tests
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
        # Now it's player 1's turn; check that vertex 0 and its neighbours are
        # excluded from legal placements.
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
        """During ROLL_DICE pending, only RollDice is returned when no knight held."""
        state = _make_2p_state()
        state.phase = GamePhase.MAIN
        state.turn_state = TurnState(
            player_index=0, pending_action=PendingActionType.ROLL_DICE
        )
        actions = get_legal_actions(state, 0)
        self.assertEqual(len(actions), 1)
        self.assertIsInstance(actions[0], RollDice)

    def test_roll_dice_includes_knight_when_held(self) -> None:
        """During ROLL_DICE pending, PlayKnight is included if player holds a knight."""
        from games.app.catan.models.actions import PlayKnight
        from games.app.catan.models.player import DevCardHand

        state = _make_2p_state()
        state.phase = GamePhase.MAIN
        state.turn_state = TurnState(
            player_index=0, pending_action=PendingActionType.ROLL_DICE
        )
        state.players[0].dev_cards = DevCardHand(knight=1)
        actions = get_legal_actions(state, 0)
        types = {type(a) for a in actions}
        self.assertIn(RollDice, types)
        self.assertIn(PlayKnight, types)

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


if __name__ == '__main__':
    unittest.main()
