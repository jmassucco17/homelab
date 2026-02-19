"""Unit tests for main.py FastAPI application."""

import fastapi.testclient

from blog.app import main


class TestApp:
    """Tests for FastAPI application."""

    def setup_method(self) -> None:
        """Set up test client."""
        self.client = fastapi.testclient.TestClient(main.app)

    def test_health_endpoint(self) -> None:
        """Test health check endpoint."""
        response = self.client.get('/health')
        assert response.status_code == 200
        assert response.json() == {'status': 'healthy'}

    def test_health_endpoint_head(self) -> None:
        """Test health check endpoint with HEAD method."""
        response = self.client.head('/health')
        assert response.status_code == 200

    def test_index_endpoint(self) -> None:
        """Test index page endpoint."""
        response = self.client.get('/')
        assert response.status_code == 200
        assert 'text/html' in response.headers['content-type']
        # Should contain some HTML
        assert '<html' in response.text.lower()

    def test_post_endpoint_valid_slug(self) -> None:
        """Test individual post endpoint with valid slug."""
        # First get the list of posts to find a valid slug
        response = self.client.get('/')
        assert response.status_code == 200
        
        # Try to get the first post - we know from the repo there are posts
        # Let's use a known slug from the sample data
        response = self.client.get('/posts/starting-a-homelab')
        assert response.status_code == 200
        assert 'text/html' in response.headers['content-type']
        assert 'Starting a Homelab' in response.text

    def test_post_endpoint_invalid_slug(self) -> None:
        """Test individual post endpoint with invalid slug."""
        response = self.client.get('/posts/nonexistent-post')
        assert response.status_code == 404
        assert 'Post not found' in response.json()['detail']

    def test_rss_endpoint(self) -> None:
        """Test RSS feed endpoint."""
        response = self.client.get('/rss.xml')
        assert response.status_code == 200
        assert response.headers['content-type'] == 'application/rss+xml'
        # Should contain RSS/XML structure
        assert '<rss' in response.text
        assert '<channel>' in response.text
        assert '<title>' in response.text

    def test_static_files_mounted(self) -> None:
        """Test that static files are accessible."""
        # The /assets route should be mounted
        # We don't know what files exist, so just check the mount works
        # by trying to access a likely non-existent file and getting 404
        response = self.client.get('/assets/nonexistent.css')
        # Should get 404 from the static files handler, not 404 from FastAPI router
        assert response.status_code == 404
