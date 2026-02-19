# Travel Maps Tests

This directory contains unit tests for the travel-maps module.

## Test Structure

- `conftest.py` - Test fixtures and configuration
- `test_models.py` - Tests for SQLModel data models (Map, Location)
- `test_services.py` - Tests for business logic service functions
- `test_routes.py` - Tests for API endpoints and page routes

## Running Tests

From the repository root:

```bash
# Run all tests
pytest travel-maps/tests/

# Run specific test file
pytest travel-maps/tests/test_models.py

# Run with verbose output
pytest travel-maps/tests/ -v

# Run a specific test
pytest travel-maps/tests/test_models.py::test_map_creation
```

## Test Coverage

The test suite covers:

- **Models** (6 tests)
  - Map and Location creation
  - Relationships between maps and locations
  - Cascade deletion
  - Location ordering

- **Services** (18 tests)
  - CRUD operations for maps
  - CRUD operations for locations
  - Location reordering
  - Edge cases (not found, invalid data)

- **Routes** (17 tests)
  - API endpoints
  - HTML page rendering
  - Request/response validation

## Test Database

Tests use an in-memory SQLite database that is created fresh for each test via the `test_db` fixture. This ensures tests are isolated and don't interfere with each other.

## Dependencies

The tests require:
- pytest
- fastapi.testclient
- sqlmodel

All dependencies are in the main `requirements.txt` file.
