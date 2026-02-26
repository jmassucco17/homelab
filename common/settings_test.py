"""Unit tests for common/settings.py."""

import importlib
import os
import unittest

import common.settings


class TestSettings(unittest.TestCase):
    """Tests for shared application settings."""

    def test_domain_defaults_to_jamesmassucco(self) -> None:
        """DOMAIN defaults to .jamesmassucco.com when DOMAIN env var is not set."""
        env_backup = os.environ.pop('DOMAIN', None)
        try:
            importlib.reload(common.settings)
            self.assertEqual(common.settings.DOMAIN, '.jamesmassucco.com')
        finally:
            if env_backup is not None:
                os.environ['DOMAIN'] = env_backup
            importlib.reload(common.settings)

    def test_domain_reads_from_env(self) -> None:
        """DOMAIN is read from the DOMAIN environment variable."""
        os.environ['DOMAIN'] = '-staging.example.com'
        try:
            importlib.reload(common.settings)
            self.assertEqual(common.settings.DOMAIN, '-staging.example.com')
        finally:
            del os.environ['DOMAIN']
            importlib.reload(common.settings)

    def test_home_url_strips_leading_dot(self) -> None:
        """HOME_URL is constructed from DOMAIN by stripping the leading dot."""
        env_backup = os.environ.pop('DOMAIN', None)
        try:
            importlib.reload(common.settings)
            self.assertEqual(common.settings.HOME_URL, 'https://jamesmassucco.com')
        finally:
            if env_backup is not None:
                os.environ['DOMAIN'] = env_backup
            importlib.reload(common.settings)

    def test_home_url_reflects_custom_domain(self) -> None:
        """HOME_URL reflects a custom DOMAIN environment variable."""
        os.environ['DOMAIN'] = '-staging.example.com'
        try:
            importlib.reload(common.settings)
            self.assertEqual(common.settings.HOME_URL, 'https://staging.example.com')
        finally:
            del os.environ['DOMAIN']
            importlib.reload(common.settings)


if __name__ == '__main__':
    unittest.main()
