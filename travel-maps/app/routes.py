from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlmodel import Session

from app import services
from app.database import get_session

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


class MapCreate(BaseModel):
    name: str
    description: Optional[str] = None


class LocationCreate(BaseModel):
    name: str
    latitude: float
    longitude: float
    nickname: Optional[str] = None
    description: Optional[str] = None


class LocationUpdate(BaseModel):
    nickname: Optional[str] = None
    description: Optional[str] = None


class LocationReorder(BaseModel):
    location_ids: list[int]


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, session: Session = Depends(get_session)):
    """Display list of all maps."""
    maps = services.get_all_maps(session)
    maps_list = [
        {
            "id": m.id,
            "name": m.name,
            "description": m.description,
            "updated_at": m.updated_at,
            "locations": m.locations,
        }
        for m in maps
    ]
    return templates.TemplateResponse("index.html.jinja2", {"request": request, "maps": maps_list})


@router.get("/maps/new", response_class=HTMLResponse)
async def new_map_form(request: Request):
    """Display form to create a new map."""
    return templates.TemplateResponse("map-edit.html.jinja2", {"request": request, "map": None})


@router.get("/maps/{map_id}/view", response_class=HTMLResponse)
async def view_map(request: Request, map_id: int, session: Session = Depends(get_session)):
    """Display a map in view mode."""
    map_obj = services.get_map_by_id(session, map_id)
    if not map_obj:
        raise HTTPException(status_code=404, detail="Map not found")

    map_dict = {
        "id": map_obj.id,
        "name": map_obj.name,
        "description": map_obj.description,
        "locations": [
            {
                "id": loc.id,
                "name": loc.name,
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "nickname": loc.nickname,
                "description": loc.description,
                "order_index": loc.order_index,
            }
            for loc in map_obj.locations
        ],
    }

    return templates.TemplateResponse("map-view.html.jinja2", {"request": request, "map": map_dict})


@router.get("/maps/{map_id}/edit", response_class=HTMLResponse)
async def edit_map_form(request: Request, map_id: int, session: Session = Depends(get_session)):
    """Display form to edit an existing map."""
    map_obj = services.get_map_by_id(session, map_id)
    if not map_obj:
        raise HTTPException(status_code=404, detail="Map not found")

    map_dict = {
        "id": map_obj.id,
        "name": map_obj.name,
        "description": map_obj.description,
        "locations": [
            {
                "id": loc.id,
                "name": loc.name,
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "nickname": loc.nickname,
                "description": loc.description,
                "order_index": loc.order_index,
            }
            for loc in map_obj.locations
        ],
    }

    return templates.TemplateResponse("map-edit.html.jinja2", {"request": request, "map": map_dict})


@router.post("/api/maps")
async def create_map(map_data: MapCreate, session: Session = Depends(get_session)):
    """Create a new map."""
    map_obj = services.create_map(session, map_data.name, map_data.description)
    return {"id": map_obj.id, "name": map_obj.name, "description": map_obj.description}


@router.get("/api/maps/{map_id}")
async def get_map(map_id: int, session: Session = Depends(get_session)):
    """Get map details with locations."""
    map_obj = services.get_map_by_id(session, map_id)
    if not map_obj:
        raise HTTPException(status_code=404, detail="Map not found")

    return {
        "id": map_obj.id,
        "name": map_obj.name,
        "description": map_obj.description,
        "created_at": map_obj.created_at.isoformat(),
        "updated_at": map_obj.updated_at.isoformat(),
        "locations": [
            {
                "id": loc.id,
                "name": loc.name,
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "nickname": loc.nickname,
                "description": loc.description,
                "order_index": loc.order_index,
            }
            for loc in map_obj.locations
        ],
    }


@router.put("/api/maps/{map_id}")
async def update_map(map_id: int, map_data: MapCreate, session: Session = Depends(get_session)):
    """Update a map."""
    map_obj = services.update_map(session, map_id, map_data.name, map_data.description)
    if not map_obj:
        raise HTTPException(status_code=404, detail="Map not found")

    return {"id": map_obj.id, "name": map_obj.name, "description": map_obj.description}


@router.delete("/api/maps/{map_id}")
async def delete_map(map_id: int, session: Session = Depends(get_session)):
    """Delete a map."""
    success = services.delete_map(session, map_id)
    if not success:
        raise HTTPException(status_code=404, detail="Map not found")

    return {"success": True}


@router.post("/api/maps/{map_id}/locations")
async def add_location(map_id: int, location_data: LocationCreate, session: Session = Depends(get_session)):
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
        raise HTTPException(status_code=404, detail="Map not found")

    return {
        "id": location.id,
        "name": location.name,
        "latitude": location.latitude,
        "longitude": location.longitude,
        "nickname": location.nickname,
        "description": location.description,
        "order_index": location.order_index,
    }


@router.put("/api/locations/{location_id}")
async def update_location(location_id: int, location_data: LocationUpdate, session: Session = Depends(get_session)):
    """Update a location's nickname and description."""
    location = services.update_location(session, location_id, location_data.nickname, location_data.description)
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    return {
        "id": location.id,
        "nickname": location.nickname,
        "description": location.description,
    }


@router.delete("/api/locations/{location_id}")
async def delete_location(location_id: int, session: Session = Depends(get_session)):
    """Delete a location."""
    success = services.delete_location(session, location_id)
    if not success:
        raise HTTPException(status_code=404, detail="Location not found")

    return {"success": True}


@router.post("/api/locations/reorder")
async def reorder_locations(reorder_data: LocationReorder, session: Session = Depends(get_session)):
    """Reorder locations."""
    success = services.reorder_locations(session, reorder_data.location_ids)
    return {"success": success}


@router.get("/api/geocode")
async def geocode(q: str):
    """Search for locations using geocoding."""
    if not q or len(q) < 2:
        return []

    results = await services.geocode_location(q)
    return results
