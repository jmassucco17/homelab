"""Unit tests for games.app.wordle.words."""

import datetime
import unittest

from games.app.wordle import words


class TestGetPuzzleNumber(unittest.TestCase):
    """Tests for get_puzzle_number."""

    def test_start_date_is_puzzle_one(self) -> None:
        """Puzzle #1 is on the START_DATE."""
        self.assertEqual(words.get_puzzle_number(words.START_DATE), 1)

    def test_next_day_is_puzzle_two(self) -> None:
        """The day after START_DATE is puzzle #2."""
        day_two = words.START_DATE + datetime.timedelta(days=1)
        self.assertEqual(words.get_puzzle_number(day_two), 2)

    def test_before_start_date_clamped_to_one(self) -> None:
        """Dates before the start are treated as puzzle #1."""
        past = words.START_DATE - datetime.timedelta(days=10)
        self.assertEqual(words.get_puzzle_number(past), 1)

    def test_one_year_later(self) -> None:
        """365 days later is puzzle #366."""
        later = words.START_DATE + datetime.timedelta(days=365)
        self.assertEqual(words.get_puzzle_number(later), 366)


class TestGetUsedAnswers(unittest.TestCase):
    """Tests for get_used_answers."""

    def test_on_start_date_no_used_answers(self) -> None:
        """On puzzle #1 day no previous answers have been revealed."""
        used = words.get_used_answers(words.START_DATE)
        self.assertEqual(used, [])

    def test_one_day_later_one_used(self) -> None:
        """One day after start the first answer has been revealed."""
        day_two = words.START_DATE + datetime.timedelta(days=1)
        used = words.get_used_answers(day_two)
        self.assertEqual(len(used), 1)
        all_answers = words.get_all_answers()
        self.assertEqual(used[0], all_answers[0])

    def test_used_answers_not_in_remaining(self) -> None:
        """Used answers must not appear in the remaining pool."""
        test_date = words.START_DATE + datetime.timedelta(days=50)
        used = set(words.get_used_answers(test_date))
        remaining = words.get_remaining_answers(test_date)
        overlap = used & set(remaining)
        self.assertEqual(overlap, set())


class TestGetRemainingAnswers(unittest.TestCase):
    """Tests for get_remaining_answers."""

    def test_on_start_date_all_answers_remain(self) -> None:
        """On puzzle #1 day every answer is still a candidate."""
        remaining = words.get_remaining_answers(words.START_DATE)
        all_answers = words.get_all_answers()
        self.assertEqual(remaining, all_answers)

    def test_remaining_decreases_over_time(self) -> None:
        """The remaining pool shrinks each day."""
        later = words.START_DATE + datetime.timedelta(days=100)
        remaining = words.get_remaining_answers(later)
        all_answers = words.get_all_answers()
        self.assertLess(len(remaining), len(all_answers))

    def test_remaining_non_empty_after_exhaustion(self) -> None:
        """After the list is exhausted the full list is returned as fallback."""
        far_future = datetime.date(2099, 1, 1)
        remaining = words.get_remaining_answers(far_future)
        self.assertGreater(len(remaining), 0)

    def test_all_are_five_letters(self) -> None:
        """Every word in the remaining pool is exactly five letters."""
        remaining = words.get_remaining_answers(words.START_DATE)
        for word in remaining:
            self.assertEqual(len(word), 5, f'Word {word!r} is not 5 letters')


class TestLoadWords(unittest.TestCase):
    """Tests for the word-list loader helpers."""

    def test_answers_non_empty(self) -> None:
        """The answer list must contain at least one word."""
        self.assertGreater(len(words.get_all_answers()), 0)

    def test_guesses_non_empty(self) -> None:
        """The extra-guesses list must contain at least one word."""
        self.assertGreater(len(words.get_all_guesses()), 0)

    def test_answers_are_lowercase(self) -> None:
        """All answers are lowercase."""
        for word in words.get_all_answers():
            self.assertEqual(word, word.lower(), f'Word {word!r} is not lowercase')

    def test_guesses_not_overlap_answers(self) -> None:
        """Extra guesses must not duplicate entries in the answer list."""
        answer_set = set(words.get_all_answers())
        for guess in words.get_all_guesses():
            self.assertNotIn(guess, answer_set, f'{guess!r} appears in both lists')


if __name__ == '__main__':
    unittest.main()
