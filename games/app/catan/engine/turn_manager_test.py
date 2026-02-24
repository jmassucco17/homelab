"""Unit tests for the Catan turn manager."""

from __future__ import annotations

import unittest

from games.app.catan.engine import processor, turn_manager
from games.app.catan.models import actions, game_state

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


class TestTurnManager(unittest.TestCase):
    """Tests for create_initial_game_state, advance_turn, etc."""

    def test_create_initial_state_player_count(self) -> None:
        """Initial state has the correct number of players."""
        state = turn_manager.create_initial_game_state(['A', 'B', 'C'], ['r', 'g', 'b'])
        self.assertEqual(len(state.players), 3)

    def test_create_initial_state_phase(self) -> None:
        """Initial state starts in SETUP_FORWARD phase."""
        state = _make_2p_state()
        self.assertEqual(state.phase, game_state.GamePhase.SETUP_FORWARD)

    def test_create_initial_state_pending_action(self) -> None:
        """Player 0 starts with PLACE_SETTLEMENT pending."""
        state = _make_2p_state()
        self.assertEqual(
            state.turn_state.pending_action,
            game_state.PendingActionType.PLACE_SETTLEMENT,
        )
        self.assertEqual(state.turn_state.player_index, 0)

    def test_create_initial_state_deck_size(self) -> None:
        """Dev card deck starts with 25 cards."""
        state = _make_2p_state()
        self.assertEqual(len(state.dev_card_deck), 25)

    def test_setup_forward_advances_player(self) -> None:
        """In SETUP_FORWARD, advance_turn moves to the next player."""
        state = _make_2p_state()
        state.turn_state = game_state.TurnState(
            player_index=0, pending_action=game_state.PendingActionType.PLACE_SETTLEMENT
        )
        turn_manager.advance_turn(state)
        self.assertEqual(state.turn_state.player_index, 1)
        self.assertEqual(state.phase, game_state.GamePhase.SETUP_FORWARD)

    def test_setup_forward_last_player_switches_backward(self) -> None:
        """Last player in SETUP_FORWARD flips phase to SETUP_BACKWARD."""
        state = _make_2p_state()
        state.turn_state = game_state.TurnState(
            player_index=1, pending_action=game_state.PendingActionType.PLACE_SETTLEMENT
        )
        turn_manager.advance_turn(state)
        self.assertEqual(state.phase, game_state.GamePhase.SETUP_BACKWARD)
        self.assertEqual(state.turn_state.player_index, 1)

    def test_setup_backward_decrements_player(self) -> None:
        """In SETUP_BACKWARD, advance_turn moves to the previous player."""
        state = _make_2p_state()
        state.phase = game_state.GamePhase.SETUP_BACKWARD
        state.turn_state = game_state.TurnState(
            player_index=1, pending_action=game_state.PendingActionType.PLACE_SETTLEMENT
        )
        turn_manager.advance_turn(state)
        self.assertEqual(state.turn_state.player_index, 0)
        self.assertEqual(state.phase, game_state.GamePhase.SETUP_BACKWARD)

    def test_setup_backward_first_player_starts_main(self) -> None:
        """Player 0 finishing SETUP_BACKWARD transitions to MAIN phase."""
        state = _make_2p_state()
        state.phase = game_state.GamePhase.SETUP_BACKWARD
        state.turn_state = game_state.TurnState(
            player_index=0, pending_action=game_state.PendingActionType.PLACE_SETTLEMENT
        )
        turn_manager.advance_turn(state)
        self.assertEqual(state.phase, game_state.GamePhase.MAIN)
        self.assertEqual(state.turn_state.player_index, 0)
        self.assertEqual(
            state.turn_state.pending_action, game_state.PendingActionType.ROLL_DICE
        )
        self.assertEqual(state.turn_number, 1)

    def test_main_advance_cycles_players(self) -> None:
        """In MAIN phase, advance_turn cycles player indices."""
        state = _make_2p_state()
        state.phase = game_state.GamePhase.MAIN
        state.turn_number = 1
        state.turn_state = game_state.TurnState(
            player_index=0, pending_action=game_state.PendingActionType.BUILD_OR_TRADE
        )
        turn_manager.advance_turn(state)
        self.assertEqual(state.turn_state.player_index, 1)

    def test_main_advance_wraps_and_increments_turn(self) -> None:
        """In MAIN phase, wrapping from last to first player increments turn_number."""
        state = _make_2p_state()
        state.phase = game_state.GamePhase.MAIN
        state.turn_number = 1
        state.turn_state = game_state.TurnState(
            player_index=1, pending_action=game_state.PendingActionType.BUILD_OR_TRADE
        )
        turn_manager.advance_turn(state)
        self.assertEqual(state.turn_state.player_index, 0)
        self.assertEqual(state.turn_number, 2)

    def test_get_next_setup_player_forward(self) -> None:
        """get_next_setup_player increments index in SETUP_FORWARD."""
        idx, phase = turn_manager.get_next_setup_player(
            0, 4, game_state.GamePhase.SETUP_FORWARD
        )
        self.assertEqual(idx, 1)
        self.assertEqual(phase, game_state.GamePhase.SETUP_FORWARD)

    def test_get_next_setup_player_forward_last(self) -> None:
        """Last player in SETUP_FORWARD switches to SETUP_BACKWARD."""
        idx, phase = turn_manager.get_next_setup_player(
            3, 4, game_state.GamePhase.SETUP_FORWARD
        )
        self.assertEqual(idx, 3)
        self.assertEqual(phase, game_state.GamePhase.SETUP_BACKWARD)

    def test_get_next_setup_player_backward(self) -> None:
        """get_next_setup_player decrements index in SETUP_BACKWARD."""
        idx, phase = turn_manager.get_next_setup_player(
            2, 4, game_state.GamePhase.SETUP_BACKWARD
        )
        self.assertEqual(idx, 1)
        self.assertEqual(phase, game_state.GamePhase.SETUP_BACKWARD)

    def test_get_next_setup_player_backward_first(self) -> None:
        """Player 0 finishing SETUP_BACKWARD returns MAIN phase."""
        idx, phase = turn_manager.get_next_setup_player(
            0, 4, game_state.GamePhase.SETUP_BACKWARD
        )
        self.assertEqual(idx, 0)
        self.assertEqual(phase, game_state.GamePhase.MAIN)

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

        self.assertEqual(state.phase, game_state.GamePhase.MAIN)
        self.assertEqual(state.turn_state.player_index, 0)
        self.assertEqual(
            state.turn_state.pending_action, game_state.PendingActionType.ROLL_DICE
        )

    def test_create_initial_state_with_ai_types(self) -> None:
        """AI types are properly assigned to players when specified."""
        state = turn_manager.create_initial_game_state(
            ['Alice', 'AI Easy', 'Bob'],
            ['red', 'blue', 'green'],
            ai_types=[None, 'easy', None],
        )
        self.assertEqual(len(state.players), 3)
        self.assertFalse(state.players[0].is_ai)
        self.assertIsNone(state.players[0].ai_type)
        self.assertTrue(state.players[1].is_ai)
        self.assertEqual(state.players[1].ai_type, 'easy')
        self.assertFalse(state.players[2].is_ai)
        self.assertIsNone(state.players[2].ai_type)

    def test_create_initial_state_without_ai_types(self) -> None:
        """When ai_types is not provided, all players are human."""
        state = turn_manager.create_initial_game_state(
            ['Alice', 'Bob'], ['red', 'blue']
        )
        self.assertEqual(len(state.players), 2)
        self.assertFalse(state.players[0].is_ai)
        self.assertIsNone(state.players[0].ai_type)
        self.assertFalse(state.players[1].is_ai)
        self.assertIsNone(state.players[1].ai_type)

    def test_create_initial_state_all_ai_players(self) -> None:
        """All players can be AI with different difficulty levels."""
        state = turn_manager.create_initial_game_state(
            ['AI Easy', 'AI Medium', 'AI Hard'],
            ['red', 'blue', 'green'],
            ai_types=['easy', 'medium', 'hard'],
        )
        self.assertEqual(len(state.players), 3)
        self.assertTrue(state.players[0].is_ai)
        self.assertEqual(state.players[0].ai_type, 'easy')
        self.assertTrue(state.players[1].is_ai)
        self.assertEqual(state.players[1].ai_type, 'medium')
        self.assertTrue(state.players[2].is_ai)
        self.assertEqual(state.players[2].ai_type, 'hard')


if __name__ == '__main__':
    unittest.main()
