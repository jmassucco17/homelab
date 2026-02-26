"""Factory for creating standard FastAPI applications."""

from typing import Any

import fastapi

import common.health
import common.log


def create_app(title: str, **kwargs: Any) -> fastapi.FastAPI:
    """Create a FastAPI app with health endpoint and logging configured.

    Additional keyword arguments are forwarded to FastAPI.__init__ (e.g. lifespan).
    """
    app = fastapi.FastAPI(title=title, **kwargs)
    common.log.configure_logging()
    app.include_router(common.health.router)
    return app
