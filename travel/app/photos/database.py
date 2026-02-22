"""Database configuration and session management for the photos module."""

import os
from collections.abc import Generator

import sqlmodel

data_dir = os.environ.get('DATA_DIR', 'data')
DATABASE_URL = f'sqlite:///{data_dir}/travel.db'

# Create engine with check_same_thread=False for SQLite
engine = sqlmodel.create_engine(
    DATABASE_URL,
    connect_args={'check_same_thread': False},
    echo=True,
)


def create_db_and_tables() -> None:
    """Create database tables."""
    # Import models to ensure they're registered with SQLModel
    from . import models  # noqa: F401 # pyright: ignore[reportUnusedImport]

    sqlmodel.SQLModel.metadata.create_all(engine)


def get_session() -> Generator[sqlmodel.Session, None, None]:
    """Get database session."""
    with sqlmodel.Session(engine) as session:
        yield session


def get_admin_session() -> Generator[sqlmodel.Session, None, None]:
    """Get admin database session - same as regular session in this case."""
    with sqlmodel.Session(engine) as session:
        yield session
