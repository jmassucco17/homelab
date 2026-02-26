"""Shared Jinja2 templates instance for the games sub-site."""

import pathlib

import common.templates

APP_DIR = pathlib.Path(__file__).resolve().parent

templates = common.templates.make_templates(APP_DIR / 'templates')
