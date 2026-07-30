"""Wordle starting-word suggester router."""

import datetime

import fastapi
import fastapi.responses

from .. import templates as tmpl
from ..wordle import solver, words

templates = tmpl.templates

router = fastapi.APIRouter()


@router.get('/wordle', response_class=fastapi.responses.HTMLResponse)
async def wordle_starter(request: fastapi.Request) -> fastapi.responses.HTMLResponse:
    """Render the Wordle starting-word suggestion page for today."""
    today = datetime.date.today()
    remaining = words.get_remaining_answers(today)
    all_words = words.get_all_answers() + words.get_all_guesses()
    suggestions = solver.suggest_starters(remaining, all_words)
    used_count = len(words.get_used_answers(today))
    return templates.TemplateResponse(
        request=request,
        name='wordle.html.jinja2',
        context={
            'suggestions': suggestions,
            'remaining_count': len(remaining),
            'used_count': used_count,
            'today': today.isoformat(),
        },
    )
