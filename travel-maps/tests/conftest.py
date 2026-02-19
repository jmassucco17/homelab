"""Test configuration and fixtures for travel-maps tests."""

import os
import tempfile
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app import database, main


@pytest.fixture(name='test_db')
def test_database() -> Generator[None, None, None]:
    """Create a test database that is cleaned up after the test."""
    # Use in-memory SQLite database for testing
    test_engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )

    # Replace the global engine with test engine
    original_engine = database.engine
    database.engine = test_engine

    # Create tables
    SQLModel.metadata.create_all(test_engine)

    yield

    # Cleanup
    SQLModel.metadata.drop_all(test_engine)
    database.engine = original_engine


@pytest.fixture(name='session')
def session_fixture(test_db: None) -> Generator[Session, None, None]:
    """Create a test database session."""
    with Session(database.engine) as session:
        yield session


@pytest.fixture(name='client')
def client_fixture(test_db: None) -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(main.app)
