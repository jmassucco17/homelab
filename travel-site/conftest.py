"""Configure pytest for travel-site tests."""

import os
import pathlib
import sys

# Add travel-site directory to sys.path so tests can import from app
sys.path.insert(0, str(pathlib.Path(__file__).parent))

# Change working directory to travel-site for correct relative paths (e.g. static files)
os.chdir(pathlib.Path(__file__).parent)
