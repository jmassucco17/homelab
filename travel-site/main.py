import datetime
from typing import Annotated

import database
import fastapi
import fastapi.responses
import fastapi.staticfiles
import fastapi.templating
import uvicorn


def get_current_user(
    request: fastapi.Request,
    db: database.DatabaseSession,
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

# Create app
app = fastapi.FastAPI(title='Travel Locations Admin', lifespan=database.db_lifespan)
app.mount('/static', fastapi.staticfiles.StaticFiles(directory='static'), name='static')
templates = fastapi.templating.Jinja2Templates(directory='templates')


@app.get('/', response_class=fastapi.responses.HTMLResponse)
def read_root() -> fastapi.responses.RedirectResponse:
    return fastapi.responses.RedirectResponse(
        url='/admin', status_code=fastapi.status.HTTP_302_FOUND
    )


@app.get('/admin', response_class=fastapi.responses.HTMLResponse)
def admin_dashboard(
    request: fastapi.Request,
    current_user: CurrentUser,
    db: database.DatabaseSession,
) -> fastapi.responses.HTMLResponse:
    locations = db.query(database.Location).all()
    return templates.TemplateResponse(
        'admin.html.jinja2',
        {'request': request, 'locations': locations, 'user': current_user},
    )


@app.post('/admin/locations')
def create_location(
    name: String,
    city: String,
    country: String,
    start_date: Date,
    end_date: Date,
    current_user: CurrentUser,
    db: database.DatabaseSession,
) -> fastapi.responses.RedirectResponse:
    location = database.Location(
        name=name,
        city=city,
        country=country,
        start_date=start_date,
        end_date=end_date,
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
    db: database.DatabaseSession,
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
    end_date: Date,
    db: database.DatabaseSession,
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
    location.end_date = end_date  # type: ignore

    db.commit()
    return fastapi.responses.RedirectResponse(
        url='/admin', status_code=fastapi.status.HTTP_302_FOUND
    )


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
