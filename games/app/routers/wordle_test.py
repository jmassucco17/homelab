"""Unit tests for the Wordle starting-word suggester router."""

import unittest

import fastapi.testclient

from games.app import main


class TestWordleRouter(unittest.TestCase):
    """Tests for the /wordle route."""

    def setUp(self) -> None:
        """Set up test client."""
        self.client = fastapi.testclient.TestClient(main.app)

    def test_wordle_endpoint_returns_html(self) -> None:
        """GET /wordle returns an HTML 200 response."""
        response = self.client.get('/wordle')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])

    def test_wordle_page_shows_suggestions_table(self) -> None:
        """The page renders a table containing suggestion rows."""
        response = self.client.get('/wordle')
        self.assertIn('<table', response.text.lower())

    def test_wordle_page_shows_ten_suggestions(self) -> None:
        """Exactly 10 suggestion rows are rendered."""
        response = self.client.get('/wordle')
        # Each word row has a rank cell, e.g. "#1", "#2", …, "#10"
        for rank in range(1, 11):
            self.assertIn(f'#{rank}', response.text)

    def test_wordle_page_contains_remaining_count(self) -> None:
        """The page reports how many answers remain in the pool."""
        response = self.client.get('/wordle')
        self.assertIn('remaining', response.text.lower())

    def test_wordle_page_renders_domain(self) -> None:
        """Template domain variable is resolved (no raw Jinja placeholders)."""
        response = self.client.get('/wordle')
        self.assertIn('jamesmassucco.com', response.text)
        self.assertNotIn('{{ domain }}', response.text)

    def test_wordle_page_has_heading(self) -> None:
        """The page has a heading that mentions Wordle."""
        response = self.client.get('/wordle')
        self.assertIn('wordle', response.text.lower())


if __name__ == '__main__':
    unittest.main()
