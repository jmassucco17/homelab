"""Core FastAPI application utilities shared across all services."""

import logging
import os
import pathlib
from typing import Any

import fastapi
import fastapi.templating

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


class HealthCheckFilter(logging.Filter):
    """Filter out health check requests from uvicorn access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Return False to suppress health check log entries."""
        return '/health' not in record.getMessage()


def configure_logging() -> None:
    """Configure uvicorn access logging to suppress health check entries."""
    logging.getLogger('uvicorn.access').addFilter(HealthCheckFilter())


# ---------------------------------------------------------------------------
# Health router
# ---------------------------------------------------------------------------

_health_router = fastapi.APIRouter()


@_health_router.api_route('/health', methods=['GET', 'HEAD'])
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {'status': 'healthy'}


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


def make_templates(
    directory: pathlib.Path | str,
) -> fastapi.templating.Jinja2Templates:
    """Create a Jinja2Templates instance with domain and home_url globals pre-set."""
    domain = os.environ.get('DOMAIN', '.jamesmassucco.com')
    templates = fastapi.templating.Jinja2Templates(directory=str(directory))
    templates.env.globals['domain'] = domain  # type: ignore[reportUnknownMemberType]
    templates.env.globals['home_url'] = 'https://' + domain[1:]  # type: ignore[reportUnknownMemberType]
    return templates


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app(title: str, **kwargs: Any) -> fastapi.FastAPI:
    """Create a FastAPI app with health endpoint and logging configured.

    Additional keyword arguments are forwarded to FastAPI.__init__ (e.g. lifespan).
    """
    app = fastapi.FastAPI(title=title, **kwargs)
    configure_logging()
    app.include_router(_health_router)
    return app
