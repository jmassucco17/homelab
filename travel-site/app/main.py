"""
Consolidated travel site app with selective OAuth2 authentication.

- Public routes: No authentication required
- Admin routes: OAuth2 authentication required
- Smart database session management (read-only vs read-write)
"""

import contextlib
import datetime
from typing import Annotated

import fastapi
import uvicorn
from app import database
from fastapi import APIRouter, responses, templating
from sqlalchemy import orm


@contextlib.asynccontextmanager
async def db_lifespan(app: fastapi.FastAPI):
    """Lifespan function for database"""
    # Initialize database
    test_session = database.start_db()
    test_session.close()
    yield


def get_read_only_db():
    """Get read-only database session for public routes"""
    session = database.start_db_read_only()
    try:
        yield session
    finally:
        session.close()


def get_admin_db():
    """Get admin database session for protected routes"""
    session = database.start_db()
    try:
        yield session
    finally:
        session.close()


def get_current_user_optional(
    request: fastapi.Request,
) -> database.User | None:
    """
    Get current user if authenticated, None otherwise.
    Used for optional authentication.
    """
    email = request.headers.get('X-Auth-Request-Email')
    if not email:
        return None

    # Get admin DB session for user lookup/creation
    admin_session = database.start_db()
    try:
        user = (
            admin_session.query(database.User)
            .filter(database.User.email == email)
            .first()
        )
        if user is not None:
            return user

        # Create new user if doesn't exist
        user = database.User(email=email, is_active=True)
        admin_session.add(user)
        admin_session.commit()
        admin_session.refresh(user)
        return user
    finally:
        admin_session.close()


def get_current_user_required(
    request: fastapi.Request,
) -> database.User:
    """
    Get current user, raise 401 if not authenticated.
    Used for required authentication.
    """
    user = get_current_user_optional(request)
    if user is None:
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_401_UNAUTHORIZED,
            detail='Authentication required. Please log in.',
        )
    return user


# Type annotations for dependency injection
ReadOnlyDB = Annotated[database.ReadOnlySession, fastapi.Depends(get_read_only_db)]
AdminDB = Annotated[orm.Session, fastapi.Depends(get_admin_db)]
OptionalUser = Annotated[
    database.User | None, fastapi.Depends(get_current_user_optional)
]
RequiredUser = Annotated[database.User, fastapi.Depends(get_current_user_required)]

# Form types for admin routes
String = Annotated[str, fastapi.Form(...)]
Date = Annotated[datetime.date, fastapi.Form(...)]
Int = Annotated[int, fastapi.Form(...)]
AfterLocationId = Annotated[int, fastapi.Form(...)]

# Create main app
app = fastapi.FastAPI(
    title='Travel Site',
    description='Public calendar with admin interface',
    lifespan=db_lifespan,
)

# Template engine
templates = templating.Jinja2Templates(directory='app/templates')

# Create routers for organization
public_router = APIRouter(tags=['Public'])
admin_router = APIRouter(prefix='/admin', tags=['Admin'])


# =============================================================================
# PUBLIC ROUTES (No authentication required)
# =============================================================================


@public_router.get('/health')
def health_check():
    """Health check endpoint"""
    return {'status': 'healthy', 'service': 'travel-site-consolidated'}


@public_router.get('/', response_class=responses.HTMLResponse)
def public_calendar(request: fastapi.Request, db: ReadOnlyDB) -> responses.HTMLResponse:
    """Public calendar view of all trips"""
    trips = db.query(database.Trip).all()  # type: ignore
    return templates.TemplateResponse(
        'public/calendar.html.jinja2',
        {'request': request, 'trips': trips},
    )


# =============================================================================
# ADMIN ROUTES (Authentication required)
# =============================================================================


@admin_router.get('/', response_class=responses.HTMLResponse)
def admin_dashboard(
    request: fastapi.Request, current_user: RequiredUser, db: AdminDB
) -> responses.HTMLResponse:
    """Main admin dashboard"""
    trips = db.query(database.Trip).all()
    return templates.TemplateResponse(
        'admin/admin.html.jinja2',
        {'request': request, 'trips': trips, 'user': current_user},
    )


@admin_router.post('/trips')
def create_trip(
    name: String, start_date: Date, current_user: RequiredUser, db: AdminDB
) -> responses.RedirectResponse:
    """Create a trip"""
    trip = database.Trip(name=name, start_date=start_date, created_by=current_user.id)
    db.add(trip)
    db.commit()
    return responses.RedirectResponse(
        url='/admin', status_code=fastapi.status.HTTP_302_FOUND
    )


@admin_router.post('/trips/{trip_id}/delete')
def delete_trip(
    trip_id: int, current_user: RequiredUser, db: AdminDB
) -> responses.RedirectResponse:
    """Delete a trip"""
    trip = db.query(database.Trip).filter(database.Trip.id == trip_id).first()
    if not trip:
        raise fastapi.HTTPException(status_code=404, detail='Trip not found')

    db.delete(trip)
    db.commit()
    return responses.RedirectResponse(
        url='/admin', status_code=fastapi.status.HTTP_302_FOUND
    )


@admin_router.post('/trips/{trip_id}/locations')
def create_location(
    trip_id: int,
    name: String,
    city: String,
    country: String,
    days: Int,
    current_user: RequiredUser,
    db: AdminDB,
    after_location_id: AfterLocationId = 0,
) -> responses.RedirectResponse:
    """Create a location in a trip"""
    trip = db.query(database.Trip).filter(database.Trip.id == trip_id).first()
    if not trip:
        raise fastapi.HTTPException(status_code=404, detail='Trip not found')

    # Calculate order index (same logic as before)
    if after_location_id:
        after_location = (
            db.query(database.Location)
            .filter(
                database.Location.id == after_location_id,
                database.Location.trip_id == trip_id,
            )
            .first()
        )
        if after_location:
            order_index = after_location.order_index + 1
            # Update order of subsequent locations
            db.query(database.Location).filter(
                database.Location.trip_id == trip_id,
                database.Location.order_index >= order_index,
            ).update({database.Location.order_index: database.Location.order_index + 1})
        else:
            order_index = 0
    else:
        # Add at end
        max_order = (
            db.query(database.Location)
            .filter(database.Location.trip_id == trip_id)
            .count()
        )
        order_index = max_order

    location = database.Location(
        name=name,
        city=city,
        country=country,
        days=days,
        trip_id=trip_id,
        order_index=order_index,
        created_by=current_user.id,
    )
    db.add(location)
    db.commit()
    return responses.RedirectResponse(
        url='/admin', status_code=fastapi.status.HTTP_302_FOUND
    )


@admin_router.post('/locations/{location_id}/delete')
def delete_location(
    location_id: int,
    current_user: RequiredUser,
    db: AdminDB,
) -> responses.RedirectResponse:
    """Delete a location"""
    location = (
        db.query(database.Location).filter(database.Location.id == location_id).first()
    )
    if not location:
        raise fastapi.HTTPException(status_code=404, detail='Location not found')

    db.delete(location)
    db.commit()
    return responses.RedirectResponse(
        url='/admin', status_code=fastapi.status.HTTP_302_FOUND
    )


@admin_router.post('/locations/{location_id}/edit')
def edit_location(
    location_id: int,
    name: String,
    city: String,
    country: String,
    days: Int,
    current_user: RequiredUser,
    db: AdminDB,
) -> responses.RedirectResponse:
    """Edit a location"""
    location = (
        db.query(database.Location).filter(database.Location.id == location_id).first()
    )
    if not location:
        raise fastapi.HTTPException(status_code=404, detail='Location not found')

    location.name = name  # type: ignore
    location.city = city  # type: ignore
    location.country = country  # type: ignore
    location.days = days  # type: ignore

    db.commit()
    return responses.RedirectResponse(
        url='/admin', status_code=fastapi.status.HTTP_302_FOUND
    )


@admin_router.post('/locations/{location_id}/move')
def move_location(
    location_id: int,
    direction: String,
    current_user: RequiredUser,
    db: AdminDB,
) -> responses.RedirectResponse:
    """Move a location up or down in order"""
    location = (
        db.query(database.Location).filter(database.Location.id == location_id).first()
    )
    if not location:
        raise fastapi.HTTPException(status_code=404, detail='Location not found')

    if direction == 'up':
        # Find the location immediately above
        prev_location = (
            db.query(database.Location)
            .filter(
                database.Location.trip_id == location.trip_id,
                database.Location.order_index < location.order_index,
            )
            .order_by(database.Location.order_index.desc())
            .first()
        )

        if prev_location:
            # Swap order indices
            temp_order = location.order_index
            location.order_index = prev_location.order_index  # type: ignore
            prev_location.order_index = temp_order  # type: ignore

    elif direction == 'down':
        # Find the location immediately below
        next_location = (
            db.query(database.Location)
            .filter(
                database.Location.trip_id == location.trip_id,
                database.Location.order_index > location.order_index,
            )
            .order_by(database.Location.order_index.asc())
            .first()
        )

        if next_location:
            # Swap order indices
            temp_order = location.order_index
            location.order_index = next_location.order_index  # type: ignore
            next_location.order_index = temp_order  # type: ignore

    db.commit()
    return responses.RedirectResponse(
        url='/admin', status_code=fastapi.status.HTTP_302_FOUND
    )


# =============================================================================
# MIXED ROUTES (Optional authentication)
# =============================================================================


@app.get('/status')
def status_page(request: fastapi.Request, user: OptionalUser, db: ReadOnlyDB):
    """
    Example of mixed route - shows different info based on auth status.
    Public info for everyone, admin info if authenticated.
    """
    trip_count = db.query(database.Trip).count()  # type: ignore

    if user:
        # Show admin info
        location_count = db.query(database.Location).count()  # type: ignore
        return {
            'status': 'authenticated',
            'user': user.email,
            'stats': {'trips': trip_count, 'locations': location_count},
        }
    else:
        # Show public info only
        return {'status': 'public', 'stats': {'trips': trip_count}}


# Register routers
app.include_router(public_router)
app.include_router(admin_router)


# Root redirect based on authentication status
@app.get('/admin')
def admin_redirect() -> responses.RedirectResponse:
    """Redirect to admin dashboard"""
    return responses.RedirectResponse(
        url='/admin/', status_code=fastapi.status.HTTP_302_FOUND
    )


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
