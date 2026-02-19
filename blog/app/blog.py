"""Blog post loading and rendering logic."""

import datetime
import pathlib

import frontmatter  # type: ignore[reportMissingTypeStubs]
import markdown
import pydantic

BLOG_POSTS_DIR = pathlib.Path(__file__).resolve().parent.parent / 'blog_posts'


class BlogPostMetadata(pydantic.BaseModel):
    """Metadata specification for blog posts."""

    title: str
    date: str
    tags: list[str]
    summary: str
    slug: str

    @property
    def dt(self) -> datetime.datetime:
        """Parses date into datetime object."""
        return datetime.datetime.fromisoformat(self.date)


class BlogPost:
    """Represents a single blog post.

    Provides convenience properties to convert markdown to HTML and read metadata.
    """

    md_path: pathlib.Path
    _post: frontmatter.Post | None

    def __init__(self, md_path: pathlib.Path) -> None:
        self.md_path = md_path
        self._post = None

    @property
    def post(self) -> frontmatter.Post:
        """Returns frontmatter-parsed post, loading and caching if necessary."""
        if self._post is None:
            self._post = frontmatter.load(self.md_path.as_posix())
        return self._post

    @property
    def content(self) -> str:
        """Returns markdown-rendered HTML of the post body."""
        return markdown.markdown(
            self.post.content, extensions=['fenced_code', 'codehilite', 'tables', 'toc']
        )

    @property
    def metadata(self) -> BlogPostMetadata:
        """Returns pydantic model of post metadata."""
        return BlogPostMetadata.model_validate(self.post.metadata)


def load_posts() -> list[BlogPost]:
    """Load all blog posts from the blog_posts directory, sorted newest first.

    Raises ValueError if duplicate slugs are detected.
    """
    posts = [BlogPost(path) for path in BLOG_POSTS_DIR.glob('*.md')]
    posts = sorted(posts, key=lambda p: p.metadata.dt, reverse=True)

    slugs = [p.metadata.slug for p in posts]
    seen: list[str] = []
    duplicates: list[str] = []
    for slug in slugs:
        if slug in seen:
            duplicates.append(slug)
            continue
        seen.append(slug)
    if duplicates:
        raise ValueError(f'Duplicate slugs: {duplicates}')

    return posts
