"""Unit tests for main.py FastAPI application."""

import unittest

import fastapi.testclient

from tools.app import main


class TestApp(unittest.TestCase):
    """Tests for tools FastAPI application."""

    def setUp(self) -> None:
        """Set up test client."""
        self.client = fastapi.testclient.TestClient(main.app)

    def test_health_endpoint(self) -> None:
        """Test health check endpoint returns healthy status."""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'healthy'})

    def test_health_endpoint_head(self) -> None:
        """Test health check endpoint with HEAD method."""
        response = self.client.head('/health')
        self.assertEqual(response.status_code, 200)

    def test_index_endpoint(self) -> None:
        """Test index page returns HTML."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])
        self.assertIn('<html', response.text.lower())

    def test_index_page_contains_tool_links(self) -> None:
        """Test index page links to all tools."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('/movie-picker', response.text)

    def test_static_files_mounted(self) -> None:
        """Test that the /static route is mounted (404 for missing file, not 405)."""
        response = self.client.get('/static/nonexistent.js')
        self.assertEqual(response.status_code, 404)

    def test_movie_picker_route_registered(self) -> None:
        """Test that the movie picker router is registered in the app."""
        response = self.client.get('/movie-picker')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])


if __name__ == '__main__':
    unittest.main()
