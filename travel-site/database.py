import datetime
import os

import sqlalchemy
from sqlalchemy import orm

DATABASE_URL = 'sqlite:///./data/travel.db'

# Create sqlalchemy classes
engine = sqlalchemy.create_engine(
    DATABASE_URL, connect_args={'check_same_thread': False}
)
SessionLocal = orm.sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = orm.declarative_base()


def current_time_utc() -> datetime.datetime:
    """Helper for getting current utc datetime"""
    return datetime.datetime.now(tz=datetime.UTC)


class User(Base):
    """User (reflection of Google OAuth user)"""

    __tablename__ = 'users'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, index=True)
    email = sqlalchemy.Column(
        sqlalchemy.String, unique=True, index=True, nullable=False
    )
    is_active = sqlalchemy.Column(sqlalchemy.Boolean, default=True)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, default=current_time_utc)

    locations = orm.relationship('Location', back_populates='creator')


class Location(Base):
    __tablename__ = 'locations'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, index=True)
    name = sqlalchemy.Column(sqlalchemy.String, nullable=False, index=True)
    city = sqlalchemy.Column(sqlalchemy.String)
    country = sqlalchemy.Column(sqlalchemy.String)
    start_date = sqlalchemy.Column(sqlalchemy.Date)
    end_date = sqlalchemy.Column(sqlalchemy.Date)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, default=current_time_utc)
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime, default=current_time_utc, onupdate=current_time_utc
    )
    created_by = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey('users.id')
    )

    creator = orm.relationship('User', back_populates='locations')


def start_db() -> orm.Session:
    os.makedirs('data', exist_ok=True)
    Base.metadata.create_all(bind=engine)
    return SessionLocal()
