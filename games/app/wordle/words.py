"""Wordle word-list loading and date-based answer-pool filtering.

Data files live alongside this module in ``data/``:

* ``answers.txt``  — ordered list of Wordle answer words (one per line,
  in the same sequence as the original game).
* ``guesses.txt``  — additional words that are valid guesses but are never
  used as Wordle answers.

Puzzle #1 was played on :data:`START_DATE`.  On each subsequent day the next
word in ``answers.txt`` becomes the answer.  This module exposes helpers to
compute which answers have already been used and which remain as candidates
for today or future puzzles.
"""

import datetime
import pathlib

_DATA_DIR = pathlib.Path(__file__).resolve().parent / 'data'

# The date on which Wordle puzzle #1 was played (word = "cigar").
START_DATE = datetime.date(2021, 6, 19)


def _load_words(filename: str) -> list[str]:
    """Read a newline-delimited word file and return a list of stripped words."""
    path = _DATA_DIR / filename
    return [
        line.strip().lower() for line in path.read_text().splitlines() if line.strip()
    ]


def get_all_answers() -> list[str]:
    """Return the full ordered Wordle answer list."""
    return _load_words('answers.txt')


def get_all_guesses() -> list[str]:
    """Return words that are valid guesses but are never Wordle answers."""
    return _load_words('guesses.txt')


def get_puzzle_number(as_of: datetime.date) -> int:
    """Return the 1-based puzzle number for the given date.

    Returns 1 for :data:`START_DATE`, 2 for the next day, and so on.
    Dates before :data:`START_DATE` are treated as puzzle #1.
    """
    delta = (as_of - START_DATE).days
    return max(1, delta + 1)


def get_used_answers(as_of: datetime.date) -> list[str]:
    """Return answers that have already been the puzzle answer before *as_of*.

    Today's answer is *not* included because we don't want to spoil it — it
    remains a candidate in the suggestion pool.
    """
    answers = get_all_answers()
    puzzle_num = get_puzzle_number(as_of)
    # Puzzle indices 0 … puzzle_num-2 have already been revealed.
    used_count = max(0, puzzle_num - 1)
    return answers[:used_count]


def get_remaining_answers(as_of: datetime.date) -> list[str]:
    """Return answers that have *not* yet been used, including today's.

    These form the pool of possible correct answers when suggesting starting
    words for today's puzzle.
    """
    answers = get_all_answers()
    puzzle_num = get_puzzle_number(as_of)
    used_count = max(0, puzzle_num - 1)
    remaining = answers[used_count:]
    # If we've exhausted the scheduled list, treat all answers as available.
    return remaining if remaining else answers
