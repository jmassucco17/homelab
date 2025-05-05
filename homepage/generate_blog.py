import pathlib
import subprocess

import markdown

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
MARKDOWN_POSTS_DIR = SCRIPT_DIR / 'blog_posts'
HTML_OUTPUT_FILE = SCRIPT_DIR / 'site/blog.html'
HTML_TEMPLATE_FILE = SCRIPT_DIR / 'blog_template.html'

# Template for each individual blog post rendered as a card
POST_TEMPLATE: str = """
<a class=\"card\" href=\"#\">
  <h3>{title}</h3>
  <p class=\"date\">{date}</p>
  <div class=\"content\">
    {content}
  </div>
</a>
"""


def get_markdown_title(content: str) -> str:
    """Extract first level-1 heading from markdown content"""
    lines: list[str] = content.strip().splitlines()
    l1_heading_str = '# '
    for line in lines:
        if not line.startswith(l1_heading_str):
            continue
        return line.lstrip(l1_heading_str).strip()
    return 'Untitled'


def generate_blog_post_html(mardown_path: pathlib.Path) -> str:
    """Generate blog post HTML from markdown file"""
    # Read markdown file
    with open(mardown_path, encoding='utf-8') as f:
        md_content: str = f.read()

    # Convert markdown content to HTML
    html_content: str = markdown.markdown(md_content)

    # Extract post title from markdown content
    title: str = get_markdown_title(md_content)

    # Use the filename (without extension) as the post date
    date: str = mardown_path.stem

    # Format the post using the HTML template
    post_html = POST_TEMPLATE.format(title=title, date=date, content=html_content)

    return post_html


def main() -> None:
    """Generate a blog.html page by converting all markdown posts to HTML cards this."""
    posts: list[str] = []

    # Process each markdown file in the blog directory
    # (sorted by filename, newest first)
    for md_file in sorted(MARKDOWN_POSTS_DIR.glob('*.md'), reverse=True):
        posts.append(generate_blog_post_html(md_file))

    # Load the main HTML template with placeholder for posts
    with open(HTML_TEMPLATE_FILE, encoding='utf-8') as f:
        template: str = f.read()

    # Replace the placeholder with all generated post cards
    full_page: str = template.replace('{{ posts }}', '\n'.join(posts))

    # Write the final output to blog.html
    with open(HTML_OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(full_page)

    # Format the generated HTML using Prettier
    subprocess.run(['npx', 'prettier', '--write', str(HTML_OUTPUT_FILE)])


if __name__ == '__main__':
    main()
