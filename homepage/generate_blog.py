import pathlib
import subprocess

import markdown

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
MARKDOWN_POSTS_DIR = SCRIPT_DIR / 'blog_posts'
HTML_OUTPUT_FILE = SCRIPT_DIR / 'site/blog.html'
HTML_TEMPLATE_FILE = SCRIPT_DIR / 'blog_template.html.jinja2'

# Template for each individual blog post rendered as a card
POST_TEMPLATE: str = """
<div class=\"card\" href=\"#\">
  <div class=\"content\">
    {content}
  </div>
</div>
"""


def generate_blog_post_html(mardown_path: pathlib.Path) -> str:
    """Generate blog post HTML from markdown file"""
    # Read markdown file to HTML
    with open(mardown_path, encoding='utf-8') as f:
        md_content = f.read()
    html_content = markdown.markdown(
        md_content, extensions=['fenced_code', 'codehilite', 'tables', 'toc']
    )

    # Format the post using the HTML template
    post_html = POST_TEMPLATE.format(content=html_content)

    return post_html


def main() -> None:
    """Generate a blog.html page by converting all markdown posts to HTML cards this."""
    posts: list[str] = []

    # Process each markdown file in the blog directory. Filenames are assumed to be
    # dates, so we sort in reverse order to populate the newest first
    for md_file in sorted(MARKDOWN_POSTS_DIR.glob('*.md'), reverse=True):
        post = generate_blog_post_html(md_file)
        posts.append(post)

    # Load HTML template and insert the posts
    with open(HTML_TEMPLATE_FILE, encoding='utf-8') as f:
        template: str = f.read()
    full_page: str = template.replace('{{ posts }}', '\n'.join(posts))

    # Write the final output to blog.html and format
    with open(HTML_OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(full_page)
    subprocess.run(['npx', 'prettier', '--write', str(HTML_OUTPUT_FILE)])


if __name__ == '__main__':
    main()
