"""API routes for the travel picture site."""

import os
import typing

import fastapi
import fastapi.responses
import sqlmodel

from . import database, models, services

# Create routers
admin_router = fastapi.APIRouter(prefix='/admin')
public_router = fastapi.APIRouter()


# Helper function to serialize pictures with location relationship
def serialize_picture(picture: models.Picture) -> dict[str, typing.Any]:
    """Serialize a picture including its location relationship."""
    return {
        **picture.model_dump(),
        'location': picture.location.model_dump() if picture.location else None,
    }


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
    file: typing.Annotated[fastapi.UploadFile, fastapi.File(...)],
    description: typing.Annotated[str | None, fastapi.Form()] = None,
    session: sqlmodel.Session = fastapi.Depends(database.get_admin_session),
    picture_service: services.PictureService = fastapi.Depends(get_picture_service),
    location_service: services.LocationService = fastapi.Depends(get_location_service),
) -> dict[str, typing.Any]:
    """Upload a new picture with optional description."""
    # Validate file type
    if not file.content_type or not file.content_type.startswith('image/'):
        raise fastapi.HTTPException(status_code=400, detail='File must be an image')

    # Save picture
    picture = await picture_service.save_picture(
        session, location_service, file, description
    )

    return {
        'message': 'Picture uploaded successfully',
        'picture_id': picture.id,
        'filename': picture.filename,
    }


@admin_router.get('/pictures')
async def get_admin_pictures(
    session: sqlmodel.Session = fastapi.Depends(database.get_admin_session),
    picture_service: services.PictureService = fastapi.Depends(get_picture_service),
) -> list[dict[str, typing.Any]]:
    """Get all pictures for admin interface."""
    pictures = picture_service.get_all_pictures(session)
    return [serialize_picture(picture) for picture in pictures]


@admin_router.delete('/pictures/{picture_id}')
async def delete_picture(
    picture_id: int,
    session: sqlmodel.Session = fastapi.Depends(database.get_admin_session),
    picture_service: services.PictureService = fastapi.Depends(get_picture_service),
) -> dict[str, str]:
    """Delete a picture."""
    success = picture_service.delete_picture(session, picture_id)
    if not success:
        raise fastapi.HTTPException(status_code=404, detail='Picture not found')

    return {'message': 'Picture deleted successfully'}


@admin_router.patch('/pictures/{picture_id}')
async def update_picture(
    picture_id: int,
    description: typing.Annotated[str | None, fastapi.Form()] = None,
    session: sqlmodel.Session = fastapi.Depends(database.get_admin_session),
    picture_service: services.PictureService = fastapi.Depends(get_picture_service),
) -> dict[str, typing.Any]:
    """Update a picture's description."""
    picture = picture_service.update_picture_description(
        session, picture_id, description
    )
    if not picture:
        raise fastapi.HTTPException(status_code=404, detail='Picture not found')

    return serialize_picture(picture)


@admin_router.post('/locations', response_model=models.PhotoLocation)
async def create_location(
    name: typing.Annotated[str, fastapi.Form(...)],
    latitude: typing.Annotated[float, fastapi.Form(...)],
    longitude: typing.Annotated[float, fastapi.Form(...)],
    session: sqlmodel.Session = fastapi.Depends(database.get_admin_session),
    location_service: services.LocationService = fastapi.Depends(get_location_service),
) -> models.PhotoLocation:
    """Create a new location."""
    location = location_service.create_location(session, name, latitude, longitude)
    if location is None:
        raise fastapi.HTTPException(status_code=400, detail='Failed to create location')
    return location


# Public routes (no authentication required)
@public_router.get('/pictures')
async def get_public_pictures(
    session: sqlmodel.Session = fastapi.Depends(database.get_session),
    picture_service: services.PictureService = fastapi.Depends(get_picture_service),
) -> list[dict[str, typing.Any]]:
    """Get all pictures for public gallery."""
    pictures = picture_service.get_all_pictures(session)
    return [serialize_picture(picture) for picture in pictures]


@public_router.get('/pictures/{picture_id}')
async def get_picture_details(
    picture_id: int,
    session: sqlmodel.Session = fastapi.Depends(database.get_session),
    picture_service: services.PictureService = fastapi.Depends(get_picture_service),
) -> dict[str, typing.Any]:
    """Get details of a specific picture."""
    picture = picture_service.get_picture_by_id(session, picture_id)
    if not picture:
        raise fastapi.HTTPException(status_code=404, detail='Picture not found')

    return serialize_picture(picture)


@public_router.get('/pictures/{picture_id}/file')
async def get_picture_file(
    picture_id: int,
    session: sqlmodel.Session = fastapi.Depends(database.get_session),
    picture_service: services.PictureService = fastapi.Depends(get_picture_service),
) -> fastapi.responses.FileResponse:
    """Serve the actual picture file."""
    picture = picture_service.get_picture_by_id(session, picture_id)
    if not picture:
        raise fastapi.HTTPException(status_code=404, detail='Picture not found')

    data_dir = os.environ.get('DATA_DIR', 'data')
    file_path = os.path.join(data_dir, 'uploads', picture.filename)
    if not os.path.exists(file_path):
        raise fastapi.HTTPException(status_code=404, detail='Picture file not found')

    return fastapi.responses.FileResponse(
        file_path, media_type=picture.mime_type, filename=picture.original_filename
    )


@public_router.get('/locations', response_model=list[models.PhotoLocation])
async def get_locations(
    session: sqlmodel.Session = fastapi.Depends(database.get_session),
    location_service: services.LocationService = fastapi.Depends(get_location_service),
) -> list[models.PhotoLocation]:
    """Get all locations."""
    return location_service.get_all_locations(session)
