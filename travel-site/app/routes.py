"""API routes for the travel picture site."""

import os
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session

from . import models, services
from .database import get_admin_session, get_session

# Create routers
admin_router = APIRouter(prefix='/admin')
public_router = APIRouter()


# Dependencies
def get_picture_service() -> services.PictureService:
    """Get picture service instance."""
    return services.PictureService()


def get_location_service() -> services.LocationService:
    """Get location service instance."""
    return services.LocationService()


# Admin routes (require authentication via Traefik OAuth)
@admin_router.post('/upload', response_model=dict)
async def upload_picture(
    file: UploadFile = File(...),
    description: Annotated[str | None, Form()] = None,
    session: Session = Depends(get_admin_session),
    picture_service: services.PictureService = Depends(get_picture_service),
):
    """Upload a new picture with optional description."""
    # Validate file type
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail='File must be an image')

    # Save picture
    picture = await picture_service.save_picture(session, file, description)

    return {
        'message': 'Picture uploaded successfully',
        'picture_id': picture.id,
        'filename': picture.filename,
    }


@admin_router.get('/pictures', response_model=list[models.Picture])
async def get_admin_pictures(
    session: Session = Depends(get_admin_session),
    picture_service: services.PictureService = Depends(get_picture_service),
):
    """Get all pictures for admin interface."""
    return picture_service.get_all_pictures(session)


@admin_router.delete('/pictures/{picture_id}')
async def delete_picture(
    picture_id: int,
    session: Session = Depends(get_admin_session),
    picture_service: services.PictureService = Depends(get_picture_service),
):
    """Delete a picture."""
    success = picture_service.delete_picture(session, picture_id)
    if not success:
        raise HTTPException(status_code=404, detail='Picture not found')

    return {'message': 'Picture deleted successfully'}


@admin_router.post('/locations', response_model=models.Location)
async def create_location(
    name: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    country: str | None = Form(None),
    city: str | None = Form(None),
    session: Session = Depends(get_admin_session),
    location_service: services.LocationService = Depends(get_location_service),
):
    """Create a new location."""
    return location_service.create_location(
        session, name, latitude, longitude, country, city
    )


# Public routes (no authentication required)
@public_router.get('/pictures', response_model=list[models.Picture])
async def get_public_pictures(
    session: Session = Depends(get_session),
    picture_service: services.PictureService = Depends(get_picture_service),
):
    """Get all pictures for public gallery."""
    return picture_service.get_all_pictures(session)


@public_router.get('/pictures/{picture_id}', response_model=models.Picture)
async def get_picture_details(
    picture_id: int,
    session: Session = Depends(get_session),
    picture_service: services.PictureService = Depends(get_picture_service),
):
    """Get details of a specific picture."""
    picture = picture_service.get_picture_by_id(session, picture_id)
    if not picture:
        raise HTTPException(status_code=404, detail='Picture not found')

    return picture


@public_router.get('/pictures/{picture_id}/file')
async def get_picture_file(
    picture_id: int,
    session: Session = Depends(get_session),
    picture_service: services.PictureService = Depends(get_picture_service),
):
    """Serve the actual picture file."""
    picture = picture_service.get_picture_by_id(session, picture_id)
    if not picture:
        raise HTTPException(status_code=404, detail='Picture not found')

    data_dir = os.environ.get('DATA_DIR', 'data')
    file_path = os.path.join(data_dir, 'uploads', picture.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail='Picture file not found')

    return FileResponse(
        file_path, media_type=picture.mime_type, filename=picture.original_filename
    )


@public_router.get('/locations', response_model=list[models.Location])
async def get_locations(
    session: Session = Depends(get_session),
    location_service: services.LocationService = Depends(get_location_service),
):
    """Get all locations."""
    return location_service.get_all_locations(session)
