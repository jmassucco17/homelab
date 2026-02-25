"""Unit tests for snake router."""

import unittest

import fastapi.testclient

from games.app import main


class TestSnakeRouter(unittest.TestCase):
    """Tests for the snake game router."""

    def setUp(self) -> None:
        """Set up test client."""
        self.client = fastapi.testclient.TestClient(main.app)

    def test_snake_endpoint_returns_html(self) -> None:
        """Test GET /snake returns an HTML response."""
        response = self.client.get('/snake')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])

    def test_snake_page_contains_canvas(self) -> None:
        """Test the snake page includes a canvas element."""
        response = self.client.get('/snake')
        self.assertIn('<canvas', response.text.lower())

    def test_snake_page_loads_game_script(self) -> None:
        """Test the snake page references the game JS file."""
        response = self.client.get('/snake')
        self.assertIn('snake.js', response.text)

    def test_snake_page_has_score_display(self) -> None:
        """Test the snake page includes score and high-score elements."""
        response = self.client.get('/snake')
        self.assertIn('id="score"', response.text)
        self.assertIn('id="high-score"', response.text)

    def test_snake_page_has_start_button(self) -> None:
        """Test the snake page includes a start/restart button."""
        response = self.client.get('/snake')
        self.assertIn('id="start-btn"', response.text)

    def test_snake_page_renders_domain(self) -> None:
        """Test the snake page renders the domain variable from shared templates."""
        response = self.client.get('/snake')
        self.assertEqual(response.status_code, 200)
        self.assertIn('jamesmassucco.com', response.text)
        self.assertNotIn('{{ domain }}', response.text)


if __name__ == '__main__':
    unittest.main()
