"""Unit tests for games.app.wordle.solver."""

import unittest

from games.app.wordle import solver


class TestBuildLetterFrequencies(unittest.TestCase):
    """Tests for build_letter_frequencies."""

    def test_single_word(self) -> None:
        """A pool with one word yields frequencies of 1 for each unique letter."""
        freq = solver.build_letter_frequencies(['crane'])
        for letter in 'crane':
            self.assertEqual(freq[letter], 1)

    def test_repeated_letters_counted_once_per_word(self) -> None:
        """Repeated letters within a single word count only once toward frequency."""
        freq = solver.build_letter_frequencies(['aazze'])
        self.assertEqual(freq['a'], 1)
        self.assertEqual(freq['z'], 1)
        self.assertEqual(freq['e'], 1)

    def test_two_words_sharing_letter(self) -> None:
        """A letter appearing in both words has frequency 2."""
        freq = solver.build_letter_frequencies(['crane', 'chart'])
        # 'c', 'r', 'a' appear in both
        self.assertEqual(freq['c'], 2)
        self.assertEqual(freq['r'], 2)
        self.assertEqual(freq['a'], 2)
        # 'n' and 'e' only in 'crane'
        self.assertEqual(freq['n'], 1)
        self.assertEqual(freq['e'], 1)

    def test_empty_pool(self) -> None:
        """An empty pool yields an empty frequency dict."""
        freq = solver.build_letter_frequencies([])
        self.assertEqual(freq, {})


class TestScoreWord(unittest.TestCase):
    """Tests for score_word."""

    def test_all_letters_present(self) -> None:
        """A word whose letters all have high frequency scores well."""
        # Build a freq where a,e,r,s,t are common
        freq = {'a': 10, 'e': 9, 'r': 8, 's': 7, 't': 6}
        score = solver.score_word('rates', freq)
        self.assertEqual(score, 10 + 9 + 8 + 7 + 6)

    def test_repeated_letter_counted_once(self) -> None:
        """Repeated letters in the candidate word score only once."""
        freq = {'a': 5, 'e': 3, 'l': 2}
        # 'allele' would have repeated a, l, e — test with 5-letter analogue
        score = solver.score_word('aalle', freq)
        # unique letters: a, l, e → 5 + 2 + 3 = 10
        self.assertEqual(score, 5 + 2 + 3)

    def test_unknown_letter_scores_zero(self) -> None:
        """Letters absent from the frequency dict contribute 0."""
        freq = {'a': 5}
        score = solver.score_word('bbbbb', freq)
        self.assertEqual(score, 0)

    def test_empty_freq(self) -> None:
        """An empty frequency dict causes all words to score 0."""
        self.assertEqual(solver.score_word('crane', {}), 0)


class TestSuggestStarters(unittest.TestCase):
    """Tests for suggest_starters."""

    def setUp(self) -> None:
        """Small controlled pool for deterministic tests."""
        self.pool = ['crane', 'slate', 'audio', 'zzzzz']
        self.remaining = ['crane', 'rates', 'arose', 'snare', 'laser']

    def test_returns_n_suggestions(self) -> None:
        """The function returns exactly n results when pool is large enough."""
        results = solver.suggest_starters(self.remaining, self.pool, n=3)
        self.assertEqual(len(results), 3)

    def test_returns_tuples_word_score(self) -> None:
        """Each item in the result is a (word, int) tuple."""
        results = solver.suggest_starters(self.remaining, self.pool, n=2)
        for word, score in results:
            self.assertIsInstance(word, str)
            self.assertIsInstance(score, int)

    def test_sorted_descending(self) -> None:
        """Results are sorted from highest to lowest score."""
        results = solver.suggest_starters(self.remaining, self.pool, n=4)
        scores = [score for _, score in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_high_entropy_word_ranked_first(self) -> None:
        """A word covering the most common letters should outscore 'zzzzz'."""
        results = solver.suggest_starters(self.remaining, self.pool)
        words = [w for w, _ in results]
        self.assertIn('zzzzz', words)
        zzz_pos = words.index('zzzzz')
        # zzzzz should not be first
        self.assertGreater(zzz_pos, 0)

    def test_n_larger_than_pool(self) -> None:
        """When n > pool size, all pool words are returned."""
        small_pool = ['crane', 'slate']
        results = solver.suggest_starters(self.remaining, small_pool, n=100)
        self.assertEqual(len(results), 2)

    def test_empty_remaining_all_scores_zero(self) -> None:
        """With an empty remaining pool every candidate scores 0."""
        results = solver.suggest_starters([], self.pool, n=4)
        for _, score in results:
            self.assertEqual(score, 0)


if __name__ == '__main__':
    unittest.main()
