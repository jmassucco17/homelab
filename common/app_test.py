"""Unit tests for common/app.py."""

import contextlib
import logging
import os
import pathlib
import tempfile
import unittest
from collections.abc import AsyncGenerator

import fastapi
import fastapi.testclient

import common.app

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


class TestHealthCheckFilter(unittest.TestCase):
    """Tests for the HealthCheckFilter logging filter."""

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
        f = common.app.HealthCheckFilter()
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
        f = common.app.HealthCheckFilter()
        self.assertTrue(f.filter(record))


class TestConfigureLogging(unittest.TestCase):
    """Tests for configure_logging()."""

    def test_adds_filter_to_uvicorn_access_logger(self) -> None:
        """configure_logging() installs HealthCheckFilter on uvicorn.access."""
        logger = logging.getLogger('uvicorn.access')
        before = list(logger.filters)
        common.app.configure_logging()
        after = logger.filters
        new_filters = [f for f in after if f not in before]
        self.assertTrue(
            any(isinstance(f, common.app.HealthCheckFilter) for f in new_filters)
        )


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


class TestMakeTemplates(unittest.TestCase):
    """Tests for the make_templates factory."""

    def setUp(self) -> None:
        """Create a temporary directory to use as a templates directory."""
        self.tmpdir = tempfile.mkdtemp()

    def test_domain_global_set(self) -> None:
        """make_templates sets the domain global from the DOMAIN env var."""
        templates = common.app.make_templates(self.tmpdir)
        self.assertEqual(
            templates.env.globals['domain'],  # type: ignore[reportUnknownMemberType]
            os.environ.get('DOMAIN', '.jamesmassucco.com'),
        )

    def test_home_url_global_set(self) -> None:
        """make_templates sets the home_url global derived from the DOMAIN env var."""
        templates = common.app.make_templates(self.tmpdir)
        domain = os.environ.get('DOMAIN', '.jamesmassucco.com')
        self.assertEqual(
            templates.env.globals['home_url'],  # type: ignore[reportUnknownMemberType]
            'https://' + domain[1:],
        )

    def test_accepts_pathlib_path(self) -> None:
        """make_templates accepts a pathlib.Path directory."""
        templates = common.app.make_templates(pathlib.Path(self.tmpdir))
        self.assertIn('domain', templates.env.globals)  # type: ignore[reportUnknownMemberType,reportUnknownArgumentType]

    def test_accepts_string_path(self) -> None:
        """make_templates accepts a string directory path."""
        templates = common.app.make_templates(self.tmpdir)
        self.assertIn('home_url', templates.env.globals)  # type: ignore[reportUnknownMemberType,reportUnknownArgumentType]

    def test_domain_defaults_to_jamesmassucco(self) -> None:
        """domain global defaults to .jamesmassucco.com when DOMAIN env var is unset."""
        env_backup = os.environ.pop('DOMAIN', None)
        try:
            templates = common.app.make_templates(self.tmpdir)
            self.assertEqual(templates.env.globals['domain'], '.jamesmassucco.com')  # type: ignore[reportUnknownMemberType]
        finally:
            if env_backup is not None:
                os.environ['DOMAIN'] = env_backup

    def test_domain_reads_from_env(self) -> None:
        """domain global is read from the DOMAIN environment variable."""
        os.environ['DOMAIN'] = '-staging.example.com'
        try:
            templates = common.app.make_templates(self.tmpdir)
            self.assertEqual(templates.env.globals['domain'], '-staging.example.com')  # type: ignore[reportUnknownMemberType]
        finally:
            del os.environ['DOMAIN']

    def test_home_url_strips_leading_dot(self) -> None:
        """home_url global strips the leading dot from DOMAIN."""
        env_backup = os.environ.pop('DOMAIN', None)
        try:
            templates = common.app.make_templates(self.tmpdir)
            self.assertEqual(
                templates.env.globals['home_url'], 'https://jamesmassucco.com'
            )  # type: ignore[reportUnknownMemberType]
        finally:
            if env_backup is not None:
                os.environ['DOMAIN'] = env_backup

    def test_home_url_reflects_custom_domain(self) -> None:
        """home_url global reflects a custom DOMAIN environment variable."""
        os.environ['DOMAIN'] = '-staging.example.com'
        try:
            templates = common.app.make_templates(self.tmpdir)
            self.assertEqual(
                templates.env.globals['home_url'], 'https://staging.example.com'
            )  # type: ignore[reportUnknownMemberType]
        finally:
            del os.environ['DOMAIN']


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


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
