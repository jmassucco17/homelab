# Blog Module Tests

This directory contains unit tests for the blog module.

## Running Tests

To run all tests for the blog module:

```bash
# From the repository root
python -m pytest blog/tests/ -v
```

To run specific test files:

```bash
python -m pytest blog/tests/test_blog.py -v
python -m pytest blog/tests/test_main.py -v
```

To run tests with coverage:

```bash
python -m pytest blog/tests/ --cov=blog.app --cov-report=term-missing
```

## Test Structure

- `test_blog.py` - Tests for blog post loading, metadata parsing, and content rendering
- `test_main.py` - Tests for FastAPI endpoints (index, post, RSS, health)
- `test_post.md` - Sample blog post used for testing

## Test Coverage

The test suite covers:

1. **BlogPostMetadata**
   - Metadata validation
   - Date parsing (dt property)

2. **BlogPost**
   - Post loading and lazy initialization
   - Metadata parsing from frontmatter
   - Markdown to HTML content rendering

3. **load_posts()**
   - Loading posts from the posts directory
   - Posts sorted by date (newest first)
   - Duplicate slug detection

4. **FastAPI Endpoints**
   - Health check endpoint (GET and HEAD)
   - Index page rendering
   - Individual post rendering
   - 404 handling for non-existent posts
   - RSS feed generation
   - Static file mounting
