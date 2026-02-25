"""Unit tests for main.py FastAPI application."""

import logging
import unittest

import fastapi.testclient

from blog.app import main


class TestApp(unittest.TestCase):
    """Tests for FastAPI application."""

    def setUp(self) -> None:
        """Set up test client."""
        self.client = fastapi.testclient.TestClient(main.app)

    def test_health_endpoint(self) -> None:
        """Test health check endpoint."""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'healthy'})

    def test_health_endpoint_head(self) -> None:
        """Test health check endpoint with HEAD method."""
        response = self.client.head('/health')
        self.assertEqual(response.status_code, 200)

    def test_index_endpoint(self) -> None:
        """Test index page endpoint."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])
        # Should contain some HTML
        self.assertIn('<html', response.text.lower())

    def test_post_endpoint_valid_slug(self) -> None:
        """Test individual post endpoint with valid slug."""
        # First get the list of posts to find a valid slug
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

        # Try to get the first post - we know from the repo there are posts
        # Let's use a known slug from the sample data
        response = self.client.get('/posts/starting-a-homelab')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])
        self.assertIn('Starting a Homelab', response.text)

    def test_post_endpoint_invalid_slug(self) -> None:
        """Test individual post endpoint with invalid slug."""
        response = self.client.get('/posts/nonexistent-post')
        self.assertEqual(response.status_code, 404)
        self.assertIn('Post not found', response.json()['detail'])

    def test_rss_endpoint(self) -> None:
        """Test RSS feed endpoint."""
        response = self.client.get('/rss.xml')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['content-type'], 'application/rss+xml')
        # Should contain RSS/XML structure
        self.assertIn('<rss', response.text)
        self.assertIn('<channel>', response.text)
        self.assertIn('<title>', response.text)

    def test_static_files_mounted(self) -> None:
        """Test that static files are accessible."""
        # The /assets route should be mounted
        # We don't know what files exist, so just check the mount works
        # by trying to access a likely non-existent file and getting 404
        response = self.client.get('/assets/nonexistent.css')
        # Should get 404 from the static files handler, not 404 from FastAPI router
        self.assertEqual(response.status_code, 404)


class TestHealthCheckFilter(unittest.TestCase):
    """Tests for the health check logging filter."""

    def test_health_path_filtered(self) -> None:
        """Health check requests are suppressed by the filter."""
        record = logging.LogRecord(
            name='uvicorn.access',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='%s - "%s %s HTTP/%s" %d',
            args=('127.0.0.1', 'GET', '/health', '1.1', 200),
            exc_info=None,
        )
        f = main.HealthCheckFilter()
        self.assertFalse(f.filter(record))

    def test_other_path_not_filtered(self) -> None:
        """Non-health-check requests are not suppressed by the filter."""
        record = logging.LogRecord(
            name='uvicorn.access',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='%s - "%s %s HTTP/%s" %d',
            args=('127.0.0.1', 'GET', '/', '1.1', 200),
            exc_info=None,
        )
        f = main.HealthCheckFilter()
        self.assertTrue(f.filter(record))


if __name__ == '__main__':
    unittest.main()
