"""Tests for travel-maps API routes."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import services


def test_health_endpoint(client: TestClient) -> None:
    """Test the health check endpoint."""
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'healthy'}


def test_index_page_empty(client: TestClient) -> None:
    """Test the index page with no maps."""
    response = client.get('/')
    assert response.status_code == 200
    assert 'No maps yet' in response.text


def test_index_page_with_maps(client: TestClient, session: Session) -> None:
    """Test the index page with maps."""
    services.create_map(session, 'Test Map', 'A test map')

    response = client.get('/')
    assert response.status_code == 200
    assert 'Test Map' in response.text


def test_new_map_form(client: TestClient) -> None:
    """Test the new map form page."""
    response = client.get('/maps/new')
    assert response.status_code == 200
    assert 'Create New Map' in response.text


def test_create_map_api(client: TestClient) -> None:
    """Test creating a map via API."""
    response = client.post(
        '/api/maps', json={'name': 'New Map', 'description': 'Test description'}
    )
    assert response.status_code == 200
    data = response.json()
    assert data['name'] == 'New Map'
    assert data['description'] == 'Test description'
    assert 'id' in data


def test_create_map_without_description(client: TestClient) -> None:
    """Test creating a map without description."""
    response = client.post('/api/maps', json={'name': 'Simple Map'})
    assert response.status_code == 200
    data = response.json()
    assert data['name'] == 'Simple Map'
    assert data['description'] is None


def test_get_map_api(client: TestClient, session: Session) -> None:
    """Test getting a map via API."""
    map_obj = services.create_map(session, 'Test Map')

    response = client.get(f'/api/maps/{map_obj.id}')
    assert response.status_code == 200
    data = response.json()
    assert data['id'] == map_obj.id
    assert data['name'] == 'Test Map'
    assert 'locations' in data


def test_get_map_not_found(client: TestClient) -> None:
    """Test getting a non-existent map."""
    response = client.get('/api/maps/999')
    assert response.status_code == 404


def test_update_map_api(client: TestClient, session: Session) -> None:
    """Test updating a map via API."""
    map_obj = services.create_map(session, 'Original Name')

    response = client.put(
        f'/api/maps/{map_obj.id}',
        json={'name': 'Updated Name', 'description': 'Updated description'},
    )
    assert response.status_code == 200
    data = response.json()
    assert data['name'] == 'Updated Name'
    assert data['description'] == 'Updated description'


def test_delete_map_api(client: TestClient, session: Session) -> None:
    """Test deleting a map via API."""
    map_obj = services.create_map(session, 'To Delete')

    response = client.delete(f'/api/maps/{map_obj.id}')
    assert response.status_code == 200
    assert response.json()['success'] is True


def test_add_location_api(client: TestClient, session: Session) -> None:
    """Test adding a location via API."""
    map_obj = services.create_map(session, 'Test Map')

    response = client.post(
        f'/api/maps/{map_obj.id}/locations',
        json={
            'name': 'Paris, France',
            'latitude': 48.8566,
            'longitude': 2.3522,
            'nickname': 'City of Light',
            'description': 'Beautiful',
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data['name'] == 'Paris, France'
    assert data['latitude'] == 48.8566
    assert data['longitude'] == 2.3522
    assert data['nickname'] == 'City of Light'
    assert data['order_index'] == 0


def test_update_location_api(client: TestClient, session: Session) -> None:
    """Test updating a location via API."""
    map_obj = services.create_map(session, 'Test Map')
    location = services.add_location_to_map(session, map_obj.id, 'Paris', 48.8566, 2.3522)

    response = client.put(
        f'/api/locations/{location.id}',
        json={'nickname': 'City of Light', 'description': 'Beautiful city'},
    )
    assert response.status_code == 200
    data = response.json()
    assert data['nickname'] == 'City of Light'
    assert data['description'] == 'Beautiful city'


def test_delete_location_api(client: TestClient, session: Session) -> None:
    """Test deleting a location via API."""
    map_obj = services.create_map(session, 'Test Map')
    location = services.add_location_to_map(session, map_obj.id, 'Paris', 48.8566, 2.3522)

    response = client.delete(f'/api/locations/{location.id}')
    assert response.status_code == 200
    assert response.json()['success'] is True


def test_reorder_locations_api(client: TestClient, session: Session) -> None:
    """Test reordering locations via API."""
    map_obj = services.create_map(session, 'Test Map')
    loc1 = services.add_location_to_map(session, map_obj.id, 'First', 0, 0)
    loc2 = services.add_location_to_map(session, map_obj.id, 'Second', 0, 0)

    response = client.post(
        '/api/locations/reorder', json={'location_ids': [loc2.id, loc1.id]}
    )
    assert response.status_code == 200
    assert response.json()['success'] is True


def test_view_map_page(client: TestClient, session: Session) -> None:
    """Test viewing a map page."""
    map_obj = services.create_map(session, 'Europe Trip', 'Summer vacation')

    response = client.get(f'/maps/{map_obj.id}/view')
    assert response.status_code == 200
    assert 'Europe Trip' in response.text
    assert 'Summer vacation' in response.text


def test_edit_map_page(client: TestClient, session: Session) -> None:
    """Test editing a map page."""
    map_obj = services.create_map(session, 'Europe Trip')

    response = client.get(f'/maps/{map_obj.id}/edit')
    assert response.status_code == 200
    assert 'Edit Map' in response.text
    assert 'Europe Trip' in response.text


def test_geocode_endpoint(client: TestClient) -> None:
    """Test the geocode endpoint."""
    # Without mocking, this will fail unless we have internet
    # But we can test that it returns an empty list for short queries
    response = client.get('/api/geocode?q=P')
    assert response.status_code == 200
    assert response.json() == []
