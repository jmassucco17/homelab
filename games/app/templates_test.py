"""Unit tests for the shared templates module."""

import os
import unittest


class TestTemplatesModule(unittest.TestCase):
    """Tests for the shared Jinja2 templates module."""

    def test_domain_global_set(self) -> None:
        """Test that the domain global is set in the templates environment."""
        from games.app import templates as tmpl

        self.assertIn('domain', tmpl.templates.env.globals)  # type: ignore[reportUnknownMemberType,reportUnknownArgumentType]

    def test_domain_defaults_to_jamesmassucco(self) -> None:
        """Test that the domain defaults to jamesmassucco.com when DOMAIN is not set."""
        # Reload the module without DOMAIN set
        import importlib

        env_backup = os.environ.pop('DOMAIN', None)
        try:
            import games.app.templates

            importlib.reload(games.app.templates)
            self.assertEqual(games.app.templates.DOMAIN, 'jamesmassucco.com')
        finally:
            if env_backup is not None:
                os.environ['DOMAIN'] = env_backup

    def test_domain_reads_from_env(self) -> None:
        """Test that the domain is read from the DOMAIN environment variable."""
        import importlib

        os.environ['DOMAIN'] = 'staging.example.com'
        try:
            import games.app.templates

            importlib.reload(games.app.templates)
            self.assertEqual(games.app.templates.DOMAIN, 'staging.example.com')
        finally:
            del os.environ['DOMAIN']


if __name__ == '__main__':
    unittest.main()
