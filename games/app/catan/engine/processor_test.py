"""Unit tests for the Catan action processor."""

from __future__ import annotations

import unittest

from games.app.catan.engine import processor, turn_manager
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestActionProcessor(unittest.TestCase):
    """Tests for apply_action."""

    def test_place_settlement_setup(self) -> None:
        """PlaceSettlement places building, decrements inventory, adds VP."""
        state = _make_2p_state()
        result = processor.apply_action(
            state, actions.PlaceSettlement(player_index=0, vertex_id=5)
        )
        self.assertTrue(result.success)
        assert result.updated_state is not None
        new = result.updated_state
        self.assertEqual(new.board.vertices[5].building.player_index, 0)
        self.assertEqual(new.players[0].build_inventory.settlements_remaining, 4)
        self.assertEqual(new.players[0].victory_points, 1)

    def test_place_settlement_sets_place_road_pending(self) -> None:
        """After setup settlement, pending action is PLACE_ROAD."""
        state = _make_2p_state()
        result = processor.apply_action(
            state, actions.PlaceSettlement(player_index=0, vertex_id=5)
        )
        self.assertTrue(result.success)
        assert result.updated_state is not None
        self.assertEqual(
            result.updated_state.turn_state.pending_action,
            game_state.PendingActionType.PLACE_ROAD,
        )

    def test_place_settlement_distance_rule_rejected(self) -> None:
        """Can't place settlement adjacent to existing building."""
        state = _make_2p_state()
        result1 = processor.apply_action(
            state, actions.PlaceSettlement(player_index=0, vertex_id=0)
        )
        self.assertTrue(result1.success)
        assert result1.updated_state is not None
        state2 = result1.updated_state
        adjacent_vertex = state2.board.vertices[0].adjacent_vertex_ids[0]
        # Try placing at adjacent vertex (should fail after road placed).
        result2 = processor.apply_action(
            state2, actions.PlaceSettlement(player_index=0, vertex_id=adjacent_vertex)
        )
        self.assertFalse(result2.success)

    def test_place_settlement_setup_forward_no_resources(self) -> None:
        """During SETUP_FORWARD, placing settlement does not award resources."""
        state = _make_2p_state()
        self.assertEqual(state.phase, game_state.GamePhase.SETUP_FORWARD)
        # Record initial resource count
        initial_resources = state.players[0].resources.total()
        # Place settlement
        result = processor.apply_action(
            state, actions.PlaceSettlement(player_index=0, vertex_id=5)
        )
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
        result = processor.apply_action(
            state, actions.PlaceRoad(player_index=0, edge_id=road_edge)
        )
        assert result.success and result.updated_state is not None
        state = result.updated_state

        # Player 1 places first settlement and road
        state = _place_setup_settlement(state, 10)
        road_edge = state.board.vertices[10].adjacent_edge_ids[0]
        result = processor.apply_action(
            state, actions.PlaceRoad(player_index=1, edge_id=road_edge)
        )
        assert result.success and result.updated_state is not None
        state = result.updated_state

        # Now we should be in SETUP_BACKWARD with player 1
        self.assertEqual(state.phase, game_state.GamePhase.SETUP_BACKWARD)
        self.assertEqual(state.turn_state.player_index, 1)

        # Record initial resource count for player 1
        initial_resources = state.players[1].resources.total()

        # Place second settlement for player 1
        result = processor.apply_action(
            state, actions.PlaceSettlement(player_index=1, vertex_id=15)
        )
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
        result = processor.apply_action(
            state, actions.PlaceRoad(player_index=0, edge_id=road_edge)
        )
        assert result.success and result.updated_state is not None
        state = result.updated_state

        # Player 1 places
        state = _place_setup_settlement(state, 10)
        road_edge = state.board.vertices[10].adjacent_edge_ids[0]
        result = processor.apply_action(
            state, actions.PlaceRoad(player_index=1, edge_id=road_edge)
        )
        assert result.success and result.updated_state is not None
        state = result.updated_state

        # Now in SETUP_BACKWARD - place second settlement
        vertex_id = 15
        vertex = state.board.vertices[vertex_id]

        # Count non-desert tiles adjacent to this vertex
        non_desert_tiles = 0
        for tile_idx in vertex.adjacent_tile_indices:
            tile = state.board.tiles[tile_idx]
            if tile.tile_type != board.TileType.DESERT:
                non_desert_tiles += 1

        initial_resources = state.players[1].resources.total()
        result = processor.apply_action(
            state, actions.PlaceSettlement(player_index=1, vertex_id=vertex_id)
        )
        assert result.success and result.updated_state is not None
        final_resources = result.updated_state.players[1].resources.total()

        # Should receive exactly one resource per non-desert tile
        self.assertEqual(final_resources - initial_resources, non_desert_tiles)

    def test_place_settlement_normal_play_deducts_resources(self) -> None:
        """During normal play, placing a settlement deducts settlement cost."""
        state = _make_2p_state()
        state.phase = game_state.GamePhase.MAIN
        state.turn_state = game_state.TurnState(
            player_index=0, pending_action=game_state.PendingActionType.BUILD_OR_TRADE
        )
        state.players[0].resources = player.Resources(wood=1, brick=1, wheat=1, sheep=1)
        result = processor.apply_action(
            state, actions.PlaceSettlement(player_index=0, vertex_id=5)
        )
        self.assertTrue(result.success)
        assert result.updated_state is not None
        res = result.updated_state.players[0].resources
        self.assertEqual(res.wood, 0)
        self.assertEqual(res.brick, 0)
        self.assertEqual(res.wheat, 0)
        self.assertEqual(res.sheep, 0)

    def test_place_settlement_normal_play_insufficient_resources(self) -> None:
        """During normal play, placing a settlement without resources fails."""
        state = _make_2p_state()
        state.phase = game_state.GamePhase.MAIN
        state.turn_state = game_state.TurnState(
            player_index=0, pending_action=game_state.PendingActionType.BUILD_OR_TRADE
        )
        state.players[0].resources = player.Resources()
        result = processor.apply_action(
            state, actions.PlaceSettlement(player_index=0, vertex_id=5)
        )
        self.assertFalse(result.success)
        self.assertIn('Insufficient', result.error_message or '')

    def test_place_road_setup_advances_turn(self) -> None:
        """After placing a road in setup, turn advances to next player."""
        state = _make_2p_state()
        state = _place_setup_settlement(state, 0)
        road_edge = state.board.vertices[0].adjacent_edge_ids[0]
        result = processor.apply_action(
            state, actions.PlaceRoad(player_index=0, edge_id=road_edge)
        )
        self.assertTrue(result.success)
        assert result.updated_state is not None
        # After setup road, player 1 should be up.
        self.assertEqual(result.updated_state.turn_state.player_index, 1)

    def test_place_road_decrements_inventory(self) -> None:
        """Placing a road decrements roads_remaining."""
        state = _make_2p_state()
        state = _place_setup_settlement(state, 0)
        road_edge = state.board.vertices[0].adjacent_edge_ids[0]
        result = processor.apply_action(
            state, actions.PlaceRoad(player_index=0, edge_id=road_edge)
        )
        self.assertTrue(result.success)
        assert result.updated_state is not None
        self.assertEqual(
            result.updated_state.players[0].build_inventory.roads_remaining, 14
        )

    def test_roll_dice_sets_roll_value(self) -> None:
        """RollDice records a roll between 2 and 12 inclusive."""
        state = _make_2p_state()
        state.phase = game_state.GamePhase.MAIN
        state.turn_state = game_state.TurnState(
            player_index=0, pending_action=game_state.PendingActionType.ROLL_DICE
        )
        result = processor.apply_action(state, actions.RollDice(player_index=0))
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
        state.phase = game_state.GamePhase.MAIN
        state.turn_state = game_state.TurnState(
            player_index=0, pending_action=game_state.PendingActionType.ROLL_DICE
        )
        # Force a roll of 7.
        with unittest.mock.patch('random.randint', side_effect=[4, 3]):
            result = processor.apply_action(state, actions.RollDice(player_index=0))
        self.assertTrue(result.success)
        assert result.updated_state is not None
        self.assertEqual(
            result.updated_state.turn_state.pending_action,
            game_state.PendingActionType.MOVE_ROBBER,
        )

    def test_roll_7_large_hand_triggers_discard(self) -> None:
        """When a player holds >7 cards, rolling 7 requires discarding."""
        import unittest.mock

        state = _make_2p_state()
        state.phase = game_state.GamePhase.MAIN
        state.turn_state = game_state.TurnState(
            player_index=0, pending_action=game_state.PendingActionType.ROLL_DICE
        )
        state.players[1].resources = player.Resources(
            wood=2, brick=2, wheat=2, sheep=2, ore=2
        )  # 10 cards
        with unittest.mock.patch('random.randint', side_effect=[4, 3]):
            result = processor.apply_action(state, actions.RollDice(player_index=0))
        self.assertTrue(result.success)
        assert result.updated_state is not None
        self.assertEqual(
            result.updated_state.turn_state.pending_action,
            game_state.PendingActionType.DISCARD_RESOURCES,
        )
        self.assertIn(1, result.updated_state.turn_state.discard_player_indices)

    def test_discard_clears_player_from_list(self) -> None:
        """Discarding removes player from discard_player_indices."""
        state = _make_2p_state()
        state.phase = game_state.GamePhase.MAIN
        state.turn_state = game_state.TurnState(
            player_index=0,
            pending_action=game_state.PendingActionType.DISCARD_RESOURCES,
            discard_player_indices=[1],
        )
        state.players[1].resources = player.Resources(
            wood=4, brick=4, wheat=2
        )  # 10 cards
        result = processor.apply_action(
            state,
            actions.DiscardResources(player_index=1, resources={'wood': 3, 'brick': 2}),
        )
        self.assertTrue(result.success)
        assert result.updated_state is not None
        self.assertNotIn(1, result.updated_state.turn_state.discard_player_indices)

    def test_discard_all_done_moves_to_move_robber(self) -> None:
        """After last player discards, pending becomes MOVE_ROBBER."""
        state = _make_2p_state()
        state.phase = game_state.GamePhase.MAIN
        state.turn_state = game_state.TurnState(
            player_index=0,
            pending_action=game_state.PendingActionType.DISCARD_RESOURCES,
            discard_player_indices=[1],
        )
        state.players[1].resources = player.Resources(wood=4, brick=4, wheat=2)
        result = processor.apply_action(
            state,
            actions.DiscardResources(player_index=1, resources={'wood': 3, 'brick': 2}),
        )
        self.assertTrue(result.success)
        assert result.updated_state is not None
        self.assertEqual(
            result.updated_state.turn_state.pending_action,
            game_state.PendingActionType.MOVE_ROBBER,
        )

    def test_resource_distribution_on_roll(self) -> None:
        """Rolling a tile's number awards resources to adjacent buildings."""
        state = _make_2p_state()
        state.phase = game_state.GamePhase.MAIN
        # Find a non-desert tile with a number token.
        game_board = state.board
        target_tile = next(
            (t for t in game_board.tiles if t.number_token is not None),
            None,
        )
        self.assertIsNotNone(target_tile)
        assert target_tile is not None
        tile_idx = game_board.tiles.index(target_tile)

        adj_vertices = [
            v for v in game_board.vertices if tile_idx in v.adjacent_tile_indices
        ]
        self.assertGreater(len(adj_vertices), 0)
        target_vertex = adj_vertices[0]
        game_board.vertices[target_vertex.vertex_id].building = board.Building(
            player_index=0, building_type=board.BuildingType.SETTLEMENT
        )

        # Make sure the robber is not on the target tile.
        if game_board.robber_tile_index == tile_idx:
            for i, _t in enumerate(game_board.tiles):
                if i != tile_idx:
                    game_board.robber_tile_index = i
                    break

        roll = target_tile.number_token
        assert roll is not None
        import unittest.mock

        state.turn_state = game_state.TurnState(
            player_index=0, pending_action=game_state.PendingActionType.ROLL_DICE
        )
        with unittest.mock.patch(
            'random.randint',
            side_effect=[roll - 1, 1],  # sum == roll
        ):
            result = processor.apply_action(state, actions.RollDice(player_index=0))

        self.assertTrue(result.success)
        assert result.updated_state is not None

        expected_resource = board.TILE_RESOURCE.get(target_tile.tile_type)
        if expected_resource is not None:
            total_received = result.updated_state.players[0].resources.get(
                expected_resource
            )
            self.assertGreater(total_received, 0)

    def test_original_state_not_modified(self) -> None:
        """apply_action must not mutate the original game state."""
        state = _make_2p_state()
        original_player0_vp = state.players[0].victory_points
        processor.apply_action(
            state, actions.PlaceSettlement(player_index=0, vertex_id=0)
        )
        self.assertEqual(state.players[0].victory_points, original_player0_vp)

    def test_victory_detected_on_apply(self) -> None:
        """apply_action sets phase=ENDED when a player reaches 10 VP."""
        state = _make_2p_state()
        state.players[0].victory_points = 9
        state.phase = game_state.GamePhase.MAIN
        state.turn_state = game_state.TurnState(
            player_index=0, pending_action=game_state.PendingActionType.BUILD_OR_TRADE
        )
        # Give player resources for a settlement and connect a road.

        state.players[0].resources = player.Resources(wood=1, brick=1, wheat=1, sheep=1)
        # Place an existing road so player can build settlement.
        game_board = state.board
        edge = game_board.edges[0]
        game_board.edges[0].road = board.Road(player_index=0)
        # Find a connected, empty vertex.
        for vid in edge.vertex_ids:
            vertex = game_board.vertices[vid]
            if vertex.building is None and all(
                game_board.vertices[adj].building is None
                for adj in vertex.adjacent_vertex_ids
            ):
                target_vid = vid
                break
        else:
            self.skipTest('No valid vertex found for this test.')
        result = processor.apply_action(
            state, actions.PlaceSettlement(player_index=0, vertex_id=target_vid)
        )
        self.assertTrue(result.success)
        assert result.updated_state is not None
        self.assertEqual(result.updated_state.phase, game_state.GamePhase.ENDED)
        self.assertEqual(result.updated_state.winner_index, 0)

    def test_end_turn_moves_new_dev_cards(self) -> None:
        """EndTurn moves new_dev_cards into dev_cards."""
        state = _make_2p_state()
        state.phase = game_state.GamePhase.MAIN
        state.turn_state = game_state.TurnState(
            player_index=0, pending_action=game_state.PendingActionType.BUILD_OR_TRADE
        )
        state.players[0].new_dev_cards = player.DevCardHand(knight=1)
        result = processor.apply_action(state, actions.EndTurn(player_index=0))
        self.assertTrue(result.success)
        assert result.updated_state is not None
        # dev_cards should now have the knight; new_dev_cards cleared.
        self.assertEqual(result.updated_state.players[0].dev_cards.knight, 1)
        self.assertEqual(result.updated_state.players[0].new_dev_cards.knight, 0)

    def test_setup_second_road_must_connect_to_second_settlement(self) -> None:
        """During setup, second road must connect to second settlement."""
        state = _make_2p_state()

        # Player 0: Place first settlement and road
        state = _place_setup_settlement(state, 0)
        first_settlement_vertex = 0
        vertex = state.board.vertices[first_settlement_vertex]
        first_road_edge = vertex.adjacent_edge_ids[0]
        result = processor.apply_action(
            state, actions.PlaceRoad(player_index=0, edge_id=first_road_edge)
        )
        self.assertTrue(result.success)
        assert result.updated_state is not None
        state = result.updated_state

        # Player 1: Place first settlement and road
        state = _place_setup_settlement(state, 10)
        player1_road_edge = state.board.vertices[10].adjacent_edge_ids[0]
        result = processor.apply_action(
            state, actions.PlaceRoad(player_index=1, edge_id=player1_road_edge)
        )
        self.assertTrue(result.success)
        assert result.updated_state is not None
        state = result.updated_state

        # Now in SETUP_BACKWARD, player 1 places second settlement
        state = _place_setup_settlement(state, 20)
        second_settlement_vertex = 20
        v = state.board.vertices[second_settlement_vertex]
        player1_second_road = v.adjacent_edge_ids[0]
        result = processor.apply_action(
            state, actions.PlaceRoad(player_index=1, edge_id=player1_second_road)
        )
        self.assertTrue(result.success)
        assert result.updated_state is not None
        state = result.updated_state

        # Player 0: Place second settlement at a different location
        state = _place_setup_settlement(state, 30)
        second_settlement_vertex = 30

        # Get edges adjacent to both settlements
        v1 = state.board.vertices[first_settlement_vertex]
        first_settlement_edges = set(v1.adjacent_edge_ids)
        v2 = state.board.vertices[second_settlement_vertex]
        second_settlement_edges = set(v2.adjacent_edge_ids)

        # Find edge only adjacent to first settlement (not second)
        first_only_edges = first_settlement_edges - second_settlement_edges
        if first_only_edges:
            invalid_edge = next(iter(first_only_edges))
            # Make sure this edge doesn't already have a road
            if state.board.edges[invalid_edge].road is None:
                result = processor.apply_action(
                    state, actions.PlaceRoad(player_index=0, edge_id=invalid_edge)
                )
                self.assertFalse(result.success)
                assert result.error_message is not None
                self.assertIn('most recently placed settlement', result.error_message)

        # Place road adjacent to second settlement - should succeed
        valid_edge = None
        for edge_id in second_settlement_edges:
            if state.board.edges[edge_id].road is None:
                valid_edge = edge_id
                break
        assert valid_edge is not None
        result = processor.apply_action(
            state, actions.PlaceRoad(player_index=0, edge_id=valid_edge)
        )
        self.assertTrue(result.success)


# ---------------------------------------------------------------------------
# Event-generation tests
# ---------------------------------------------------------------------------


class TestActionProcessorEvents(unittest.TestCase):
    """Tests that apply_action populates recent_events correctly."""

    def test_place_settlement_emits_event(self) -> None:
        """PlaceSettlement appends a settlement event."""
        state = _make_2p_state()
        result = processor.apply_action(
            state, actions.PlaceSettlement(player_index=0, vertex_id=5)
        )
        self.assertTrue(result.success)
        assert result.updated_state is not None
        events = result.updated_state.recent_events
        self.assertEqual(len(events), 1)
        self.assertIn('Alice', events[0])
        self.assertIn('settlement', events[0])

    def test_place_road_emits_event(self) -> None:
        """PlaceRoad appends a road event."""
        state = _make_2p_state()
        state = _place_setup_settlement(state, 0)
        edge_id = state.board.vertices[0].adjacent_edge_ids[0]
        result = processor.apply_action(
            state, actions.PlaceRoad(player_index=0, edge_id=edge_id)
        )
        self.assertTrue(result.success)
        assert result.updated_state is not None
        events = result.updated_state.recent_events
        self.assertTrue(any('road' in e for e in events))

    def test_place_city_emits_event(self) -> None:
        """PlaceCity appends a city event."""
        state = _make_2p_state()
        state.phase = game_state.GamePhase.MAIN
        state.turn_state = game_state.TurnState(
            player_index=0, pending_action=game_state.PendingActionType.BUILD_OR_TRADE
        )
        # Place a settlement first
        state.board.vertices[3].building = board.Building(
            player_index=0, building_type=board.BuildingType.SETTLEMENT
        )
        state.players[0].resources = player.Resources(wheat=2, ore=3)
        result = processor.apply_action(
            state, actions.PlaceCity(player_index=0, vertex_id=3)
        )
        self.assertTrue(result.success)
        assert result.updated_state is not None
        events = result.updated_state.recent_events
        self.assertTrue(any('city' in e for e in events))

    def test_roll_dice_emits_roll_event(self) -> None:
        """RollDice appends a dice-roll event."""
        state = _make_2p_state()
        state.phase = game_state.GamePhase.MAIN
        state.turn_state = game_state.TurnState(
            player_index=0, pending_action=game_state.PendingActionType.ROLL_DICE
        )
        result = processor.apply_action(state, actions.RollDice(player_index=0))
        self.assertTrue(result.success)
        assert result.updated_state is not None
        events = result.updated_state.recent_events
        roll_events = [e for e in events if 'rolled' in e]
        self.assertEqual(len(roll_events), 1)
        self.assertIn('Alice', roll_events[0])

    def test_roll_7_emits_robber_event(self) -> None:
        """Rolling 7 appends a robber-activation event."""
        import unittest.mock

        state = _make_2p_state()
        state.phase = game_state.GamePhase.MAIN
        state.turn_state = game_state.TurnState(
            player_index=0, pending_action=game_state.PendingActionType.ROLL_DICE
        )
        with unittest.mock.patch('random.randint', side_effect=[4, 3]):
            result = processor.apply_action(state, actions.RollDice(player_index=0))
        self.assertTrue(result.success)
        assert result.updated_state is not None
        events = result.updated_state.recent_events
        self.assertTrue(any('robber' in e.lower() for e in events))

    def test_roll_non_7_emits_resource_events(self) -> None:
        """A non-7 roll that distributes resources appends per-player gain events."""
        import unittest.mock

        state = _make_2p_state()
        state.phase = game_state.GamePhase.MAIN

        # Find a tile with a number token and place a settlement on it.
        game_board = state.board
        target_tile = next(t for t in game_board.tiles if t.number_token is not None)
        tile_idx = game_board.tiles.index(target_tile)
        adj_vertex = next(
            v for v in game_board.vertices if tile_idx in v.adjacent_tile_indices
        )
        game_board.vertices[adj_vertex.vertex_id].building = board.Building(
            player_index=0, building_type=board.BuildingType.SETTLEMENT
        )
        # Ensure robber is not on the target tile.
        if game_board.robber_tile_index == tile_idx:
            game_board.robber_tile_index = next(
                i for i, _ in enumerate(game_board.tiles) if i != tile_idx
            )

        roll = target_tile.number_token
        assert roll is not None
        state.turn_state = game_state.TurnState(
            player_index=0, pending_action=game_state.PendingActionType.ROLL_DICE
        )
        with unittest.mock.patch('random.randint', side_effect=[roll - 1, 1]):
            result = processor.apply_action(state, actions.RollDice(player_index=0))

        self.assertTrue(result.success)
        assert result.updated_state is not None
        events = result.updated_state.recent_events
        # At least one "received" event should be present.
        self.assertTrue(any('received' in e for e in events))

    def test_end_turn_emits_next_player_event(self) -> None:
        """EndTurn appends a turn-change event naming the next player."""
        state = _make_2p_state()
        state.phase = game_state.GamePhase.MAIN
        state.turn_state = game_state.TurnState(
            player_index=0, pending_action=game_state.PendingActionType.BUILD_OR_TRADE
        )
        result = processor.apply_action(state, actions.EndTurn(player_index=0))
        self.assertTrue(result.success)
        assert result.updated_state is not None
        events = result.updated_state.recent_events
        self.assertEqual(len(events), 1)
        # Should name the next player (Bob in a 2-player game).
        self.assertIn('Bob', events[0])
        self.assertIn('turn', events[0])

    def test_move_robber_emits_event(self) -> None:
        """MoveRobber appends a robber-move event."""
        state = _make_2p_state()
        state.phase = game_state.GamePhase.MAIN
        state.turn_state = game_state.TurnState(
            player_index=0, pending_action=game_state.PendingActionType.MOVE_ROBBER
        )
        new_tile = next(
            i
            for i in range(len(state.board.tiles))
            if i != state.board.robber_tile_index
        )
        result = processor.apply_action(
            state, actions.MoveRobber(player_index=0, tile_index=new_tile)
        )
        self.assertTrue(result.success)
        assert result.updated_state is not None
        events = result.updated_state.recent_events
        self.assertTrue(any('robber' in e for e in events))
        self.assertTrue(any('Alice' in e for e in events))

    def test_discard_emits_event(self) -> None:
        """DiscardResources appends a discard event with correct count."""
        state = _make_2p_state()
        state.phase = game_state.GamePhase.MAIN
        state.turn_state = game_state.TurnState(
            player_index=0,
            pending_action=game_state.PendingActionType.DISCARD_RESOURCES,
            discard_player_indices=[0],
        )
        state.players[0].resources = player.Resources(wood=4, brick=4, wheat=2)
        result = processor.apply_action(
            state,
            actions.DiscardResources(player_index=0, resources={'wood': 3, 'brick': 2}),
        )
        self.assertTrue(result.success)
        assert result.updated_state is not None
        events = result.updated_state.recent_events
        self.assertTrue(any('discarded' in e for e in events))
        self.assertTrue(any('5' in e for e in events))

    def test_recent_events_cleared_between_actions(self) -> None:
        """recent_events from a previous action are cleared before each new action."""
        state = _make_2p_state()
        result1 = processor.apply_action(
            state, actions.PlaceSettlement(player_index=0, vertex_id=5)
        )
        assert result1.updated_state is not None
        # First action should have exactly one settlement event.
        self.assertEqual(len(result1.updated_state.recent_events), 1)

        road_edge = result1.updated_state.board.vertices[5].adjacent_edge_ids[0]
        result2 = processor.apply_action(
            result1.updated_state,
            actions.PlaceRoad(player_index=0, edge_id=road_edge),
        )
        assert result2.updated_state is not None
        # Second action events should NOT include the settlement event.
        self.assertFalse(
            any('settlement' in e for e in result2.updated_state.recent_events)
        )

    def test_bank_trade_emits_event(self) -> None:
        """TradeWithBank appends a bank-trade event."""
        state = _make_2p_state()
        state.phase = game_state.GamePhase.MAIN
        state.turn_state = game_state.TurnState(
            player_index=0, pending_action=game_state.PendingActionType.BUILD_OR_TRADE
        )
        state.players[0].resources = player.Resources(wood=4)
        result = processor.apply_action(
            state,
            actions.TradeWithBank(
                player_index=0,
                giving=actions.ResourceType('wood'),
                receiving=actions.ResourceType('ore'),
            ),
        )
        self.assertTrue(result.success)
        assert result.updated_state is not None
        events = result.updated_state.recent_events
        self.assertTrue(any('bank' in e for e in events))
        self.assertTrue(any('Alice' in e for e in events))


class TestActionProcessorDebugLogging(unittest.TestCase):
    """Tests that verify detailed debug log messages are emitted."""

    def test_roll_dice_logs_individual_dice(self) -> None:
        """Rolling dice emits a debug log with die1, die2, and total."""
        state = _make_2p_state()
        # Advance through setup to reach MAIN phase with player 0 to roll.
        state = _setup_full_game(state)
        with self.assertLogs('games.app.catan.engine.processor', level='DEBUG') as cm:
            processor.apply_action(state, actions.RollDice(player_index=0))
        roll_logs = [m for m in cm.output if '[roll_dice]' in m]
        self.assertEqual(len(roll_logs), 1)
        self.assertIn('die1=', roll_logs[0])
        self.assertIn('die2=', roll_logs[0])
        self.assertIn('total=', roll_logs[0])

    def test_place_settlement_logs_vertex_and_player(self) -> None:
        """Placing a settlement emits a debug log with vertex and player info."""
        state = _make_2p_state()
        with self.assertLogs('games.app.catan.engine.processor', level='DEBUG') as cm:
            processor.apply_action(
                state, actions.PlaceSettlement(player_index=0, vertex_id=5)
            )
        settle_logs = [m for m in cm.output if '[place_settlement]' in m]
        self.assertGreater(len(settle_logs), 0)
        self.assertIn('vertex=5', settle_logs[0])
        self.assertIn('Alice', settle_logs[0])

    def test_place_road_logs_edge_and_road_length(self) -> None:
        """Placing a road emits a debug log with edge_id and new road length."""
        state = _make_2p_state()
        result = processor.apply_action(
            state, actions.PlaceSettlement(player_index=0, vertex_id=5)
        )
        assert result.updated_state is not None
        state2 = result.updated_state
        road_edge = state2.board.vertices[5].adjacent_edge_ids[0]
        with self.assertLogs('games.app.catan.engine.processor', level='DEBUG') as cm:
            processor.apply_action(
                state2, actions.PlaceRoad(player_index=0, edge_id=road_edge)
            )
        road_logs = [m for m in cm.output if '[place_road]' in m]
        self.assertEqual(len(road_logs), 1)
        self.assertIn(f'edge={road_edge}', road_logs[0])
        self.assertIn('new_road_length=', road_logs[0])

    def test_steal_resource_logs_stolen_resource(self) -> None:
        """Stealing a resource emits a debug log naming the stolen resource."""
        state = _make_2p_state()
        state = _setup_full_game(state)
        # Give Bob a resource so Alice can steal it.
        state.players[1].resources = player.Resources(wood=1)
        state.turn_state.pending_action = game_state.PendingActionType.STEAL_RESOURCE
        state.board.robber_tile_index = 0
        # Place Bob's settlement adjacent to tile 0 so steal is legal.
        for vertex in state.board.vertices:
            if 0 in vertex.adjacent_tile_indices and vertex.building is None:
                vertex.building = board.Building(
                    player_index=1, building_type=board.BuildingType.SETTLEMENT
                )
                break
        with self.assertLogs('games.app.catan.engine.processor', level='DEBUG') as cm:
            processor.apply_action(
                state,
                actions.StealResource(player_index=0, target_player_index=1),
            )
        steal_logs = [m for m in cm.output if '[steal_resource]' in m]
        self.assertEqual(len(steal_logs), 1)
        self.assertIn('Alice', steal_logs[0])
        self.assertIn('Bob', steal_logs[0])


def _setup_full_game(state: game_state.GameState) -> game_state.GameState:
    """Advance a 2-player game through the entire setup phase to MAIN/ROLL_DICE."""
    # Forward: player 0 settlement + road, player 1 settlement + road
    # Backward: player 1 settlement + road, player 0 settlement + road
    for vertex_id in [0, 10, 20, 30]:
        player_idx = state.turn_state.player_index
        result = processor.apply_action(
            state, actions.PlaceSettlement(player_index=player_idx, vertex_id=vertex_id)
        )
        assert result.success and result.updated_state is not None
        state = result.updated_state
        # Place road on first available adjacent edge.
        road_edges = state.board.vertices[vertex_id].adjacent_edge_ids
        for edge_id in road_edges:
            if state.board.edges[edge_id].road is None:
                result = processor.apply_action(
                    state, actions.PlaceRoad(player_index=player_idx, edge_id=edge_id)
                )
                assert result.success and result.updated_state is not None
                state = result.updated_state
                break
        if state.phase == game_state.GamePhase.MAIN:
            break
    return state


if __name__ == '__main__':
    unittest.main()
