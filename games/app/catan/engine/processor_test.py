"""Unit tests for the Catan action processor."""

from __future__ import annotations

import unittest

from games.app.catan.engine.processor import apply_action
from games.app.catan.engine.turn_manager import create_initial_game_state
from games.app.catan.models.actions import (
    DiscardResources,
    EndTurn,
    PlaceRoad,
    PlaceSettlement,
    RollDice,
)
from games.app.catan.models.board import Building, BuildingType, Road, TileType
from games.app.catan.models.game_state import (
    GamePhase,
    GameState,
    PendingActionType,
    TurnState,
)
from games.app.catan.models.player import DevCardHand, Resources

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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestActionProcessor(unittest.TestCase):
    """Tests for apply_action."""

    def test_place_settlement_setup(self) -> None:
        """PlaceSettlement places building, decrements inventory, adds VP."""
        state = _make_2p_state()
        result = apply_action(state, PlaceSettlement(player_index=0, vertex_id=5))
        self.assertTrue(result.success)
        assert result.updated_state is not None
        new = result.updated_state
        self.assertEqual(new.board.vertices[5].building.player_index, 0)
        self.assertEqual(new.players[0].build_inventory.settlements_remaining, 4)
        self.assertEqual(new.players[0].victory_points, 1)

    def test_place_settlement_sets_place_road_pending(self) -> None:
        """After setup settlement, pending action is PLACE_ROAD."""
        state = _make_2p_state()
        result = apply_action(state, PlaceSettlement(player_index=0, vertex_id=5))
        self.assertTrue(result.success)
        assert result.updated_state is not None
        self.assertEqual(
            result.updated_state.turn_state.pending_action,
            PendingActionType.PLACE_ROAD,
        )

    def test_place_settlement_distance_rule_rejected(self) -> None:
        """Can't place settlement adjacent to existing building."""
        state = _make_2p_state()
        result1 = apply_action(state, PlaceSettlement(player_index=0, vertex_id=0))
        self.assertTrue(result1.success)
        assert result1.updated_state is not None
        state2 = result1.updated_state
        adjacent_vertex = state2.board.vertices[0].adjacent_vertex_ids[0]
        # Try placing at adjacent vertex (should fail after road placed).
        result2 = apply_action(
            state2, PlaceSettlement(player_index=0, vertex_id=adjacent_vertex)
        )
        self.assertFalse(result2.success)

    def test_place_settlement_setup_forward_no_resources(self) -> None:
        """During SETUP_FORWARD, placing settlement does not award resources."""
        state = _make_2p_state()
        self.assertEqual(state.phase, GamePhase.SETUP_FORWARD)
        # Record initial resource count
        initial_resources = state.players[0].resources.total()
        # Place settlement
        result = apply_action(state, PlaceSettlement(player_index=0, vertex_id=5))
        self.assertTrue(result.success)
        assert result.updated_state is not None
        # Resources should not change
        final_resources = result.updated_state.players[0].resources.total()
        self.assertEqual(initial_resources, final_resources)

    def test_place_settlement_setup_backward_awards_resources(self) -> None:
        """During SETUP_BACKWARD, placing settlement awards initial resources."""
        state = _make_2p_state()
        # Advance through SETUP_FORWARD to reach SETUP_BACKWARD
        # Player 0 places first settlement and road
        state = _place_setup_settlement(state, 0)
        road_edge = state.board.vertices[0].adjacent_edge_ids[0]
        result = apply_action(state, PlaceRoad(player_index=0, edge_id=road_edge))
        assert result.success and result.updated_state is not None
        state = result.updated_state

        # Player 1 places first settlement and road
        state = _place_setup_settlement(state, 10)
        road_edge = state.board.vertices[10].adjacent_edge_ids[0]
        result = apply_action(state, PlaceRoad(player_index=1, edge_id=road_edge))
        assert result.success and result.updated_state is not None
        state = result.updated_state

        # Now we should be in SETUP_BACKWARD with player 1
        self.assertEqual(state.phase, GamePhase.SETUP_BACKWARD)
        self.assertEqual(state.turn_state.player_index, 1)

        # Record initial resource count for player 1
        initial_resources = state.players[1].resources.total()

        # Place second settlement for player 1
        result = apply_action(state, PlaceSettlement(player_index=1, vertex_id=15))
        self.assertTrue(result.success)
        assert result.updated_state is not None

        # Resources should have increased
        final_resources = result.updated_state.players[1].resources.total()
        self.assertGreater(final_resources, initial_resources)

    def test_place_settlement_setup_backward_correct_resource_types(self) -> None:
        """Resources awarded match adjacent tiles (excluding desert)."""
        state = _make_2p_state()
        # Advance through SETUP_FORWARD to SETUP_BACKWARD
        # Player 0 places
        state = _place_setup_settlement(state, 0)
        road_edge = state.board.vertices[0].adjacent_edge_ids[0]
        result = apply_action(state, PlaceRoad(player_index=0, edge_id=road_edge))
        assert result.success and result.updated_state is not None
        state = result.updated_state

        # Player 1 places
        state = _place_setup_settlement(state, 10)
        road_edge = state.board.vertices[10].adjacent_edge_ids[0]
        result = apply_action(state, PlaceRoad(player_index=1, edge_id=road_edge))
        assert result.success and result.updated_state is not None
        state = result.updated_state

        # Now in SETUP_BACKWARD - place second settlement
        vertex_id = 15
        vertex = state.board.vertices[vertex_id]

        # Count non-desert tiles adjacent to this vertex
        non_desert_tiles = 0
        for tile_idx in vertex.adjacent_tile_indices:
            tile = state.board.tiles[tile_idx]
            if tile.tile_type != TileType.DESERT:
                non_desert_tiles += 1

        initial_resources = state.players[1].resources.total()
        result = apply_action(
            state, PlaceSettlement(player_index=1, vertex_id=vertex_id)
        )
        assert result.success and result.updated_state is not None
        final_resources = result.updated_state.players[1].resources.total()

        # Should receive exactly one resource per non-desert tile
        self.assertEqual(final_resources - initial_resources, non_desert_tiles)

    def test_place_road_setup_advances_turn(self) -> None:
        """After placing a road in setup, turn advances to next player."""
        state = _make_2p_state()
        state = _place_setup_settlement(state, 0)
        road_edge = state.board.vertices[0].adjacent_edge_ids[0]
        result = apply_action(state, PlaceRoad(player_index=0, edge_id=road_edge))
        self.assertTrue(result.success)
        assert result.updated_state is not None
        # After setup road, player 1 should be up.
        self.assertEqual(result.updated_state.turn_state.player_index, 1)

    def test_place_road_decrements_inventory(self) -> None:
        """Placing a road decrements roads_remaining."""
        state = _make_2p_state()
        state = _place_setup_settlement(state, 0)
        road_edge = state.board.vertices[0].adjacent_edge_ids[0]
        result = apply_action(state, PlaceRoad(player_index=0, edge_id=road_edge))
        self.assertTrue(result.success)
        assert result.updated_state is not None
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
        assert result.updated_state is not None
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
        assert result.updated_state is not None
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
        assert result.updated_state is not None
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
        assert result.updated_state is not None
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
        assert result.updated_state is not None
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
        assert target_tile is not None
        tile_idx = board.tiles.index(target_tile)

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
            for i, _t in enumerate(board.tiles):
                if i != tile_idx:
                    board.robber_tile_index = i
                    break

        roll = target_tile.number_token
        assert roll is not None
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
        assert result.updated_state is not None
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
        assert result.updated_state is not None
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
        assert result.updated_state is not None
        # dev_cards should now have the knight; new_dev_cards cleared.
        self.assertEqual(result.updated_state.players[0].dev_cards.knight, 1)
        self.assertEqual(result.updated_state.players[0].new_dev_cards.knight, 0)


if __name__ == '__main__':
    unittest.main()
