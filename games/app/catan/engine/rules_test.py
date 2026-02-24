"""Unit tests for the Catan rules engine."""

from __future__ import annotations

import unittest

from games.app.catan import board_generator
from games.app.catan.engine import processor, rules, turn_manager
from games.app.catan.models import actions, board, game_state, player

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_2p_state(seed: int = 42) -> game_state.GameState:
    """Create a fresh 2-player game state for testing."""
    return turn_manager.create_initial_game_state(
        ['Alice', 'Bob'], ['red', 'blue'], seed=seed
    )


def _place_setup_settlement(
    state: game_state.GameState, vertex_id: int
) -> game_state.GameState:
    """Apply a PlaceSettlement action and assert it succeeded."""
    player_idx = state.turn_state.player_index
    result = processor.apply_action(
        state, actions.PlaceSettlement(player_index=player_idx, vertex_id=vertex_id)
    )
    assert result.success, result.error_message
    assert result.updated_state is not None
    return result.updated_state


def _place_setup_road(
    state: game_state.GameState, edge_id: int
) -> game_state.GameState:
    """Apply a PlaceRoad action and assert it succeeded."""
    player_idx = state.turn_state.player_index
    result = processor.apply_action(
        state, actions.PlaceRoad(player_index=player_idx, edge_id=edge_id)
    )
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
        legal_actions = rules.get_legal_actions(self.state, 0)
        settlement_actions = [
            a for a in legal_actions if isinstance(a, actions.PlaceSettlement)
        ]
        self.assertEqual(len(settlement_actions), 54)

    def test_setup_nonactive_player_no_actions(self) -> None:
        """A non-active player has no legal actions during setup."""
        actions = rules.get_legal_actions(self.state, 1)
        self.assertEqual(actions, [])

    def test_setup_distance_rule_reduces_choices(self) -> None:
        """After placing a settlement, adjacent vertices are excluded."""
        # Place at vertex 0.
        state = _place_setup_settlement(self.state, 0)
        # Need to be in PLACE_ROAD pending, advance to PLACE_SETTLEMENT again.
        # Find a valid road edge and place it.
        game_board = state.board
        road_edge = game_board.vertices[0].adjacent_edge_ids[0]
        state = _place_setup_road(state, road_edge)
        # Now it's player 1's turn; check that vertex 0 and its neighbours are
        # excluded from legal placements.
        actions_p1 = rules.get_legal_actions(state, 1)
        settlement_ids = {
            a.vertex_id for a in actions_p1 if isinstance(a, actions.PlaceSettlement)
        }
        self.assertNotIn(0, settlement_ids)
        for adj_id in game_board.vertices[0].adjacent_vertex_ids:
            self.assertNotIn(adj_id, settlement_ids)

    def test_setup_place_road_adjacent_to_own_settlement(self) -> None:
        """Setup road actions are only adjacent to own settlement."""
        # Place settlement at vertex 0 → pending becomes PLACE_ROAD.
        state = _place_setup_settlement(self.state, 0)
        legal_actions = rules.get_legal_actions(state, 0)
        road_actions = [a for a in legal_actions if isinstance(a, actions.PlaceRoad)]
        game_board = state.board
        expected_edges = set(game_board.vertices[0].adjacent_edge_ids)
        actual_edges = {a.edge_id for a in road_actions}
        self.assertEqual(actual_edges, expected_edges)

    def test_roll_dice_is_only_action_on_main_turn(self) -> None:
        """During ROLL_DICE pending, only RollDice is returned when no knight held."""
        state = _make_2p_state()
        state.phase = game_state.GamePhase.MAIN
        state.turn_state = game_state.TurnState(
            player_index=0, pending_action=game_state.PendingActionType.ROLL_DICE
        )
        legal_actions = rules.get_legal_actions(state, 0)
        self.assertEqual(len(legal_actions), 1)
        self.assertIsInstance(legal_actions[0], actions.RollDice)

    def test_roll_dice_includes_knight_when_held(self) -> None:
        """During ROLL_DICE pending, PlayKnight is included if player holds a knight."""

        state = _make_2p_state()
        state.phase = game_state.GamePhase.MAIN
        state.turn_state = game_state.TurnState(
            player_index=0, pending_action=game_state.PendingActionType.ROLL_DICE
        )
        state.players[0].dev_cards = player.DevCardHand(knight=1)
        legal_actions = rules.get_legal_actions(state, 0)
        types = {type(a) for a in legal_actions}
        self.assertIn(actions.RollDice, types)
        self.assertIn(actions.PlayKnight, types)

    def test_roll_dice_no_actions_for_non_active(self) -> None:
        """Non-active player gets no actions during ROLL_DICE."""
        state = _make_2p_state()
        state.phase = game_state.GamePhase.MAIN
        state.turn_state = game_state.TurnState(
            player_index=0, pending_action=game_state.PendingActionType.ROLL_DICE
        )
        self.assertEqual(rules.get_legal_actions(state, 1), [])

    def test_longest_road_empty(self) -> None:
        """Player with no roads has road length 0."""
        game_board = board_generator.generate_board(seed=1)
        self.assertEqual(rules.calculate_longest_road(game_board, 0), 0)

    def test_longest_road_chain(self) -> None:
        """A simple chain of 3 roads scores 3."""
        game_board = board_generator.generate_board(seed=1)
        # Build a 3-road chain: edge0 – vertex – edge1 – vertex – edge2.
        e0 = game_board.edges[0]
        # From edge0, pick a vertex and find the next edge.
        v_shared = e0.vertex_ids[1]
        next_edges = [
            eid
            for eid in game_board.vertices[v_shared].adjacent_edge_ids
            if eid != e0.edge_id
        ]
        if not next_edges:
            self.skipTest('Board geometry does not support this test case.')
        e1_id = next_edges[0]
        e1 = game_board.edges[e1_id]
        v2 = e1.vertex_ids[0] if e1.vertex_ids[1] == v_shared else e1.vertex_ids[1]
        next_edges2 = [
            eid
            for eid in game_board.vertices[v2].adjacent_edge_ids
            if eid not in {e0.edge_id, e1_id}
        ]
        if not next_edges2:
            self.skipTest('Board geometry does not support 3-road chain here.')
        e2_id = next_edges2[0]

        game_board.edges[e0.edge_id].road = board.Road(player_index=0)
        game_board.edges[e1_id].road = board.Road(player_index=0)
        game_board.edges[e2_id].road = board.Road(player_index=0)

        self.assertEqual(rules.calculate_longest_road(game_board, 0), 3)

    def test_longest_road_opponent_blocks(self) -> None:
        """Opponent building in the middle of a road chain breaks it."""
        game_board = board_generator.generate_board(seed=1)
        e0 = game_board.edges[0]
        v_mid = e0.vertex_ids[1]
        next_edges = [
            eid
            for eid in game_board.vertices[v_mid].adjacent_edge_ids
            if eid != e0.edge_id
        ]
        if not next_edges:
            self.skipTest('Board geometry insufficient.')
        e1_id = next_edges[0]

        game_board.edges[e0.edge_id].road = board.Road(player_index=0)
        game_board.edges[e1_id].road = board.Road(player_index=0)
        # Place opponent building at the shared vertex.
        game_board.vertices[v_mid].building = board.Building(
            player_index=1, building_type=board.BuildingType.SETTLEMENT
        )

        # Each segment is isolated: max road is 1.
        self.assertEqual(rules.calculate_longest_road(game_board, 0), 1)

    def test_victory_condition_no_winner(self) -> None:
        """No winner when all players have < 10 VP."""
        state = _make_2p_state()
        self.assertIsNone(rules.check_victory_condition(state))

    def test_victory_condition_winner(self) -> None:
        """Returns the player_index when a player reaches 10 VP."""
        state = _make_2p_state()
        state.players[1].victory_points = 10
        self.assertEqual(rules.check_victory_condition(state), 1)

    def test_victory_condition_longest_road_counts(self) -> None:
        """Longest road bonus contributes to victory."""
        state = _make_2p_state()
        state.players[0].victory_points = 8
        state.longest_road_owner = 0
        self.assertEqual(rules.check_victory_condition(state), 0)

    def test_largest_army_holder_none_below_threshold(self) -> None:
        """get_largest_army_holder returns None if no player has >= 3 knights."""
        players = [
            player.Player(player_index=i, name=str(i), color='red') for i in range(2)
        ]
        players[0].knights_played = 2
        self.assertIsNone(rules.get_largest_army_holder(players))

    def test_largest_army_holder_awarded(self) -> None:
        """Player with most knights (>= 3) gets the award."""
        players = [
            player.Player(player_index=i, name=str(i), color='red') for i in range(2)
        ]
        players[0].knights_played = 3
        players[1].knights_played = 2
        self.assertEqual(rules.get_largest_army_holder(players), 0)

    def test_discard_legal_action(self) -> None:
        """Player in discard_player_indices with >7 cards gets DiscardResources."""
        state = _make_2p_state()
        state.phase = game_state.GamePhase.MAIN
        state.turn_state = game_state.TurnState(
            player_index=0,
            pending_action=game_state.PendingActionType.DISCARD_RESOURCES,
            discard_player_indices=[1],
        )
        state.players[1].resources = player.Resources(
            wood=2, brick=2, wheat=2, sheep=2, ore=2
        )  # 10 cards
        legal_actions = rules.get_legal_actions(state, 1)
        self.assertEqual(len(legal_actions), 1)
        self.assertIsInstance(legal_actions[0], actions.DiscardResources)

    def test_ended_game_no_actions(self) -> None:
        """No legal actions in ENDED phase."""
        state = _make_2p_state()
        state.phase = game_state.GamePhase.ENDED
        self.assertEqual(rules.get_legal_actions(state, 0), [])


if __name__ == '__main__':
    unittest.main()
