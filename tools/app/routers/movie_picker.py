"""Movie picker router with TMDB API integration."""

import os
import pathlib

import fastapi
import fastapi.responses
import fastapi.templating
import httpx
import pydantic

APP_DIR = pathlib.Path(__file__).resolve().parent.parent
templates = fastapi.templating.Jinja2Templates(directory=APP_DIR / 'templates')

router = fastapi.APIRouter()

TMDB_BASE_URL = 'https://api.themoviedb.org/3'
TMDB_IMAGE_BASE = 'https://image.tmdb.org/t/p/w500'


class MovieSearchResult(pydantic.BaseModel):
    """A single movie result from TMDB search."""

    id: int
    title: str
    year: str
    poster_path: str | None


class WatchProvider(pydantic.BaseModel):
    """A streaming/rental provider from TMDB."""

    provider_name: str
    logo_url: str


class MovieDetails(pydantic.BaseModel):
    """Full movie details including watch providers."""

    id: int
    title: str
    year: str
    runtime: int | None
    poster_url: str | None
    streaming: list[WatchProvider]
    rent: list[WatchProvider]
    buy: list[WatchProvider]


def _get_api_key() -> str | None:
    """Return the TMDB API key from the environment, or None if not set."""
    return os.environ.get('TMDB_API_KEY') or None


def _make_headers(api_key: str) -> dict[str, str]:
    """Build TMDB request headers."""
    return {'Authorization': f'Bearer {api_key}', 'accept': 'application/json'}


@router.get('/movie-picker', response_class=fastapi.responses.HTMLResponse)
async def movie_picker(request: fastapi.Request) -> fastapi.responses.HTMLResponse:
    """Render the movie picker page."""
    return templates.TemplateResponse(request=request, name='movie_picker.html')


@router.get('/api/movies/search', response_model=list[MovieSearchResult])
async def search_movies(
    q: str = fastapi.Query(..., min_length=1),
) -> list[MovieSearchResult]:
    """Search for movies by title using TMDB."""
    api_key = _get_api_key()
    if api_key is None:
        raise fastapi.HTTPException(
            status_code=503,
            detail='TMDB_API_KEY is not configured on this server.',
        )

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f'{TMDB_BASE_URL}/search/movie',
            headers=_make_headers(api_key),
            params={
                'query': q,
                'include_adult': 'false',
                'language': 'en-US',
                'page': '1',
            },
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

    results: list[MovieSearchResult] = []
    for item in data.get('results', [])[:10]:
        release_date: str = item.get('release_date') or ''
        year = release_date[:4] if release_date else 'N/A'
        results.append(
            MovieSearchResult(
                id=item['id'],
                title=item.get('title', 'Unknown'),
                year=year,
                poster_path=(
                    f'{TMDB_IMAGE_BASE}{item["poster_path"]}'
                    if item.get('poster_path')
                    else None
                ),
            )
        )
    return results


@router.get('/api/movies/{movie_id}', response_model=MovieDetails)
async def get_movie_details(movie_id: int) -> MovieDetails:
    """Get full movie details and watch providers from TMDB."""
    api_key = _get_api_key()
    if api_key is None:
        raise fastapi.HTTPException(
            status_code=503,
            detail='TMDB_API_KEY is not configured on this server.',
        )

    headers = _make_headers(api_key)

    async with httpx.AsyncClient() as client:
        details_response, providers_response = await _fetch_movie_data(
            client, headers, movie_id
        )

    details_data = details_response.json()
    providers_data = providers_response.json()

    release_date: str = details_data.get('release_date') or ''
    year = release_date[:4] if release_date else 'N/A'

    poster_path: str | None = details_data.get('poster_path')
    poster_url = f'{TMDB_IMAGE_BASE}{poster_path}' if poster_path else None

    us_providers: dict[str, list[dict[str, str]]] = providers_data.get(
        'results', {}
    ).get('US', {})

    def _parse_providers(key: str) -> list[WatchProvider]:
        return [
            WatchProvider(
                provider_name=p.get('provider_name', ''),
                logo_url=(
                    f'{TMDB_IMAGE_BASE}{p["logo_path"]}' if p.get('logo_path') else ''
                ),
            )
            for p in us_providers.get(key, [])
        ]

    return MovieDetails(
        id=details_data['id'],
        title=details_data.get('title', 'Unknown'),
        year=year,
        runtime=details_data.get('runtime'),
        poster_url=poster_url,
        streaming=_parse_providers('flatrate'),
        rent=_parse_providers('rent'),
        buy=_parse_providers('buy'),
    )


async def _fetch_movie_data(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    movie_id: int,
) -> tuple[httpx.Response, httpx.Response]:
    """Fetch movie details and watch providers concurrently."""
    import asyncio

    details_task = client.get(
        f'{TMDB_BASE_URL}/movie/{movie_id}',
        headers=headers,
        params={'language': 'en-US'},
        timeout=10.0,
    )
    providers_task = client.get(
        f'{TMDB_BASE_URL}/movie/{movie_id}/watch/providers',
        headers=headers,
        timeout=10.0,
    )
    details_response, providers_response = await asyncio.gather(
        details_task, providers_task
    )
    details_response.raise_for_status()
    providers_response.raise_for_status()
    return details_response, providers_response
