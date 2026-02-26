"""Shared health check router for FastAPI applications."""

import fastapi

router = fastapi.APIRouter()


@router.api_route('/health', methods=['GET', 'HEAD'])
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {'status': 'healthy'}
