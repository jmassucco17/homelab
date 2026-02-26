"""Unit tests for common/health.py."""

import unittest

import fastapi
import fastapi.testclient

import common.health


class TestHealthRouter(unittest.TestCase):
    """Tests for the shared health check router."""

    def setUp(self) -> None:
        """Set up a minimal test app with the health router included."""
        app = fastapi.FastAPI()
        app.include_router(common.health.router)
        self.client = fastapi.testclient.TestClient(app)

    def test_health_get(self) -> None:
        """GET /health returns 200 with healthy status."""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'healthy'})

    def test_health_head(self) -> None:
        """HEAD /health returns 200."""
        response = self.client.head('/health')
        self.assertEqual(response.status_code, 200)


if __name__ == '__main__':
    unittest.main()
