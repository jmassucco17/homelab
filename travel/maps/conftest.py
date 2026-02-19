"""Configure pytest for travel/maps tests."""

import os
import pathlib
import sys

# Add travel/maps directory to sys.path so tests can import from app
sys.path.insert(0, str(pathlib.Path(__file__).parent))

# Change working directory to travel/maps for correct relative paths (e.g. static files)
os.chdir(pathlib.Path(__file__).parent)
