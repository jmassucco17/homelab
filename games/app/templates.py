"""Shared Jinja2 templates instance for the games sub-site."""

import pathlib

import fastapi.templating

import common.settings

APP_DIR = pathlib.Path(__file__).resolve().parent

templates = fastapi.templating.Jinja2Templates(directory=APP_DIR / 'templates')
templates.env.globals['domain'] = common.settings.DOMAIN  # type: ignore[reportUnknownMemberType]
templates.env.globals['home_url'] = common.settings.HOME_URL  # type: ignore[reportUnknownMemberType]
