"""Unit tests for the shared templates module."""

import unittest


class TestTemplatesModule(unittest.TestCase):
    """Tests for the shared Jinja2 templates module."""

    def test_domain_global_set(self) -> None:
        """Test that the domain global is set in the templates environment."""
        from games.app import templates as tmpl

        self.assertIn('domain', tmpl.templates.env.globals)  # type: ignore[reportUnknownMemberType,reportUnknownArgumentType]

    def test_home_url_global_set(self) -> None:
        """Test that the home_url global is set in the templates environment."""
        from games.app import templates as tmpl

        self.assertIn('home_url', tmpl.templates.env.globals)  # type: ignore[reportUnknownMemberType,reportUnknownArgumentType]

    def test_domain_contains_jamesmassucco(self) -> None:
        """Test that the domain global contains the default domain."""
        from games.app import templates as tmpl

        domain = tmpl.templates.env.globals['domain']  # type: ignore[reportUnknownMemberType]
        self.assertIn('jamesmassucco.com', domain)  # type: ignore[reportUnknownArgumentType]


if __name__ == '__main__':
    unittest.main()
