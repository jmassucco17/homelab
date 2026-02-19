# Travel Maps Module - Implementation Plan

## Overview

This document describes the detailed plan for implementing a new **travel-maps** module for the homelab website. The module will provide an interactive web application for creating, viewing, editing, and exporting custom travel maps with multiple locations.

## Project Summary

The travel-maps module will be a standalone web service deployed at `maps.jamesmassucco.com` that allows users to:
- Create named travel maps
- Add locations using a Google Maps-style search interface
- Reorder locations in the map
- Add nicknames and descriptions to each location
- View an interactive map with dots for each location connected by lines
- Export maps as JPG images

## Architecture

### Technology Stack

Based on the existing repository patterns, the travel-maps module will use:

- **Backend Framework**: FastAPI (Python 3.12)
- **Database**: SQLModel with SQLite for data persistence
- **Frontend**: HTML/CSS/JavaScript with Jinja2 templates
- **Mapping Library**: Leaflet.js (open-source alternative to Google Maps)
- **Geocoding API**: Nominatim (OpenStreetMap's geocoding service) or Google Maps Geocoding API
- **Image Export**: html2canvas or Leaflet's built-in export capabilities
- **Containerization**: Docker with docker-compose
- **Reverse Proxy**: Traefik (existing infrastructure)

### Module Structure

Following the existing pattern (similar to `blog/` and `travel-site/`), the module will be organized as:

```
travel-maps/
├── Dockerfile
├── docker-compose.yml
├── start.sh
├── README.md
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point
│   ├── database.py          # Database configuration and initialization
│   ├── models.py            # SQLModel data models
│   ├── routes.py            # API endpoints and page routes
│   ├── services.py          # Business logic for maps and locations
│   ├── static/
│   │   ├── css/
│   │   │   └── styles.css   # Custom styles
│   │   └── js/
│   │       ├── map-viewer.js    # Map display logic
│   │       ├── map-editor.js    # Map editing logic
│   │       └── location-search.js  # Location search functionality
│   └── templates/
│       ├── base.html.jinja2
│       ├── index.html.jinja2       # List of all maps
│       ├── map-view.html.jinja2   # View a single map
│       └── map-edit.html.jinja2   # Create/edit a map
└── migrations/              # Database migration scripts (if needed)
```

## Data Model

### Database Schema

The module will use three main database tables:

#### 1. Map Table
Stores information about each travel map:

```python
class Map(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=200, index=True)
    description: str | None = Field(default=None, max_length=1000)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    locations: list["Location"] = Relationship(back_populates="map", 
                                               cascade_delete=True,
                                               sa_relationship_kwargs={"order_by": "Location.order_index"})
```

#### 2. Location Table
Stores individual locations within a map:

```python
class Location(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    map_id: int = Field(foreign_key="map.id", index=True)
    order_index: int = Field(default=0)  # Order of location in the journey
    
    # Geographic data
    name: str = Field(max_length=200)  # Full place name from geocoding
    latitude: float
    longitude: float
    
    # Optional user-provided data
    nickname: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    map: Map = Relationship(back_populates="locations")
```

#### 3. MapSettings Table (Optional Enhancement)
Store user preferences for map display:

```python
class MapSettings(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    map_id: int = Field(foreign_key="map.id", unique=True)
    
    # Display settings
    default_zoom: int = Field(default=2)
    center_lat: float = Field(default=0.0)
    center_lng: float = Field(default=0.0)
    
    # Styling options
    line_color: str = Field(default="#FF5733")
    line_width: int = Field(default=3)
    marker_color: str = Field(default="#3498db")
    
    # Relationship
    map: Map = Relationship()
```

## User Interface Design

### Page 1: Map List (Index Page)

**Route**: `/`

**Features**:
- Display a grid or list of all existing maps
- Each map card shows:
  - Map name
  - Number of locations
  - Thumbnail preview (optional for MVP)
  - Created/updated date
  - Actions: View, Edit, Delete
- "Create New Map" button prominently displayed at the top
- Search/filter functionality (optional for MVP)

**UI Elements**:
```html
<!-- Simplified mockup -->
<div class="container">
  <header>
    <h1>My Travel Maps</h1>
    <button class="btn-primary" onclick="createMap()">+ New Map</button>
  </header>
  
  <div class="maps-grid">
    <!-- For each map -->
    <div class="map-card">
      <h3>European Adventure</h3>
      <p>5 locations</p>
      <p class="date">Updated: Feb 10, 2026</p>
      <div class="actions">
        <a href="/maps/1/view">View</a>
        <a href="/maps/1/edit">Edit</a>
        <button onclick="deleteMap(1)">Delete</button>
      </div>
    </div>
  </div>
</div>
```

### Page 2: Create/Edit Map Page

**Routes**: 
- `/maps/new` - Create new map
- `/maps/{map_id}/edit` - Edit existing map

**Features**:

1. **Map Information Section**:
   - Text input for map name (required)
   - Textarea for map description (optional)

2. **Location Search Section**:
   - Search input with autocomplete
   - Powered by Nominatim or Google Places Autocomplete
   - Results dropdown showing matching locations
   - Click to add location to map

3. **Locations List Section**:
   - Draggable list showing all added locations in order
   - Each location shows:
     - Order number (auto-numbered)
     - Location name
     - Edit button (opens modal for nickname/description)
     - Remove button
   - Drag handles for reordering

4. **Map Preview Section**:
   - Live-updating Leaflet map
   - Shows markers for all locations
   - Lines connecting locations in order
   - Pan/zoom controls

5. **Action Buttons**:
   - Save Map
   - Cancel (return to index)
   - Export as JPG

**UI Flow**:
```
┌─────────────────────────────────────────┐
│ Edit Map: European Adventure            │
├─────────────────────────────────────────┤
│                                         │
│ Map Name: [European Adventure      ]   │
│ Description: [My trip across Europe]   │
│                                         │
│ Add Location                            │
│ Search: [Paris, France          ][🔍]  │
│         └─ Autocomplete dropdown        │
│                                         │
│ Locations (drag to reorder):           │
│ ┌───────────────────────────────────┐  │
│ │ ≡ 1. Paris, France           ✏️ ❌│  │
│ │ ≡ 2. Rome, Italy             ✏️ ❌│  │
│ │ ≡ 3. Barcelona, Spain        ✏️ ❌│  │
│ └───────────────────────────────────┘  │
│                                         │
│ ┌─────────────────────────────────┐    │
│ │                                 │    │
│ │      [Interactive Map]          │    │
│ │    with markers and lines       │    │
│ │                                 │    │
│ └─────────────────────────────────┘    │
│                                         │
│ [Save] [Cancel] [Export as JPG]        │
└─────────────────────────────────────────┘
```

**Location Edit Modal**:
```
┌──────────────────────────────────┐
│ Edit Location: Paris, France     │
├──────────────────────────────────┤
│ Nickname (optional):             │
│ [City of Light            ]      │
│                                  │
│ Description (optional):          │
│ ┌──────────────────────────────┐ │
│ │ Amazing food and culture.    │ │
│ │ Visited the Eiffel Tower!    │ │
│ └──────────────────────────────┘ │
│                                  │
│        [Save] [Cancel]           │
└──────────────────────────────────┘
```

### Page 3: View Map Page

**Route**: `/maps/{map_id}/view`

**Features**:
- Display map name and description
- Full-screen interactive Leaflet map
- Markers for each location with:
  - Order number badge
  - Popup showing:
    - Location name
    - Nickname (if provided)
    - Description (if provided)
- Lines connecting locations in order
- "Export as JPG" button
- "Edit Map" button
- "Back to Maps" button

**UI Elements**:
```html
<div class="map-view">
  <header>
    <h1>European Adventure</h1>
    <p class="description">My trip across Europe in summer 2025</p>
    <div class="actions">
      <button onclick="exportMap()">Export as JPG</button>
      <a href="/maps/1/edit">Edit Map</a>
      <a href="/">Back to Maps</a>
    </div>
  </header>
  
  <div id="map-container" style="height: 80vh;">
    <!-- Leaflet map rendered here -->
  </div>
  
  <aside class="location-list">
    <!-- Optional sidebar with location list -->
    <h3>Journey Route</h3>
    <ol>
      <li>Paris, France - "City of Light"</li>
      <li>Rome, Italy - "Eternal City"</li>
      <li>Barcelona, Spain</li>
    </ol>
  </aside>
</div>
```

## API Endpoints

### Map Management

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| GET | `/` | Render index page with all maps | - | HTML |
| GET | `/api/maps` | Get all maps (JSON) | - | `{maps: [Map]}` |
| GET | `/api/maps/{id}` | Get single map with locations | - | `{map: Map, locations: [Location]}` |
| POST | `/api/maps` | Create new map | `{name: string, description?: string}` | `{id: int, ...}` |
| PUT | `/api/maps/{id}` | Update map | `{name?: string, description?: string}` | `{id: int, ...}` |
| DELETE | `/api/maps/{id}` | Delete map | - | `{success: bool}` |

### Location Management

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| POST | `/api/maps/{map_id}/locations` | Add location to map | `{name: string, latitude: float, longitude: float, nickname?: string, description?: string}` | `{id: int, ...}` |
| PUT | `/api/locations/{id}` | Update location | `{nickname?: string, description?: string, order_index?: int}` | `{id: int, ...}` |
| DELETE | `/api/locations/{id}` | Remove location | - | `{success: bool}` |
| PUT | `/api/maps/{map_id}/locations/reorder` | Reorder locations | `{location_ids: [int]}` | `{success: bool}` |

### Geocoding

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| GET | `/api/geocode/search?q={query}` | Search for locations | - | `{results: [{name: string, lat: float, lon: float}]}` |

### Export

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| GET | `/api/maps/{id}/export` | Export map as JPG | - | Binary JPG file |

## Frontend Implementation Details

### Location Search with Autocomplete

**Library**: Use Leaflet-Geosearch or custom implementation with Nominatim API

**Implementation**:
```javascript
// location-search.js
class LocationSearch {
  constructor(inputElement, onSelectCallback) {
    this.input = inputElement;
    this.onSelect = onSelectCallback;
    this.setupAutocomplete();
  }
  
  async search(query) {
    // Call Nominatim API
    const response = await fetch(
      `https://nominatim.openstreetmap.org/search?` +
      `q=${encodeURIComponent(query)}&format=json&limit=5`
    );
    return await response.json();
  }
  
  setupAutocomplete() {
    // Debounced search on input
    let timeout;
    this.input.addEventListener('input', (e) => {
      clearTimeout(timeout);
      timeout = setTimeout(() => this.handleInput(e.target.value), 300);
    });
  }
  
  async handleInput(query) {
    if (query.length < 3) return;
    const results = await this.search(query);
    this.showResults(results);
  }
  
  showResults(results) {
    // Display dropdown with results
    // On click, call this.onSelect(result)
  }
}
```

### Map Visualization with Leaflet

**Library**: Leaflet.js (CDN or npm package)

**Implementation**:
```javascript
// map-viewer.js
class TravelMapViewer {
  constructor(containerId, locations) {
    this.locations = locations;
    this.map = L.map(containerId);
    this.setupMap();
    this.renderLocations();
  }
  
  setupMap() {
    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors'
    }).addTo(this.map);
  }
  
  renderLocations() {
    if (this.locations.length === 0) return;
    
    const markers = [];
    const latlngs = [];
    
    this.locations.forEach((loc, index) => {
      // Create custom marker with number
      const marker = L.marker([loc.latitude, loc.longitude], {
        icon: this.createNumberedIcon(index + 1)
      });
      
      // Add popup with location info
      const popupContent = this.createPopupContent(loc, index + 1);
      marker.bindPopup(popupContent);
      marker.addTo(this.map);
      
      markers.push(marker);
      latlngs.push([loc.latitude, loc.longitude]);
    });
    
    // Draw line connecting locations
    if (latlngs.length > 1) {
      const polyline = L.polyline(latlngs, {
        color: '#FF5733',
        weight: 3
      }).addTo(this.map);
    }
    
    // Fit map to show all markers
    const group = L.featureGroup(markers);
    this.map.fitBounds(group.getBounds().pad(0.1));
  }
  
  createNumberedIcon(number) {
    // Create custom marker with number badge
    return L.divIcon({
      className: 'numbered-marker',
      html: `<div class="marker-pin"><span>${number}</span></div>`,
      iconSize: [30, 42],
      iconAnchor: [15, 42]
    });
  }
  
  createPopupContent(location, number) {
    return `
      <div class="location-popup">
        <h4>${number}. ${location.name}</h4>
        ${location.nickname ? `<p class="nickname">"${location.nickname}"</p>` : ''}
        ${location.description ? `<p class="description">${location.description}</p>` : ''}
      </div>
    `;
  }
}
```

### Drag-and-Drop Reordering

**Library**: SortableJS or custom drag-and-drop implementation

**Implementation**:
```javascript
// map-editor.js
import Sortable from 'sortablejs';

class MapEditor {
  constructor(listElement, onReorderCallback) {
    this.list = listElement;
    this.onReorder = onReorderCallback;
    this.setupSortable();
  }
  
  setupSortable() {
    Sortable.create(this.list, {
      animation: 150,
      handle: '.drag-handle',
      onEnd: (evt) => {
        // Get new order of location IDs
        const locationIds = Array.from(this.list.children)
          .map(el => parseInt(el.dataset.locationId));
        this.onReorder(locationIds);
      }
    });
  }
}
```

### JPG Export

**Approach 1: Server-Side Export (Recommended)**
- Use Playwright or Selenium to render the map page
- Take a screenshot of the map container
- Return as downloadable JPG

**Approach 2: Client-Side Export**
- Use html2canvas library to convert the map div to canvas
- Export canvas as JPG using `canvas.toDataURL('image/jpeg')`

**Implementation (Client-side)**:
```javascript
// In map-viewer.js
async exportAsJPG() {
  const mapContainer = document.getElementById('map-container');
  
  // Use html2canvas to capture the map
  const canvas = await html2canvas(mapContainer, {
    useCORS: true,
    allowTaint: true,
    backgroundColor: '#ffffff'
  });
  
  // Convert to JPG and download
  canvas.toBlob((blob) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${this.mapName}-map.jpg`;
    a.click();
    URL.revokeObjectURL(url);
  }, 'image/jpeg', 0.95);
}
```

**Implementation (Server-side - preferred for quality)**:
```python
# In services.py
import asyncio
from playwright.async_api import async_playwright

async def export_map_as_jpg(map_id: int) -> bytes:
    """Export a map as a JPG image using headless browser."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1920, 'height': 1080})
        
        # Navigate to the map view page
        await page.goto(f'http://localhost:8000/maps/{map_id}/view')
        
        # Wait for map to load
        await page.wait_for_selector('.leaflet-map-pane', state='visible')
        await asyncio.sleep(2)  # Extra time for tiles to load
        
        # Take screenshot of map container
        map_element = await page.query_selector('#map-container')
        screenshot = await map_element.screenshot(type='jpeg', quality=90)
        
        await browser.close()
        return screenshot
```

## Docker Configuration

### Dockerfile

Following the existing pattern:

```dockerfile
FROM python:3.12-slim
WORKDIR /app

# Install dependencies for Playwright (if using server-side export)
RUN apt-get update && apt-get install -y \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and browsers (if using server-side export)
RUN playwright install chromium

COPY travel-maps/app ./app
RUN mkdir -p /data

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

### docker-compose.yml

```yaml
services:
  travel-maps:
    container_name: travel-maps
    build:
      context: ..
      dockerfile: travel-maps/Dockerfile
    environment:
      - DATA_DIR=/data
    volumes:
      - data-volume:/data
      - ./app:/app/app  # Live reload during development
    networks:
      - web
    labels:
      - traefik.enable=true
      
      # Public routes - no authentication
      - traefik.http.routers.maps-public.rule=Host(`maps.jamesmassucco.com`)
      - traefik.http.routers.maps-public.entrypoints=websecure
      - traefik.http.routers.maps-public.tls.certresolver=cloudflare
      - traefik.http.routers.maps-public.middlewares=ratelimit
      - traefik.http.routers.maps-public.priority=50
      
      # Service configuration
      - traefik.http.services.travel-maps.loadbalancer.server.port=8000
    healthcheck:
      test:
        [
          'CMD',
          'python3',
          '-c',
          "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')",
        ]
      interval: 5s
      timeout: 1s
      retries: 3
      start_period: 5s
    restart: unless-stopped

volumes:
  data-volume:

networks:
  web:
    external: true
```

### start.sh

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "Shutting down containers..."
sudo docker compose down --remove-orphans

echo "Building and starting containers..."
sudo docker compose up -d --build --wait
```

## Integration Points

### 1. Update scripts/start_all.sh

Add "travel-maps" to the PROJECTS array:

```bash
PROJECTS=("networking" "shared-assets" "homepage" "blog" "travel-site" "travel-maps")
```

### 2. Update networking configuration

Add subdomain configuration to `networking/docker-compose.yml` or DNS configuration as needed (the Traefik labels in the service should handle routing).

### 3. Update .github/dependabot.yml

Add new entry for the travel-maps directory:

```yaml
- package-ecosystem: "docker"
  directory: "/travel-maps"
  schedule:
    interval: "weekly"
    day: "monday"
  groups:
    docker-images:
      patterns: ["*"]
```

### 4. Update requirements.txt

Add any new dependencies:
- `playwright>=1.40,<2` (if using server-side export)
- No additional dependencies needed if using existing libraries

### 5. Update README.md

Add the new service to the webpages list:

```markdown
## Webpages

- Homepage: [jamesmassucco.com](https://jamesmassucco.com)
- Blog: [blog.jamesmassucco.com](https://blog.jamesmassucco.com/)
- Travel Maps: [maps.jamesmassucco.com](https://maps.jamesmassucco.com)
```

## Testing Strategy

### Unit Tests

Create `travel-maps/tests/` directory with:

1. **test_models.py**: Test database models
   - Test Map and Location model creation
   - Test relationships
   - Test validation

2. **test_services.py**: Test business logic
   - Test map CRUD operations
   - Test location CRUD operations
   - Test reordering logic

3. **test_routes.py**: Test API endpoints
   - Test all GET/POST/PUT/DELETE endpoints
   - Test error handling
   - Test geocoding proxy

### Integration Tests

1. **test_map_workflow.py**: End-to-end workflow tests
   - Create map → Add locations → Reorder → View → Export
   - Test map deletion cascades to locations

### Manual Testing Checklist

- [ ] Create a new map with a name
- [ ] Search for a location and add it
- [ ] Add multiple locations
- [ ] Reorder locations via drag-and-drop
- [ ] Edit location nickname and description
- [ ] Remove a location
- [ ] Save the map
- [ ] View the map with proper markers and lines
- [ ] Export map as JPG
- [ ] Delete a map
- [ ] Test responsiveness on mobile

## Security Considerations

### Authentication

**Decision Point**: Should map creation/editing require authentication?

**Options**:
1. **Public (No Auth)**: Anyone can create/edit/delete maps
   - Simple to implement
   - Risk of spam/abuse
   - Good for MVP

2. **OAuth Protected**: Use existing Traefik OAuth middleware
   - Similar to travel-site admin routes
   - Only authenticated users can create/edit
   - Public can view maps

**Recommendation**: Start with public access for MVP, add OAuth protection later if needed.

**Implementation with OAuth**:
```yaml
# In docker-compose.yml labels
# Admin/edit routes - require OAuth
- traefik.http.routers.maps-admin.rule=Host(`maps.jamesmassucco.com`) && (PathPrefix(`/maps/new`) || PathPrefix(`/maps/`) && Method(`POST`, `PUT`, `DELETE`))
- traefik.http.routers.maps-admin.entrypoints=websecure
- traefik.http.routers.maps-admin.tls.certresolver=cloudflare
- traefik.http.routers.maps-admin.middlewares=oauth-auth,ratelimit
- traefik.http.routers.maps-admin.priority=100

# Public view routes - no authentication
- traefik.http.routers.maps-public.rule=Host(`maps.jamesmassucco.com`)
- traefik.http.routers.maps-public.entrypoints=websecure
- traefik.http.routers.maps-public.tls.certresolver=cloudflare
- traefik.http.routers.maps-public.middlewares=ratelimit
- traefik.http.routers.maps-public.priority=50
```

### Input Validation

- Validate map names (max length, no special characters)
- Validate coordinates (valid lat/long ranges)
- Sanitize user input for XSS prevention
- Rate limit API endpoints
- Validate file sizes for export operations

### Data Protection

- Use parameterized queries (SQLModel handles this)
- Limit map export size to prevent DoS
- Store database in persistent volume

## Performance Considerations

### Database Optimization

- Index on `map_id` in Location table
- Index on `order_index` for efficient ordering
- Use database connection pooling

### Caching

- Cache geocoding results to reduce API calls
- Cache rendered map tiles where possible
- Use browser caching for static assets

### Scalability

- Current design supports up to ~1000 maps with 50 locations each
- For larger scale, consider:
  - PostgreSQL instead of SQLite
  - Redis for caching
  - CDN for map tiles
  - Background job queue for exports

## Future Enhancements

Beyond the MVP, consider these features:

1. **Map Sharing**
   - Public/private toggle
   - Shareable links
   - Embed codes

2. **Rich Location Data**
   - Photo attachments
   - Date ranges for visits
   - Travel notes/journal entries

3. **Map Customization**
   - Choose line colors
   - Different marker styles
   - Custom map tiles/styles

4. **Collaboration**
   - Multi-user editing
   - Comments on locations
   - Suggested locations

5. **Import/Export**
   - Import from GPX files
   - Export to KML
   - Integration with Google Maps

6. **Statistics**
   - Total distance traveled
   - Countries/cities visited
   - Travel timeline visualization

7. **Mobile App**
   - Native iOS/Android apps
   - Offline map viewing

## Implementation Phases

### Phase 1: MVP (Recommended for initial implementation)

**Goal**: Basic functionality - create, view, and export maps

**Features**:
- Create maps with names
- Add locations via search
- Basic reordering (no drag-drop, just up/down buttons)
- View map with markers and lines
- Simple JPG export (client-side)
- No authentication

**Estimated Effort**: 2-3 days

### Phase 2: Enhanced UX

**Goal**: Improve user experience

**Features**:
- Drag-and-drop reordering
- Location nicknames and descriptions
- Better map styling
- Server-side export for higher quality
- Responsive design

**Estimated Effort**: 1-2 days

### Phase 3: Polish & Production

**Goal**: Production-ready with authentication

**Features**:
- OAuth authentication for editing
- Comprehensive error handling
- Unit and integration tests
- Performance optimization
- Documentation

**Estimated Effort**: 1-2 days

## Development Workflow

### Step 1: Setup Module Structure
1. Create `travel-maps/` directory
2. Copy Dockerfile, docker-compose.yml, start.sh from existing module
3. Create app structure with empty files
4. Verify container builds and starts

### Step 2: Database & Models
1. Implement models.py with Map and Location models
2. Implement database.py with initialization
3. Test database creation and migrations

### Step 3: Backend API
1. Implement routes.py with all endpoints
2. Implement services.py with business logic
3. Add health check endpoint
4. Test API endpoints with curl/Postman

### Step 4: Frontend - Index Page
1. Create base.html.jinja2 template
2. Create index.html.jinja2 with map list
3. Add CSS styling
4. Test map creation and deletion

### Step 5: Frontend - Map Editor
1. Create map-edit.html.jinja2 template
2. Implement location search with autocomplete
3. Implement location list with reordering
4. Add Leaflet map preview
5. Test full edit workflow

### Step 6: Frontend - Map Viewer
1. Create map-view.html.jinja2 template
2. Implement full-screen map with markers and lines
3. Add popups with location details
4. Test map rendering

### Step 7: Export Functionality
1. Implement JPG export (start with client-side)
2. Test export quality
3. Add download functionality

### Step 8: Integration
1. Update scripts/start_all.sh
2. Update dependabot.yml
3. Update README.md
4. Test with full stack running

### Step 9: Testing & Documentation
1. Write unit tests
2. Write integration tests
3. Manual testing
4. Update README with usage instructions

### Step 10: Deployment
1. Build and deploy to homelab
2. Test on production domain
3. Monitor for issues

## File Creation Checklist

### Configuration Files
- [ ] `travel-maps/Dockerfile`
- [ ] `travel-maps/docker-compose.yml`
- [ ] `travel-maps/start.sh` (make executable)
- [ ] `travel-maps/README.md`
- [ ] `travel-maps/.gitignore` (for local data/volumes)

### Python Application Files
- [ ] `travel-maps/app/__init__.py`
- [ ] `travel-maps/app/main.py`
- [ ] `travel-maps/app/database.py`
- [ ] `travel-maps/app/models.py`
- [ ] `travel-maps/app/routes.py`
- [ ] `travel-maps/app/services.py`

### Template Files
- [ ] `travel-maps/app/templates/base.html.jinja2`
- [ ] `travel-maps/app/templates/index.html.jinja2`
- [ ] `travel-maps/app/templates/map-view.html.jinja2`
- [ ] `travel-maps/app/templates/map-edit.html.jinja2`

### Static Files - CSS
- [ ] `travel-maps/app/static/css/styles.css`
- [ ] `travel-maps/app/static/css/markers.css` (for custom marker styling)

### Static Files - JavaScript
- [ ] `travel-maps/app/static/js/map-viewer.js`
- [ ] `travel-maps/app/static/js/map-editor.js`
- [ ] `travel-maps/app/static/js/location-search.js`
- [ ] `travel-maps/app/static/js/utils.js` (shared utilities)

### Test Files (Optional for MVP)
- [ ] `travel-maps/tests/__init__.py`
- [ ] `travel-maps/tests/test_models.py`
- [ ] `travel-maps/tests/test_services.py`
- [ ] `travel-maps/tests/test_routes.py`

### Repository Updates
- [ ] Update `scripts/start_all.sh`
- [ ] Update `.github/dependabot.yml`
- [ ] Update `README.md`
- [ ] Update `requirements.txt` (if new dependencies needed)

## Dependencies

### Python Packages (to add to requirements.txt if not already present)

```
# Already in requirements.txt:
fastapi>=0.116,<1
uvicorn>=0.35,<1
sqlmodel>=0.0.24,<1
jinja2>=3.1,<4
python-multipart>=0.0.20,<1

# May need to add:
playwright>=1.40,<2  # Only if using server-side export
httpx>=0.27,<1       # For making HTTP requests to geocoding API
```

### JavaScript Libraries (via CDN in templates)

```html
<!-- Leaflet for maps -->
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<!-- SortableJS for drag-and-drop (if using) -->
<script src="https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js"></script>

<!-- html2canvas for client-side export (if using) -->
<script src="https://html2canvas.hertzen.com/dist/html2canvas.min.js"></script>
```

## Open Questions / Decisions Needed

1. **Authentication**: Should editing require OAuth authentication or be public?
   - **Recommendation**: Start public, add auth later if needed

2. **Geocoding Service**: Nominatim (free, OSM) vs Google Maps API (paid, higher quality)?
   - **Recommendation**: Start with Nominatim, switch to Google if quality is insufficient

3. **Export Method**: Client-side (html2canvas) vs Server-side (Playwright)?
   - **Recommendation**: Start with client-side for simplicity, upgrade to server-side if quality issues

4. **Database**: SQLite vs PostgreSQL?
   - **Recommendation**: SQLite for MVP (consistent with travel-site), upgrade if scaling needed

5. **Map Visibility**: Should all maps be public or have private/public toggle?
   - **Recommendation**: All public for MVP, add privacy toggle in Phase 2

6. **Location Limits**: Should there be a max number of locations per map?
   - **Recommendation**: Yes, limit to 100 locations per map initially

## Success Criteria

The travel-maps module will be considered successfully implemented when:

1. ✅ Users can create a new map with a name
2. ✅ Users can search for locations using a Google Maps-style interface
3. ✅ Users can add multiple locations to a map
4. ✅ Users can reorder locations
5. ✅ Users can add optional nicknames and descriptions to locations
6. ✅ Users can view an interactive map showing all locations with:
   - Numbered markers
   - Lines connecting them in order
   - Popups with location details
7. ✅ Users can export the map as a JPG image
8. ✅ Maps are persisted to database and survive container restarts
9. ✅ The module is accessible at maps.jamesmassucco.com
10. ✅ The module is integrated into the start_all.sh script

## Conclusion

This plan provides a comprehensive roadmap for implementing the travel-maps module. The design follows existing patterns in the repository while introducing new functionality for interactive map creation and visualization. The phased approach allows for incremental development, starting with a minimal viable product and adding enhancements based on user feedback.

Key design decisions prioritize:
- **Simplicity**: Leveraging existing patterns and technologies
- **User Experience**: Google Maps-style interface for familiarity
- **Flexibility**: Support for customization through nicknames and descriptions
- **Scalability**: Database design that can handle future enhancements
- **Integration**: Seamless fit with existing homelab infrastructure

The next step is to review this plan, make any necessary adjustments, and then proceed with implementation following the development workflow outlined above.
