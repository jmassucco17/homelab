"""Unit tests for movie_picker router."""

import unittest
import unittest.mock

import fastapi.testclient
import httpx

from tools.app import main


class TestMoviePickerRouter(unittest.TestCase):
    """Tests for the movie picker router."""

    def setUp(self) -> None:
        """Set up test client."""
        self.client = fastapi.testclient.TestClient(main.app)

    def test_movie_picker_endpoint_returns_html(self) -> None:
        """Test GET /movie-picker returns an HTML response."""
        response = self.client.get('/movie-picker')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])

    def test_movie_picker_page_has_search_input(self) -> None:
        """Test the movie picker page includes a search input."""
        response = self.client.get('/movie-picker')
        self.assertIn('id="movie-search"', response.text)

    def test_movie_picker_page_has_pick_button(self) -> None:
        """Test the movie picker page includes the pick button."""
        response = self.client.get('/movie-picker')
        self.assertIn('id="pick-btn"', response.text)

    def test_movie_picker_page_loads_js(self) -> None:
        """Test the movie picker page references the JS file."""
        response = self.client.get('/movie-picker')
        self.assertIn('movie_picker.js', response.text)

    def test_search_returns_503_without_api_key(self) -> None:
        """Test search endpoint returns 503 when TMDB_API_KEY is not set."""
        import os

        with unittest.mock.patch.dict(os.environ, {}, clear=True):
            # Ensure TMDB_API_KEY is not set
            os.environ.pop('TMDB_API_KEY', None)
            response = self.client.get('/api/movies/search?q=inception')
        self.assertEqual(response.status_code, 503)
        self.assertIn('TMDB_API_KEY', response.json()['detail'])

    def test_details_returns_503_without_api_key(self) -> None:
        """Test details endpoint returns 503 when TMDB_API_KEY is not set."""
        import os

        with unittest.mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop('TMDB_API_KEY', None)
            response = self.client.get('/api/movies/12345')
        self.assertEqual(response.status_code, 503)
        self.assertIn('TMDB_API_KEY', response.json()['detail'])

    def test_search_returns_results_with_api_key(self) -> None:
        """Test search returns movie results when API key is set."""
        import os

        mock_response_data = {
            'results': [
                {
                    'id': 27205,
                    'title': 'Inception',
                    'release_date': '2010-07-16',
                    'poster_path': '/oYuLEt3zVCKq57qu2F8dT7NIa6f.jpg',
                }
            ]
        }

        with unittest.mock.patch.dict(os.environ, {'TMDB_API_KEY': 'test-key'}):
            with unittest.mock.patch('httpx.AsyncClient') as mock_client_cls:
                mock_resp = unittest.mock.MagicMock(spec=httpx.Response)
                mock_resp.json.return_value = mock_response_data
                mock_resp.raise_for_status = unittest.mock.MagicMock()
                mock_client = unittest.mock.AsyncMock()
                mock_client.get.return_value = mock_resp
                mock_client.__aenter__ = unittest.mock.AsyncMock(
                    return_value=mock_client
                )
                mock_client.__aexit__ = unittest.mock.AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                response = self.client.get('/api/movies/search?q=inception')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['title'], 'Inception')
        self.assertEqual(data[0]['year'], '2010')
        self.assertEqual(data[0]['id'], 27205)

    def test_search_missing_query_param(self) -> None:
        """Test search endpoint returns 422 when query param is missing."""
        response = self.client.get('/api/movies/search')
        self.assertEqual(response.status_code, 422)

    def test_details_returns_movie_with_api_key(self) -> None:
        """Test details endpoint returns full movie info when API key is set."""
        import os

        mock_details = {
            'id': 27205,
            'title': 'Inception',
            'release_date': '2010-07-16',
            'runtime': 148,
            'poster_path': '/oYuLEt3zVCKq57qu2F8dT7NIa6f.jpg',
        }
        mock_providers = {
            'results': {
                'US': {
                    'flatrate': [
                        {
                            'provider_name': 'Netflix',
                            'logo_path': '/t2yyOv40HZeVlLjYsCsPHnWLk4W.jpg',
                        }
                    ],
                    'rent': [],
                    'buy': [],
                }
            }
        }

        with unittest.mock.patch.dict(os.environ, {'TMDB_API_KEY': 'test-key'}):
            with unittest.mock.patch(
                'tools.app.routers.movie_picker._fetch_movie_data'
            ) as mock_fetch:
                details_resp = unittest.mock.MagicMock()
                details_resp.json.return_value = mock_details
                providers_resp = unittest.mock.MagicMock()
                providers_resp.json.return_value = mock_providers

                async def fake_fetch(
                    client: object, headers: object, movie_id: int
                ) -> tuple[object, object]:
                    return details_resp, providers_resp

                mock_fetch.side_effect = fake_fetch

                response = self.client.get('/api/movies/27205')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['title'], 'Inception')
        self.assertEqual(data['runtime'], 148)
        self.assertEqual(data['year'], '2010')
        self.assertEqual(len(data['streaming']), 1)
        self.assertEqual(data['streaming'][0]['provider_name'], 'Netflix')
        logo_url = data['streaming'][0]['logo_url']
        self.assertIn('/t2yyOv40HZeVlLjYsCsPHnWLk4W.jpg', logo_url)

    def test_search_result_without_poster(self) -> None:
        """Test search handles movies with no poster_path gracefully."""
        import os

        mock_response_data = {
            'results': [
                {
                    'id': 99999,
                    'title': 'Obscure Film',
                    'release_date': '1995-01-01',
                    'poster_path': None,
                }
            ]
        }

        with unittest.mock.patch.dict(os.environ, {'TMDB_API_KEY': 'test-key'}):
            with unittest.mock.patch('httpx.AsyncClient') as mock_client_cls:
                mock_resp = unittest.mock.MagicMock(spec=httpx.Response)
                mock_resp.json.return_value = mock_response_data
                mock_resp.raise_for_status = unittest.mock.MagicMock()
                mock_client = unittest.mock.AsyncMock()
                mock_client.get.return_value = mock_resp
                mock_client.__aenter__ = unittest.mock.AsyncMock(
                    return_value=mock_client
                )
                mock_client.__aexit__ = unittest.mock.AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                response = self.client.get('/api/movies/search?q=obscure')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNone(data[0]['poster_path'])

    def test_static_js_is_served(self) -> None:
        """Test the movie picker JS file is served."""
        response = self.client.get('/static/js/movie_picker.js')
        self.assertEqual(response.status_code, 200)
        self.assertIn('movie', response.text.lower())


if __name__ == '__main__':
    unittest.main()
