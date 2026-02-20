let map;
let markers = [];
let polyline;

function initMapViewer(mapData) {
    if (!mapData.locations || mapData.locations.length === 0) {
        document.getElementById('map-container').innerHTML = 
            '<div style="display: flex; align-items: center; justify-content: center; height: 100%; color: #999;">No locations to display</div>';
        return;
    }
    
    map = L.map('map-container');
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19
    }).addTo(map);
    
    const locations = mapData.locations;
    const bounds = [];
    
    locations.forEach((location, index) => {
        const marker = L.marker([location.latitude, location.longitude]).addTo(map);
        
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
        
        markers.push(marker);
        bounds.push([location.latitude, location.longitude]);
    });
    
    const latLngs = locations.map(loc => [loc.latitude, loc.longitude]);
    polyline = L.polyline(latLngs, {
        color: '#3498db',
        weight: 3,
        opacity: 0.7
    }).addTo(map);
    
    map.fitBounds(bounds, { padding: [50, 50] });
}
