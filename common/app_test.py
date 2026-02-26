"""Unit tests for common/app.py."""

import contextlib
import unittest
from collections.abc import AsyncGenerator

import fastapi
import fastapi.testclient

import common.app


class TestCreateApp(unittest.TestCase):
    """Tests for the create_app factory."""

    def test_returns_fastapi_instance(self) -> None:
        """create_app returns a FastAPI instance."""
        app = common.app.create_app('TestApp')
        self.assertIsInstance(app, fastapi.FastAPI)

    def test_title_is_set(self) -> None:
        """create_app sets the app title."""
        app = common.app.create_app('MyTitle')
        self.assertEqual(app.title, 'MyTitle')

    def test_health_endpoint_registered(self) -> None:
        """create_app registers the /health endpoint."""
        app = common.app.create_app('TestApp')
        client = fastapi.testclient.TestClient(app)
        response = client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'healthy'})

    def test_health_head_method(self) -> None:
        """create_app health endpoint accepts HEAD requests."""
        app = common.app.create_app('TestApp')
        client = fastapi.testclient.TestClient(app)
        response = client.head('/health')
        self.assertEqual(response.status_code, 200)

    def test_kwargs_forwarded_to_fastapi(self) -> None:
        """Extra kwargs (e.g. lifespan) are forwarded to FastAPI."""

        @contextlib.asynccontextmanager
        async def my_lifespan(app: fastapi.FastAPI) -> AsyncGenerator[None, None]:
            yield

        app = common.app.create_app('TestApp', lifespan=my_lifespan)
        self.assertIsInstance(app, fastapi.FastAPI)


if __name__ == '__main__':
    unittest.main()
