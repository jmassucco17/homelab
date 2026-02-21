"""Database configuration for daily location tracking."""

import os
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

DATA_DIR = os.getenv('DATA_DIR', '/data')
DATABASE_PATH = Path(DATA_DIR) / 'travel_location.db'

DATABASE_URL = f'sqlite:///{DATABASE_PATH}'

engine = create_engine(DATABASE_URL, echo=False)


def create_db_and_tables():
    """Create database tables if they don't exist."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)


def get_session():
    """Get a database session."""
    with Session(engine) as session:
        yield session
