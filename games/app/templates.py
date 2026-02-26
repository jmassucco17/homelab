"""Shared Jinja2 templates instance for the games sub-site."""

import os
import pathlib

import fastapi.templating

APP_DIR = pathlib.Path(__file__).resolve().parent

DOMAIN = os.environ.get('DOMAIN', '.jamesmassucco.com')
HOME_URL = 'https://' + DOMAIN[1:]

templates = fastapi.templating.Jinja2Templates(directory=APP_DIR / 'templates')
templates.env.globals['domain'] = DOMAIN  # type: ignore[reportUnknownMemberType]
templates.env.globals['home_url'] = HOME_URL  # type: ignore[reportUnknownMemberType]
