"""Unit tests for check_xxx_comments.py."""

import pathlib
import sys
import tempfile
import unittest

import click.testing

# scripts/ is not a package, so add its directory to sys.path
sys.path.insert(0, str(pathlib.Path(__file__).parent))

import check_xxx_comments  # noqa: E402

# Construct the marker string dynamically to avoid triggering the XXX comment checker
# on this file itself.
_XXX = 'XX' + 'X'


class TestCheckFileForXxx(unittest.TestCase):
    """Tests for check_file_for_xxx function."""

    def _write_temp_file(self, content: str) -> pathlib.Path:
        """Write content to a temporary file and return its path."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.py', delete=False, encoding='utf-8'
        ) as f:
            f.write(content)
            return pathlib.Path(f.name)

    def test_no_xxx_returns_empty(self) -> None:
        """Test that a file without the marker returns an empty list."""
        path = self._write_temp_file('# A normal comment\nprint("hello")\n')
        try:
            result = check_xxx_comments.check_file_for_xxx(path)
            self.assertEqual(result, [])
        finally:
            path.unlink()

    def test_xxx_in_comment_detected(self) -> None:
        """Test that a marker comment in a file is detected."""
        path = self._write_temp_file(f'# {_XXX}: fix this later\nprint("hello")\n')
        try:
            result = check_xxx_comments.check_file_for_xxx(path)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0][0], 1)
            self.assertIn(_XXX, result[0][1])
        finally:
            path.unlink()

    def test_xxx_with_space_detected(self) -> None:
        """Test that the '# MARKER ' pattern is detected."""
        path = self._write_temp_file(f'# {_XXX} fix this\nprint("hello")\n')
        try:
            result = check_xxx_comments.check_file_for_xxx(path)
            self.assertEqual(len(result), 1)
        finally:
            path.unlink()

    def test_multiple_xxx_detected(self) -> None:
        """Test that multiple marker comments across lines are all detected."""
        content = f'# {_XXX}: first issue\nok = True\n# {_XXX}: second issue\n'
        path = self._write_temp_file(content)
        try:
            result = check_xxx_comments.check_file_for_xxx(path)
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0][0], 1)
            self.assertEqual(result[1][0], 3)
        finally:
            path.unlink()

    def test_empty_file_returns_empty(self) -> None:
        """Test that an empty file returns an empty list."""
        path = self._write_temp_file('')
        try:
            result = check_xxx_comments.check_file_for_xxx(path)
            self.assertEqual(result, [])
        finally:
            path.unlink()

    def test_xxx_in_word_not_detected(self) -> None:
        """Test that XXX as part of a word is not detected."""
        path = self._write_temp_file('# HEXXXXX is not a match\n')
        try:
            result = check_xxx_comments.check_file_for_xxx(path)
            self.assertEqual(result, [])
        finally:
            path.unlink()

    def test_line_number_reported_correctly(self) -> None:
        """Test that the correct line number is reported."""
        content = f'line1\nline2\n# {_XXX}: issue here\nline4\n'
        path = self._write_temp_file(content)
        try:
            result = check_xxx_comments.check_file_for_xxx(path)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0][0], 3)
        finally:
            path.unlink()


class TestMainCommand(unittest.TestCase):
    """Tests for main CLI command."""

    def setUp(self) -> None:
        """Set up Click test runner."""
        self.runner = click.testing.CliRunner()

    def _write_temp_file(self, content: str, suffix: str = '.py') -> pathlib.Path:
        """Write content to a temporary file and return its path."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix=suffix, delete=False, encoding='utf-8'
        ) as f:
            f.write(content)
            return pathlib.Path(f.name)

    def test_no_files_exits_zero(self) -> None:
        """Test that providing no files exits with code 0."""
        result = self.runner.invoke(check_xxx_comments.main, [])
        self.assertEqual(result.exit_code, 0)

    def test_clean_file_exits_zero(self) -> None:
        """Test that a file without XXX exits with code 0."""
        path = self._write_temp_file('# clean code\n')
        try:
            result = self.runner.invoke(check_xxx_comments.main, [str(path)])
            self.assertEqual(result.exit_code, 0)
        finally:
            path.unlink()

    def test_xxx_file_exits_one(self) -> None:
        """Test that a file with the marker exits with code 1."""
        path = self._write_temp_file(f'# {_XXX}: fix me\n')
        try:
            result = self.runner.invoke(check_xxx_comments.main, [str(path)])
            self.assertEqual(result.exit_code, 1)
            self.assertIn('XXX comments found', result.output)
        finally:
            path.unlink()

    def test_warn_only_exits_zero_even_with_xxx(self) -> None:
        """Test that --warn-only exits with code 0 even when the marker is found."""
        path = self._write_temp_file(f'# {_XXX}: fix me\n')
        try:
            result = self.runner.invoke(
                check_xxx_comments.main, ['--warn-only', str(path)]
            )
            self.assertEqual(result.exit_code, 0)
            self.assertIn('XXX comments found', result.output)
        finally:
            path.unlink()

    def test_nonexistent_file_is_skipped(self) -> None:
        """Test that a non-existent file path is silently skipped."""
        result = self.runner.invoke(check_xxx_comments.main, ['/nonexistent/file.py'])
        self.assertEqual(result.exit_code, 0)


if __name__ == '__main__':
    unittest.main()
