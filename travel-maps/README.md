# Travel Maps Module

Interactive web application for creating and viewing custom travel maps with multiple locations.

## Features

- Create named travel maps
- Search and add locations using OpenStreetMap geocoding
- Reorder locations in your journey
- Add optional nicknames and descriptions to locations
- View interactive maps with Leaflet.js
- Export maps as JPG images

## Technology Stack

- **Backend**: FastAPI with Python 3.12
- **Database**: SQLModel with SQLite
- **Frontend**: Jinja2 templates, Leaflet.js for maps
- **Geocoding**: Nominatim (OpenStreetMap)
- **Deployment**: Docker, accessible at maps.jamesmassucco.com

## Local Development

```bash
# Start the service
./start.sh

# Access at http://localhost:8002
```

## Testing

```bash
# Run tests from the travel-maps directory
cd travel-maps
python -m unittest discover -s app -p "*_test.py"
```

## API Endpoints

- `GET /` - List all maps
- `GET /maps/new` - Create new map form
- `GET /maps/{id}/view` - View a map
- `GET /maps/{id}/edit` - Edit a map
- `POST /api/maps` - Create a new map
- `GET /api/maps/{id}` - Get map details
- `PUT /api/maps/{id}` - Update a map
- `DELETE /api/maps/{id}` - Delete a map
- `POST /api/maps/{id}/locations` - Add location to map
- `PUT /api/locations/{id}` - Update location details
- `DELETE /api/locations/{id}` - Remove location from map
- `POST /api/locations/reorder` - Reorder locations
- `GET /api/geocode` - Search for locations
