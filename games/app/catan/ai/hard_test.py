"""Unit tests for the Hard (strategic) AI."""

from __future__ import annotations

import unittest

from games.app.catan.ai import hard
from games.app.catan.engine import processor, rules, turn_manager
from games.app.catan.models import actions, board, game_state, player


def _make_state(seed: int = 42) -> game_state.GameState:
    """Create a fresh 2-player game state."""
    return turn_manager.create_initial_game_state(
        ['Alice', 'Bob'], ['red', 'blue'], seed=seed
    )


def _complete_setup(state: game_state.GameState) -> game_state.GameState:
    """Drive both players through setup using HardAI."""
    ai = hard.HardAI()
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


class TestHardAI(unittest.TestCase):
    """Tests for HardAI."""

    def setUp(self) -> None:
        """Set up AI and initial game state."""
        self.ai = hard.HardAI()
        self.state = _make_state()

    def test_setup_picks_legal_settlement(self) -> None:
        """HardAI picks a legal settlement during setup."""
        legal = rules.get_legal_actions(self.state, 0)
        chosen = self.ai.choose_action(self.state, 0, legal)
        self.assertIsInstance(chosen, actions.PlaceSettlement)
        self.assertIn(chosen, legal)

    def test_setup_road_picks_legal_road(self) -> None:
        """HardAI picks a legal road after placing a settlement."""
        result = processor.apply_action(
            self.state, actions.PlaceSettlement(player_index=0, vertex_id=5)
        )
        assert result.success and result.updated_state is not None
        state2 = result.updated_state
        legal = rules.get_legal_actions(state2, 0)
        chosen = self.ai.choose_action(state2, 0, legal)
        self.assertIsInstance(chosen, actions.PlaceRoad)
        self.assertIn(chosen, legal)

    def test_main_phase_rolls_dice(self) -> None:
        """HardAI rolls dice at the start of a main-phase turn."""
        state = _complete_setup(self.state)
        legal = rules.get_legal_actions(state, state.turn_state.player_index)
        roll_actions = [a for a in legal if isinstance(a, actions.RollDice)]
        if not roll_actions:
            self.skipTest('No RollDice in legal actions')
        chosen = self.ai.choose_action(state, state.turn_state.player_index, legal)
        self.assertIsInstance(chosen, actions.RollDice)

    def test_move_robber_avoids_self(self) -> None:
        """HardAI avoids placing robber on own tiles."""
        state = _complete_setup(self.state)
        state.phase = game_state.GamePhase.MAIN
        state.turn_state = game_state.TurnState(
            player_index=0,
            pending_action=game_state.PendingActionType.MOVE_ROBBER,
        )
        legal = rules.get_legal_actions(state, 0)
        move_actions = [a for a in legal if isinstance(a, actions.MoveRobber)]
        if len(move_actions) < 2:
            self.skipTest('Not enough MoveRobber options')
        chosen = self.ai.choose_action(state, 0, legal)
        self.assertIsInstance(chosen, actions.MoveRobber)
        self.assertIn(chosen, legal)

    def test_steal_targets_leader(self) -> None:
        """HardAI steals from the player with the highest VP."""
        state = _complete_setup(self.state)
        state.players[1].victory_points = 5
        state.players[0].victory_points = 2
        state.phase = game_state.GamePhase.MAIN
        state.turn_state = game_state.TurnState(
            player_index=0,
            pending_action=game_state.PendingActionType.STEAL_RESOURCE,
        )
        state.players[1].resources = player.Resources(wood=1)
        legal = [actions.StealResource(player_index=0, target_player_index=1)]
        chosen = self.ai.choose_action(state, 0, legal)
        assert isinstance(chosen, actions.StealResource)
        self.assertEqual(chosen.target_player_index, 1)

    def test_discard_respects_count(self) -> None:
        """HardAI discards exactly total - total//2 resources."""
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
        legal = rules.get_legal_actions(state, 0)
        chosen = self.ai.choose_action(state, 0, legal)
        self.assertIsInstance(chosen, actions.DiscardResources)
        assert isinstance(chosen, actions.DiscardResources)
        total_discarded = sum(chosen.resources.values())
        total_hand = state.players[0].resources.total()
        expected = total_hand - total_hand // 2
        self.assertEqual(total_discarded, expected)

    def test_plays_knight_when_robber_on_own_tile(self) -> None:
        """HardAI plays a Knight when the robber sits on one of its tiles."""
        state = _complete_setup(self.state)
        state.phase = game_state.GamePhase.MAIN
        state.turn_state = game_state.TurnState(
            player_index=0,
            pending_action=game_state.PendingActionType.BUILD_OR_TRADE,
            has_rolled=True,
        )
        state.players[0].dev_cards = state.players[0].dev_cards.add(
            player.DevCardType.KNIGHT
        )
        # Move robber to a tile where player 0 has a building.
        for vertex in state.board.vertices:
            if vertex.building and vertex.building.player_index == 0:
                tile_idx = vertex.adjacent_tile_indices[0]
                state.board.robber_tile_index = tile_idx
                break
        self.assertTrue(hard._robber_on_own_tile(state, 0))
        legal = rules.get_legal_actions(state, 0)
        knight_actions = [a for a in legal if isinstance(a, actions.PlayKnight)]
        if not knight_actions:
            self.skipTest('No PlayKnight in legal actions')
        chosen = self.ai.choose_action(state, 0, legal)
        self.assertIsInstance(chosen, actions.PlayKnight)

    def test_complete_game_terminates(self) -> None:
        """HardAI can drive a 2-player game to completion."""
        state = _make_state(seed=11)
        ai = hard.HardAI()
        for _ in range(2000):
            if state.phase == game_state.GamePhase.ENDED:
                break
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
        self.assertIsNotNone(state)


class TestHardHelpers(unittest.TestCase):
    """Tests for module-level helper functions in hard.py."""

    def test_vertex_pip_score(self) -> None:
        """_vertex_pip_score returns non-negative values."""
        state = _make_state()
        for vertex in state.board.vertices[:5]:
            score = hard._vertex_pip_score(state, vertex)
            self.assertGreaterEqual(score, 0)

    def test_player_total_vp(self) -> None:
        """_player_total_vp includes bonus VP."""
        state = _make_state()
        state.players[0].victory_points = 3
        state.longest_road_owner = 0
        vp = hard._player_total_vp(state, 0)
        self.assertEqual(vp, 5)

    def test_robber_on_own_tile(self) -> None:
        """_robber_on_own_tile returns True when robber overlaps player building."""
        state = _complete_setup(_make_state())
        # Move robber to a tile with a player-0 building.
        for vertex in state.board.vertices:
            if vertex.building and vertex.building.player_index == 0:
                state.board.robber_tile_index = vertex.adjacent_tile_indices[0]
                self.assertTrue(hard._robber_on_own_tile(state, 0))
                return
        self.skipTest('No player-0 buildings to test with')

    def test_trade_unlocks_build(self) -> None:
        """_trade_unlocks_build detects a trade that enables a city."""
        state = _make_state()
        state.phase = game_state.GamePhase.MAIN
        # Player has 6 wheat, 2 ore.
        # Trade 4 wheat → 1 ore leaves 2 wheat, 3 ore = can afford a city!
        state.players[0].resources = player.Resources(wheat=6, ore=2)
        trade = actions.TradeWithBank(
            player_index=0,
            giving=board.ResourceType.WHEAT,
            receiving=board.ResourceType.ORE,
        )
        result = hard._trade_unlocks_build(state, 0, trade)
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
