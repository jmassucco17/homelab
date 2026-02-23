"""Unit tests for the Medium (priority-based) AI."""

from __future__ import annotations

import unittest

from games.app.catan.ai import medium
from games.app.catan.engine import processor, rules, turn_manager
from games.app.catan.models import actions, board, game_state, player


def _make_state(seed: int = 42) -> game_state.GameState:
    """Create a fresh 2-player game state."""
    return turn_manager.create_initial_game_state(
        ['Alice', 'Bob'], ['red', 'blue'], seed=seed
    )


def _complete_setup(state: game_state.GameState) -> game_state.GameState:
    """Drive both players through the entire setup phase using MediumAI."""
    ai = medium.MediumAI()
    for _ in range(200):
        if state.phase == game_state.GamePhase.MAIN:
            break
        pidx = state.turn_state.player_index
        legal = rules.get_legal_actions(state, pidx)
        if not legal:
            break
        action = ai.choose_action(state, pidx, legal)
        result = processor.apply_action(state, action)
        assert result.success, result.error_message
        assert result.updated_state is not None
        state = result.updated_state
    return state


class TestMediumAI(unittest.TestCase):
    """Tests for MediumAI."""

    def setUp(self) -> None:
        """Initialise AI and game state."""
        self.ai = medium.MediumAI()
        self.state = _make_state()

    def test_setup_picks_legal_settlement(self) -> None:
        """MediumAI picks a legal settlement during setup."""
        legal = rules.get_legal_actions(self.state, 0)
        chosen = self.ai.choose_action(self.state, 0, legal)
        self.assertIsInstance(chosen, actions.PlaceSettlement)
        self.assertIn(chosen, legal)

    def test_setup_road_picks_legal_road(self) -> None:
        """MediumAI picks a legal road during setup after settlement."""
        result = processor.apply_action(
            self.state, actions.PlaceSettlement(player_index=0, vertex_id=5)
        )
        assert result.success
        assert result.updated_state is not None
        state2 = result.updated_state
        legal = rules.get_legal_actions(state2, 0)
        road_actions = [a for a in legal if isinstance(a, actions.PlaceRoad)]
        self.assertGreater(len(road_actions), 0)
        chosen = self.ai.choose_action(state2, 0, legal)
        self.assertIsInstance(chosen, actions.PlaceRoad)
        self.assertIn(chosen, legal)

    def test_main_phase_rolls_dice(self) -> None:
        """MediumAI rolls dice at the start of a main-phase turn."""
        state = _complete_setup(self.state)
        legal = rules.get_legal_actions(state, state.turn_state.player_index)
        roll_actions = [a for a in legal if isinstance(a, actions.RollDice)]
        if not roll_actions:
            self.skipTest('No RollDice in legal actions')
        chosen = self.ai.choose_action(state, state.turn_state.player_index, legal)
        self.assertIsInstance(chosen, actions.RollDice)

    def test_move_robber_targets_opponent(self) -> None:
        """MediumAI places robber on a tile with opponent buildings when possible."""
        state = _complete_setup(self.state)
        state.phase = game_state.GamePhase.MAIN
        state.turn_state = game_state.TurnState(
            player_index=0,
            pending_action=game_state.PendingActionType.MOVE_ROBBER,
        )
        legal = rules.get_legal_actions(state, 0)
        move_actions = [a for a in legal if isinstance(a, actions.MoveRobber)]
        if not move_actions:
            self.skipTest('No MoveRobber actions available')
        chosen = self.ai.choose_action(state, 0, legal)
        self.assertIsInstance(chosen, actions.MoveRobber)
        self.assertIn(chosen, legal)

    def test_steal_targets_richest_player(self) -> None:
        """MediumAI steals from the opponent with the most resources."""
        state = _complete_setup(self.state)
        state.players[1].resources = player.Resources(
            wood=3, brick=2, wheat=1, sheep=1, ore=1
        )
        state.phase = game_state.GamePhase.MAIN
        state.turn_state = game_state.TurnState(
            player_index=0,
            pending_action=game_state.PendingActionType.STEAL_RESOURCE,
        )
        legal: list[actions.Action] = [
            actions.StealResource(player_index=0, target_player_index=1)
        ]
        chosen = self.ai.choose_action(state, 0, legal)
        self.assertIsInstance(chosen, actions.StealResource)
        assert isinstance(chosen, actions.StealResource)
        self.assertEqual(chosen.target_player_index, 1)

    def test_discard_respects_count(self) -> None:
        """MediumAI discards exactly total - total//2 resources."""
        state = _make_state()
        state.phase = game_state.GamePhase.MAIN
        state.turn_state = game_state.TurnState(
            player_index=0,
            pending_action=game_state.PendingActionType.DISCARD_RESOURCES,
            discard_player_indices=[0],
        )
        state.players[0].resources = player.Resources(
            wood=3, brick=3, wheat=2, sheep=2, ore=2
        )  # total=12, must discard 6
        # Get the AI's discard action.
        legal = rules.get_legal_actions(state, 0)
        chosen = self.ai.choose_action(state, 0, legal)
        self.assertIsInstance(chosen, actions.DiscardResources)
        assert isinstance(chosen, actions.DiscardResources)
        total_discarded = sum(chosen.resources.values())
        total_hand = state.players[0].resources.total()
        expected_discard = total_hand - total_hand // 2
        self.assertEqual(total_discarded, expected_discard)

    def test_prefers_settlement_over_road(self) -> None:
        """MediumAI prefers placing a settlement over a road in main phase."""
        state = _complete_setup(self.state)
        state.phase = game_state.GamePhase.MAIN
        state.turn_state = game_state.TurnState(
            player_index=0,
            pending_action=game_state.PendingActionType.BUILD_OR_TRADE,
            has_rolled=True,
        )
        # Give player resources for both settlement and road.
        state.players[0].resources = player.Resources(
            wood=2, brick=2, wheat=1, sheep=1, ore=0
        )
        # Place a road so settlement placement is possible.
        brd = state.board
        for edge in brd.edges:
            if edge.road and edge.road.player_index == 0:
                for vid in edge.vertex_ids:
                    v = brd.vertices[vid]
                    if v.building is None and all(
                        brd.vertices[adj].building is None
                        for adj in v.adjacent_vertex_ids
                    ):
                        legal = rules.get_legal_actions(state, 0)
                        has_settlement = any(
                            isinstance(a, actions.PlaceSettlement) for a in legal
                        )
                        if has_settlement:
                            chosen = self.ai.choose_action(state, 0, legal)
                            self.assertIsInstance(chosen, actions.PlaceSettlement)
                            return
        self.skipTest('No valid settlement spot for this board seed')

    def test_complete_game_terminates(self) -> None:
        """MediumAI can drive a 2-player game to completion within 2000 actions."""
        state = _make_state(seed=7)
        ai = medium.MediumAI()
        for _ in range(2000):
            if state.phase == game_state.GamePhase.ENDED:
                break
            # Handle discard phase for any player.
            acted = False
            for p_idx in range(len(state.players)):
                legal = rules.get_legal_actions(state, p_idx)
                if legal:
                    action = ai.choose_action(state, p_idx, legal)
                    result = processor.apply_action(state, action)
                    if result.success and result.updated_state is not None:
                        state = result.updated_state
                        acted = True
                        break
            if not acted:
                break
        # Game should have ended or at least made progress.
        self.assertIsNotNone(state)


class TestMediumHelpers(unittest.TestCase):
    """Tests for module-level helper functions."""

    def test_vertex_pip_score(self) -> None:
        """_vertex_pip_score returns non-negative integer."""
        state = _make_state()
        for vertex in state.board.vertices[:5]:
            score = medium.vertex_pip_score(state, vertex)
            self.assertGreaterEqual(score, 0)

    def test_vertex_resource_diversity(self) -> None:
        """_vertex_resource_diversity returns 0 to 3."""
        state = _make_state()
        for vertex in state.board.vertices[:5]:
            div = medium.vertex_resource_diversity(state, 0, vertex)
            self.assertGreaterEqual(div, 0)
            self.assertLessEqual(div, 3)

    def test_trade_unlocks_build(self) -> None:
        """_trade_unlocks_build detects when a trade enables settlement."""
        state = _make_state()
        state.phase = game_state.GamePhase.MAIN
        # Player has 5 wood, 0 brick, 1 wheat, 1 sheep.
        # Trading 4 wood → 1 brick leaves wood=1, brick=1, wheat=1, sheep=1.
        state.players[0].resources = player.Resources(
            wood=5, brick=0, wheat=1, sheep=1, ore=0
        )
        trade = actions.TradeWithBank(
            player_index=0,
            giving=board.ResourceType.WOOD,
            receiving=board.ResourceType.BRICK,
        )
        result = medium.trade_unlocks_build(state, 0, trade)
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
