"""FastAPI application for the blog site."""

import pathlib

import fastapi
import fastapi.responses
import fastapi.staticfiles
import fastapi.templating

import common.log
import common.settings

from . import blog

APP_DIR = pathlib.Path(__file__).resolve().parent

app = fastapi.FastAPI(title='Blog')

common.log.configure_logging()

app.mount(
    '/assets',
    fastapi.staticfiles.StaticFiles(directory=APP_DIR / 'static'),
    name='assets',
)

templates = fastapi.templating.Jinja2Templates(directory=APP_DIR / 'templates')
templates.env.filters['datefmt'] = lambda value, fmt='%B %d, %Y': value.strftime(fmt)  # type: ignore[assignment]
templates.env.globals['domain'] = common.settings.DOMAIN  # type: ignore[reportUnknownMemberType]
templates.env.globals['home_url'] = common.settings.HOME_URL  # type: ignore[reportUnknownMemberType]


@app.get('/', response_class=fastapi.responses.HTMLResponse)
async def index(request: fastapi.Request) -> fastapi.responses.HTMLResponse:
    """Render the blog index page listing all posts."""
    posts = blog.load_posts()
    return templates.TemplateResponse(
        request=request, name='index.html.jinja2', context={'posts': posts}
    )


@app.get('/posts/{slug}', response_class=fastapi.responses.HTMLResponse)
async def post(request: fastapi.Request, slug: str) -> fastapi.responses.HTMLResponse:
    """Render an individual blog post by slug."""
    posts = blog.load_posts()
    matched = next((p for p in posts if p.metadata.slug == slug), None)
    if matched is None:
        raise fastapi.HTTPException(status_code=404, detail='Post not found')
    return templates.TemplateResponse(
        request=request, name='post.html.jinja2', context={'post': matched}
    )


@app.get('/rss.xml')
async def rss(request: fastapi.Request) -> fastapi.responses.Response:
    """Render and serve the RSS feed."""
    posts = blog.load_posts()
    xml = templates.get_template('rss.xml.jinja2').render(posts=posts)  # type: ignore
    return fastapi.responses.Response(content=xml, media_type='application/rss+xml')


@app.api_route('/health', methods=['GET', 'HEAD'])
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {'status': 'healthy'}
