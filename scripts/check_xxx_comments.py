#!/usr/bin/env python3
"""
Linter to check for XXX comments in source files.
Fails if any XXX comments are found, as these should be resolved before committing.
"""

import re
import sys
from pathlib import Path

import click


def check_file_for_xxx(file_path: Path) -> list[tuple[int, str]]:
    """Check a single file for XXX comments

    Returns list of (line number, content) tuples
    """
    xxx_lines: list[tuple[int, str]] = []

    try:
        with open(file_path, encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                # Look for XXX as a TODO comment marker
                # Match XXX followed by colon or space in comments
                xxx_pattern = r'\bXXX\s*[:]\s*|^\s*#\s*XXX\s|//\s*XXX\s'
                if re.search(xxx_pattern, line, re.IGNORECASE):
                    xxx_lines.append((line_num, line.strip()))
    except (UnicodeDecodeError, PermissionError):
        # Skip binary files or files we can't read
        pass

    return xxx_lines


@click.command()
@click.argument('files', nargs=-1, type=click.Path())
@click.option('--warn-only', is_flag=True)
def main(files: tuple[str, ...], warn_only: bool) -> None:
    """Check for XXX comments in source files."""
    if not files:
        click.echo('No files provided to check')
        sys.exit(0)

    found_xxx = False

    for file_path_str in files:
        file_path = Path(file_path_str)

        if not file_path.exists() or not file_path.is_file():
            continue

        xxx_lines = check_file_for_xxx(file_path)

        if xxx_lines:
            found_xxx = True
            click.echo(f'\nXXX comments found in {file_path}:')
            for line_num, line_content in xxx_lines:
                click.echo(f'  Line {line_num}: {line_content}')

    if found_xxx:
        click.echo('\nError: XXX comments found!')
        if warn_only:
            sys.exit(0)
        else:
            sys.exit(1)


if __name__ == '__main__':
    main()
