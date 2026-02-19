"""Unit tests for blog.py module."""

import pathlib
import tempfile

import pytest

from blog.app import blog


class TestBlogPostMetadata:
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
        assert metadata.title == 'Test Post'
        assert metadata.date == '2025-01-01'
        assert metadata.tags == ['test']
        assert metadata.summary == 'A test post'
        assert metadata.slug == 'test-post'

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
        assert dt.year == 2025
        assert dt.month == 1
        assert dt.day == 15


class TestBlogPost:
    """Tests for BlogPost class."""

    @pytest.fixture
    def test_post_path(self) -> pathlib.Path:
        """Returns path to test post file."""
        return pathlib.Path(__file__).parent / 'test_post.md'

    def test_post_loading(self, test_post_path: pathlib.Path) -> None:
        """Test that post loads correctly."""
        post = blog.BlogPost(test_post_path)
        assert post.md_path == test_post_path
        assert post._post is None  # Lazy loading
        # Access post to trigger loading
        _ = post.post
        assert post._post is not None

    def test_metadata_parsing(self, test_post_path: pathlib.Path) -> None:
        """Test that metadata is parsed correctly."""
        post = blog.BlogPost(test_post_path)
        metadata = post.metadata
        assert metadata.title == 'Test Blog Post'
        assert metadata.date == '2025-01-01'
        assert metadata.tags == ['test', 'example']
        assert metadata.summary == 'A test blog post for unit testing'
        assert metadata.slug == 'test-blog-post'

    def test_content_rendering(self, test_post_path: pathlib.Path) -> None:
        """Test that markdown content is rendered to HTML."""
        post = blog.BlogPost(test_post_path)
        content = post.content
        # Check that markdown was converted to HTML
        assert '<h1' in content
        assert '<h2' in content
        assert '<code>' in content
        assert '<table>' in content


class TestLoadPosts:
    """Tests for load_posts function."""

    def test_load_posts_from_real_directory(self) -> None:
        """Test loading posts from the actual posts directory."""
        posts = blog.load_posts()
        # Should have at least some posts
        assert len(posts) > 0
        # All posts should have valid metadata
        for post in posts:
            assert post.metadata.title
            assert post.metadata.date
            assert post.metadata.slug
            assert post.metadata.summary

    def test_posts_sorted_by_date(self) -> None:
        """Test that posts are sorted newest first."""
        posts = blog.load_posts()
        if len(posts) > 1:
            for i in range(len(posts) - 1):
                assert posts[i].metadata.dt >= posts[i + 1].metadata.dt

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
                with pytest.raises(ValueError, match='Duplicate slugs'):
                    blog.load_posts()
            finally:
                blog.POSTS_DIR = original_posts_dir
