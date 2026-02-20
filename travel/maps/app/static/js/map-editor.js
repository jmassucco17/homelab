let editorMap;
let editorMarkers = [];
let editorPolyline;
let locations = [];
let currentMapId = null;

function initMapEditor(mapId, initialData) {
    currentMapId = mapId;
    
    editorMap = L.map('map-container').setView([20, 0], 2);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19
    }).addTo(editorMap);
    
    if (initialData && initialData.locations) {
        locations = initialData.locations.sort((a, b) => a.order_index - b.order_index);
        updateLocationsList();
        updateMapDisplay();
    }
    
    initSortable();
}

function initSortable() {
    const locationsList = document.getElementById('locations-list');
    new Sortable(locationsList, {
        animation: 150,
        handle: '.drag-handle',
        onEnd: async function(evt) {
            const items = Array.from(locationsList.children).filter(el => el.classList.contains('location-item'));
            const locationIds = items.map(item => parseInt(item.dataset.locationId));
            
            await fetch('/api/locations/reorder', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({location_ids: locationIds})
            });
            
            locations = locations.sort((a, b) => {
                return locationIds.indexOf(a.id) - locationIds.indexOf(b.id);
            });
            
            updateMapDisplay();
        }
    });
}

async function addLocationFromSearch(result) {
    if (!currentMapId) {
        alert('Please save the map first before adding locations');
        return;
    }
    
    try {
        const response = await fetch(`/api/maps/${currentMapId}/locations`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                name: result.name,
                latitude: result.latitude,
                longitude: result.longitude
            })
        });
        
        if (response.ok) {
            const location = await response.json();
            locations.push(location);
            updateLocationsList();
            updateMapDisplay();
            
            document.getElementById('location-search').value = '';
            document.getElementById('search-results').classList.remove('show');
        }
    } catch (error) {
        console.error('Error adding location:', error);
        alert('Failed to add location');
    }
}

function updateLocationsList() {
    const locationsList = document.getElementById('locations-list');
    const locationCount = document.getElementById('location-count');
    
    locationCount.textContent = `(${locations.length})`;
    
    if (locations.length === 0) {
        locationsList.innerHTML = '<p class="empty-message">No locations yet. Search and add a location to get started.</p>';
        return;
    }
    
    locationsList.innerHTML = locations.map((location, index) => `
        <div class="location-item" data-location-id="${location.id}">
            <span class="drag-handle">≡</span>
            <div class="location-info">
                <span class="location-number">${index + 1}.</span>
                <span class="location-name">${location.name}</span>
                ${location.nickname ? `<span class="location-nickname">"${location.nickname}"</span>` : ''}
            </div>
            <div class="location-actions">
                <button onclick="editLocation(${location.id})" title="Edit">✏️</button>
                <button class="delete" onclick="deleteLocation(${location.id})" title="Delete">❌</button>
            </div>
        </div>
    `).join('');
}

function updateMapDisplay() {
    editorMarkers.forEach(marker => editorMap.removeLayer(marker));
    editorMarkers = [];
    
    if (editorPolyline) {
        editorMap.removeLayer(editorPolyline);
    }
    
    if (locations.length === 0) {
        return;
    }
    
    const bounds = [];
    
    locations.forEach((location, index) => {
        const marker = L.marker([location.latitude, location.longitude]).addTo(editorMap);
        
        const icon = L.divIcon({
            className: 'custom-marker',
            html: `<div style="background: #3498db; color: white; width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; border: 2px solid white; box-shadow: 0 2px 5px rgba(0,0,0,0.3);">${index + 1}</div>`,
            iconSize: [30, 30],
            iconAnchor: [15, 15]
        });
        
        marker.setIcon(icon);
        
        const popupContent = `
            <div class="location-popup">
                <h4>${index + 1}. ${location.name}</h4>
                ${location.nickname ? `<div class="popup-nickname">${location.nickname}</div>` : ''}
                ${location.description ? `<div class="popup-description">${location.description}</div>` : ''}
            </div>
        `;
        marker.bindPopup(popupContent);
        
        editorMarkers.push(marker);
        bounds.push([location.latitude, location.longitude]);
    });
    
    const latLngs = locations.map(loc => [loc.latitude, loc.longitude]);
    editorPolyline = L.polyline(latLngs, {
        color: '#3498db',
        weight: 3,
        opacity: 0.7
    }).addTo(editorMap);
    
    editorMap.fitBounds(bounds, { padding: [50, 50] });
}

function editLocation(locationId) {
    const location = locations.find(loc => loc.id === locationId);
    if (!location) return;
    
    document.getElementById('edit-location-id').value = location.id;
    document.getElementById('edit-location-name').textContent = location.name;
    document.getElementById('edit-nickname').value = location.nickname || '';
    document.getElementById('edit-description').value = location.description || '';
    
    document.getElementById('location-modal').classList.add('show');
}

async function saveLocationEdit() {
    const locationId = parseInt(document.getElementById('edit-location-id').value);
    const nickname = document.getElementById('edit-nickname').value;
    const description = document.getElementById('edit-description').value;
    
    try {
        const response = await fetch(`/api/locations/${locationId}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({nickname, description})
        });
        
        if (response.ok) {
            const location = locations.find(loc => loc.id === locationId);
            if (location) {
                location.nickname = nickname;
                location.description = description;
            }
            
            updateLocationsList();
            updateMapDisplay();
            closeLocationModal();
        }
    } catch (error) {
        console.error('Error updating location:', error);
        alert('Failed to update location');
    }
}

function closeLocationModal() {
    document.getElementById('location-modal').classList.remove('show');
}

async function deleteLocation(locationId) {
    if (!confirm('Are you sure you want to delete this location?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/locations/${locationId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            locations = locations.filter(loc => loc.id !== locationId);
            updateLocationsList();
            updateMapDisplay();
        }
    } catch (error) {
        console.error('Error deleting location:', error);
        alert('Failed to delete location');
    }
}

document.getElementById('location-modal').addEventListener('click', (e) => {
    if (e.target.id === 'location-modal') {
        closeLocationModal();
    }
});
