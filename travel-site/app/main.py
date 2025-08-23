import contextlib
import datetime
from typing import Annotated

import fastapi
import fastapi.responses
import fastapi.templating
import uvicorn
from app import database
from sqlalchemy import orm


@contextlib.asynccontextmanager
async def db_lifespan(app: fastapi.FastAPI):
    """Lifespan function for database"""
    app.state.db = database.start_db()
    yield
    app.state.db.close()


def get_db(request: fastapi.Request) -> orm.Session:
    return request.app.state.db


DatabaseSession = Annotated[
    orm.Session,
    fastapi.Depends(get_db),
]


def get_current_user(
    request: fastapi.Request,
    db: DatabaseSession,
) -> database.User:
    """Get user from OAuth headers and keep in sync with database"""
    email = request.headers.get('X-Auth-Request-Email')
    if not email:
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_401_UNAUTHORIZED,
            detail='Not authenticated via OAuth',
        )

    # If user is in the database, return corresponding entry
    user = db.query(database.User).filter(database.User.email == email).first()
    if user is not None:
        return user

    # If not, register them in the database and return
    user = database.User(email=email, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


CurrentUser = Annotated[database.User, fastapi.Depends(get_current_user)]
String = Annotated[str, fastapi.Form(...)]
Date = Annotated[datetime.date, fastapi.Form(...)]
AfterLocationId = Annotated[int, fastapi.Form(...)]

# Create app
app = fastapi.FastAPI(title='Travel Locations Admin', lifespan=db_lifespan)
templates = fastapi.templating.Jinja2Templates(directory='app/templates')


@app.get('/', response_class=fastapi.responses.HTMLResponse)
def read_root() -> fastapi.responses.RedirectResponse:
    return fastapi.responses.RedirectResponse(
        url='/admin', status_code=fastapi.status.HTTP_302_FOUND
    )


@app.get('/admin', response_class=fastapi.responses.HTMLResponse)
def admin_dashboard(
    request: fastapi.Request,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> fastapi.responses.HTMLResponse:
    trips = db.query(database.Trip).all()
    return templates.TemplateResponse(
        'admin.html.jinja2',
        {'request': request, 'trips': trips, 'user': current_user},
    )


@app.post('/admin/trips')
def create_trip(
    name: String,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> fastapi.responses.RedirectResponse:
    trip = database.Trip(
        name=name,
        created_by=current_user.id,
    )
    db.add(trip)
    db.commit()
    return fastapi.responses.RedirectResponse(
        url='/admin', status_code=fastapi.status.HTTP_302_FOUND
    )


@app.post('/admin/trips/{trip_id}/locations')
def create_location(
    trip_id: int,
    name: String,
    city: String,
    country: String,
    start_date: Date,
    current_user: CurrentUser,
    db: DatabaseSession,
    after_location_id: AfterLocationId = 0,
) -> fastapi.responses.RedirectResponse:
    trip = db.query(database.Trip).filter(database.Trip.id == trip_id).first()
    if not trip:
        raise fastapi.HTTPException(status_code=404, detail='Trip not found')

    # Calculate order index
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
        start_date=start_date,
        trip_id=trip_id,
        order_index=order_index,
        created_by=current_user.id,
    )
    db.add(location)
    db.commit()
    return fastapi.responses.RedirectResponse(
        url='/admin', status_code=fastapi.status.HTTP_302_FOUND
    )


@app.post('/admin/locations/{location_id}/delete')
def delete_location(
    location_id: int,
    db: DatabaseSession,
) -> fastapi.responses.RedirectResponse:
    location = (
        db.query(database.Location).filter(database.Location.id == location_id).first()
    )
    if not location:
        raise fastapi.HTTPException(status_code=404, detail='Location not found')

    db.delete(location)
    db.commit()
    return fastapi.responses.RedirectResponse(
        url='/admin', status_code=fastapi.status.HTTP_302_FOUND
    )


@app.post('/admin/locations/{location_id}/edit')
def edit_location(
    location_id: int,
    name: String,
    city: String,
    country: String,
    start_date: Date,
    db: DatabaseSession,
) -> fastapi.responses.RedirectResponse:
    location = (
        db.query(database.Location).filter(database.Location.id == location_id).first()
    )
    if not location:
        raise fastapi.HTTPException(status_code=404, detail='Location not found')

    location.name = name  # type: ignore
    location.city = city  # type: ignore
    location.country = country  # type: ignore
    location.start_date = start_date  # type: ignore

    db.commit()
    return fastapi.responses.RedirectResponse(
        url='/admin', status_code=fastapi.status.HTTP_302_FOUND
    )


@app.post('/admin/locations/{location_id}/move')
def move_location(
    location_id: int,
    direction: String,
    db: DatabaseSession,
) -> fastapi.responses.RedirectResponse:
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
    return fastapi.responses.RedirectResponse(
        url='/admin', status_code=fastapi.status.HTTP_302_FOUND
    )


@app.post('/admin/trips/{trip_id}/delete')
def delete_trip(
    trip_id: int,
    db: DatabaseSession,
) -> fastapi.responses.RedirectResponse:
    trip = db.query(database.Trip).filter(database.Trip.id == trip_id).first()
    if not trip:
        raise fastapi.HTTPException(status_code=404, detail='Trip not found')

    db.delete(trip)
    db.commit()
    return fastapi.responses.RedirectResponse(
        url='/admin', status_code=fastapi.status.HTTP_302_FOUND
    )


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
