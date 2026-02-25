"""API routes for the travel maps feature."""

import os
import pathlib
import typing

import fastapi
import fastapi.responses
import fastapi.templating
import pydantic
import sqlmodel

from . import database, services

APP_DIR = pathlib.Path(__file__).resolve().parent

router = fastapi.APIRouter()
templates = fastapi.templating.Jinja2Templates(directory=APP_DIR / 'templates')
templates.env.globals['domain'] = os.environ.get('DOMAIN', 'jamesmassucco.com')  # type: ignore[reportUnknownMemberType]


class MapCreate(pydantic.BaseModel):
    """Request body for creating or updating a map."""

    name: str
    description: str | None = None


class LocationCreate(pydantic.BaseModel):
    """Request body for creating a new location."""

    name: str
    latitude: float
    longitude: float
    nickname: str | None = None
    description: str | None = None


class LocationUpdate(pydantic.BaseModel):
    """Request body for updating a location's details."""

    nickname: str | None = None
    description: str | None = None


class LocationReorder(pydantic.BaseModel):
    """Request body for reordering locations."""

    location_ids: list[int]


@router.get('/', response_class=fastapi.responses.HTMLResponse)
async def index(
    request: fastapi.Request,
    session: sqlmodel.Session = fastapi.Depends(database.get_session),
) -> fastapi.responses.HTMLResponse:
    """Display list of all maps."""
    maps = services.get_all_maps(session)
    maps_list = [
        {
            'id': m.id,
            'name': m.name,
            'description': m.description,
            'updated_at': m.updated_at,
            'locations': m.locations,
        }
        for m in maps
    ]
    return templates.TemplateResponse(
        request=request, name='index.html.jinja2', context={'maps': maps_list}
    )


@router.get('/new', response_class=fastapi.responses.HTMLResponse)
async def new_map_form(request: fastapi.Request) -> fastapi.responses.HTMLResponse:
    """Display form to create a new map."""
    return templates.TemplateResponse(
        request=request, name='map-edit.html.jinja2', context={'map': None}
    )


@router.get('/{map_id}/view', response_class=fastapi.responses.HTMLResponse)
async def view_map(
    request: fastapi.Request,
    map_id: int,
    session: sqlmodel.Session = fastapi.Depends(database.get_session),
) -> fastapi.responses.HTMLResponse:
    """Display a map in view mode."""
    map_obj = services.get_map_by_id(session, map_id)
    if not map_obj:
        raise fastapi.HTTPException(status_code=404, detail='Map not found')

    map_dict = {
        'id': map_obj.id,
        'name': map_obj.name,
        'description': map_obj.description,
        'locations': [
            {
                'id': loc.id,
                'name': loc.name,
                'latitude': loc.latitude,
                'longitude': loc.longitude,
                'nickname': loc.nickname,
                'description': loc.description,
                'order_index': loc.order_index,
            }
            for loc in map_obj.locations
        ],
    }

    return templates.TemplateResponse(
        request=request, name='map-view.html.jinja2', context={'map': map_dict}
    )


@router.get('/{map_id}/edit', response_class=fastapi.responses.HTMLResponse)
async def edit_map_form(
    request: fastapi.Request,
    map_id: int,
    session: sqlmodel.Session = fastapi.Depends(database.get_session),
) -> fastapi.responses.HTMLResponse:
    """Display form to edit an existing map."""
    map_obj = services.get_map_by_id(session, map_id)
    if not map_obj:
        raise fastapi.HTTPException(status_code=404, detail='Map not found')

    map_dict = {
        'id': map_obj.id,
        'name': map_obj.name,
        'description': map_obj.description,
        'locations': [
            {
                'id': loc.id,
                'name': loc.name,
                'latitude': loc.latitude,
                'longitude': loc.longitude,
                'nickname': loc.nickname,
                'description': loc.description,
                'order_index': loc.order_index,
            }
            for loc in map_obj.locations
        ],
    }

    return templates.TemplateResponse(
        request=request, name='map-edit.html.jinja2', context={'map': map_dict}
    )


@router.post('/api/maps')
async def create_map(
    map_data: MapCreate,
    session: sqlmodel.Session = fastapi.Depends(database.get_session),
) -> dict[str, typing.Any]:
    """Create a new map."""
    map_obj = services.create_map(session, map_data.name, map_data.description)
    return {'id': map_obj.id, 'name': map_obj.name, 'description': map_obj.description}


@router.get('/api/maps/{map_id}')
async def get_map(
    map_id: int, session: sqlmodel.Session = fastapi.Depends(database.get_session)
) -> dict[str, typing.Any]:
    """Get map details with locations."""
    map_obj = services.get_map_by_id(session, map_id)
    if not map_obj:
        raise fastapi.HTTPException(status_code=404, detail='Map not found')

    return {
        'id': map_obj.id,
        'name': map_obj.name,
        'description': map_obj.description,
        'created_at': map_obj.created_at.isoformat(),
        'updated_at': map_obj.updated_at.isoformat(),
        'locations': [
            {
                'id': loc.id,
                'name': loc.name,
                'latitude': loc.latitude,
                'longitude': loc.longitude,
                'nickname': loc.nickname,
                'description': loc.description,
                'order_index': loc.order_index,
            }
            for loc in map_obj.locations
        ],
    }


@router.put('/api/maps/{map_id}')
async def update_map(
    map_id: int,
    map_data: MapCreate,
    session: sqlmodel.Session = fastapi.Depends(database.get_session),
) -> dict[str, typing.Any]:
    """Update a map."""
    map_obj = services.update_map(session, map_id, map_data.name, map_data.description)
    if not map_obj:
        raise fastapi.HTTPException(status_code=404, detail='Map not found')

    return {
        'id': map_obj.id,
        'name': map_obj.name,
        'description': map_obj.description,
    }


@router.delete('/api/maps/{map_id}')
async def delete_map(
    map_id: int, session: sqlmodel.Session = fastapi.Depends(database.get_session)
) -> dict[str, bool]:
    """Delete a map."""
    success = services.delete_map(session, map_id)
    if not success:
        raise fastapi.HTTPException(status_code=404, detail='Map not found')

    return {'success': True}


@router.post('/api/maps/{map_id}/locations')
async def add_location(
    map_id: int,
    location_data: LocationCreate,
    session: sqlmodel.Session = fastapi.Depends(database.get_session),
) -> dict[str, typing.Any]:
    """Add a location to a map."""
    location = services.add_location_to_map(
        session,
        map_id,
        location_data.name,
        location_data.latitude,
        location_data.longitude,
        location_data.nickname,
        location_data.description,
    )
    if not location:
        raise fastapi.HTTPException(status_code=404, detail='Map not found')

    return {
        'id': location.id,
        'name': location.name,
        'latitude': location.latitude,
        'longitude': location.longitude,
        'nickname': location.nickname,
        'description': location.description,
        'order_index': location.order_index,
    }


@router.put('/api/locations/{location_id}')
async def update_location(
    location_id: int,
    location_data: LocationUpdate,
    session: sqlmodel.Session = fastapi.Depends(database.get_session),
) -> dict[str, typing.Any]:
    """Update a location's nickname and description."""
    location = services.update_location(
        session,
        location_id,
        location_data.nickname,
        location_data.description,
    )
    if not location:
        raise fastapi.HTTPException(status_code=404, detail='Location not found')

    return {
        'id': location.id,
        'nickname': location.nickname,
        'description': location.description,
    }


@router.delete('/api/locations/{location_id}')
async def delete_location(
    location_id: int,
    session: sqlmodel.Session = fastapi.Depends(database.get_session),
) -> dict[str, bool]:
    """Delete a location."""
    success = services.delete_location(session, location_id)
    if not success:
        raise fastapi.HTTPException(status_code=404, detail='Location not found')

    return {'success': True}


@router.post('/api/locations/reorder')
async def reorder_locations(
    reorder_data: LocationReorder,
    session: sqlmodel.Session = fastapi.Depends(database.get_session),
) -> dict[str, bool]:
    """Reorder locations."""
    success = services.reorder_locations(session, reorder_data.location_ids)
    return {'success': success}


@router.get('/api/geocode')
async def geocode(q: str) -> list[dict[str, str | float]]:
    """Search for locations using geocoding."""
    if not q or len(q) < 2:
        return []

    results: list[dict[str, str | float]] = await services.geocode_location(q)
    return results
