"""Unit tests for common/templates.py."""

import pathlib
import tempfile
import unittest

import common.settings
import common.templates


class TestMakeTemplates(unittest.TestCase):
    """Tests for the make_templates factory."""

    def setUp(self) -> None:
        """Create a temporary directory to use as a templates directory."""
        self.tmpdir = tempfile.mkdtemp()

    def test_domain_global_set(self) -> None:
        """make_templates sets the domain global from common.settings."""
        templates = common.templates.make_templates(self.tmpdir)
        self.assertEqual(
            templates.env.globals['domain'],  # type: ignore[reportUnknownMemberType]
            common.settings.DOMAIN,
        )

    def test_home_url_global_set(self) -> None:
        """make_templates sets the home_url global from common.settings."""
        templates = common.templates.make_templates(self.tmpdir)
        self.assertEqual(
            templates.env.globals['home_url'],  # type: ignore[reportUnknownMemberType]
            common.settings.HOME_URL,
        )

    def test_accepts_pathlib_path(self) -> None:
        """make_templates accepts a pathlib.Path directory."""
        templates = common.templates.make_templates(pathlib.Path(self.tmpdir))
        self.assertIn('domain', templates.env.globals)  # type: ignore[reportUnknownMemberType,reportUnknownArgumentType]

    def test_accepts_string_path(self) -> None:
        """make_templates accepts a string directory path."""
        templates = common.templates.make_templates(self.tmpdir)
        self.assertIn('home_url', templates.env.globals)  # type: ignore[reportUnknownMemberType,reportUnknownArgumentType]


if __name__ == '__main__':
    unittest.main()
