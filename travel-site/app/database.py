"""Database configuration and session management."""

# Database URL - using SQLite stored in the data directory
import os

from sqlmodel import Session, SQLModel, create_engine

data_dir = os.environ.get('DATA_DIR', 'data')
DATABASE_URL = f'sqlite:///{data_dir}/travel.db'

# Create engine with check_same_thread=False for SQLite
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False})


def create_db_and_tables():
    """Create database tables."""
    # Import models to ensure they're registered with SQLModel
    from . import models  # noqa: F401 # pyright: ignore[reportUnusedImport]

    SQLModel.metadata.create_all(engine)


def get_session():
    """Get database session."""
    with Session(engine) as session:
        yield session


def get_admin_session():
    """Get admin database session - same as regular session in this case."""
    with Session(engine) as session:
        yield session
