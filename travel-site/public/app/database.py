import datetime
import os

import sqlalchemy
from sqlalchemy import orm

DATABASE_URL = 'sqlite:////data/travel.db'

# Create read-only sqlalchemy engine
engine = sqlalchemy.create_engine(
    DATABASE_URL,
    connect_args={
        'check_same_thread': False,
        'isolation_level': None,  # Autocommit mode for better read consistency
    },
    # Set connection to read-only mode
    pool_pre_ping=True,
    pool_recycle=300,  # Recycle connections every 5 minutes
    echo=False,
)

# Create read-only session
ReadOnlySessionLocal = orm.sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = orm.declarative_base()


def current_time_utc() -> datetime.datetime:
    """Helper for getting current utc datetime"""
    return datetime.datetime.now(tz=datetime.UTC)


class User(Base):
    """User (reflection of Google OAuth user) - READ ONLY"""

    __tablename__ = 'users'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, index=True)
    email = sqlalchemy.Column(
        sqlalchemy.String, unique=True, index=True, nullable=False
    )
    is_active = sqlalchemy.Column(sqlalchemy.Boolean, default=True)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, default=current_time_utc)

    locations = orm.relationship('Location', back_populates='creator')
    trips = orm.relationship('Trip', back_populates='creator')


class Trip(Base):
    """Trip (contains one or more locations) - READ ONLY"""

    __tablename__ = 'trips'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, index=True)
    name = sqlalchemy.Column(sqlalchemy.String, nullable=False, index=True)
    start_date = sqlalchemy.Column(sqlalchemy.Date, nullable=False)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, default=current_time_utc)
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime, default=current_time_utc, onupdate=current_time_utc
    )
    created_by = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey('users.id')
    )

    creator = orm.relationship('User', back_populates='trips')
    locations = orm.relationship(
        'Location', back_populates='trip', order_by='Location.order_index'
    )

    @property
    def end_date(self) -> datetime.date:
        """Calculate end date based on location durations"""
        if not self.locations:
            return self.start_date  # type: ignore

        total_days = sum(location.days for location in self.locations)
        return self.start_date + datetime.timedelta(days=total_days - 1)  # type: ignore

    @property
    def duration_days(self) -> int:
        """Calculate total duration in days"""
        return (
            sum(location.days for location in self.locations) if self.locations else 1
        )


class Location(Base):
    """Location (city or similar) - READ ONLY"""

    __tablename__ = 'locations'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, index=True)
    name = sqlalchemy.Column(sqlalchemy.String, nullable=False, index=True)
    city = sqlalchemy.Column(sqlalchemy.String)
    country = sqlalchemy.Column(sqlalchemy.String)
    days = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=1)
    order_index = sqlalchemy.Column(sqlalchemy.Integer, default=0)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, default=current_time_utc)
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime, default=current_time_utc, onupdate=current_time_utc
    )
    created_by = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey('users.id')
    )
    trip_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey('trips.id'))

    creator = orm.relationship('User', back_populates='locations')
    trip = orm.relationship('Trip', back_populates='locations')

    @property
    def start_date(self) -> datetime.date:
        """Calculate start date based on trip start date and previous locations"""
        if not self.trip:
            return datetime.date.today()

        trip_start = self.trip.start_date

        # Find all locations before this one in the same trip
        previous_locations = [
            loc for loc in self.trip.locations if loc.order_index < self.order_index
        ]

        # Calculate days from previous locations (with overlap). Each location overlaps
        # by 1 day with the next (location 2 starts when location 1 ends)
        days_offset = (
            sum(loc.days - 1 for loc in previous_locations) if previous_locations else 0
        )

        return trip_start + datetime.timedelta(days=days_offset)

    @property
    def end_date(self) -> datetime.date:
        """Calculate end date based on start date and duration"""
        return self.start_date + datetime.timedelta(days=self.days - 1)  # type: ignore


class ReadOnlySession:
    """Wrapper to ensure database session is read-only"""

    _session: orm.Session

    def __init__(self, session: orm.Session):
        self._session = session

    def query(self, *args, **kwargs):  # type: ignore
        """Allow queries"""
        return self._session.query(*args, **kwargs)  # type: ignore

    def get(self, *args, **kwargs):  # type: ignore
        """Allow get operations"""
        return self._session.get(*args, **kwargs)  # type: ignore

    def close(self) -> None:
        """Allow closing session"""
        return self._session.close()

    def __getattr__(self, name: str):
        """Block write operations"""
        if name in [
            'add',
            'delete',
            'commit',
            'flush',
            'merge',
            'bulk_insert_mappings',
            'bulk_update_mappings',
        ]:
            raise AttributeError(
                f"Write operation '{name}' not allowed in read-only mode"
            )
        return getattr(self._session, name)


def start_db() -> ReadOnlySession:
    """Start db and return read-only session"""
    # Ensure data directory exists
    os.makedirs('/data', exist_ok=True)

    # If database doesn't exist, create the schema but don't populate it
    # The admin site will handle data creation
    if not os.path.exists('/data/travel.db'):
        # Create empty database with schema
        Base.metadata.create_all(bind=engine)

    session = ReadOnlySessionLocal()
    return ReadOnlySession(session)
