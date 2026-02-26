"""Unit tests for common/log.py."""

import logging
import unittest

import common.log


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
        f = common.log.HealthCheckFilter()
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
        f = common.log.HealthCheckFilter()
        self.assertTrue(f.filter(record))


class TestConfigureLogging(unittest.TestCase):
    """Tests for configure_logging()."""

    def test_adds_filter_to_uvicorn_access_logger(self) -> None:
        """configure_logging() installs HealthCheckFilter on uvicorn.access."""
        logger = logging.getLogger('uvicorn.access')
        before = list(logger.filters)
        common.log.configure_logging()
        after = logger.filters
        new_filters = [f for f in after if f not in before]
        self.assertTrue(
            any(isinstance(f, common.log.HealthCheckFilter) for f in new_filters)
        )


if __name__ == '__main__':
    unittest.main()
