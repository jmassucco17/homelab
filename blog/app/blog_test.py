"""Unit tests for blog.py module."""

import pathlib
import tempfile
import unittest

from blog.app import blog


class TestBlogPostMetadata(unittest.TestCase):
    """Tests for BlogPostMetadata class."""

    def test_metadata_validation(self) -> None:
        """Test that metadata validates correctly."""
        metadata = blog.BlogPostMetadata(
            title='Test Post',
            date='2025-01-01',
            tags=['test'],
            summary='A test post',
            slug='test-post',
        )
        self.assertEqual(metadata.title, 'Test Post')
        self.assertEqual(metadata.date, '2025-01-01')
        self.assertEqual(metadata.tags, ['test'])
        self.assertEqual(metadata.summary, 'A test post')
        self.assertEqual(metadata.slug, 'test-post')

    def test_dt_property(self) -> None:
        """Test that dt property parses date correctly."""
        metadata = blog.BlogPostMetadata(
            title='Test',
            date='2025-01-15',
            tags=[],
            summary='Test',
            slug='test',
        )
        dt = metadata.dt
        self.assertEqual(dt.year, 2025)
        self.assertEqual(dt.month, 1)
        self.assertEqual(dt.day, 15)


class TestBlogPost(unittest.TestCase):
    """Tests for BlogPost class."""

    def test_post_loading_from_real_posts(self) -> None:
        """Test that post loads correctly from real posts directory."""
        posts_dir = blog.POSTS_DIR
        md_files = list(posts_dir.glob('*.md'))
        if len(md_files) > 0:
            # Create a fresh BlogPost instance to test loading
            post: blog.BlogPost = blog.BlogPost(md_files[0])
            # Access post property - it should load successfully
            loaded_post = post.post
            self.assertIsNotNone(loaded_post)
            # Verify the post has expected attributes
            self.assertTrue(hasattr(loaded_post, 'metadata'))
            self.assertTrue(hasattr(loaded_post, 'content'))

    def test_metadata_parsing_from_real_posts(self) -> None:
        """Test that metadata is parsed correctly from real posts."""
        posts = blog.load_posts()
        if len(posts) > 0:
            post = posts[0]
            metadata = post.metadata
            self.assertTrue(metadata.title)
            self.assertTrue(metadata.date)
            self.assertTrue(metadata.slug)
            self.assertTrue(metadata.summary)

    def test_content_rendering(self) -> None:
        """Test that markdown content is rendered to HTML."""
        # Create a temporary test post
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(
                """---
title: 'Test Blog Post'
date: '2025-01-01'
tags: ['test', 'example']
summary: 'A test blog post for unit testing'
slug: test-blog-post
---

# Test Blog Post

This is a test blog post used for unit testing purposes.

## Section 1

Some test content here.

```python
def hello():
    print("Hello, world!")
```

## Section 2

More test content with a table:

| Column 1 | Column 2 |
|----------|----------|
| A        | B        |
| C        | D        |
"""
            )
            test_post_path = pathlib.Path(f.name)

        try:
            post = blog.BlogPost(test_post_path)
            content = post.content
            # Check that markdown was converted to HTML
            self.assertIn('<h1', content)
            self.assertIn('<h2', content)
            self.assertIn('<code>', content)
            self.assertIn('<table>', content)
        finally:
            test_post_path.unlink()


class TestLoadPosts(unittest.TestCase):
    """Tests for load_posts function."""

    def test_load_posts_from_real_directory(self) -> None:
        """Test loading posts from the actual posts directory."""
        posts = blog.load_posts()
        # Should have at least some posts
        self.assertGreater(len(posts), 0)
        # All posts should have valid metadata
        for post in posts:
            self.assertTrue(post.metadata.title)
            self.assertTrue(post.metadata.date)
            self.assertTrue(post.metadata.slug)
            self.assertTrue(post.metadata.summary)

    def test_posts_sorted_by_date(self) -> None:
        """Test that posts are sorted newest first."""
        posts = blog.load_posts()
        if len(posts) > 1:
            for i in range(len(posts) - 1):
                self.assertGreaterEqual(posts[i].metadata.dt, posts[i + 1].metadata.dt)

    def test_duplicate_slugs_raises_error(self) -> None:
        """Test that duplicate slugs raise a ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = pathlib.Path(tmpdir)
            # Create two posts with the same slug
            post1 = tmppath / 'post1.md'
            post2 = tmppath / 'post2.md'
            content = """---
title: 'Test'
date: '2025-01-01'
tags: []
summary: 'Test'
slug: 'duplicate'
---
Content"""
            post1.write_text(content)
            post2.write_text(content)

            # Temporarily override POSTS_DIR
            original_posts_dir = blog.POSTS_DIR
            try:
                blog.POSTS_DIR = tmppath
                with self.assertRaisesRegex(ValueError, 'Duplicate slugs'):
                    blog.load_posts()
            finally:
                blog.POSTS_DIR = original_posts_dir


if __name__ == '__main__':
    unittest.main()
