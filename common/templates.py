"""Factory for creating Jinja2Templates with standard domain globals."""

import pathlib

import fastapi.templating

import common.settings


def make_templates(
    directory: pathlib.Path | str,
) -> fastapi.templating.Jinja2Templates:
    """Create a Jinja2Templates instance with domain and home_url globals pre-set."""
    templates = fastapi.templating.Jinja2Templates(directory=str(directory))
    templates.env.globals['domain'] = common.settings.DOMAIN  # type: ignore[reportUnknownMemberType]
    templates.env.globals['home_url'] = common.settings.HOME_URL  # type: ignore[reportUnknownMemberType]
    return templates
