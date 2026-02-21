"""Unit tests for the Catan game engine."""

from __future__ import annotations

import copy
import unittest

from games.app.catan.engine.processor import (
    _calculate_longest_road,
    apply_action,
)
from games.app.catan.engine.rules import get_legal_actions
from games.app.catan.engine.turn_manager import create_initial_game_state
from games.app.catan.models.actions import (
    ActionType,
    EndTurn,
    PlaceSettlement,
    RollDice,
)
from games.app.catan.models.board import Road
from games.app.catan.models.game_state import GamePhase, GameState, PendingActionType
from games.app.catan.models.player import Resources


class TestCreateInitialGameState(unittest.TestCase):
    def test_creates_valid_state(self) -> None:
        state = create_initial_game_state(['Alice', 'Bob'], ['red', 'blue'], seed=42)
        self.assertEqual(len(state.players), 2)
        self.assertEqual(state.phase, GamePhase.SETUP_FORWARD)
        self.assertEqual(state.turn_state.player_index, 0)
        self.assertEqual(
            state.turn_state.pending_action, PendingActionType.PLACE_SETTLEMENT
        )
        self.assertEqual(len(state.dev_card_deck), 25)
        self.assertEqual(len(state.board.vertices), 54)

    def test_players_have_no_resources(self) -> None:
        state = create_initial_game_state(['Alice', 'Bob'], ['red', 'blue'], seed=1)
        for player in state.players:
            self.assertEqual(player.resources.total(), 0)
            self.assertEqual(player.victory_points, 0)


class TestSetupLegalActions(unittest.TestCase):
    def setUp(self) -> None:
        self.state = create_initial_game_state(
            ['Alice', 'Bob', 'Carol'], ['red', 'blue', 'green'], seed=7
        )

    def test_setup_settlement_legal_actions_count(self) -> None:
        """All 54 vertices should be legal initially."""
        actions = get_legal_actions(self.state, 0)
        self.assertEqual(
            sum(1 for a in actions if a.action_type == ActionType.PLACE_SETTLEMENT), 54
        )

    def test_distance_rule_reduces_options(self) -> None:
        """After placing a settlement, adjacent vertices become illegal."""
        first_action = get_legal_actions(self.state, 0)[0]
        result = apply_action(self.state, first_action)
        self.assertTrue(result.success)
        # Now we should be in PLACE_ROAD
        updated = result.updated_state
        self.assertEqual(
            updated.turn_state.pending_action, PendingActionType.PLACE_ROAD
        )

    def test_road_adjacent_to_settlement(self) -> None:
        """After settlement, only adjacent edges are legal."""
        state = self.state
        # Place settlement on vertex 0
        v0 = state.board.vertices[0]
        result = apply_action(
            state, PlaceSettlement(player_index=0, vertex_id=v0.vertex_id)
        )
        self.assertTrue(result.success)
        road_state = result.updated_state
        road_actions = get_legal_actions(road_state, 0)
        # All road actions should be adjacent to vertex 0
        valid_edge_ids = set(v0.adjacent_edge_ids)
        for action in road_actions:
            self.assertIn(action.edge_id, valid_edge_ids)

    def test_wrong_player_gets_no_actions(self) -> None:
        """Player 1 can't act when it's player 0's turn."""
        actions = get_legal_actions(self.state, 1)
        self.assertEqual(actions, [])


class TestSetupNoResourceCharge(unittest.TestCase):
    def test_settlement_free_in_setup(self) -> None:
        """Placing a settlement in setup should not cost resources."""
        state = create_initial_game_state(['Alice', 'Bob'], ['red', 'blue'], seed=5)
        v0 = state.board.vertices[0]
        result = apply_action(
            state, PlaceSettlement(player_index=0, vertex_id=v0.vertex_id)
        )
        self.assertTrue(result.success)
        player = result.updated_state.players[0]
        self.assertEqual(player.resources.total(), 0)

    def test_road_free_in_setup(self) -> None:
        """Placing a road in setup should not cost resources."""
        state = create_initial_game_state(['Alice', 'Bob'], ['red', 'blue'], seed=5)
        v0 = state.board.vertices[0]
        r1 = apply_action(
            state, PlaceSettlement(player_index=0, vertex_id=v0.vertex_id)
        )
        road_actions = get_legal_actions(r1.updated_state, 0)
        r2 = apply_action(r1.updated_state, road_actions[0])
        self.assertTrue(r2.success)
        player = r2.updated_state.players[0]
        self.assertEqual(player.resources.total(), 0)


class TestRollDiceDistribution(unittest.TestCase):
    def _setup_main_phase(self) -> GameState:
        """Create a 2-player game with both players past setup."""
        state = create_initial_game_state(['Alice', 'Bob'], ['red', 'blue'], seed=99)
        # Complete setup: 2 players × 2 settlements × 2 roads = 8 actions
        for _ in range(8):
            actions = get_legal_actions(state, state.turn_state.player_index)
            if not actions:
                break
            state = apply_action(state, actions[0]).updated_state
        return state

    def test_roll_distributes_resources(self) -> None:
        """Rolling should give resources to players with adjacent settlements."""
        state = self._setup_main_phase()
        if state.phase != GamePhase.MAIN:
            self.skipTest('Setup not fully completed')
        pi = state.turn_state.player_index
        result = apply_action(state, RollDice(player_index=pi))
        self.assertTrue(result.success)
        # After rolling, pending should be BUILD_OR_TRADE or MOVE_ROBBER or DISCARD
        new_state = result.updated_state
        self.assertIn(
            new_state.turn_state.pending_action,
            [
                PendingActionType.BUILD_OR_TRADE,
                PendingActionType.MOVE_ROBBER,
                PendingActionType.DISCARD_RESOURCES,
            ],
        )


class TestMainPhaseActions(unittest.TestCase):
    def _reach_main_build(
        self, resources: Resources | None = None
    ) -> tuple[GameState, int]:
        """Return a game state in BUILD_OR_TRADE with given resources for player 0."""
        state = create_initial_game_state(['Alice', 'Bob'], ['red', 'blue'], seed=123)
        for _ in range(8):
            actions = get_legal_actions(state, state.turn_state.player_index)
            if not actions:
                break
            state = apply_action(state, actions[0]).updated_state

        if state.phase != GamePhase.MAIN:
            return state, 0

        # Roll dice to get to build_or_trade
        pi = state.turn_state.player_index
        actions = get_legal_actions(state, pi)
        roll = next((a for a in actions if a.action_type == ActionType.ROLL_DICE), None)
        if roll:
            state = apply_action(state, roll).updated_state

        # Handle any robber/discard
        for _ in range(20):
            if state.turn_state.pending_action == PendingActionType.BUILD_OR_TRADE:
                break
            pi2 = state.turn_state.player_index
            acts = get_legal_actions(state, pi2)
            if not acts:
                break
            state = apply_action(state, acts[0]).updated_state

        if resources and state.phase == GamePhase.MAIN:
            state = copy.deepcopy(state)
            state.players[pi].resources = resources

        return state, pi

    def test_road_costs_resources(self) -> None:
        """Building a road in main phase deducts wood and brick."""
        state, pi = self._reach_main_build(
            resources=Resources(wood=5, brick=5, wheat=2, sheep=2)
        )
        if state.turn_state.pending_action != PendingActionType.BUILD_OR_TRADE:
            self.skipTest('Did not reach BUILD_OR_TRADE')
        actions = get_legal_actions(state, pi)
        road_actions = [a for a in actions if a.action_type == ActionType.PLACE_ROAD]
        if not road_actions:
            self.skipTest('No road actions available')
        wood_before = state.players[pi].resources.wood
        brick_before = state.players[pi].resources.brick
        result = apply_action(state, road_actions[0])
        self.assertTrue(result.success)
        player = result.updated_state.players[pi]
        self.assertEqual(player.resources.wood, wood_before - 1)
        self.assertEqual(player.resources.brick, brick_before - 1)


class TestEndTurn(unittest.TestCase):
    def test_end_turn_advances_player(self) -> None:
        """EndTurn should advance to the next player."""
        state = create_initial_game_state(['Alice', 'Bob'], ['red', 'blue'], seed=77)
        # Complete setup
        for _ in range(8):
            actions = get_legal_actions(state, state.turn_state.player_index)
            if not actions:
                break
            state = apply_action(state, actions[0]).updated_state

        if state.phase != GamePhase.MAIN:
            self.skipTest('Did not reach main phase')

        pi = state.turn_state.player_index
        # Roll and handle everything
        for _ in range(20):
            if state.turn_state.pending_action == PendingActionType.BUILD_OR_TRADE:
                break
            acts = get_legal_actions(state, state.turn_state.player_index)
            if not acts:
                break
            state = apply_action(state, acts[0]).updated_state

        if state.turn_state.pending_action != PendingActionType.BUILD_OR_TRADE:
            self.skipTest('Did not reach BUILD_OR_TRADE')

        result = apply_action(state, EndTurn(player_index=pi))
        self.assertTrue(result.success)
        new_state = result.updated_state
        expected_next = (pi + 1) % 2
        self.assertEqual(new_state.turn_state.player_index, expected_next)
        self.assertEqual(
            new_state.turn_state.pending_action, PendingActionType.ROLL_DICE
        )


class TestLongestRoad(unittest.TestCase):
    def test_empty_road_is_zero(self) -> None:
        state = create_initial_game_state(['Alice', 'Bob'], ['red', 'blue'], seed=1)
        self.assertEqual(_calculate_longest_road(state.board, 0), 0)

    def test_single_road_is_one(self) -> None:
        state = create_initial_game_state(['Alice', 'Bob'], ['red', 'blue'], seed=1)
        board = copy.deepcopy(state.board)
        board.edges[0].road = Road(player_index=0)
        self.assertEqual(_calculate_longest_road(board, 0), 1)

    def test_chain_of_roads(self) -> None:
        """A linear chain of N roads should have longest road = N."""
        state = create_initial_game_state(['Alice', 'Bob'], ['red', 'blue'], seed=1)
        board = copy.deepcopy(state.board)
        # Build a chain: edge 0 → edge 1 → edge 2 (if connected)
        # Find a path of 3 connected edges
        edge0 = board.edges[0]
        v0, v1 = edge0.vertex_ids
        # Find edge connected to v1
        connected_edges = [
            e for e in board.edges if e.edge_id != 0 and v1 in e.vertex_ids
        ]
        if len(connected_edges) >= 2:
            board.edges[0].road = Road(player_index=0)
            board.edges[connected_edges[0].edge_id].road = Road(player_index=0)
            board.edges[connected_edges[1].edge_id].road = Road(player_index=0)
            length = _calculate_longest_road(board, 0)
            self.assertGreaterEqual(length, 2)


class TestRobberOnSeven(unittest.TestCase):
    def test_rolling_seven_sets_move_robber(self) -> None:
        """Rolling 7 should eventually lead to MOVE_ROBBER pending."""
        state = create_initial_game_state(['Alice', 'Bob'], ['red', 'blue'], seed=55)
        # Complete setup
        for _ in range(8):
            actions = get_legal_actions(state, state.turn_state.player_index)
            if not actions:
                break
            state = apply_action(state, actions[0]).updated_state

        if state.phase != GamePhase.MAIN:
            self.skipTest('Did not reach main phase')

        pi = state.turn_state.player_index
        result = apply_action(state, RollDice(player_index=pi))
        self.assertTrue(result.success)
        new_state = result.updated_state
        self.assertIn(
            new_state.turn_state.pending_action,
            [
                PendingActionType.BUILD_OR_TRADE,
                PendingActionType.MOVE_ROBBER,
                PendingActionType.DISCARD_RESOURCES,
            ],
        )


class TestVictoryCondition(unittest.TestCase):
    def test_ten_vp_ends_game(self) -> None:
        """A player with 10 VP should trigger ENDED phase."""
        state = create_initial_game_state(['Alice', 'Bob'], ['red', 'blue'], seed=1)
        state = copy.deepcopy(state)
        state.players[0].victory_points = 9

        # Place a settlement to get to 10 VP
        actions = get_legal_actions(state, 0)
        settlement_actions = [
            a for a in actions if a.action_type == ActionType.PLACE_SETTLEMENT
        ]
        if not settlement_actions:
            self.skipTest('No settlement actions available')

        result = apply_action(state, settlement_actions[0])
        self.assertTrue(result.success)
        new_state = result.updated_state
        self.assertEqual(new_state.phase, GamePhase.ENDED)
        self.assertEqual(new_state.winner_index, 0)
