"""Shared logging utilities for FastAPI applications."""

import logging


class HealthCheckFilter(logging.Filter):
    """Filter out health check requests from uvicorn access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Return False to suppress health check log entries."""
        return '/health' not in record.getMessage()


def configure_logging() -> None:
    """Configure uvicorn access logging to suppress health check entries."""
    logging.getLogger('uvicorn.access').addFilter(HealthCheckFilter())
