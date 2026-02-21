# Python Style Guide

- Import at the module level and access classes or functions as <module>.<func>; never import classes or functions directly
- Provide argument and return type hinting for all methods and functions
- Include docstrings for most classes and functions with brief description; in general, don't include args/returns info in the docstring unless it's non-obvious (e.g. if it returns a dict, describe the structure)
- Include comments for operations that need additional explanation
- Use modern type hints (`X | None` instead of `Optional[X]`)
- Use `datetime.now(UTC)` instead of deprecated `datetime.utcnow()`
- Whenever you create a new Python file, you must also create an associated `<module>_test.py` in the same directory

## Tests

- Use the `unittest` module when writing tests, but run them with `pytest` in command line
- Tests should always be housed in the same directory as the file they test, and be named `<module>_test.py` (e.g. test for `main.py` should be `main_test.py`)

## Code Checking

- Always run these commands before completing work, and fix any issues found

```bash
ruff check --fix . && ruff format .
npx pyright
pytest -v -W error
```
