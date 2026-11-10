"""Wordle starting-word ranking algorithm.

The ranking is based on **letter-frequency coverage**: a candidate starting
word scores higher the more frequently its *unique* letters appear across the
pool of remaining possible answers.  This strategy maximises the expected
number of green/yellow tiles on the first guess, narrowing the answer space
as quickly as possible.

Scoring formula
---------------
For each letter in the candidate word (counted only once per word):

    score += frequency_of_letter_in_remaining_pool

where ``frequency_of_letter`` is the number of remaining answers that contain
that letter at least once.  Using unique letters avoids double-counting when
a candidate word has repeated letters (e.g. ``speed`` only benefits from the
``e`` once).
"""

import collections


def build_letter_frequencies(word_pool: list[str]) -> dict[str, int]:
    """Count how many words in *word_pool* contain each letter at least once.

    Returns a mapping from letter to its document frequency.
    """
    freq: dict[str, int] = collections.defaultdict(int)
    for word in word_pool:
        for letter in set(word):  # unique letters per word
            freq[letter] += 1
    return dict(freq)


def score_word(word: str, letter_freq: dict[str, int]) -> int:
    """Return the letter-frequency coverage score for *word*.

    Each unique letter in *word* contributes its frequency in the remaining
    answer pool.  Repeated letters count only once.
    """
    return sum(letter_freq.get(letter, 0) for letter in set(word))


def suggest_starters(
    remaining_answers: list[str],
    candidate_pool: list[str],
    n: int = 10,
) -> list[tuple[str, int]]:
    """Return the top *n* starting words from *candidate_pool*, ranked by score.

    Parameters
    ----------
    remaining_answers:
        The answers that are still possible today (used to compute letter
        frequencies).
    candidate_pool:
        All words that may be used as a starting guess (answers + extra guesses).
    n:
        Number of suggestions to return.

    Returns
    -------
    A list of ``(word, score)`` tuples ordered from highest to lowest score.
    """
    letter_freq = build_letter_frequencies(remaining_answers)
    scored = [(word, score_word(word, letter_freq)) for word in candidate_pool]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:n]
