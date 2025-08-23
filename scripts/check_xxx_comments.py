#!/usr/bin/env python3
"""
Linter to check for XXX comments in source files.
Fails if any XXX comments are found, as these should be resolved before committing.
"""

import argparse
import re
import sys
from pathlib import Path


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


def main() -> int:
    """Main function to check files for XXX comments."""
    parser = argparse.ArgumentParser(
        description='Check for XXX comments in source files'
    )
    parser.add_argument(
        'files',
        nargs='*',
        help='Files to check (if none provided, checks all tracked files)',
    )

    args = parser.parse_args()

    if not args.files:
        print('No files provided to check')
        return 0

    found_xxx = False

    for file_path_str in args.files:
        file_path = Path(file_path_str)

        if not file_path.exists() or not file_path.is_file():
            continue

        xxx_lines = check_file_for_xxx(file_path)

        if xxx_lines:
            found_xxx = True
            print(f'\nXXX comments found in {file_path}:')
            for line_num, line_content in xxx_lines:
                print(f'  Line {line_num}: {line_content}')

    if found_xxx:
        print(
            '\nError: XXX comments found! Please resolve these TODOs before committing.'
        )
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
