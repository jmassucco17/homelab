import datetime
import pathlib
import subprocess

import frontmatter
import jinja2
import markdown
import pydantic

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
MARKDOWN_POSTS_DIR = SCRIPT_DIR / 'blog_posts'

# Templates
TEMPLATES_DIR = SCRIPT_DIR / 'templates'
INDEX_TEMPLATE_FILE = 'index.html.jinja2'
POST_TEMPLATE_FILE = 'post.html.jinja2'
RSS_TEMPLATE_FILE = 'rss.xml.jinja2'

# Outputs
SITE_DIR = SCRIPT_DIR / 'site'
INDEX_OUTPUT_FILE = SITE_DIR / 'index.html'
POST_OUTPUT_DIR = SITE_DIR / 'posts'
RSS_OUTPUT_FILE = SITE_DIR / 'rss.xml'


class BlogPost:
    md_path: pathlib.Path
    _post: frontmatter.Post | None

    def __init__(self, md_path: pathlib.Path):
        self.md_path = md_path
        self._post = None

    @property
    def post(self) -> frontmatter.Post:
        """Returns post, loading and caching if necessary"""
        if self._post is None:
            self._post = frontmatter.load(self.md_path)
        return self._post

    @property
    def content(self) -> str:
        """Returns markdown-parsed version of content"""
        return markdown.markdown(
            self.post.content, extensions=['fenced_code', 'codehilite', 'tables', 'toc']
        )

    @property
    def metadata(self) -> 'BlogPostMetadata':
        """Returns pydantic model of metadata"""
        return BlogPostMetadata.model_validate(self.post.metadata)


class BlogPostMetadata(pydantic.BaseModel):
    title: str
    date: str  # XXX should be a date?
    tags: list[str]
    summary: str
    slug: str

    @property
    def dt(self) -> datetime.datetime:
        return datetime.datetime.fromisoformat(self.date)


def write_and_format_html(html: str, path: pathlib.Path) -> None:
    """Write html to path and format with prettier"""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    subprocess.run(['npx', 'prettier', '--write', str(path)])


def main() -> None:
    """Generate a blog index.html page by converting all markdown posts to HTML cards"""
    # Load jinja templates
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATES_DIR))
    env.filters['datefmt'] = lambda value, fmt='%B %d, %Y': value.strftime(fmt)
    post_template = env.get_template(POST_TEMPLATE_FILE)
    index_template = env.get_template(INDEX_TEMPLATE_FILE)
    rss_template = env.get_template(RSS_TEMPLATE_FILE)

    # Load posts
    posts = [BlogPost(path) for path in MARKDOWN_POSTS_DIR.glob('*.md')]
    posts = sorted(posts, key=lambda p: p.metadata.dt, reverse=True)

    # Generate index
    index_page = index_template.render(posts=posts)
    write_and_format_html(index_page, INDEX_OUTPUT_FILE)

    # Generate post pages
    for post in posts:
        out_path = POST_OUTPUT_DIR / f'{post.metadata.slug}.html'
        post_html = post_template.render(post=post)
        write_and_format_html(post_html, out_path)

    # Generate RSS
    rss_xml = rss_template.render(posts=posts)
    RSS_OUTPUT_FILE.write_text(rss_xml)


if __name__ == '__main__':
    main()
