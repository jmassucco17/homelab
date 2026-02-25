"""Unit tests for pong router."""

import unittest

import fastapi.testclient

from games.app import main


class TestPongRouter(unittest.TestCase):
    """Tests for the pong game router."""

    def setUp(self) -> None:
        """Set up test client."""
        self.client = fastapi.testclient.TestClient(main.app)

    def test_pong_endpoint_returns_html(self) -> None:
        """Test GET /pong returns an HTML response."""
        response = self.client.get('/pong')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])

    def test_pong_page_contains_canvas(self) -> None:
        """Test the pong page includes a canvas element."""
        response = self.client.get('/pong')
        self.assertIn('<canvas', response.text.lower())

    def test_pong_page_loads_game_script(self) -> None:
        """Test the pong page references the game JS file."""
        response = self.client.get('/pong')
        self.assertIn('pong.js', response.text)

    def test_pong_page_has_score_display(self) -> None:
        """Test the pong page includes the score element."""
        response = self.client.get('/pong')
        self.assertIn('id="pong-score"', response.text)

    def test_pong_page_has_mode_buttons(self) -> None:
        """Test the pong page includes 1P and 2P mode selection buttons."""
        response = self.client.get('/pong')
        self.assertIn('id="btn-1p"', response.text)
        self.assertIn('id="btn-2p"', response.text)

    def test_pong_page_has_rematch_button(self) -> None:
        """Test the pong page includes a rematch button."""
        response = self.client.get('/pong')
        self.assertIn('id="rematch-btn"', response.text)

    def test_pong_page_renders_domain(self) -> None:
        """Test the pong page renders the domain variable from shared templates."""
        response = self.client.get('/pong')
        self.assertEqual(response.status_code, 200)
        self.assertIn('jamesmassucco.com', response.text)
        self.assertNotIn('{{ domain }}', response.text)


if __name__ == '__main__':
    unittest.main()
