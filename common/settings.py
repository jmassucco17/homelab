"""Shared application settings read from environment variables."""

import os

DOMAIN: str = os.environ.get('DOMAIN', '.jamesmassucco.com')
HOME_URL: str = 'https://' + DOMAIN[1:]
