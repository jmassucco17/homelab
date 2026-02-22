"""Database configuration and session management for the maps module."""

import collections.abc
import os
import pathlib

import sqlmodel

DATA_DIR = os.getenv('DATA_DIR', '/data')
DATABASE_PATH = pathlib.Path(DATA_DIR) / 'travel_maps.db'

DATABASE_URL = f'sqlite:///{DATABASE_PATH}'

engine = sqlmodel.create_engine(DATABASE_URL, echo=False)


def create_db_and_tables() -> None:
    """Create database tables if they don't exist."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    sqlmodel.SQLModel.metadata.create_all(engine)


def get_session() -> collections.abc.Generator[sqlmodel.Session, None, None]:
    """Get a database session."""
    with sqlmodel.Session(engine) as session:
        yield session
